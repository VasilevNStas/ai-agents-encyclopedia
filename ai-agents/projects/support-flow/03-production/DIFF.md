# DIFF: Stage 3 — Production

> Относительно: [[../../02-memory/DIFF|Stage 2 — Memory & RAG]]
> Модуль курса: [[../../../05-production/01-guardrails]]

## Что изменилось

### Добавлено

| Компонент | Описание |
|-----------|----------|
| `InputGuardrail` | Блокировка prompt injection (7 паттернов), обнаружение sensitive data (API keys, emails, credit cards) |
| `ToolGuardrail` | Блокировка опасных инструментов (delete/rm/sudo), HITL-флаг для дорогих операций (send_email/charge/refund) |
| `BudgetController` | Лимит $0.50/сессия, 20 вызовов, предупреждение на 80% |
| `StepMetrics` / `SessionMetrics` | Метрики каждого шага: latency, cost, guardrail triggers |
| `ProductionAgent` | Новый класс с 4 слоями защиты: input guardrail → budget → tool guardrail → output guardrail |

### Изменено

| Аспект | Stage 2 | Stage 3 |
|--------|---------|---------|
| Иерархия | MemoryAgent (прямой ReAct) | ProductionAgent (4 слоя защиты вокруг ReAct) |
| System prompt | "Save/read memory" | + safety rules, запрет деструктивных операций |
| Tool calls | Прямые | Через tool guardrail + budget check |
| Output | Как есть | Sanitize sensitive data |
| Ошибки | Пробрасываются | Graceful recovery с сообщением пользователю |

### Архитектура слоёв

```
User Input
    │
    ▼
┌──────────────────────┐
│  InputGuardrail      │  ← блокирует injection
│  (prompt injection)  │
└──────┬───────────────┘
       ▼
┌──────────────────────┐
│  BudgetController    │  ← проверяет лимиты
│  ($0.50, 20 calls)  │
└──────┬───────────────┘
       ▼
┌──────────────────────┐
│  ReAct Loop          │
│  (LLM + tools)       │
│                      │
│  ┌────────────────┐  │
│  │ToolGuardrail   │  │  ← блокирует rm/sudo
│  │ (dangerous ops)│  │
│  └────────────────┘  │
└──────┬───────────────┘
       ▼
┌──────────────────────┐
│  OutputGuardrail     │  ← sanitize sensitive data
│  (sanitize)          │
└──────────────────────┘
```

## Как запустить

```bash
python agent.py --provider openai "как сбросить пароль?"
python agent.py "удали все файлы"  # → заблокировано guardrail
```

## Что дальше

[[../../04-multi-agent/DIFF|Stage 4 — Multi-Agent: supervisor + specialists]]
