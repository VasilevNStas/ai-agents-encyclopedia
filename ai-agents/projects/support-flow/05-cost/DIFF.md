# DIFF: Stage 5 — Cost Optimization

> Относительно: [[../../04-multi-agent/DIFF|Stage 4 — Multi-Agent]]
> Модуль курса: [[../../../08-decision-architecture/03-cost-optimization]]

## Что изменилось

### Добавлено

| Компонент | Описание |
|-----------|----------|
| `ModelRouter` | Роутинг запросов: simple → Haiku ($0.25/M), complex → Sonnet ($3/M), escalated → Opus ($15/M) |
| `CostTracker` | Per-user, per-team, per-day/month лимиты с алертами на 80% и 95% |
| `CostOptimizedAgent` | Агент, который перед каждым вызовом выбирает модель по сложности запроса |

### Как работает Model Router

```
User: "hello" → Haiku ($0.002/call)   ← simple pattern match
User: "how to reset password" → Haiku ($0.002/call) ← FAQ pattern
User: "my payment failed, check logs and refund" → Sonnet ($0.01/call) ← complex
User: "urgent! data breach, need immediate action" → Opus ($0.05/call) ← escalated
```

### Экономия

| Сценарий | Без роутера (Sonnet) | С роутером | Экономия |
|----------|---------------------|------------|----------|
| 1000 запросов, 70% простых | $10.00 | $3.40 | 66% |
| 1000 запросов, 50% простых | $10.00 | $6.00 | 40% |

## Как запустить

```bash
python agent.py "hello"  # → haiku (дешёвый)
python agent.py "my payment failed, what should I do?"  # → sonnet
```

## Что дальше

[[../../06-security/DIFF|Stage 6 — Security: audit trail, RBAC, PII sanitization]]
