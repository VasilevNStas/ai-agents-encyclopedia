---
created: 2026-05-08
updated: 2026-05-28
tags: [course/index, nav]
status: active
---

# AI-агенты: от нуля до Архитектора

> **English version below** &nbsp;·&nbsp; *English below*

Мы стоим на пороге мира, где программировать будут не люди, а агенты. Где вопрос «как написать этот код?» сменится на «как объяснить агенту, какой код мне нужен?». Эта книга — не про то, как пользоваться ChatGPT. Она про то, как устроены агенты изнутри: как они думают, как ошибаются, как проектируются и как работают в production.

104 урока, 25 модулей. От ментальной модели токена до распределённой памяти мультиагентной системы. От одного промпта до Kubernetes-кластера с LoRA-адаптерами. От «что такое LLM?» до «как работает speculative decoding?». Это не туториал. Это архитектурный справочник и инженерный манифест — для тех, кто хочет не просто вызывать API, а понимать, как спроектировать систему, которая выживет в реальном мире.

---

## AI Agents: From Zero to Architect

We are standing at the threshold of a world where code will be written not by humans, but by agents. Where the question "how do I write this code?" will become "how do I explain to an agent what code I need?" This book is not about using ChatGPT. It is about how agents work from the inside: how they think, how they fail, how they are designed, and how they operate in production.

104 lessons, 25 modules. From a mental model of a token to distributed memory for multi-agent systems. From a single prompt to a Kubernetes cluster with LoRA adapters. From "what is an LLM?" to "how does speculative decoding work?" This is not a tutorial. It is an architectural reference and an engineering manifesto — for those who want not just to call an API, but to understand how to design a system that survives in the real world.

---

**Уровень / Level:** с нуля до архитектора / zero to architect  
**Формат / Format:** Теория → Пример → Практика → Проверка / Theory → Example → Practice → Review  
**Язык / Language:** русский, код на английском / Russian, code in English  
**Всего уроков / Total lessons:** 104

---

## Структура курса

### Модуль 1 — Фундамент (3 урока)
| # | Тема | Ссылка |
|---|------|--------|
| 1 | Как работают LLM — ментальная модель | [[01-fundamentals/01-how-llms-work]] |
| 2 | Что такое AI-агент? Анатомия агента | [[01-fundamentals/02-what-is-agent]] |
| 3 | Паттерн ReAct — Reasoning + Acting | [[01-fundamentals/03-react-pattern]] |

### Модуль 2 — Паттерны агентов (3 урока)
| # | Тема | Ссылка |
|---|------|--------|
| 4 | Plan-and-Solve — стратегия + тактика | [[02-agent-patterns/01-plan-and-solve]] |
| 5 | Reflexion — саморефлексия агента | [[02-agent-patterns/02-reflexion]] |
| 6 | Tool Use & Function Calling | [[02-agent-patterns/03-tool-use]] |

### Модуль 3 — Память и RAG (5 уроков)
| # | Тема | Ссылка |
|---|------|--------|
| 7 | Три слоя памяти: Short-term / Working / Long-term | [[03-memory-and-rag/01-memory-types]] |
| 8 | RAG 2.0 — от Naive к Production | [[03-memory-and-rag/02-rag-advanced]] |
| 9 | LLM Wiki — подход Карпати | [[03-memory-and-rag/03-llm-wiki]] |
| 10 | GRACE — Graph-RAG для кода | [[03-memory-and-rag/04-grace]] |
| **11** | **Vector Databases — типы, выбор, индекс** | [[03-memory-and-rag/05-vector-databases]] |

### Модуль 4 — Мультиагентные системы (4 урока)
| # | Тема | Ссылка |
|---|------|--------|
| 12 | Оркестрация: 6 топологий, Supervisor, Consensus, Escalation | [[04-multi-agent/01-orchestration]] |
| 13 | Коммуникация: протоколы, Message Bus | [[04-multi-agent/02-communication]] |
| 14 | 6 антипаттернов мультиагентных систем | [[04-multi-agent/03-anti-patterns]] |
| 15 | A2A — Agent-to-Agent Protocol | [[04-multi-agent/04-a2a-protocol]] |

