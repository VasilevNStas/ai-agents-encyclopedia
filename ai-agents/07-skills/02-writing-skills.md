---
created: 2026-05-09
tags: [course/skills, writing-skills, custom-skills]
status: active
---

# Урок 26: Написание собственных Skills

> [!quote] Ключевая идея
> Если нужного skill нет в OpenCode Superpowers — напиши свой. Skill — это markdown-файл с инструкциями. Ты можешь создать skill для любой повторяющейся задачи.

**Этот урок — краткое введение.** Полное руководство по написанию skills: [[../../../opencode-skills/05-writing-skills/01-first-skill]], [[../../../opencode-skills/05-writing-skills/02-best-practices]].

---

## Структура

```markdown
---
name: my-skill
description: Краткое описание для триггера
tags: [skill, category]
---

# Skill: My Skill

## Когда использовать
<условия для триггера>

## Процесс
<пошаговая инструкция>

## Чеклист
- [ ] пункт 1
```

Детально: [[../../../opencode-skills/02-anatomy/01-skill-file-structure]], спецификация: [agentskills.io](https://agentskills.io/specification)

---

## Правила

1. **Один skill — одна задача**
2. **Чеклист важнее прозы** — LLM лучше следует пунктам
3. **YAML frontmatter обязателен** — name и description для поиска
4. **Будь конкретным** — не «проверь уязвимости», а «проверь SQL injection, XSS, hardcoded secrets»
5. **Gotchas-секция** — неочевидные подводные камни (самое ценное)

Детально: [[../../../opencode-skills/05-writing-skills/02-best-practices]]

---

## Skills этого курса

```bash
ls skills/
# prompt-engineer.skill.md
# agent-architect.skill.md
# lesson-creator.skill.md
# wiki-maintainer.skill.md
```

Пример реального skill (Code Reviewer): [[../../../opencode-skills/examples/marp-slide/SKILL]]

---

## Практическое задание

1. Создай свой первый skill-файл для задачи, которую ты делаешь чаще всего (например, code review, написание тестов, рефакторинг). Используй шаблон из урока: YAML frontmatter + «Когда использовать» + «Процесс» + «Чеклист».

2. Сохрани файл как `skills/my-first-skill.skill.md`, загрузи его через `skill("my-first-skill")` и проверь, что агент следует чеклисту.

---

## Ссылки

- Назад: [[07-skills/01-opencode-skills]]
- Дальше: [[07-skills/03-mcp-integration]]
- Полный курс: [[../../../opencode-skills/index|opencode-skills]]
