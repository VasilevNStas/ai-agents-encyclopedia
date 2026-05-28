# DIFF: Stage 4 — Multi-Agent

> Относительно: [[../../03-production/DIFF|Stage 3 — Production]]
> Модуль курса: [[../../../04-multi-agent/01-orchestration]]

## Что изменилось

### Добавлено

| Компонент | Описание |
|-----------|----------|
| `SupervisorAgent` | Классификация тикетов (LLM + keyword fallback), дедупликация, роутинг к специалистам, эскалация человеку |
| `BillingAgent` / `TechnicalAgent` / `AccountAgent` | Специализированные агенты с domain-specific инструментами |
| `LLMClassifier` | Классификация через LLM (gpt-4o-mini) вместо keyword matching |
| `MultiAgentSupport` | Оркестратор: classify → route → process → handoff |

### Архитектура

```
User Ticket
    │
    ▼
┌─────────────────────┐
│   Supervisor Agent  │
│                     │
│  1. Classify (LLM)  │
│  2. De-duplicate    │
│  3. Route           │
└──────┬──────────────┘
       │
       ▼ (routed to specialist)
┌─────────────────────┐
│   Specialist Agent  │
│                     │
│  ┌─────────────────┐│
│  │Billing   │ Tools││  ← lookup_invoice, process_refund
│  │Technical│ Tools││  ← diagnose, check_status
│  │Account  │ Tools││  ← view_profile, update_email
│  └─────────────────┘│
└──────┬──────────────┘
       │
       ├── resolved → response
       ├── escalate → human
       └── clarify → more info
```

### Handoff Protocol

| Статус | Действие |
|--------|----------|
| `resolved` | Ответ пользователю |
| `escalate` | Supervisor отправляет человеку с reason |
| `clarify` | Запрос дополнительной информации |

## Как запустить

```bash
# LLM классификация (по умолчанию)
python agent.py "у меня не проходит платёж, спишете ещё раз?"
python agent.py --keyword-only "помогите с ошибкой в API"

# Interactive
python agent.py
```

## Что дальше

[[../../05-cost/DIFF|Stage 5 — Cost Optimization: model router + budget control]]