> [!tip] После модуля 4
> Рекомендуется сразу перейти к [[13-ecosystem-operations/01-agent-frameworks|уроку 46 (фреймворки)]] — LangGraph, CrewAI, MS Agent Framework. Это даст инструменты для экспериментов на протяжении оставшихся модулей.

### Модуль 5 — Production (6 уроков)
| # | Тема | Ссылка |
|---|------|--------|
| 16 | Guardrails: Input, Output, Data | [[05-production/01-guardrails]] |
| 17 | Observability: трассировка, логи, метрики | [[05-production/02-observability]] |
| 18 | Log Driven Development (LDD) | [[05-production/03-log-driven-development]] |
| 19 | Resilience: Retry, Fallback, Circuit Breaker | [[05-production/04-resilience]] |
| 20 | Testing & Evaluation | [[05-production/05-agent-testing]] |
| **+** | **LangFuse Integration — observability на практике** | [[05-production/06-langfuse-integration]] |

### Модуль 6 — Prompt Engineering для агентов (4 урока)
| # | Тема | Ссылка |
|---|------|--------|
| 21 | System Prompt — конституция агента | [[06-prompt-engineering/01-system-prompts]] |
| 22 | Few-shot и Chain-of-Thought | [[06-prompt-engineering/02-few-shot-cot]] |
| 23 | Structured Output: JSON, Function Calling | [[06-prompt-engineering/03-structured-output]] |
| **24** | **Prompt Caching — кеширование контекста** | [[06-prompt-engineering/04-prompt-caching]] |

> [!info] Связь с курсом Prompt Engineering
> Модуль 6 — **агентно-ориентированная** версия PE: system prompt для агента, function calling, caching. Это не дубликат, а дополнение. Полный курс [[../../../prompt-engineering/index|Prompt Engineering]] (9 core + 4 universal + 2 advanced) даёт фундамент. **Что, где, когда проходить** — [[wiki/pe-course-map|карта курсов PE →]]

### Модуль 7 — Skills и Экосистема (3 урока)
| # | Тема | Ссылка |
|---|------|--------|
| 25 | OpenCode Skills — введение | [[07-skills/01-opencode-skills]] |
| 26 | Написание Skills — введение | [[07-skills/02-writing-skills]] |
| 27 | MCP — Model Context Protocol | [[07-skills/03-mcp-integration]] |

> [!info] Полный курс по Skills
> Уроки 24-25 — краткое введение. Глубокое изучение — [[../../../opencode-skills/index|opencode-skills]] (9 модулей, 27 уроков).

### Модуль 8 — Decision Architecture (5 уроков)
| # | Тема | Ссылка |
|---|------|--------|
| 28 | Fine-tuning vs RAG vs Prompting | [[08-decision-architecture/01-fine-tuning-rag-prompting]] |
| 29 | Model Selection & Local vs Cloud | [[08-decision-architecture/02-model-selection]] |
| 30 | Cost Optimization — Token Burn Rate, TCO, Break-even, ROI | [[08-decision-architecture/03-cost-optimization]] |
| 31 | Model Comparison — сравнительный анализ моделей | [[08-decision-architecture/04-model-comparison]] |
| 32 | AI Gateway — Model Router и прокси-слой | [[08-decision-architecture/05-ai-gateway]] |

