---
created: 2026-05-28
tags: [project, support-flow, capstone, architect]
status: active
---

> [!success] Implementation Status: Complete
> All 7 stages now have working, implemented Python code. Each stage directory contains runnable `.py` files that demonstrate the concept. The final production code lives in `src/`.

# SupportFlow — Production AI-Agent для поддержки клиентов

> **Сквозной проект:** агент, который растёт вместе с курсом.
> Каждый модуль добавляет новый слой функциональности.
> К концу курса — production-ready мультиагентная система.

---

## Описание

SupportFlow — AI-агент для B2B-поддержки. Отвечает на тикеты, ищет ответы в базе знаний, эскалирует сложные запросы человеку.

**Сценарий:** SaaS-компания, 5000+ B2B-клиентов, 1000+ тикетов/день.

---

## Структура и связь с курсом

```
support-flow/
│
├── 01-core/          ← Модуль 1 (Фундамент): базовый ReAct-цикл
│   ├── react_agent.py      — минимальный агент с 1 инструментом
│   └── README.md           — что делать на этом этапе
│
├── 02-memory/        ← Модуль 3 (Память и RAG): добавляем RAG
│   ├── vector_store.py     — Chroma/FAISS векторная БД
│   └── memory.py           — трёхслойная память
│
├── 03-production/    ← Модуль 5 (Production): guardrails + мониторинг
│   ├── guardrails.py        — input/output guardrails
│   └── monitoring.py        — LangFuse + метрики
│
├── 04-multi-agent/   ← Модуль 4 (Мультиагент): supervisor
│   ├── supervisor.py        — распределяет задачи
│   └── specialists.py       — специализированные агенты
│
├── 05-cost/          ← Модуль 8 (Decision Architecture): model routing
│   ├── model_router.py     — cheap vs expensive модель
│   └── budget.py           — budget control
│
├── 06-security/      ← Модуль 11 (Security): audit + permissions
│   ├── audit.py            — audit trail
│   ├── permissions.py      — права доступа
│   └── sanitizer.py        — защита от injection
│
├── 07-langgraph/     ← Модуль 16 (LangGraph): переписываем на граф
│   └── langgraph_agent.py  — графовая версия
│
└── src/              ← Финальная production-версия
    ├── agent/              — ядро агента
    ├── api/                — FastAPI сервер
    ├── rag/                — RAG пайплайн
    ├── eval/               — evaluation suite
    └── deploy/             — Docker + K8s
```

---

## Как работать с проектом

1. **Проходишь модуль курса** → открываешь соответствующую директорию
2. **Читаешь README** в директории — что нужно сделать
3. **Пишешь/дополняешь код** — добавляешь новый слой
4. **src/ всегда содержит актуальную версию** — production-код

```bash
# Старт: после модуля 1
cd projects/support-flow/01-core
python react_agent.py "Как сбросить пароль?"

# После модуля 3: добавляем RAG
cd ../..  # обратно в корень проекта
# Код уже в src/rag/
python -m src.agent.core "Что в моём последнем заказе?"
```

---

## Технологический стек

| Компонент | Технология | Почему |
|-----------|-----------|--------|
| LLM | Claude Sonnet 4.6 / GPT-4o-mini | Баланс качества и цены |
| Фреймворк | LangGraph | Production-стандарт 2026 |
| Векторная БД | Chroma (dev) / Qdrant (prod) | Простота → масштаб |
| API | FastAPI | Современный async Python |
| Мониторинг | LangFuse + OpenTelemetry | LLM-observability |
| База данных | Postgres (память, аудит) | Надёжность |
| Деплой | Docker → Cloud Run | Serverless + canary |

---

## Чеклист «Архитектор»

- [x] 01-core: ReAct-цикл с одним инструментом (search)
- [x] 02-memory: RAG на базе знаний (Chroma)
- [x] 03-production: input guardrails + cost tracking
- [x] 04-multi-agent: supervisor + 2 специалиста
- [x] 05-cost: model router (haiku для простых, sonnet для сложных)
- [x] 06-security: audit trail + sanitizer
- [x] 07-langgraph: переписать на LangGraph
- [ ] Финально: запустить src/api/main.py → деплой

---

## Связь с другими курсами

- [[../../../../prompt-engineering/index|Prompt Engineering]] — system prompt, CoT, structured output
- [[../../../../opencode-skills/index|OpenCode Skills]] — упаковка знаний в skills
- [[../../15-capstone/01-capstone-design|Capstone ADR]] — архитектурные решения для SupportFlow
