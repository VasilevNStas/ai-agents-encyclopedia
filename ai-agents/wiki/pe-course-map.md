---
created: 2026-05-28
tags: [course/map, prompt-engineering, cross-reference, nav]
status: active
---

# Prompt Engineering: карта курсов

> [!abstract]
> В vault есть два курса, связанных с PE: **ai-agents** (модуль 6, 4 урока) и **prompt-engineering** (16 модулей, ~18 уроков). Они пересекаются, но не идентичны. Эта карта показывает, что где покрыто, что уникально, и в каком порядке проходить.

---

## 1. Сводная карта покрытия

| Тема | ai-agents M6 | PE-курс | Детали |
|------|:-----------:|:-------:|--------|
| Анатомия LLM (токены, attention, sampling) | ❌ | M1 | Только в PE |
| Анатомия промпта (8 элементов) | ❌ | M2 | Только в PE |
| **System Prompt для агента** | ✅ Урок 21 | M7 | **ai-agents:** конституция, role, rules, guardrails для агента
**PE:** общая теория + meta-prompting |
| **Chain-of-Thought** | ✅ Урок 22 | M3 | **ai-agents:** CoT для ReAct-цикла агента
**PE:** глубокая теория CoT, вариации, когда использовать |
| **Few-shot** | ✅ Урок 22 | M2 (частично) | **ai-agents:** примеры для function calling
**PE:** общая теория few-shot |
| **Structured Output / Function Calling** | ✅ Урок 23 | ❌ | **Уникально для ai-agents** — JSON mode, tool definitions, function calling для агентов |
| **Prompt Caching** | ✅ Урок 24 | ❌ | **Уникально для ai-agents** — кэширование в контексте агентного цикла |
| ReAct & Агенты | ❌ (база в M1) | M4 | PE: глубокий разбор ReAct как паттерна промптинга |
| RAG 2.0 | ❌ (M3 курс) | M5 | Оба курса покрывают, но с разных сторон |
| MCP — Model Context Protocol | ❌ (M7 курс) | M6 | PE: концептуально; ai-agents: инженерно |
| Guardrails | ❌ (M5 курс) | M7 | PE: теория; ai-agents: реализация |
| AI Safety & Alignment | ❌ | M7b | Только в PE |
| Evaluation & Security | ❌ (M5, M11) | M8 | PE: для промптов; ai-agents: для агентов |
| Fine-tuning (LoRA, RLHF, DPO) | ❌ | M8b | Только в PE |
| Архитектурные паттерны | ❌ (M4, M8) | M9 | PE: паттерны промптинга; ai-agents: архитектура агентов |
| Role Prompting (по профессиям) | ❌ | M10 | Только в PE |
| Работа с текстом | ❌ | M11 | Только в PE |
| Креативные промпты | ❌ | M12 | Только в PE |
| Аналитика и исследования | ❌ | M13 | Только в PE |
| Evals & Benchmarks | ❌ | M15 | Только в PE |

---

## 2. Визуальная карта

```
                         PE-курс (16 модулей)
┌──────────────────────────────────────────────────────────┐
│  Фундамент:                                              │
│  M1  Анатомия LLM                    ◄── база для всего  │
│  M2  Анатомия промпта                                     │
│  M3  Chain-of-Thought ─────────────┐                     │
│  M4  ReAct & Агенты ──────────────┤                     │
│  M5  RAG 2.0                       │                     │
│  M6  MCP                           │                     │
│  M7  System Prompts & Guardrails ──┼──┐                  │
│  M7b AI Safety                     │  │                  │
│  M8  Evaluation & Production ──────┤  │                  │
│  M8b Fine-tuning                   │  │                  │
│  M9  Архитектурные паттерны        │  │                  │
│  M10-M13 Универсальные модули      │  │                  │
│  M15 Evals & Benchmarks            │  │                  │
└────────────────────────────────────┼──┼──────────────────┘
                                     │  │
             ПЕРЕСЕЧЕНИЕ              │  │
                                     │  │
         ai-agents М6 (4 урока)       │  │
┌────────────────────────────────────┼──┼──────────────────┐
│  Урок 21 System Prompt ────────────┘  │  агент-специфика │
│  Урок 22 Few-shot + CoT ─────────────┘                  │
│  Урок 23 Structured Output / FC    ◄── УНИКАЛЬНО         │
│  Урок 24 Prompt Caching            ◄── УНИКАЛЬНО         │
└──────────────────────────────────────────────────────────┘
```

