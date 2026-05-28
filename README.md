---
created: 2026-05-28
tags: [readme, nav, meta]
---

# Обучение

Три курса по AI-инженерии: от ментальной модели LLM до production-архитектур.

> Технические термины, код, имена и форматы — на английском.  
> Объяснения, инструкции и обсуждения — на русском.

---

## 📖 Что это?

Obsidian-хранилище с тремя курсами по AI-агентам, собранными как система знаний. Каждый курс — последовательность уроков с теорией, примерами, практикой и проверкой. Курсы связаны перекрёстными ссылками: `[[ai-agents/...]]`, `[[opencode-skills/...]]`, `[[../../../ai-agents/...]]`.

Можно проходить последовательно (рекомендуется) или брать курсы по отдельности, если есть база.

---

## 📦 Состав

| # | Директория | Уроков | Строк | Статус |
|---|------------|:------:|:-----:|:------:|
| 1 | [`ai-agents/`](./ai-agents/) | **69** | ~16 000 | ✅ complete |
| 2 | [`opencode-skills/`](./opencode-skills/) | **32** | ~4500 | ✅ complete |
| 3 | [`prompt-engineering/`](./prompt-engineering/) | **18 модулей** | ~6000 | ✅ complete |

Общий объём: **~26 000+ строк, ~150+ файлов, 80+ перекрёстных ссылок**.

---

## 🧭 Как они связаны

Курсы выстроены от фундамента к практике:

