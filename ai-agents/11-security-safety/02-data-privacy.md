---
created: 2026-05-28
tags: [course/security, data-privacy, pii, gdpr, audit]
status: active
---

# Урок 41: Data Privacy, Isolation & Audit

> [!quote] Ключевая идея
> Агент видит данные пользователей — значит, он обязан их защищать. Data isolation, PII filtering, audit trails и политики удаления — это не бюрократия, а архитектурные решения. Без них агент — юристов кошмар.

---

## Data isolation: разделение данных

Когда агент обслуживает несколько пользователей (или tenant-ов), данные должны быть изолированы на уровне архитектуры, а не договорённости.

### Мультитенантная модель

```python
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class TenantContext:
    tenant_id: str
    user_id: str
    session_id: str


class DataIsolationMiddleware:
    """Гарантирует, что агент видит данные только своего tenant-а."""

    def __init__(self):
        self._stores: dict[str, dict] = {}

    def get_store(self, tenant: TenantContext) -> dict:
        if tenant.tenant_id not in self._stores:
            self._stores[tenant.tenant_id] = {}
        return self._stores[tenant.tenant_id]

    def write(self, tenant: TenantContext, key: str, value: Any) -> None:
        store = self.get_store(tenant)
        store[f"{tenant.user_id}:{key}"] = value

    def read(self, tenant: TenantContext, key: str) -> Optional[Any]:
        store = self.get_store(tenant)
        return store.get(f"{tenant.user_id}:{key}")

    def delete_user_data(self, tenant: TenantContext) -> int:
        """Удаляет все данные пользователя (right to erasure)."""
        store = self.get_store(tenant)
        prefix = f"{tenant.user_id}:"
        keys = [k for k in store if k.startswith(prefix)]
        for k in keys:
            del store[k]
        return len(keys)


# Использование
tenant_a = TenantContext(tenant_id="acme-corp", user_id="user_1", session_id="sess_1")
tenant_b = TenantContext(tenant_id="beta-inc", user_id="user_1", session_id="sess_2")

middleware = DataIsolationMiddleware()
middleware.write(tenant_a, "email", "alice@acme.com")
middleware.write(tenant_b, "email", "alice@beta.com")

# Данные не пересекаются
assert middleware.read(tenant_a, "email") == "alice@acme.com"
assert middleware.read(tenant_b, "email") == "alice@beta.com"
```

> [!warning]
> Никогда не используй `user_id` как единственный ключ изоляции. Всегда добавляй `tenant_id`. Иначе пользователь из одного tenant-а прочитает данные из другого.

---

## PII Detection

**PII** (Personally Identifiable Information) — данные, по которым можно идентифицировать человека. Агент должен сканировать и вход, и выход.

### PIIFilter

```python
import re
from dataclasses import dataclass, field


@dataclass
class PIIMatch:
    type: str
    value: str
    start: int
    end: int


PII_PATTERNS: dict[str, str] = {
    "email": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
    "phone": r"(\+7|8)[\s-]?\(?\d{3}\)?[\s-]?\d{3}[\s-]?\d{2}[\s-]?\d{2}",
    "inn": r"\b\d{12}\b",  # ИНН физ. лица
    "snils": r"\b\d{3}-\d{3}-\d{3} \d{2}\b",
    "credit_card": r"\b(?:\d[ -]*?){13,16}\b",
    "ip_address": r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b",
    "passport_ru": r"\b\d{2}[ ]\d{2}[ ]\d{6}\b",
}


class PIIFilter:
    """Сканирует текст на наличие PII. Маскирует или блокирует."""

    def __init__(self, patterns: dict[str, str] | None = None):
        self.patterns = patterns or PII_PATTERNS
        self._compiled = {
            name: re.compile(pattern)
            for name, pattern in self.patterns.items()
        }

    def scan(self, text: str) -> list[PIIMatch]:
        matches = []
        for name, regex in self._compiled.items():
            for m in regex.finditer(text):
                matches.append(PIIMatch(
                    type=name,
                    value=m.group(),
                    start=m.start(),
                    end=m.end(),
                ))
        return matches

    def mask(self, text: str, placeholder: str = "[REDACTED]") -> str:
        for regex in self._compiled.values():
            text = regex.sub(placeholder, text)
        return text

    def contains_pii(self, text: str) -> bool:
        return len(self.scan(text)) > 0


# Пример
filter = PIIFilter()
user_msg = "Мой email: ivan@example.com, телефон: +7 (999) 123-45-67"

print(filter.scan(user_msg))
# [PIIMatch(type='email', value='ivan@example.com', ...),
#  PIIMatch(type='phone', value='+7 (999) 123-45-67', ...)]

print(filter.mask(user_msg))
# "Мой email: [REDACTED], телефон: [REDACTED]"
```

