# ai-agents

> Персональный курс «Работа с AI-агентом: от нуля до Архитектора», построенный как LLM Wiki по методологии Andrej Karpathy.

**Курс — 22 урока в 8 модулях. Практика — 7 рабочих скриптов. Навыки — 5 кастомных skills. Весь проект — Obsidian vault, готовый к использованию.**

---

## Что это?

Это **живой курс**, который ведёт AI-ассистент (OpenCode / Claude Code / Codex). Всё содержание — markdown-файлы в Obsidian-совместимом формате, связанные `[[WikiLinks]]`.

**Концепция:** вы открываете проект в OpenCode, ассистент читает `AGENTS.md` (Schema Layer), понимает свою роль профессора и ведёт вас от урока к уроку — объясняет, задаёт вопросы, проверяет знания, создаёт wiki-страницы по обсуждениям.

### Ключевые идеи

1. **LLM Wiki (Карпати)** — знания не теряются в истории чатов, а компилируются в markdown-файлы, которые богатеют с каждым занятием
2. **Schema Layer** — `AGENTS.md` определяет, как ассистент должен себя вести, чему учить и как поддерживать wiki
3. **Skills** — специализированные инструкции, которые ассистент загружает по необходимости (методология, создание промптов, чеклист архитектора)
4. **Слоистое обучение** — Теория → Пример → Практика → Проверка

---

## Структура

