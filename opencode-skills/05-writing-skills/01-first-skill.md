# Первый skill: от идеи до SKILL.md

**Время чтения:** 10 мин

## Суть

Skill — директория с файлом `SKILL.md`, содержащим YAML frontmatter и Markdown-инструкции. Процесс создания включает 6 шагов: от формулировки идеи до тестирования готового skill.

## Основной материал

### Процесс создания skill

1. **Сформулируй задачу** — какую проблему решает skill? Какую работу автоматизирует? Какие ошибки агент делает без этого skill?
2. **Выбери имя** — kebab-case, только lowercase и дефисы, совпадает с именем директории
3. **Напиши description** — что делает skill и когда его использовать. Это триггер для агента. Начинай с "Use when..."
4. **Напиши тело инструкций** — чёткие шаги, примеры, gotchas
5. **Сохрани в правильную директорию** — `skills/<skill-name>/SKILL.md`
6. **Протестируй** — вызови skill на реальной задаче, проверь триггеринг и выполнение

### Description как триггер

Описание — первое, что видит агент. От него зависит, загрузится ли skill.

Правила:
- Начинай с "Use when..." — это фокусирует на условиях триггера
- Будь конкретен: "Use when PDF text extraction fails or returns garbled output"
- Пиши от третьего лица (встраивается в system prompt)
- **НЕ описывай workflow внутри skill** — иначе агент будет следовать description вместо чтения полного SKILL.md

```yaml
# ✅ Правильно: только условия триггера
description: >-
  Use when implementing any feature or bugfix, before writing
  implementation code.

# ❌ Неправильно: описывает workflow
description: >-
  Use for TDD - write test first, watch it fail, write minimal
  code, refactor.
```

### Тело инструкций

Пиши как рецепт — конкретные шаги, никакой теории:

```markdown
When user provides unformatted JSON:
1. Parse the JSON input using available tools
2. Format with 2-space indentation
3. Output the formatted version in a code block
```

Рекомендуемые секции в теле:
- **Overview** — ключевой принцип в 1-2 предложениях
- **When to Use** — когда применять, а когда нет
- **Инструкции** — пошаговое руководство
- **Примеры** — конкретные примеры ввода/вывода
- **Common Mistakes** — что идёт не так и как чинить
- **Gotchas** — неочевидные подводные камни

### Пример готового skill

```markdown
---
name: json-formatter
description: >-
  Format JSON data with proper indentation. Use when user provides
  unformatted JSON or asks to format/beautify JSON.
---

When user provides unformatted JSON:
1. Parse the JSON input
2. Format with 2-space indentation
3. Output in a code block

## Common Mistakes

- Do NOT modify data structure or values
- Only whitespace formatting

## Example

Input: `{"a":1,"b":2}`

Output:
```json
{
  "a": 1,
  "b": 2
}
```
```

### Три подхода к созданию skill

**1. Написать вручную** — для простых skills, где ты точно знаешь инструкции.

**2. Извлечь из диалога** — выполни реальную задачу с агентом, фиксируй свои правки и коррекции, затем извлеки повторяющийся паттерн в skill. Это даёт skill, основанный на реальном опыте, а не на теории.

**3. Использовать skill-creator** — официальный skill от Anthropic, который задаёт вопросы и генерирует SKILL.md за 5 минут.

### Тестирование

Минимальный тест: открой новую сессию и дай задачу, которая должна триггернуть skill. Проверь:
- Skill загрузился? (агент следует инструкциям)
- Description сработал? (достаточно ключевых слов)
- Инструкции выполняются? (нет пропущенных шагов)

Для более тщательного тестирования — eval-запросы: 8-10 запросов, которые должны триггернуть skill, и 8-10, которые не должны.

## Упражнение

Напиши свой первый skill для "help commit formatter". Создай директорию `skills/commit-formatter/SKILL.md` с YAML frontmatter и инструкцией по форматированию commit message в conventional commits.

## Проверь себя

1. Перечислите 6 шагов процесса создания skill.
2. С какой фразы рекомендуется начинать description и почему?
3. Почему description не должен описывать workflow внутри skill?
4. Назовите три подхода к созданию skill.
5. Как минимально протестировать, что skill работает?

## Ключевые выводы

- Skill = директория + SKILL.md с YAML frontmatter
- Description — ключевой триггер: только условия применения, без описания workflow
- Тело — свободный Markdown с конкретными шагами и примерами
- Три подхода к созданию: вручную, из диалога, через skill-creator
- Тестирование обязательно: eval-запросы, триггеринг, выполнение

## Что дальше

→ [Best Practices](02-best-practices.md)
