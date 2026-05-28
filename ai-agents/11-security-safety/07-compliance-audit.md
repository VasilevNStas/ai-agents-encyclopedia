---
created: 2026-05-28
tags: [course/security, compliance, audit, eu-ai-act, gdpr, architect]
status: active
---

# Урок 43e: Compliance, Audit & EU AI Act для AI-агентов

> [!quote] Ключевая идея
> С 2025 года EU AI Act регулирует AI-системы. Агенты, работающие с пользователями ЕС, обязаны обеспечивать transparency, explainability и audit trail. Compliance — не бюрократия, а инженерные требования к архитектуре.

---

## 1. EU AI Act: категории для агентов

### Risk classification

| Категория | Пример агента | Требования |
|-----------|--------------|------------|
| **Minimal** | Чат-бот для генерации идей | Базовые: transparency |
| **Limited** | Агент поддержки | + Контроль контента |
| **High-risk** | Агент для кредитного скоринга | + Audit, explainability, HITL |
| **Unacceptable** | Социальный скоринг | Запрещены |

```python
class RiskClassifier:
    """Классифицирует агента по EU AI Act."""

    HIGH_RISK_DOMAINS = [
        "credit_scoring", "employment", "education_access",
        "law_enforcement", "migration", "biometric",
    ]

    def classify(self, agent: dict) -> str:
        domain = agent.get("domain", "")
        if domain in self.HIGH_RISK_DOMAINS:
            return "high-risk"
        if agent.get("autonomous_actions", False):
            return "limited"
        return "minimal"
```

---

## 2. Audit Trail: что логировать

```python
@dataclass
class AgentAuditRecord:
    """Полная запись действия агента для аудита."""

    # Идентификация
    record_id: str  # UUID
    timestamp: datetime
    agent_version: str
    user_id: str

    # Контекст решения
    input_query: str
    system_prompt_snapshot: str  # какой промпт был в момент запроса
    model_id: str
    model_version: str
    temperature: float

    # Цепочка рассуждений
    thought_chain: list[dict]  # что «думал» агент
    tool_calls: list[dict]     # какие инструменты вызвал
    tool_results: list[str]    # что вернули инструменты

    # Итоговое решение
    final_output: str
    confidence_score: float
    guardrail_actions: list[str]

    # Мета-информация
    latency_ms: int
    cost_usd: float
    token_count: int
    human_reviewed: bool = False

    def to_audit_log(self) -> dict:
        """Сериализация для immutable audit log."""
        return {
            "record_id": self.record_id,
            "timestamp": self.timestamp.isoformat(),
            "agent_version": self.agent_version,
            "user_id": hashed(self.user_id),  # GDPR: псевдонимизация
            "input": self.input_query,
            "system_prompt": self.system_prompt_snapshot,
            "model": f"{self.model_id}@{self.model_version}",
            "reasoning": self.thought_chain,
            "actions": self.tool_calls,
            "output": self.final_output,
            "guardrails": self.guardrail_actions,
            "cost": self.cost_usd,
            "human_reviewed": self.human_reviewed,
        }
```

### Immutable audit storage

```python
class AuditStore:
    """Immutable audit log для compliance."""

    def __init__(self, db):
        self.db = db

    def append(self, record: AgentAuditRecord):
        """Добавляет запись в audit log (append-only)."""
        self.db.execute(
            "INSERT INTO agent_audit (id, data, created_at, hash) "
            "VALUES ($1, $2, $3, $4)",
            record.record_id,
            json.dumps(record.to_audit_log()),
            record.timestamp,
            self._hash(record),
        )

    def get_by_user(self, user_id: str,
                    start: datetime, end: datetime) -> list[dict]:
        """Получить все действия агента по пользователю (GDPR)."""
        rows = self.db.fetch(
            "SELECT data FROM agent_audit "
            "WHERE data->>'user_id' = $1 "
            "AND created_at BETWEEN $2 AND $3",
            hashed(user_id), start, end,
        )
        return [r["data"] for r in rows]

    def verify_integrity(self) -> list[str]:
        """Проверяет целостность audit log."""
        violations = []
        rows = self.db.fetch("SELECT id, data, hash FROM agent_audit ORDER BY created_at")
        for row in rows:
            expected = self._hash(row["data"])
            if row["hash"] != expected:
                violations.append(f"Tampered record: {row['id']}")
        return violations

    def _hash(self, record) -> str:
        return hashlib.sha256(json.dumps(record, sort_keys=True).encode()).hexdigest()
```

---

## 3. Explainability: почему агент сделал именно так?

```python
class AgentExplainer:
    """Генерирует человекочитаемое объяснение решения агента."""

    def explain_decision(self, audit_record: AgentAuditRecord) -> str:
        """Объясняет, почему агент принял такое решение."""

        if not audit_record.thought_chain:
            return "No reasoning available."

        explanation = [
            f"## Decision Explanation (ID: {audit_record.record_id})",
            f"**Model:** {audit_record.model_id}",
            f"**Temperature:** {audit_record.temperature}",
            "",
            "### Reasoning chain",
        ]

        for step in audit_record.thought_chain:
            explanation.append(f"- {step.get('thought', '—')}")
            if step.get("action"):
                explanation.append(f"  *Action:* `{step['action']}` → {step.get('observation', '—')}")

        if audit_record.guardrail_actions:
            explanation.extend([
                "",
                "### Guardrails triggered",
                *[f"- {g}" for g in audit_record.guardrail_actions],
            ])

        explanation.extend([
            "",
            "### Confidence",
            f"Score: {audit_record.confidence_score}/1.0",
            f"Cost: ${audit_record.cost_usd:.4f}",
            f"Human reviewed: {'Yes' if audit_record.human_reviewed else 'No'}",
        ])

        return "\n".join(explanation)
```