### Модуль 9 — Advanced RAG & Agents (6 уроков)
| # | Тема | Ссылка |
|---|------|--------|
| 33 | Agentic RAG | [[09-advanced-rag-agents/01-agentic-rag]] |
| 34 | Long-running & Stateful Agents | [[09-advanced-rag-agents/02-long-running-agents]] |
| 35 | Multi-Modal Agents | [[09-advanced-rag-agents/03-multi-modal-agents]] |
| 36 | Streaming и Real-Time агенты | [[09-advanced-rag-agents/04-streaming-agents]] |
| **+** | **Vision Agents — работа с изображениями** | [[09-advanced-rag-agents/05-vision-agents]] |
| **+** | **Audio Agents — обработка речи и звука** | [[09-advanced-rag-agents/06-audio-agents]] |

### Модуль 10 — Data & Communication (3 урока)
| # | Тема | Ссылка |
|---|------|--------|
| 37 | Data Engineering for AI | [[10-data-communication/01-data-engineering]] |
| 38 | Agent Communication Protocols | [[10-data-communication/02-agent-communication]] |
| 39 | Human-in-the-Loop | [[10-data-communication/03-human-in-the-loop]] |

### Модуль 11 — Security & Safety (7 уроков)
| # | Тема | Ссылка |
|---|------|--------|
| 40 | Prompt Injection & Defenses | [[11-security-safety/01-prompt-injection]] |
| 41 | Data Privacy, Isolation & Audit | [[11-security-safety/02-data-privacy]] |
| 42 | Secure Agent Architecture | [[11-security-safety/03-secure-architecture]] |
| **+** | **Supply Chain Security — защита цепочки поставок** | [[11-security-safety/04-supply-chain-security]] |
| **+** | **Red Teaming — тестирование на проникновение** | [[11-security-safety/05-red-teaming]] |
| **+** | **Incident Response — реагирование на инциденты** | [[11-security-safety/06-incident-response]] |
| **+** | **Compliance & Audit — EU AI Act, GDPR, SOC2** | [[11-security-safety/07-compliance-audit]] |

### Модуль 12 — Quality & Evolution (3 урока)
| # | Тема | Ссылка |
|---|------|--------|
| 43 | Agent Evaluation | [[12-quality-evolution/01-agent-evaluation]] |
| 44 | A/B Testing & Experimentation | [[12-quality-evolution/02-ab-testing]] |
| 45 | Continuous Improvement | [[12-quality-evolution/03-continuous-improvement]] |

### Модуль 13 — Ecosystem & Operations (3 урока)
| # | Тема | Ссылка |
|---|------|--------|
| **46** | **Agent Frameworks — LangGraph, CrewAI, AutoGen (+side-by-side код)** | [[13-ecosystem-operations/01-agent-frameworks]] |
| **47** | **Agent Lifecycle — Docker, K8s, Serverless, CI/CD, Canary** | [[13-ecosystem-operations/02-agent-lifecycle]] |
| **48** | **Production Operations — rate limit, budget, cost** | [[13-ecosystem-operations/03-production-operations]] |

> [!tip] Порядок изучения
> Модуль 13 можно (и рекомендуется) изучать сразу после модуля 4, не дожидаясь модулей 5–12. Фреймворки (урок 46) дают практические инструменты, которые пригодятся во всех последующих уроках.

### Модуль 14 — Ethics & Responsible AI (2 урока)
| # | Тема | Ссылка |
|---|------|--------|
| **49** | **Responsible AI — этика, transparency, accountability** | [[14-ethics-responsible-ai/01-responsible-ai]] |
| **50** | **Bias, Fairness & Inclusive Design** | [[14-ethics-responsible-ai/02-bias-fairness]] |

### Модуль 15 — Capstone Project (2 урока)
| # | Тема | Ссылка |
|---|------|--------|
| **51** | **Capstone: Architecture & Design (ADR)** | [[15-capstone/01-capstone-design]] |
| **52** | **Capstone: Implementation, Testing, Deploy** | [[15-capstone/02-capstone-implementation]] |