> [!important]
> PII-фильтр должен применяться **дважды**: на входе (чтобы PII не попал в лог модели) и на выходе (чтобы агент не выдал чужие данные). Фильтр на выходе — обязателен, даже если на входе уже отфильтровали.

---

## Audit Trails

Каждое действие агента должно логироваться с контекстом: кто, что, когда, какие данные были затронуты.

```python
import datetime
import json
from dataclasses import dataclass, asdict, field


@dataclass
class AuditEvent:
    timestamp: str
    tenant_id: str
    user_id: str
    session_id: str
    action: str          # tool_call, llm_generation, error
    resource: str        # какой файл/API был затронут
    status: str          # success, blocked, error
    details: dict        # дополнительные данные (БЕЗ PII)
    pii_found: bool = False


class AuditLogger:
    """Логирует все действия агента для compliance."""

    def __init__(self, storage_path: str = "/var/log/agent/audit/"):
        self.storage_path = storage_path
        self._buffer: list[AuditEvent] = []

    def log(self, event: AuditEvent) -> None:
        self._buffer.append(event)
        serialized = json.dumps(asdict(event), ensure_ascii=False)
        print(f"[AUDIT] {serialized}")  # в реальности — запись в БД

    def get_user_actions(self, user_id: str, tenant_id: str,
                         limit: int = 100) -> list[AuditEvent]:
        """GDPR: предоставить пользователю все его данные."""
        return [
            e for e in self._buffer
            if e.user_id == user_id and e.tenant_id == tenant_id
        ][:limit]

    def export_user_data(self, user_id: str, tenant_id: str) -> str:
        """GDPR Article 20: data portability."""
        events = self.get_user_actions(user_id, tenant_id)
        return json.dumps([asdict(e) for e in events],
                          ensure_ascii=False, indent=2)

    def delete_user_trail(self, user_id: str, tenant_id: str) -> int:
        """GDPR Article 17: right to erasure."""
        before = len(self._buffer)
        self._buffer = [
            e for e in self._buffer
            if not (e.user_id == user_id and e.tenant_id == tenant_id)
        ]
        return before - len(self._buffer)


# Использование
audit = AuditLogger()

audit.log(AuditEvent(
    timestamp=datetime.datetime.utcnow().isoformat(),
    tenant_id="acme-corp",
    user_id="user_42",
    session_id="sess_abc",
    action="tool_call",
    resource="read_file: /tmp/report.pdf",
    status="success",
    details={"file_size": 1024},
))
```

> [!warning]
> Audit-логи **не должны** содержать PII. Логируй `user_id`, но не email, телефон или другие персональные данные. Если нужно привязать действие к человеку — используй обезличенный идентификатор.

---

## Data Retention & Deletion

| Политика | Описание | Пример |
|----------|----------|--------|
| **TTL-based** | Данные удаляются через N дней | Логи сессий — 90 дней |
| **Event-based** | Данные удаляются при наступлении события | После закрытия аккаунта |
| **Size-based** | Старые данные удаляются при превышении квоты | Держать 1000 последних логов |
| **Mark-and-sweep** | Данные помечаются к удалению, затем удаляются | GDPR: день X — анонимизация |

```python
import time
from dataclasses import dataclass


@dataclass
class RetentionPolicy:
    max_age_days: int = 90
    max_records: int = 10_000
    auto_cleanup: bool = True


class DataRetentionManager:
    def __init__(self, policy: RetentionPolicy):
        self.policy = policy
        self._records: list[tuple[float, Any]] = []

    def add(self, record: Any) -> None:
        self._records.append((time.time(), record))
        if self.policy.auto_cleanup:
            self.cleanup()

    def cleanup(self) -> int:
        now = time.time()
        cutoff = now - (self.policy.max_age_days * 86400)

        # TTL-based: удалить старые записи
        self._records = [
            (ts, r) for ts, r in self._records
            if ts >= cutoff
        ]

        # Size-based: обрезать до лимита
        if len(self._records) > self.policy.max_records:
            self._records = self._records[-self.policy.max_records:]

        return len(self._records)

    def purge_user(self, user_id: str) -> int:
        """Полное удаление данных пользователя."""
        before = len(self._records)
        self._records = [
            (ts, r) for ts, r in self._records
            if getattr(r, "user_id", None) != user_id
        ]
        return before - len(self._records)
```

