# Практикум: разбор реальных SKILL.md

**Время чтения:** 15 мин
**Тип:** практикум с заданиями

## Суть

Теория структуры SKILL.md — это полдела. Настоящее понимание приходит, когда разбираешь чужие skills: находишь ошибки, замечаешь паттерны, понимаешь, почему одни skills работают хорошо, а другие — игнорируются агентом.

## Основной материал

### Skill A: marp-slide (эталон)

Из `examples/marp-slide/SKILL.md`.

Разбор сильных сторон:

**Frontmatter:**
```yaml
name: marp-slide
description: Create professional Marp presentation slides with 7 beautiful
  themes (default, minimal, colorful, dark, gradient, tech, business).
  Use when users request slide creation, presentations, or Marp documents.
  Supports custom themes, image layouts, and "make it look good" requests
  with automatic quality improvements.
```

Что правильно:
- `name` — kebab-case, совпадает с директорией
- `description` — начинается с "Use when", перечисляет ключевые слова (slide, presentation, Marp)
- Есть указание на негативные кейсы ("make it look good" — частый запрос)

**Тело:**
- Чёткие секции: When to Use, Quick Start, Themes, Best Practices
- Ссылки на отдельные reference-файлы (theme-selection.md, marp-syntax.md)
- Примеры кода с пояснениями
- Decision tree для выбора темы

Что можно улучшить:
- Description слишком длинный (>300 символов, хотя лимит 1024)
- Нет секции Common Mistakes
- Нет чеклиста в YAML frontmatter

### Skill B: проблемный skill (с ошибками)

```markdown
---
name: Code-Review
description: Reviews code and finds bugs
metadata:
  version: 1.0
---

# Code Review

## Instructions

1. Read the code
2. Check for bugs
3. Suggest improvements
4. Write a review
```

**Найди ошибки самостоятельно, потом сверься со списком ниже.**

<details>
<summary>Список ошибок (нажми после самостоятельного разбора)</summary>

1. **name с заглавной буквы и дефисом** — должно быть `code-review` (lowercase kebab-case)
2. **description слишком короткий и не содержит условий триггера** — нет "Use when", нет ключевых слов, агент может не загрузить skill когда нужно
3. **Инструкции расплывчаты** — "Read the code" не говорит какой код, "Check for bugs" не описывает как
4. **Нет секции When to Use** — skill будет загружаться на любой запрос про код
5. **Нет Common Mistakes** — критично для code review
6. **Нет ссылок на инструменты** — не указано, какие инструменты (grep, read) агент должен использовать
7. **Отсутствует чеклист обязательных проверок**
</details>

### Skill C:典型的なsuperpowers skill (из npm)

Возьми любой установленный skill из `node_modules/superpowers/skills/`, например `brainstorming`.

Разбери его по схеме:

```
1. Frontmatter:
   - name:                  [запиши]
   - description:           [запиши первые 100 символов]
   - metadata:              [какие поля?]

2. Секции:
   - Какие секции есть?     [перечисли]
   - Какая секция самая длинная?
   - Есть ли Checklist?

3. Ошибки (если есть):
   - Description описывает процесс а не триггер?
   - Нет ссылок на инструменты?
   - Инструкции слишком общие?
```

## Практическое задание

### Задание 1: Аудит marp-slide

Открой `examples/marp-slide/SKILL.md` и `examples/marp-slide/references/`. Ответь:

1. Какие reference-файлы подгружаются?
2. Есть ли дублирование между SKILL.md и references?
3. Что произойдёт, если агент не прочитает references?

### Задание 2: Рефакторинг проблемного skill

Возьми Skill B из этого урока и перепиши его правильно. Требования:
- name: `code-review` (kebab-case)
- description: Use when ... (минимум 50 символов, с ключевыми словами)
- Добавить секцию When to Use
- Добавить чеклист проверок (безопасность, стиль, производительность)
- Добавить Common Mistakes

### Задание 3: Сравнение двух description

Даны два description для одного skill:

```yaml
# Вариант A
description: Use when you need to analyze CSV data, find patterns,
  generate statistics, or create visualizations from tabular data.

# Вариант B
description: Analyzes CSV files, computes statistics, creates charts,
  and exports reports in various formats.
```

Какой лучше и почему?

<details>
<summary>Ответ</summary>

Вариант A лучше, потому что:
- Начинается с "Use when" — фокус на условии триггера
- Описывает когда применять, а не что делает
- Содержит ключевые слова (CSV, patterns, statistics, visualizations)

Вариант B описывает внутренний процесс — агент может попытаться выполнить
skill по description, не загружая SKILL.md целиком.
</details>

## Проверь себя

1. Какие три сильные стороны есть у skill `marp-slide` в его frontmatter?
2. Перечислите минимум три ошибки в проблемном Skill B из урока.
3. Почему вариант A description ("Use when you need to analyze CSV data...") лучше варианта B?
4. Что произойдёт, если агент не прочитает reference-файлы при выполнении skill?
5. Почему чеклист в frontmatter важен для дисциплинарных skills?

## Ключевые выводы

- Имя skill — всегда kebab-case, совпадает с именем директории
- Description — это условия триггера, а не описание процесса
- Хороший skill имеет When to Use, инструкции, Common Mistakes
- Reference-файлы — способ не раздувать SKILL.md
- Чеклист в frontmatter обязателен для дисциплинарных skills
- Аудит чужих skills — лучший способ научиться писать свои

## Что дальше

→ [Skill Tool под капотом](../03-mechanics/01-skill-tool.md)