### Модуль 16 — LangGraph Deep Track (5 уроков)
| # | Тема | Ссылка |
|---|------|--------|
| **53** | **Graph Architecture & State Management** | [[16-langgraph-track/01-graph-basics]] |
| **54** | **Tools & Function Calling** | [[16-langgraph-track/02-tools-calling]] |
| **55** | **Memory & Persistence** | [[16-langgraph-track/03-memory-persistence]] |
| **56** | **Multi-Agent Graphs** | [[16-langgraph-track/04-multi-agent-graphs]] |
| **57** | **Production: Streaming, HITL, Performance** | [[16-langgraph-track/05-production-streaming]] |

> [!tip] LangGraph — обязательный модуль для Architect
> После модулей 1-4 изучи LangGraph. Это де-факто стандарт production-агентов в 2026. Модуль 16 заменяет самописные циклы на графовую архитектуру.

### Модуль 18 — MCP Deep Track (5 уроков)
| # | Тема | Ссылка |
|---|------|--------|
| **63** | **Server Patterns: транспорт, lifecycle, stateless vs stateful** | [[18-mcp-deep/01-server-patterns]] |
| **64** | **Security & Production: auth, sandboxing, rate limiting** | [[18-mcp-deep/02-security-production]] |
| **65** | **Composition: Gateway, Caching, Transformer, Router** | [[18-mcp-deep/03-composition-patterns]] |
| **66** | **Building Servers: Python SDK, Node SDK, CI/CD** | [[18-mcp-deep/04-building-servers]] |
| **67** | **Ecosystem Map: MCP vs A2A vs Function Calling vs Agent Protocol** | [[18-mcp-deep/05-ecosystem-map]] |

### Модуль 19 — Multi-modal Deep Track (6 уроков)
| # | Тема | Ссылка |
|---|------|--------|
| **68** | **Экономика и архитектура мультимодальных систем** | [[19-multi-modal-deep/01-economics-architecture]] |
| **69** | **Vision Agents Deep Dive** | [[19-multi-modal-deep/02-vision-deep]] |
| **70** | **Audio & Voice Agents Deep Dive** | [[19-multi-modal-deep/03-audio-deep]] |
| **71** | **Video Agents Deep Dive** | [[19-multi-modal-deep/04-video-deep]] |
| **72** | **Multi-modal RAG** | [[19-multi-modal-deep/05-multimodal-rag]] |
| **73** | **Production Multi-modal Systems** | [[19-multi-modal-deep/06-production]] |

### Модуль 20 — Evaluation Tools Deep Track (6 уроков)
| # | Тема | Ссылка |
|---|------|--------|
| **74** | **Eval Tools Landscape — promptfoo vs DeepEval vs Ragas** | [[20-eval-tools-deep/01-landscape]] |
| **75** | **promptfoo Deep Dive** | [[20-eval-tools-deep/02-promptfoo-deep]] |
| **76** | **DeepEval Deep Dive** | [[20-eval-tools-deep/03-deepeval-deep]] |
| **77** | **Ragas Deep Dive** | [[20-eval-tools-deep/04-ragas-deep]] |
| **78** | **Production Eval Infrastructure** | [[20-eval-tools-deep/05-production-eval]] |
| **79** | **Building an Eval Pipeline — End-to-End** | [[20-eval-tools-deep/06-eval-pipeline]] |

### Модуль 21 — Context Window Deep Track (3 урока)
| # | Тема | Ссылка |
|---|------|--------|
| **80** | **Context Window Landscape 2026** | [[21-context-window-deep/01-landscape]] |
| **81** | **Context Window Optimization** | [[21-context-window-deep/02-optimization]] |
| **82** | **Context Window Pricing & Caching** | [[21-context-window-deep/03-pricing-caching]] |

