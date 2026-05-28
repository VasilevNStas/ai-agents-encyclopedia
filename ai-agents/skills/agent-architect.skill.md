---
name: agent-architect
description: Чеклист архитектора для проектирования систем агентов
author: ai-agents
version: 1.1.0
tags: [skill, architecture, agent, checklist]
depends_on: []
config:
  detail_level: full
  include_anti_patterns: true
---

# Skill: Agent Architect

## Когда использовать
- Проектирование нового агента
- Code review архитектуры агента
- Выбор паттерна для задачи

## Чеклист архитектора

### 1. Фундамент
- [ ] Какая модель будет ядром? (DeepSeek, Claude, GPT?)
- [ ] Какой размер контекста? (хватит ли для задачи?)
- [ ] Какой будет system prompt?
- [ ] Какие инструменты нужны?

### 2. Паттерн
- [ ] ReAct — для исследовательских задач (2-5 шагов)
- [ ] Plan-and-Solve — для сложных задач (10+ шагов)
- [ ] Reflexion — если ошибка дорого стоит

### 3. Память
- [ ] Short-term: сколько сообщений влезает в контекст?
- [ ] Working: где хранить план и промежуточные результаты?
- [ ] Long-term: что сохранять между сессиями?
- [ ] Есть ли механизм сжатия при переполнении контекста?

### 4. Безопасность
- [ ] Input guardrails — проверка запроса
- [ ] Output guardrails — проверка действий
- [ ] Data guardrails — ограничение доступа к файлам
- [ ] Prompt injection — защита от вредоносных данных

### 5. Observability
- [ ] Логируется каждый шаг (Thought → Action → Observation)?
- [ ] Считается стоимость каждой сессии?
- [ ] Есть ли детектор зацикливания?
- [ ] Есть ли summary в конце?

### 6. Resilience
- [ ] Retry with backoff — при ошибках API?
- [ ] Fallback model — если основная упала?
- [ ] Circuit breaker — при too many errors?
- [ ] Graceful degradation — мягкое падение?

## Антипаттерны

- ❌ Один агент на всё
- ❌ Все инструменты доступны всем
- ❌ Нет guardrails («LLM сама разберётся»)
- ❌ Бесконечная рефлексия (без MAX_TRIALS)
- ❌ Вся история в short-term (без сжатия)

## Конфигурация времени выполнения

```python
# Быстрая проверка (без антипаттернов)
skill("agent-architect", {
    "detail_level": "quick",     # только основные пункты
    "include_anti_patterns": false
})

# Полный аудит
skill("agent-architect", {
    "detail_level": "full",      # все разделы
    "include_anti_patterns": true
})
```