```
ai-agents/
│
├── AGENTS.md              ← Schema Layer (инструкция для ассистента)
├── index.md               ← навигация по курсу
├── log.md                 ← хронология изменений
├── README.md              ← этот файл
│
├── 01-fundamentals/       🔬 Модуль 1: Фундамент (3 урока)
│   ├── 01-how-llms-work.md    — LLM как предсказатель токенов
│   ├── 02-what-is-agent.md    — Анатомия агента
│   └── 03-react-pattern.md    — ReAct: думай → делай
│
├── 02-agent-patterns/     🧩 Модуль 2: Паттерны агентов (3 урока)
│   ├── 01-plan-and-solve.md   — Стратегия + тактика
│   ├── 02-reflexion.md        — Учимся на ошибках
│   └── 03-tool-use.md         — Инструменты = руки агента
│
├── 03-memory-and-rag/     🧠 Модуль 3: Память и RAG (3 урока)
│   ├── 01-memory-types.md     — Short-term / Working / Long-term
│   ├── 02-rag-advanced.md     — RAG 2.0: production пайплайн
│   ├── 03-llm-wiki.md         — LLM Wiki по Карпати
│   ├── 04-grace.md            — Graph-RAG для кода (GRACE)
│   └── 05-vector-databases.md — Типы, выбор, индекс векторов
│
├── 04-multi-agent/        👥 Модуль 4: Мультиагентные системы (4 урока)
│   ├── 01-orchestration.md    — 6 топологий, Supervisor / Peer / Pipeline
│   ├── 02-communication.md    — Message Bus, протоколы
│   ├── 03-anti-patterns.md    — 6 антипаттернов
│   └── 04-a2a-protocol.md     — Agent-to-Agent Protocol
│
├── 05-production/         🛡️ Модуль 5: Production (5 уроков)
│   ├── 01-guardrails.md       — Input / Output / Data guardrails
│   ├── 02-observability.md    — Трассировка, логи, метрики
│   ├── 03-log-driven-development.md — Log-Driven Development
│   ├── 04-resilience.md       — Retry, Fallback, Circuit Breaker
│   └── 05-agent-testing.md    — Unit-тесты, интеграция, evals
│
├── 06-prompt-engineering/ ✍️ Модуль 6: Prompt Engineering (4 урока)
│   ├── 01-system-prompts.md   — System prompt: конституция агента
│   ├── 02-few-shot-cot.md     — Few-shot и Chain-of-Thought
│   ├── 03-structured-output.md— JSON, Function Calling, Grammar
│   └── 04-prompt-caching.md   — Кеширование контекста
│
├── 07-skills/             🎯 Модуль 7: Skills и Экосистема (3 урока)
│   ├── 01-opencode-skills.md  — экосистема расширений
│   ├── 02-writing-skills.md   — написание своих skills
│   └── 03-mcp-integration.md  — Model Context Protocol
│
├── 08-decision-architecture/ ⚖️ Модуль 8: Decision Architecture (5 уроков)
│   ├── 01-fine-tuning-rag-prompting.md — Fine-tuning vs RAG vs Prompting
│   ├── 02-model-selection.md  — Local vs Cloud, критерии выбора
│   ├── 03-cost-optimization.md— Token burn rate, TCO, ROI
│   ├── 04-model-comparison.md — Сравнительный анализ моделей
│   └── 05-ai-gateway.md       — Model Router и прокси-слой
│
├── 09-advanced-rag-agents/ 🔬 Модуль 9: Advanced RAG (4 урока)
│   ├── 01-agentic-rag.md      — Agentic RAG
│   ├── 02-long-running-agents.md — Stateful, checkpointing
│   ├── 03-multi-modal-agents.md— Vision, Audio, Video агенты
│   └── 04-streaming-agents.md — Real-time, streaming
│
├── 10-data-communication/ 📡 Модуль 10: Data & Communication (3 урока)
│   ├── 01-data-engineering.md — Data Engineering for AI
│   ├── 02-agent-communication.md — Agent Communication Protocols
│   └── 03-human-in-the-loop.md— HITL, approval workflows
│
├── 11-security-safety/      🔐 Модуль 11: Security & Safety (3 урока)
│   ├── 01-prompt-injection.md — Injection & Defenses
│   ├── 02-data-privacy.md     — Data Privacy, Isolation, Audit
│   └── 03-secure-architecture.md — Secure Agent Architecture
│
├── 12-quality-evolution/    📊 Модуль 12: Quality & Evolution (3 урока)
│   ├── 01-agent-evaluation.md — Eval пайплайн
│   ├── 02-ab-testing.md       — A/B Testing & Experimentation
│   └── 03-continuous-improvement.md — Feedback loops, drift detection
│
├── 13-ecosystem-operations/ 🚀 Модуль 13: Ecosystem & Operations (3 урока)
│   ├── 01-agent-frameworks.md — LangGraph, CrewAI, AutoGen
│   ├── 02-agent-lifecycle.md  — Docker, K8s, Serverless, CI/CD
│   └── 03-production-operations.md — Rate limit, budget, cost
│
├── 14-ethics-responsible-ai/ 🤝 Модуль 14: Ethics & Responsible AI (2 урока)
│   ├── 01-responsible-ai.md   — Transparency, accountability, EU AI Act
│   └── 02-bias-fairness.md    — Bias types, measurement, debiasing
│
├── 15-capstone/             🏆 Модуль 15: Capstone Project (2 урока)
│   ├── 01-capstone-design.md  — ADR, архитектура, выбор решений
│   └── 02-capstone-implementation.md — Code, tests, deploy, monitoring
│
├── assets/                🛠️ Инструменты и утилиты
│   ├── token_watch.py         — мониторинг контекстного окна
│   ├── two_models_demo.py     — демонстрация model routing
│   ├── structured_output_demo.py — JSON mode vs Function Calling
│   ├── rag_pipeline.py        — RAG 2.0 пайплайн (гибридный поиск)
│   ├── build_your_agent.py    — конструктор ReAct-агента из 150 строк
│   ├── guardrails-blueprint.md— шаблон защиты агента
│   └── final_exam.md          — финальный экзамен (10 заданий)
│
├── skills/                📋 Кастомные навыки (загружаются по запросу)
│   ├── methodology.skill.md      — методика преподавания
│   ├── prompt-engineer.skill.md  — создание промптов
│   ├── agent-architect.skill.md  — чеклист архитектора
│   ├── lesson-creator.skill.md   — шаблон уроков
│   ├── wiki-maintainer.skill.md  — ведение LLM Wiki (v2.0)
│   ├── config.yaml               — конфигурация по умолчанию
│   └── README.md                 — описание skills
│
└── wiki/                  📚 Скомпилированные обсуждения
    ├── rag-discussion.md       — обсуждение RAG
    └── glossary.md             — глоссарий (70+ терминов)
```

---

## Как использовать

### Быстрый старт (открой и учись)

```bash
# 1. Открой проект в OpenCode
opencode /path/to/ai-agents

# 2. Ассистент прочитает AGENTS.md, поймёт свою роль
#    и предложит начать обучение. Просто напиши:
"начнём обучение"

# 3. Проходи модуль за модулем. Ассистент ведёт:
#    — читает урок вместе с тобой
#    — задаёт вопросы
#    — проверяет понимание
#    — фиксирует обсуждения в wiki
```

### Как продолжить с того же места

При старте новой сессии ассистент:
1. Читает `/log.md` — что было сделано в прошлый раз
2. Читает `/index.md` — актуальная навигация
3. Читает `/wiki/` — последние обсуждения
4. Продолжает с того места, где остановились

