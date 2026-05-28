---
created: 2026-05-28
updated: 2026-05-28
tags: [course/ai-agents, index, ecosystem]
status: active
---

# M13: Ecosystem & Operations

Деплой, мониторинг, производственные операции и выбор фреймворка для агентов.

```dataview
TABLE status as "Status", created as "Created"
FROM "projects/Обучение/ai-agents/13-ecosystem-operations"
WHERE file.name != "index"
SORT file.name ASC
```

## Уроки модуля

| # | Тема | Статус |
|---|------|--------|
| 43 | [[01-agent-frameworks.md\|Agent Frameworks]] | ✅ active |
| 44 | [[02-agent-lifecycle.md\|Agent Lifecycle]] | ✅ active |
| 45 | [[03-production-operations.md\|Production Operations]] | ✅ active |

## Описание

- **43: Agent Frameworks** — LangGraph, CrewAI, Microsoft Agent Framework, Pydantic AI, LlamaIndex. Сравнение, decision tree, антипаттерны.
- **44: Agent Lifecycle** — shadow / canary / blue-green деплой, versioning, rollback, feature flags, CI/CD.
- **45: Production Operations** — rate limiting, budget, cost tracking, semantic caching, model triage, alerts, runbook.

## Связи с другими модулями

- [[../05-production/01-guardrails|M05: Production]] — развёртывание и тестирование в production
- [[../21-context-window-deep/03-pricing-caching|M21: Context Window]] — оптимизация и кеширование
- [[../12-quality-evolution/01-agent-evaluation|M12: Quality & Evolution]] — качество и A/B тестирование
