---
created: 2026-05-28
updated: 2026-05-28
tags: [course/index, nav, prompt-engineering]
status: active
---

# Курс: Prompt Engineering

> От новичка до Архитектора промптных систем.
> 10 core + 4 универсальных + 2 advanced модуля + hands-on практикум.

---

## Модули

| # | Модуль | Статус |
|---|--------|--------|
| 1 | [[01-anatomy-of-llm/01-anatomy-of-llm\|Анатомия LLM]] | ✅ |
| 2 | [[02-anatomy-of-a-prompt/02-anatomy-of-a-prompt\|Анатомия промпта]] | ✅ |
| 3 | [[03-chain-of-thought/03-chain-of-thought\|Chain-of-Thought]] | ✅ |
| 4 | [[04-react-agents/04-react-agents\|ReAct & Агенты]] | ✅ |
| 5 | [[05-rag-20/05-rag-20\|RAG 2.0]] | ✅ |
| 6 | [[06-mcp/06-mcp\|MCP — Model Context Protocol]] | ✅ |
| 7 | [[07-system-prompts-meta-prompting-guardrails/07-system-prompts-meta-prompting-guardrails\|System Prompts, Meta-Prompting & Guardrails]] | ✅ |
| 7b | [[07-system-prompts-meta-prompting-guardrails/07-ai-safety\|AI Safety & Alignment (beyond injection)]] | ✅ |
| 8 | [[08-evaluation-security-production/08-evaluation-security-production\|Evaluation, Security & Production]] | ✅ |
| 8b | [[08-evaluation-security-production/08-fine-tuning-pipeline\|Fine-tuning Pipeline (LoRA, RLHF, DPO)]] | ✅ |
| 8b+ | [[08-evaluation-security-production/08b-fine-tuning-hands-on\|Практикум: LoRA Fine-tuning своими руками]] | ✅ |
| 9 | [[09-architectural-patterns/09-architectural-patterns\|Архитектурные паттерны]] | ✅ |
| 14 | [[14-prompt-operations/14-prompt-operations\|Prompt Operations & Management]] | ✅ |

## Универсальные модули (любая сфера)

| # | Модуль | Статус |
|---|--------|--------|
| 10 | [[10-role-prompting/10-role-prompting\|Role Prompting — промпты для разных профессий]] | ✅ |
| 11 | [[11-text-work/11-text-work\|Работа с текстом — суммирование, извлечение, перевод]] | ✅ |
| 12 | [[12-creative-prompting/12-creative-prompting\|Креативные промпты — идеи, сторителлинг, контент]] | ✅ |
| 13 | [[13-analytics-research/13-analytics-research\|Аналитика и исследования — SWOT, PEST, фреймворки]] | ✅ |

## Advanced

| # | Модуль | Статус |
|---|--------|--------|
| 15 | [[15-evals-benchmarks/15-evals-benchmarks\|Evals & Benchmarks — как измерять качество]] | ✅ |

## Дополнительно

- [[wiki/architecture-roles-agents-skills\|Архитектура ролей: AGENTS.md vs Skills]]
- [[wiki/example-weather-mcp-server\|Пример MCP-сервера погоды]]

## Примеры промптов

- [[prompts/example-code-review-prompt\|Code Review — production-промт]] (M2, M7)
- [[prompts/example-rag-qa-prompt\|RAG Q&A — production-промт с цитированием]] (M5)
- [[prompts/example-swot-analysis-prompt\|SWOT-анализ — стратегический промт с JSON]] (M13)
- [[prompts/example-video-script-prompt\|Сценарий видео — креативный промт]] (M12)
- [[prompts/example-system-prompt-for-support\|System Prompt для поддержки]] (M7)
- [[prompts/meta-generated-travel-agent\|Travel Agent — meta-сгенерированный промт]]

## Эталонные решения

- [[prompts/practice-solutions\|Решение всех практик — M1–M15, M8b+]]

## Правила

- [[AGENTS.md\|Правила работы с курсом]]

## Смежные курсы

Для глубины по инженерной реализации:

- [[../../ai-agents/index\|ai-agents]] — реализация guardrails, evaluation, security (Python), мультиагентные системы, мультимодальные агенты (vision, audio, video)
- [[../../opencode-skills/index\|opencode-skills]] — глубокое изучение формата SKILL.md и экосистемы

> [!tip] Карта пересечений
> [[../../ai-agents/wiki/pe-course-map\|Карта курсов PE]] — что где покрыто, порядок изучения, что уникально в каждом курсе.

## Принцип обучения

Последовательно, модуль за модулем (1 → 15). Каждый модуль опирается на предыдущий. Модуль 14 (Prompt Operations) — после освоения core, перед M15. Модули 10-13 (универсальные) можно изучать после 1-2, даже без углубления в инженерные. Модули 7b, 8b, 15 — advanced, после освоения core.

> [!tip]
> Если термин непонятен — открой соответствующий модуль. Связи между модулями указаны в разделе «Ссылки» в конце каждого урока.
