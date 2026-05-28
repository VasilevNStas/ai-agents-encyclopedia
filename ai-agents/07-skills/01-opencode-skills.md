---
created: 2026-05-09
tags: [course/skills, opencode, ecosystem]
status: active
---

# Урок 25: OpenCode Skills — экосистема расширений

> [!quote] Ключевая идея
> Skills — это предзагруженные инструкции для специализированных задач. Они превращают OpenCode из универсального помощника в эксперта по конкретной задаче — без смены модели и без переписывания system prompt.

**Полный курс по Skills** — [[../../../opencode-skills/index|opencode-skills]] (9 модулей, 23 урока). Здесь — только базовое введение и карта к полному курсу.

---

## Что такое Skill

Skill — это директория с файлом `SKILL.md` (YAML frontmatter + Markdown-инструкции). Загружается по запросу через `skill("name")` и добавляет в контекст специализированные инструкции.

```
Без skill: LLM делает задачу «как умеет» — каждый раз по-разному
С skill:   LLM следует чеклисту → результат предсказуем
```

Детально: [[../../../opencode-skills/01-fundamentals/01-what-is-a-skill]]

---

## Skills vs System Prompt

| Критерий | System prompt | Skill |
|----------|--------------|-------|
| Загружается | Всегда | По запросу |
| Размер | < 2000 токенов | Может быть любым |
| Специализация | Общая | Узкая задача |
| Количество | Один | Много |

Skill — временное дополнение к system prompt, не перезаписывает его.

Детально: [[../../../opencode-skills/01-fundamentals/02-skill-vs-prompt]]

---

## Структура SKILL.md

```markdown
---
name: my-skill
description: Краткое описание для триггера
tags: [skill, category]
---

# Skill: My Skill

## Когда использовать
<условия, при которых агент загружает skill>

## Процесс
<пошаговая инструкция>

## Чеклист
- [ ] пункт 1
- [ ] пункт 2
```

Детально: [[../../../opencode-skills/02-anatomy/01-skill-file-structure]], [[../../../opencode-skills/05-writing-skills/01-first-skill]]

---

## Жизненный цикл

```
1. Discovery — OpenCode сканирует .skill.md файлы при старте
2. Activation — пользователь пишет skill("name") или агент совпадает по description
3. Execution — инструкции добавляются в контекст, агент следует им
4. Completion — skill «выгружается», контекст очищается
```

Детально: [[../../../opencode-skills/03-mechanics/03-lifecycle]], [[../../../opencode-skills/03-mechanics/02-one-percent-rule]]

---

## Резюме

```
Skills = специализированные инструкции (загружаются по запросу)

System prompt = конституция (всегда активна)
Skill = временный контракт (на одну задачу)

Полный разбор: opencode-skills (9 модулей, 23 урока)
├── 01-fundamentals  — что такое skill
├── 02-anatomy       — структура SKILL.md, спецификация
├── 03-mechanics     — Skill Tool, lifecycle, 1% rule
├── 04-superpowers   — экосистема, пакеты
├── 05-writing       — создание, best practices
├── 06-advanced      — композиция, цепочки
├── 07-debugging     — диагностика загрузки
├── 08-testing       — тестирование, безопасность
└── 09-performance   — контекст, кэширование
```

---

## Практическое задание

1. Найди в проекте все `.skill.md` файлы (команда `ls skills/`). Прочитай один из них, разбери его структуру: YAML frontmatter, секции «Когда использовать» и «Процесс».

2. Загрузи skill `prompt-engineer` через `skill("prompt-engineer")` и попроси агента применить его к твоему текущему промпту. Посмотри, как изменилось поведение.

---

## Ссылки

- Дальше: [[07-skills/03-mcp-integration]]
- Назад: [[06-prompt-engineering/03-structured-output]]
- Полный курс: [[../../../opencode-skills/index|opencode-skills]]
