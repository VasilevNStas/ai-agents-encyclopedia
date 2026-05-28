---
created: 2026-05-28
tags: [course/case-studies, production, database, safety, architect]
status: active
---

# Case Study 2: Как агент удалил production базу данных

> [!quote] Ключевая идея
> Агент с доступом к SQL — это ассистент DBA с правами администратора. Без guardrails он выполнит `DROP TABLE` так же уверенно, как `SELECT`. Отличие — в архитектуре, не в модели.

---

## Инцидент

**Компания:** SaaS-стартап (2024)
**Сценарий:** Internal-агент для аналитики данных. Подключен к production read-replica. Разработчик попросил: «очисти тестовые данные из таблицы users».
**Результат:** `DELETE FROM users` без WHERE. 150K реальных пользователей удалены. Backup restoration — 6 часов.

## Как это произошло

```
Разработчик: "очисти тестовые данные из users"
  ↓
LLM интерпретировала: "нужно удалить данные → DELETE FROM users"
  ↓
Агент выполнил запрос (read-replica оказалась master)
  ↓
150K строк удалено
```

### Root cause: опасный инструмент без guardrails

```python
# Было: SQL-инструмент с полным доверием
@tool
def run_sql(query: str) -> str:
    """Execute SQL query on the analytics database."""
    result = database.execute(query)
    return str(result)

# Проблема: LLM может сгенерировать DELETE, DROP, TRUNCATE
# и агент выполнит их без вопросов.
```

## Что должно было быть

### Слой 1: Semantic guardrail на SQL

```python
import sqlparse
from sqlparse.sql import Identifier


class SQLGuardrail:
    DANGEROUS_KEYWORDS = {"delete", "drop", "truncate", "alter", "update", "insert"}
    DANGEROUS_PATTERNS = [
        r"\bdelete\b.*\bfrom\b",  # DELETE FROM
        r"\bdrop\b",               # DROP TABLE/DB
        r"\btruncate\b",           # TRUNCATE
    ]

    def check(self, query: str) -> dict:
        """Check SQL query for dangerous operations."""

        # Проверка на DDL/DML без WHERE
        parsed = sqlparse.parse(query)[0]
        stmt_type = parsed.get_type()

        if stmt_type in ("DELETE", "UPDATE", "DROP", "TRUNCATE", "ALTER"):
            has_where = any(
                isinstance(t, sqlparse.sql.Where) for t in parsed.tokens
            )
            return {
                "action": "block",
                "reason": f"Operation '{stmt_type}' requires confirmation",
                "requires_confirmation": True,
                "severity": "critical" if not has_where else "high",
            }

        return {"action": "allow"}


# Использование в инструменте
@tool
def run_sql(query: str) -> str:
    """Execute SQL query. Guarded against dangerous operations."""
    guardrail = SQLGuardrail()
    check = guardrail.check(query)

    if check["action"] == "block":
        if check["requires_confirmation"]:
            # HITL: запрос подтверждения
            confirm = interrupt({
                "type": "sql_confirmation",
                "query": query,
                "risk": check["severity"],
            })
            if not confirm.get("approved"):
                return f"Query blocked: {check['reason']}"

        return f"Query blocked: {check['reason']}"

    return str(database.execute(query))
```

### Слой 2: Принцип наименьших привилегий

```python
# Должно было быть: read-only подключение
DATABASES = {
    "analytics": {
        "read_only": {
            "url": "postgresql://reader:pass@host:5432/analytics",
            "options": {"options": "-c default_transaction_read_only=on"},
        },
        "read_write": {
            "url": "postgresql://writer:pass@host:5432/analytics",
            "options": {},
            "allowed_operations": ["INSERT", "UPDATE"],  # НЕ DELETE
        },
    }
}


def get_sql_connection(purpose: str = "read") -> Database:
    """Выдаёт подключение с минимальными правами."""
    cfg = DATABASES["analytics"]
    if purpose == "read":
        return Database(cfg["read_only"]["url"], cfg["read_only"]["options"])
    else:
        return Database(cfg["read_write"]["url"], cfg["read_write"]["options"])


@tool
def read_data(query: str) -> str:
    """Read-only SQL query. Only SELECT allowed."""
    db = get_sql_connection("read")
    return str(db.execute(query))


@tool
def write_data(query: str) -> str:
    """Write SQL query. Only INSERT/UPDATE on allowed tables."""
    db = get_sql_connection("write")
    return str(db.execute(query))
```

### Слой 3: Preview перед выполнением

```python
@tool
def dry_run_sql(query: str) -> str:
    """Preview SQL changes before executing."""
    # EXPLAIN ANALYZE для SELECT
    # BEGIN; ROLLBACK для DML
    preview = database.execute(f"BEGIN; {query}; ROLLBACK;")
    return f"Preview (not executed):\n{preview}"
```

### Слой 4: Аудит всех SQL-запросов

```python
@dataclass
class SQLAuditLog:
    query: str
    user: str
    agent_session: str
    timestamp: datetime
    action: Literal["executed", "blocked", "confirmed", "rolled_back"]
    rows_affected: int

    def to_audit(self):
        # Пишем в отдельную таблицу аудита (immutable)
        audit_db.execute(
            "INSERT INTO sql_audit (query, user, session, ts, action, rows) "
            "VALUES ($1, $2, $3, $4, $5, $6)",
            self.query, self.user, self.agent_session,
            self.timestamp, self.action, self.rows_affected,
        )
```

## Чеклист: SQL-безопасность для агентов

- [ ] Read-only подключение по умолчанию
- [ ] Semantic guardrail на DDL/DML (DELETE, DROP, TRUNCATE)
- [ ] HITL на destructive операции
- [ ] Dry-run preview перед записью
- [ ] Аудит всех SQL-запросов (кто, что, когда)
- [ ] Rate limit на записи (макс N rows за запрос)
- [ ] Row-level security (tenant изоляция)
- [ ] Statement timeout (30s max)

> [!warning] Золотое правило
> Агент должен иметь доступ к БД **только** через специализированные инструменты (read_data, search_users, update_order_status), а не через общий `run_sql`. Каждый инструмент — явное разрешение на определённую операцию. Никаких `execute("any SQL")`.

---

## Проверь себя

1. Какие три слоя защиты должны быть у SQL-инструмента?
2. Чем `run_sql(params)` отличается от `search_users(criteria)`?
3. Почему read-replica не спасла в этом случае?
4. Спроектируй инструмент `update_user_email(user_id, new_email)` с защитой от случайного массового обновления.

---

## Ссылки

- [[01-budget-explosion]] — предыдущий case study
- [[../../../11-security-safety/03-secure-architecture]] — secure architecture (урок 42)
- [[../../../05-production/01-guardrails]] — guardrails (урок 16)