### Модуль 22 — Fine-tuning Deep Track (6 уроков)
| # | Тема | Ссылка |
|---|------|--------|
| **83** | **Decision Framework: Prompting vs RAG vs Fine-tuning** | [[22-fine-tuning-deep/01-landscape]] |
| **84** | **LoRA/QLoRA/DoRA Deep Dive** | [[22-fine-tuning-deep/02-lora-deep]] |
| **85** | **RLHF / DPO / GRPO — Alignment** | [[22-fine-tuning-deep/03-rlhf-dpo]] |
| **86** | **Data Preparation & Quality** | [[22-fine-tuning-deep/04-data-preparation]] |
| **87** | **Fine-tuning для Агентов** | [[22-fine-tuning-deep/05-agent-finetuning]] |
| **88** | **Production: Deployment, Monitoring, TCO** | [[22-fine-tuning-deep/06-production]] |

### Модуль 23 — Coding Agents Deep Track (6 уроков)
| # | Тема | Ссылка |
|---|------|--------|
| **89** | **Coding Agents Landscape** | [[23-coding-agents-deep/01-landscape]] |
| **90** | **Code Generation Architecture** | [[23-coding-agents-deep/02-code-generation]] |
| **91** | **Self-Debugging & Self-Healing** | [[23-coding-agents-deep/03-self-debugging]] |
| **92** | **Code Repository Understanding** | [[23-coding-agents-deep/04-repo-understanding]] |
| **93** | **Multi-file Editing & Refactoring** | [[23-coding-agents-deep/05-multi-file-editing]] |
| **94** | **CI/CD для Generated Code** | [[23-coding-agents-deep/06-production-ci]] |

### Модуль 24 — Agent Memory Systems Deep Track (4 урока)
| # | Тема | Ссылка |
|---|------|--------|
| **95** | **Memory Architectures: Episodic, Semantic, Procedural** | [[24-memory-systems-deep/01-architectures]] |
| **96** | **Agentic Memory: MemGPT / Letta** | [[24-memory-systems-deep/02-memgpt]] |
| **97** | **Memory Consolidation & Compression** | [[24-memory-systems-deep/03-consolidation]] |
| **98** | **Memory at Scale: Distributed & Persistent** | [[24-memory-systems-deep/04-scale]] |

### Модуль 25 — Performance Deep Track (4 урока)
| # | Тема | Ссылка |
|---|------|--------|
| **99** | **Inference Optimization: KV-Cache, Batching, PagedAttention** | [[25-performance-deep/01-inference-optimization]] |
| **100** | **Quantization & Model Compression** | [[25-performance-deep/02-quantization]] |
| **101** | **Speculative Decoding** | [[25-performance-deep/03-speculative-decoding]] |
| **102** | **Distillation & Pruning** | [[25-performance-deep/04-distillation]] |

### Модуль 17 — Real-World Case Studies (5 уроков)
| # | Кейс | Ссылка |
|---|------|--------|
| **58** | **Бесконечный ReAct-цикл на $15,000** | [[17-case-studies/01-budget-explosion]] |
| **59** | **Как агент удалил production базу** | [[17-case-studies/02-production-db-deletion]] |
| **60** | **Indirect Injection через README** | [[17-case-studies/03-indirect-injection]] |
| **61** | **Canary-раскатка, сломавшая 30% запросов** | [[17-case-studies/04-canary-failure]] |
| **62** | **Context Window Poisoning** | [[17-case-studies/05-context-poisoning]] |

> [!warning] Учись на чужих ошибках
> Каждый case study — реальный инцидент из production. Прочитай их перед тем, как деплоить своего первого агента. Это сэкономит тебе $15,000.

### Проект: SupportFlow (сквозной)
| Этап | Тема | Модуль курса |
|------|------|--------------|
| **P1** | **Core ReAct Agent** | [[projects/support-flow/01-core/README\|M01]] |
| **P2** | **Память и RAG** | [[projects/support-flow/02-memory/README\|M03]] |
| **P3** | **Guardrails + Observability** | [[projects/support-flow/03-production/README\|M05]] |
| **P4** | **Мультиагент (Supervisor)** | [[projects/support-flow/04-multi-agent/README\|M04]] |
| **P5** | **Model Router + Budget** | [[projects/support-flow/05-cost/README\|M08]] |
| **P6** | **Security + Audit** | [[projects/support-flow/06-security/README\|M11]] |
| **P7** | **LangGraph Migration** | [[projects/support-flow/07-langgraph/README\|M16]] |