### Explainability по закону

EU AI Act требует, чтобы пользователь мог получить объяснение решения. Агент должен уметь ответить на вопрос «почему ты сделал X?»:

```python
@tool
def explain_last_decision() -> str:
    """Объясняет последнее решение агента. EU AI Act compliance."""
    record = audit_store.get_last(user_id=get_current_user())
    if not record:
        return "No previous decision found."
    explainer = AgentExplainer()
    return explainer.explain_decision(record)
```

---

## 4. GDPR для агентов

```python
class GDPRCompliance:
    """GDPR compliance для агента."""

    def __init__(self, audit_store: AuditStore):
        self.audit = audit_store

    def right_to_access(self, user_id: str) -> dict:
        """Пользователь запрашивает все свои данные (Art. 15)."""
        records = self.audit.get_by_user(user_id, start="2020-01-01", end="now")
        return {
            "user_id": user_id,
            "data_processed": [
                {
                    "timestamp": r["timestamp"],
                    "purpose": "customer_support",
                    "data_category": "conversation",
                    "retention_days": 365,
                    "data": r["input"],
                }
                for r in records
            ],
            "total_records": len(records),
        }

    def right_to_be_forgotten(self, user_id: str):
        """Удаление всех данных пользователя (Art. 17)."""
        # GDPR: удаляем персональные данные, но сохраняем audit log
        # с псевдонимизацией
        self.audit.anonymize_user(user_id)
        self.user_data.delete_all(user_id)
        return {"status": "anonymized", "user_id": user_id}

    def data_portability(self, user_id: str) -> str:
        """Экспорт данных в машиночитаемом формате (Art. 20)."""
        records = self.audit.get_by_user(user_id, start="2020-01-01", end="now")
        return json.dumps({
            "export_date": datetime.now().isoformat(),
            "user_id": user_id,
            "records": records,
        }, indent=2, ensure_ascii=False)
```

---

## 5. Compliance Checker

```python
class ComplianceChecker:
    """Проверяет агента на compliance с регуляциями."""

    CHECKS = [
        {
            "id": "EUAIA-01",
            "name": "Transparency",
            "requirement": "Пользователь должен знать, что общается с AI",
            "test": lambda a: "AI" in a.system_prompt or "assistant" in a.system_prompt,
        },
        {
            "id": "EUAIA-02",
            "name": "Explainability",
            "requirement": "Агент должен объяснить своё решение",
            "test": lambda a: hasattr(a, "explain_last_decision"),
        },
        {
            "id": "EUAIA-03",
            "name": "Audit Trail",
            "requirement": "Все действия агента логируются",
            "test": lambda a: hasattr(a, "audit_store"),
        },
        {
            "id": "GDPR-01",
            "name": "Right to Access",
            "requirement": "Пользователь может запросить свои данные",
            "test": lambda a: hasattr(a, "get_user_data"),
        },
        {
            "id": "GDPR-02",
            "name": "Right to be Forgotten",
            "requirement": "Пользователь может запросить удаление данных",
            "test": lambda a: hasattr(a, "delete_user_data"),
        },
        {
            "id": "GDPR-03",
            "name": "Data Portability",
            "requirement": "Пользователь может экспортировать данные",
            "test": lambda a: hasattr(a, "export_user_data"),
        },
        {
            "id": "SEC-01",
            "name": "Encryption at Rest",
            "requirement": "Данные пользователей зашифрованы",
            "test": lambda a: a.config.get("encryption_at_rest", False),
        },
        {
            "id": "SEC-02",
            "name": "Pseudonymization",
            "requirement": "PII псевдонимизирована в логах",
            "test": lambda a: a.config.get("pseudonymization", False),
        },
    ]

    def check(self, agent) -> dict:
        results = []
        for check in self.CHECKS:
            try:
                passed = check["test"](agent)
            except Exception:
                passed = False

            results.append({
                "id": check["id"],
                "name": check["name"],
                "passed": passed,
                "requirement": check["requirement"],
            })

        return {
            "agent": agent.name,
            "timestamp": datetime.now(),
            "total": len(results),
            "passed": sum(1 for r in results if r["passed"]),
            "failed": sum(1 for r in results if not r["passed"]),
            "checks": results,
            "compliant": all(r["passed"] for r in results),
        }
```

---

## 6. Практика: compliance audit своего агента

1. Классифицируй своего агента по EU AI Act (minimal/limited/high-risk)
2. Убедись, что у агента есть explainability (почему он сделал X?)
3. Проверь audit trail: все ли действия логируются?
4. Запусти ComplianceChecker на своём агенте
5. Исправь хотя бы один failed check

---

## Резюме

```
Compliance для агентов:

EU AI Act:
  - Risk classification (minimal/limited/high-risk)
  - Transparency: пользователь знает, что общается с AI
  - Explainability: агент объясняет решения

Audit:
  - Immutable audit log (append-only, hash chain)
  - Full trace: input → thought → action → output
  - PII pseudonymization

GDPR:
  - Right to access / be forgotten / portability
  - Data retention policy
  - Encryption at rest
```

---

## Проверь себя

1. Какие три категории риска определяет EU AI Act?
2. Что должно быть в audit trail для high-risk агента?
3. Как GDPR right to be forgotten совместим с immutable audit log?
4. Напиши explainer, который объясняет, почему агент вызвал конкретный инструмент.
5. Какой минимальный набор compliance-функций нужен агенту для работы в EU?

---

## Ссылки

- [[06-incident-response]] — предыдущий урок
- [[../../../14-ethics-responsible-ai/01-responsible-ai]] — responsible AI (урок 49)
- [[../../../14-ethics-responsible-ai/02-bias-fairness]] — bias & fairness (урок 50)
- European Commission: EU AI Act overview