```
┌────────────────────────────────────────────────────────────────────┐
│                                                                    │
│  prompt-engineering ──────── базовый                               │
│  (как общаться с LLM)                                              │
│         │                                                          │
│         ▼                                                          │
│  ai-agents ──────────────────── основной                           │
│  (как строить агентов)                                             │
│         │                                                          │
│         ▼                                                          │
│  opencode-skills ────────────────── прикладной                     │
│  (как упаковывать знания в Skills)                                 │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

**prompt-engineering → ai-agents:** Модули prompt-engineering (ReAct, MCP, RAG, guardrails) дают базу для ai-agents. Когда ai-agents углубляется в инструменты и протоколы, он ссылается на соответствующие модули prompt-engineering.

**ai-agents → opencode-skills:** Уроки 25-27 ai-agents — краткое введение в Skills. Полный курс — в opencode-skills (10 модулей, 31 урок). Ссылка: `[[../../../opencode-skills/index|opencode-skills]]`.

---

## 🗺️ Полная карта курсов

### prompt-engineering · 16 модулей (10 core + 4 universal + 1 advanced + 3 bonus)

| Модуль | Тема | Строк |
|--------|------|:-----:|
| M01 | Анатомия LLM — токены, эмбеддинги, attention, параметры | 276 |
| M02 | Анатомия промпта — 8 элементов, MVP→production, антипаттерны | 351 |
| M03 | Chain-of-Thought — Zero-shot, Few-shot, Self-Consistency, ToT | 195 |
| M04 | ReAct & Агенты — цикл агента, function calling, ошибки | 247 |
| M05 | RAG 2.0 — chunking, embedding, hybrid search, reranking | 260 |
| M06 | MCP — архитектура, три примитива, транспорт, production | 253 |
| M07 | System Prompts — модульная композиция, Constitutional AI, guardrails | 211 |
| M07b | AI Safety & Alignment — reward hacking, deception, control | 269 |
| M08 | Evaluation & Security — метрики, LLM-as-Judge, injection | 242 |
| M08b | Fine-tuning Pipeline — LoRA, RLHF, DPO, выбор подхода | 270 |
| M08b+ | Практикум: LoRA fine-tuning своими руками (код, Phi-3-mini) | 195 |
| M09 | Архитектурные паттерны — multi-agent, reflection, event-driven | 229 |
| **M14** | **Prompt Operations & Management — версионирование, CI/CD, A/B, мониторинг** | **237** |
| M10 | Role Prompting — Expert, Cascade, Multi-perspective, Adversarial | 231 |
| M11 | Работа с текстом — суммаризация, извлечение, сравнение, перевод | 241 |
| M12 | Креативные промпты — брейншторм, сторителлинг, контент-план | 209 |
| M13 | Аналитика — SWOT, PEST, 5 Whys, Decision Matrix | 288 |
| M15 | Evals & Benchmarks — MMLU, SWE-bench, Arena, production eval | 275 |

Quiz: **100+ вопросов** · Практик: **20+** · Примеров промптов: **6** · Эталонные решения: **да**

### ai-agents · 62 урока, 17 модулей + сквозной проект

| Модуль | Описание | Уроков |
|--------|----------|:------:|
| M01 — Фундамент | LLM, агент, ReAct | 3 |
| M02 — Паттерны агентов | Plan-and-Solve, Reflexion, Tool Use | 3 |
| M03 — Память и RAG | три слоя, RAG 2.0, LLM Wiki, GRACE, Vector DB | 5 |
| M04 — Мультиагентные системы | Supervisor/Peer/Pipeline, протоколы, антипаттерны, A2A | 4 |
| M05 — Production | guardrails, observability, LDD, resilience, testing, LangFuse | 6 |
| M06 — Prompt Engineering | system prompt, CoT, structured output, caching | 4 |
| M07 — Skills (введение) | OpenCode Skills + MCP | 3 |
| M08 — Decision Architecture | fine-tuning vs RAG, model selection, cost, comparison, AI Gateway | 5 |
| M09 — Advanced RAG | agentic RAG, long-running, multi-modal, vision, audio, streaming | 6 |
| M10 — Data & Communication | data eng, protocols, HITL | 3 |
| M11 — Security & Safety | injection, supply chain, red teaming, IR, compliance, secure arch | 7 |
| M12 — Quality & Evolution | evals, A/B testing, continuous improvement | 3 |
| M13 — Ecosystem & Operations | frameworks, lifecycle, production ops | 3 |
| M14 — Ethics & Responsible AI | ethics, bias, fairness | 2 |
| M15 — Capstone Project | ADR design + implementation | 2 |
| **M16 — LangGraph Deep Track** | графы, инструменты, persistence, мультиагент, production | **5** |
| **M17 — Case Studies** | 5 real-world инцидентов: budget, injection, canary, context | **5** |
| **SupportFlow Project** | сквозной проект: 7 этапов от ReAct до LangGraph | — |

Формат урока: `Ключевая идея → Теория + код → Проверь себя → Резюме → Ссылки`

### opencode-skills · 31 урок, 10 модулей

| Модуль | Темы | Уроков |
|--------|------|:------:|
| M01 — Fundamentals | Что такое Skill, vs prompt, vs AGENTS.md, сравнение экосистем | 3 |
| M02 — Anatomy | SKILL.md: YAML frontmatter, spec, validation, практикум разбора | 3 |
| M03 — Mechanics | Skill Tool, 1% rule, lifecycle | 3 |
| M04 — Superpowers Ecosystem | Пакеты, дистрибуция, npm, практикум работы с пакетом | 3 |
| M05 — Writing Skills | 6 шагов, best practices, tool mapping | 3 |
| M06 — Advanced | Композиция, chains, pitfalls | 3 |
| M07 — Debugging | Загрузка, игнор инструкций, инструменты | 3 |
| M08 — Testing & Security | Тестирование, безопасность, sandboxing, property-based testing | 4 |
| M09 — Performance | Context window, token cost, caching | 3 |
| M10 — Fleet Management | CI/CD, мониторинг, управление парком, кросс-агентность | 4 |

---

## 🚀 Сценарии использования

### Сценарий A: Полное погружение (рекомендуется)

```
Шаг 1: prompt-engineering → M01 (Анатомия LLM)
       Цель: понять, как работает то, с чем вы работаете.