> [!tip] Сквозной проект
> SupportFlow — агент, который растёт вместе с тобой. После каждого модуля ты добавляешь новый слой. Финальная версия — production-ready мультиагентная система на LangGraph. [[projects/support-flow/README|Подробнее →]]

---

## Как работать с курсом

1. Проходи модули последовательно (каждый опирается на предыдущий)
2. Выполняй практические задания в OpenCode
3. Веди конспект — каждое понятие должно осесть в твоём Obsidian vault
4. После каждого урока — проверь себя: ответь на вопросы в конце

> [!tip] Совет
> Если какой-то термин непонятен — сразу спрашивай. Лучше потратить 5 минут на прояснение сейчас, чем час на debugging агента, который не работает из-за непонимания базового принципа.

---

## Критерии «Архитектора»

Курс считается пройденным, когда ты можешь:

- [ ] Объяснить, как работает LLM (next-token prediction, attention, sampling)
- [ ] Спроектировать цикл агента (ReAct, Plan-and-Solve, Reflexion)
- [ ] Организовать трёхслойную память (short-term, working, long-term)
- [ ] Выбрать и реализовать RAG 2.0 пайплайн
- [ ] Спроектировать мультиагентную систему с топологией Supervisor
- [ ] Выбрать подход: prompting vs RAG vs fine-tuning под задачу
- [ ] Выбрать модель и оптимизировать cost (model routing, caching)
- [ ] Написать промпт с учётом анатомии (Role, Context, Task, Format)
- [ ] Защитить агента от prompt injection и утечки данных
- [ ] Обеспечить observability, evaluation и A/B тестирование
- [ ] Использовать skills и протоколы (MCP, A2A)
- [ ] Реализовать Human-in-the-Loop для критичных решений
- [ ] Выстроить continuous improvement pipeline
- [ ] Обеспечить transparency и accountability (audit trail, explainability, EU AI Act readiness)
- [ ] Измерить и смягчить bias в агенте (gender, cultural, confirmation)
- [ ] Спроектировать и реализовать production-агента от ADR до deploy (capstone)
- [ ] Построить графового агента на LangGraph с checkpointing и streaming
- [ ] Разработать многослойную защиту (supply chain, red teaming, IR)
- [ ] Провести post-mortem реального инцидента и предложить fix
- [ ] Обеспечить compliance: EU AI Act, GDPR, audit trail
- [ ] Подключить observability (LangFuse, OpenTelemetry, алерты)
- [ ] Реализовать release pipeline с canary и auto-rollback
- [ ] Интегрировать vision/audio модальности в агента
- [ ] Выполнить LoRA fine-tuning под задачу агента

---

## Ресурсы

- [[AGENTS.md]] — инструкция для AI-ассистента (Schema Layer)
- [Karpathy: LLM Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) — манифест
- [[skills/]] — кастомные навыки для этого курса

## Wiki курса

- [[log.md]] — хронология всех событий
- [[wiki/rag-discussion]] — обсуждение RAG

## Assets

- [[assets/token_watch.py]] — мониторинг контекстного окна
- [[assets/two_models_demo.py]] — демонстрация множественных вызовов моделей
- [[assets/deployment/README|Deployment]] — Docker, K8s, canary deploy
- [[assets/monitoring/README|Monitoring]] — OpenTelemetry, LangSmith, Prometheus, Grafana
- [[assets/testing/README|Testing]] — тесты агента, guardrails, RAG, tools
- [[assets/final_exam.md|Финальный экзамен]] — проверка знаний по всему курсу