---

## Compliance: GDPR и CCPA

| Право | GDPR (EU) | CCPA (California) |
|-------|-----------|-------------------|
| **Right to know** | Какие данные собраны | Категории и цель сбора |
| **Right to access** | Копия всех данных | Копия за 12 месяцев |
| **Right to deletion** | Удалить данные («право на забвение») | Удалить по запросу |
| **Right to portability** | Экспорт в машиночитаемом формате | Нет явного требования |
| **Data breach notification** | 72 часа | Без неоправданной задержки |

```python
class GDPRCompliance:
    """Обработчик GDPR-запросов."""

    def __init__(self, audit_logger: AuditLogger,
                 data_store: DataIsolationMiddleware):
        self.audit = audit_logger
        self.store = data_store

    def handle_access_request(self, tenant: TenantContext) -> dict:
        """Article 15: предоставить все данные пользователя."""
        actions = self.audit.export_user_data(tenant.user_id, tenant.tenant_id)
        return {
            "user_id": tenant.user_id,
            "data": actions,
            "generated_at": datetime.datetime.utcnow().isoformat(),
        }

    def handle_deletion_request(self, tenant: TenantContext) -> dict:
        """Article 17: право на забвение."""
        deleted_records = self.store.delete_user_data(tenant)
        deleted_logs = self.audit.delete_user_trail(
            tenant.user_id, tenant.tenant_id
        )
        return {
            "deleted_records": deleted_records,
            "deleted_log_entries": deleted_logs,
            "status": "completed",
        }

    def handle_portability_request(self, tenant: TenantContext) -> str:
        """Article 20: переносимость данных."""
        return self.audit.export_user_data(
            tenant.user_id, tenant.tenant_id
        )
```

---

## Anti-patterns

| Anti-pattern | Почему опасно |
|---|---|
| **Хранение логов с PII** | Логи — первое, что требует GDPR. PII в логах = штраф |
| **Отсутствие политик удаления** | Данные копятся годами — surface для утечки растёт |
| **Одна БД для всех tenant-ов** | Ошибка в запросе — и данные tenant-а A видит tenant B |
| **PII-фильтр только на входе** | Агент может сгенерировать PII сам (вытащить из памяти модели) |
| **Логи без контекста** | Нельзя доказать compliance без контекста (кто, что, когда) |

---

## Проверь себя

1. Зачем нужен `tenant_id` в дополнение к `user_id`?
2. Почему PII-фильтр должен применяться и на входе, и на выходе?
3. Какие 4 политики data retention описаны в уроке?
4. Что такое GDPR Article 17 и как его реализовать в архитектуре агента?
5. Почему аудит-логи не должны содержать PII?

---

## Практическое задание

1. Расширь `PIIFilter` — добавь детекцию SSN (Social Security Number) для США.
2. Напиши интеграцию `GDPRCompliance.handle_deletion_request` с реальной БД (SQLite).
3. Реализуй `AuditLogger` с ротацией: старые логи архивируются, а не удаляются сразу.

---

## Резюме

```
Data isolation:   каждый пользователь видит только свои данные
PII detection:    сканирование входа и выхода на персональные данные
Audit trails:     лог всех действий с контекстом (БЕЗ PII)
Data retention:   TTL, event-based, size-based, mark-and-sweep
GDPR compliance:  доступ, удаление, переносимость

Главное правило: PII не должен покидать границы tenant-а,
а аудит-логи не должны содержать PII.
```

---

## Ссылки

- [[05-production/02-observability]] — наблюдение за системой
- [[05-production/03-log-driven-development]] — логи как контракт
- [[03-memory-and-rag/01-memory-types]] — типы памяти агента
- [GDPR Article 17](https://gdpr-info.eu/art-17-gdpr/)
- [CCPA compliance guide](https://oag.ca.gov/privacy/ccpa)
