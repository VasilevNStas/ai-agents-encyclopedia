# Prompt Engineering Course — Правила для агента

## 1. Структура курса

```
index.md               ← Навигация по модулям
01-anatomy-of-llm/                       ← Анатомия LLM
02-anatomy-of-a-prompt/                  ← Анатомия промпта
03-chain-of-thought/                     ← Chain-of-Thought
04-react-agents/                         ← ReAct & Агенты
05-rag-20/                               ← RAG 2.0
06-mcp/                                  ← MCP
07-system-prompts-meta-prompting-guardrails/ ← System Prompts & Guardrails
   07-ai-safety.md                        ← AI Safety & Alignment
08-evaluation-security-production/       ← Evaluation, Security & Production
   08-fine-tuning-pipeline.md             ← Fine-tuning (LoRA, RLHF, DPO)
09-architectural-patterns/               ← Архитектурные паттерны
10-role-prompting/                       ← Role Prompting (универсальный)
11-text-work/                            ← Работа с текстом (универсальный)
12-creative-prompting/                   ← Креативные промпты (универсальный)
13-analytics-research/                   ← Аналитика (универсальный)
15-evals-benchmarks/                     ← Evals & Benchmarks
wiki/                  ← 2 дополнительных файла
  architecture-roles-agents-skills         — архитектура ролей
  example-weather-mcp-server               — пример MCP-сервера
prompts/               ← 6 примеров production-промптов + эталонные решения
AGENTS.md              ← Этот файл
```

## 2. Как работать с курсом

- У каждого модуля есть: теория, примеры, практическое задание, вопросы для самопроверки
- Если пользователь просит проверить знания — задавай вопросы из раздела «Практика»
- Не давай готовый ответ сразу — веди диалогом
- Всегда ссылайся на модули через `[[WikiLinks]]`

## 3. Формат ответов

- На русском
- Структурированно, с примерами
- Технические термины (API, embedding, token, function calling) — на английском
- Код — в fenced блоках с указанием языка

## 4. Связь с глобальными правилами

Глобальный `~/.config/opencode/AGENTS.md` — мои принципы и стиль.
Vault-level `~/Documents/Obsidian/AGENTS.md` — структура всего хранилища.
Этот файл — правила работы с этим конкретным курсом.

Все три дополняют друг друга. При конфликте приоритет: этот файл > vault AGENTS.md > глобальный AGENTS.md.