Шаг 2: prompt-engineering → M02 (Анатомия промпта)
       Цель: научиться писать промпты осознанно.

Шаг 3: prompt-engineering → M03–M09
       Цель: освоить CoT, ReAct, RAG, MCP, system prompts, безопасность.

Шаг 4: ai-agents → M01–M13
       Цель: от теории к production-агентам.

Шаг 5: opencode-skills → M01–M10
       Цель: упаковать знания в переиспользуемые Skills + управлять парком.

Шаг 6: prompt-engineering → M10–M13
       Цель: прикладные сценарии (аналитика, креатив, текст).
```

### Сценарий B: Только агенты

```
1. ai-agents M01–M02 (фундамент)
2. ai-agents M03     (память и RAG)
3. ai-agents M04–M06 (мультиагент, production, prompt eng)
4. ai-agents M08–M13 (выбор модели, защита, качество, экосистема)
```

### Сценарий C: Только Skills

```
opencode-skills M01 → M02 → M03 → ... → M10
Курс самодостаточен, не требует других курсов.
```

### Сценарий D: Production fast-track

```
1. ai-agents M05     — guardrails + observability + resilience + testing
2. ai-agents M11     — security (injection, privacy, audit)
3. ai-agents M12     — evaluation + A/B testing + continuous improvement
4. ai-agents M13     — frameworks + lifecycle + ops
5. prompt-engineering M08 — LLM-as-Judge, production checklist
```

---

## 🏗️ Структура директорий

```
Обучение/
├── README.ru.md                    ← этот файл
├── README.en.md                    ← English version
├── index.md                        ← навигация по курсам
│
├── ai-agents/                      ← курс агентов
│   ├── index.md                    ←   оглавление (62 урока, 17 модулей)
│   ├── AGENTS.md                   ←   инструкции для ассистента
│   ├── log.md                      ←   хронология изменений
│   ├── 01-fundamentals/ ... 15-capstone/  ←   M01–M15 (базовые)
│   ├── 16-langgraph-track/         ←   M16: LangGraph Deep Track
│   ├── 17-case-studies/            ←   M17: Real-World Case Studies
│   ├── projects/support-flow/      ←   сквозной проект (7 этапов)
│   ├── skills/                     ←   5 custom skill-файлов
│   ├── wiki/                       ←   обсуждения (RAG, LDD, GRACE)
│   └── assets/                     ←   скрипты, шаблоны, экзамен
│
├── opencode-skills/                ← курс Skills
│   ├── index.md
│   ├── AGENTS.md
│   ├── log.md
│   ├── 01-fundamentals/ ... 10-fleet-management/  ← 10 модулей
│   ├── meta/                       ←   roadmap, glossary, reference, course-index
│   ├── examples/                   ←   marp-slide (полный пример skill)
│   ├── skills/                     ←   study-helper
│   └── methodology.skill.md
│
├── prompt-engineering/             ← курс промптинга
│   ├── index.md
│   ├── AGENTS.md
│   ├── log.md
│   ├── 01-anatomy-of-llm/ ... 13-analytics-research/  ← 13 модулей
│   ├── wiki/                       ←   2 доп. темы
│   ├── prompts/                    ←   6 примеров промптов + эталонные решения
│
├── примеры-проектов/               ← реальные проекты
│   ├── загородный_дом_область/     ←   дом 150м² с AI-ассистентом
│   ├── multi-agent-code-review/    ←   5 специализированных агентов
│   └── research-rag-agent/         ←   multi-source исследование
│
├── opencode-setup.md               ← конфигурация opencode
└── environment-analysis.md         ← анализ окружения
```

---

## ✅ Чеклист навыков «Архитектор AI-агентов»

| # | Навык | Где |
|---|-------|:---:|
| 1 | Объяснить next-token prediction и attention | pe M01 |
| 2 | Спроектировать ReAct / Plan-and-Solve / Reflexion цикл | aa M01–M02 |
| 3 | Организовать трёхслойную память + RAG | aa M03, pe M05 |
| 4 | Спроектировать мультиагентную систему + A2A | aa M04, pe M09 |
| 5 | Выбрать fine-tuning vs RAG vs prompting, понимать LoRA/RLHF | aa M08, pe M08b |
| 6 | Оптимизировать cost (model routing, AI Gateway, caching) | aa M08 |
| 7 | Написать промпт (Role — Context — Task — Format) | pe M02, aa M06 |
| 8 | Защитить от injection, reward hacking, specification gaming | aa M11, pe M07, pe M07b |
| 9 | Обеспечить observability, evals, benchmarks | aa M05, aa M12, pe M15 |
| 10 | Использовать Skills (писать, отлаживать, property-based тесты, CI/CD) | os M01–M10, aa M07-skl |
| 11 | Работать с MCP-протоколом и A2A | pe M06, aa M07, aa M04 |
| 12 | Human-in-the-Loop для критичных решений | aa M10 |
| 13 | Production deploy: canary, rollback, ops, streaming | aa M13, aa M09 |
| 14 | Анализировать через SWOT / PEST / фреймворки | pe M13 |
| 15 | Писать креативные и ролевые промпты | pe M10, pe M12 |
| 16 | Понимать AI Safety (Constitutional AI, circuit breakers) | pe M07b |
| 17 | Оценивать модели через бенчмарки и свой eval | pe M15 |

*pe = prompt-engineering, aa = ai-agents, os = opencode-skills*

---

## 🛠️ Технические детали

### Формат файлов

- **Markdown** (Obsidian: `[[WikiLinks]]`, callouts, YAML frontmatter)
- **Кодировка**: UTF-8
- **Переносы**: LF
- **Без emoji в коде** (кроме README).

### Callout-блоки

| Тип | Назначение |
|-----|------------|
| `> [!note]` | Примечание |
| `> [!tip]` | Задание |
| `> [!warning]` | Важно |
| `> [!abstract]` | Цель урока |
| `> [!quote]` | Ключевая идея |
| `> [!success]` | Итоги |

### AGENTS.md

Каждый курс содержит `AGENTS.md` — правила для AI-ассистента (opencode, Claude Code и т.д.):
- Роль ассистента (профессор, наставник)
- Структура курса
- Формат ответов
- Методика преподавания

Чтобы ассистент работал в контексте курса → открой vault в opencode → AGENTS.md применится автоматически.

---

## 📊 Статистика

| Метрика | Значение |
|---------|:--------:|
| Всего курсов | 3 |
| Всего уроков | 69 + 32 + 18 модулей |
| Всего файлов | ~150 |
| Строк контента | ~26 000+ |
| Перекрёстных ссылок | 85+ |
| Quiz-вопросов | 100+ |
| Практических заданий | 62 + 32 |
| Примеров промптов | 6 |
| Примеров skills | 2 (marp-slide, code-review-agent) |
| Проектов примеров | 4 (+ SupportFlow сквозной проект) |
| Файлов AGENTS.md | 3 |

### Размеры директорий

```
ai-agents/          ~650 KB,  ~105 файлов (включая projects/support-flow/)
opencode-skills/    ~220 KB,  ~56 файлов
prompt-engineering/ ~210 KB,  ~32 файла
```

---

## 📝 Контекст (Май 2026)

- **Модели**: GPT-4.5, Claude Sonnet 4.6, Claude Haiku 4.6, DeepSeek R1/V3
- **Протоколы**: MCP, A2A, Function Calling
- **Фреймворки**: LangGraph, CrewAI, Microsoft Agent Framework, Pydantic AI, LlamaIndex
- **Векторные БД**: Chroma, Qdrant, Pinecone
- **Формат Skills**: agentskills.io specification v1.0

---

## 📄 Лицензия

Учебные материалы. Свободное использование для самообразования.

---

*Последнее обновление: 2026-05-28*
