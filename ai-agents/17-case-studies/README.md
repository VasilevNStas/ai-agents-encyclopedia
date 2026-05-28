---
created: 2026-05-28
tags: [course/case-studies, nav, index]
status: active
---

# Real-World Case Studies

> Разбор реальных инцидентов с AI-агентами в production.
> Каждый case study = инцидент → root cause → решение → выводы.

| # | Кейс | Главный урок |
|---|------|-------------|
| 01 | [[01-budget-explosion\|Бесконечный ReAct-цикл на $15,000]] | Budget control — обязательный слой |
| 02 | [[02-production-db-deletion\|Как агент удалил production базу]] | SQL-инструменты без guardrails |
| 03 | [[03-indirect-injection\|Indirect Injection через README]] | Внешний контент — не доверять |
| 04 | [[04-canary-failure\|Canary-раскатка, сломавшая 30% запросов]] | Release pipeline для агента |
| 05 | [[05-context-poisoning\|Context Window Poisoning]] | Инструкции «забываются» с длиной контекста |

**Формат:** Анализ → Root cause → Защита → Чеклист → Проверь себя.
