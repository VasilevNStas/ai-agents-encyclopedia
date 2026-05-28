---
created: 2026-05-09
tags: [wiki/ldd, logging, observability]
status: active
---

# Log Driven Development (LDD) — обсуждаемые идеи

> LDD — подход, при котором логи проектируются до кода как контракт между системой и AI.

## Ключевые мысли

- Логи — это интерфейс, а не свалка
- AI читает JSON-события, а не текстовые строки
- Контракт логов = структура + обязательные поля + метрики
- LDD + Observability + Resilience = полный цикл: логи → анализ → реакция

## Применение для агентов

- Каждый шаг ReAct-цикла — структурированное событие
- AI-дебаггер находит проблемы: циклы, пустые вызовы, перерасход
- Без LDD агент остаётся чёрным ящиком

## Связанные уроки

- [[05-production/03-log-driven-development]] — урок 16
- [[05-production/02-observability]] — Observability (урок 15)
- [[05-production/04-resilience]] — Resilience (урок 17)