### Как работает AGENTS.md

`AGENTS.md` — это **Schema Layer** (по Карпати). Он содержит только ядро:
- роль ассистента (профессор)
- структура курса
- ссылки на skills (которые загружаются по запросу)

```python
# Ассистент получает задачу → загружает нужный skill
skill("prompt-engineer")    # при написании промпта
skill("agent-architect")    # при проектировании агента
skill("wiki-maintainer")    # при ведении wiki

# Один skill в момент времени:
skill("brainstorming")      # сначала генерация идей
# ... выполнил ...
skill("writing-plans")      # потом планирование
```

### Как работают Skills

Skills — это markdown-файлы с инструкциями для ассистента. Они лежат в `/skills/`.
Каждый skill содержит:
- YAML frontmatter (name, version, depends_on, config)
- Описание «когда использовать»
- Пошаговый процесс
- Чеклист

```python
# Загрузить skill с параметрами по умолчанию
skill("wiki-maintainer")

# Загрузить с переопределением параметров
skill("agent-architect", {"detail_level": "quick"})
```

---

## Для кого этот курс

| Уровень | Что нужно знать | С чего начать |
|---------|----------------|---------------|
| Начинающий | Основы программирования | Модуль 1, урок 1 |
| Средний | Пробовал ChatGPT/DeepSeek | Модуль 1, урок 2 |
| Продвинутый | Собирал агентов, знаю RAG | Модуль 3 или 4 |

---

## Системные требования

- **OpenCode** (рекомендуется) или любой LLM-клиент с поддержкой инструментов
- **Obsidian** (опционально) — для просмотра wiki
- **Python 3.10+** — для скриптов в `assets/`
- **DeepSeek API key** (опционально) — для демонстраций `structured_output_demo.py`

```bash
# Для демонстраций с API
export DEEPSEEK_API_KEY="sk-..."

# Скрипты без API-ключа работают в режиме симуляции
python3 assets/build_your_agent.py "найди .py файлы"
```

---

## Как поддерживать курс в актуальном состоянии

### LLM Wiki workflow

1. **Обсуждаете тему** → ассистент создаёт wiki-страницу в `/wiki/`
2. **Появляются новые техники** → создаёшь новый урок, обновляешь `index.md`
3. **Периодический lint** → `skill("wiki-maintainer")` с `lint_on_ingest: true`

### Добавление нового урока

```bash
# 1. Создай файл в соответствующем модуле
touch 06-prompt-engineering/04-new-topic.md

# 2. Загрузи skill для шаблона
skill("lesson-creator")

# 3. Ассистент создаст урок по шаблону
# 4. Обнови index.md — добавь ссылку
# 5. Обнови log.md — запиши изменение
```

### Добавление нового skill

```bash
# 1. Создай файл в /skills/
touch skills/my-new-skill.skill.md

# 2. Добавь YAML frontmatter (name, version, config)
# 3. Напиши инструкции (процесс + чеклист)
# 4. Обнови /skills/README.md
# 5. Если нужно — добавь в AGENTS.md секцию 7
```

### Обновление AGENTS.md

Если появляются новые модули, skills или инструменты:
1. Добавь ссылку в секцию 3 (структура)
2. Добавь skill в секцию 7
3. Обнови критерии архитектора, если нужно
4. Проверь размер: `python3 assets/token_watch.py "$(cat AGENTS.md)"`

---

## Ключевые концепции, используемые в проекте

| Концепция | Где описана | Суть |
|-----------|-------------|------|
| **LLM Wiki** | `03-memory-and-rag/03-llm-wiki` | Знания компилируются в markdown, а не ищутся каждый раз |
| **Schema Layer** | `AGENTS.md` | Файл, который определяет поведение ассистента |
| **ReAct** | `01-fundamentals/03-react-pattern` | Цикл Thought → Action → Observation |
| **RAG 2.0** | `03-memory-and-rag/02-rag-advanced` | Query rewrite → Hybrid search → Rerank → Enrich → Generate |
| **Guardrails** | `05-production/01-guardrails` | Input / Output / Data — три слоя защиты |
| **Reflexion** | `02-agent-patterns/02-reflexion` | Агент учится на ошибках между попытками |
| **Progressive Summarization** | `skills/wiki-maintainer.skill.md` v2.0 | Страницы углубляются при каждом возврате (seedling → evergreen) |

---

## Лицензия

MIT. Используй, изменяй, делись.

Проект создан по мотивам манифеста Andrej Karpathy «LLM Wiki»:
https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f