---

## 3. Рекомендуемый порядок изучения

### Путь A: Вы здесь ради AI-агентов (рекомендуемый)

```
Шаг 1: ai-agents M1 (фундамент LLM)
         └── если надо глубже → PE M1
Шаг 2: ai-agents M2 (агентные паттерны)
Шаг 3: ai-agents M6 (PE для агентов)
         └── когда встретился термин "CoT" или "system prompt"
              └── открой PE M3 (CoT) или PE M7 (System Prompts) для глубины
         └── structured output и caching — только в M6, PE не нужен
Шаг 4: ai-agents M3-M5 (RAG, мультиагент, production)
         └── параллельно: PE M5 (RAG), PE M8 (eval)
Шаг 5: ai-agents M7-M13
         └── по мере необходимости: PE универсальные модули (M10-M13)
```

### Путь B: Вы хотите full stack PE + агенты

```
1. PE M1 (анатомия LLM)
2. PE M2 (анатомия промпта)
3. PE M3 (CoT)
4. ai-agents M1 (фундамент + ReAct)
5. ai-agents M6 (PE для агентов: system prompt, function calling, caching)
6. PE M4 (ReAct & Агенты) — теперь будет глубже
7. PE M5 (RAG) → ai-agents M3 (RAG + память)
8. PE M6 (MCP) → ai-agents M7 (Skills + MCP)
9. PE M7 (System Prompts, Guardrails) → ai-agents M5 (guardrails)
10. PE M8 (Evaluation) → ai-agents M5 (testing), M12 (eval)
11. ai-agents M8-M13 (decision architecture, security, lifecycle)
12. PE M9-M15 (архитектурные паттерны, универсальные, evals)
```

### Путь C: Только промпты, без инженерной реализации

```
PE M1 → M2 → M3 → M7 → M10-M13 → M15
(ai-agents не нужен)
```

---

## 4. Что выбрать в зависимости от цели

| Ваша цель | Какой курс | Зачем второй |
|-----------|-----------|--------------|
| Писать хорошие промпты | **PE-курс** | ai-agents не нужен |
| Построить AI-агента | **ai-agents** | PE — справочник по терминам |
| Промпты для агентов | **ai-agents M6** | PE — для углубления |
| Функции вызова (FC) | **ai-agents Урок 23** | Уникально |
| Prompt caching | **ai-agents Урок 24** | Уникально |
| Guardrails | **ai-agents M5** + **PE M7** | Дополняют друг друга |
| RAG | **ai-agents M3** + **PE M5** | PE — теория, ai-agents — код |
| Оценка качества | **PE M15** + **ai-agents M12** | PE — методология, ai-agents — реализация |
| Экономия на LLM | **ai-agents Урок 30** | Не PE |

---

## 5. Что уникально в каждом курсе

### Только в ai-agents M6 (нет в PE)
- Structured Output / JSON mode / Function Calling для инструментов агента
- Prompt Caching в контексте agent loop
- System prompt для агента с акцентом на tool use и guardrails
- Всё с инженерной реализацией на Python

### Только в PE-курсе (нет в ai-agents M6)
- Анатомия LLM (токены, attention, sampling) — фундамент
- Анатомия промпта (8 элементов, матрица критичности)
- MCP — Model Context Protocol (концептуально)
- AI Safety & Alignment
- Fine-tuning Pipeline (LoRA, RLHF, DPO)
- Role Prompting (10+ профессий)
- Работа с текстом (суммирование, извлечение, перевод)
- Креативные промпты (сторителлинг, контент)
- Аналитика (SWOT, PEST, фреймворки)
- Evals & Benchmarks (методология)

---

## Ссылки

- [[../../../ai-agents/06-prompt-engineering/01-system-prompts|ai-agents M6: System Prompt]]
- [[../../../prompt-engineering/index|PE-курс: главная]]
- [[../../../ai-agents/index|ai-agents: главная]]
