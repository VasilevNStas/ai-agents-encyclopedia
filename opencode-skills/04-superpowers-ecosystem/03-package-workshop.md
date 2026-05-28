# Практикум: работа с пакетом skills

**Время чтения:** 20 мин
**Тип:** практикум с реальными действиями

## Суть

Теория пакетов ничто без практики. В этом уроке ты установишь реальный пакет skills, разберёшь его внутреннее устройство, модифицируешь один skill и опубликуешь свою версию.

## Подготовка

Убедись, что установлены:
- Node.js (любая актуальная версия)
- npm
- OpenCode (или другой AI-агент, поддерживающий skills)

## Часть 1: Установка пакета

```bash
# Установка superpowers от Obra
npm install superpowers

# Проверка структуры
ls node_modules/superpowers/skills/
```

Ожидаемый результат: список из 50+ директорий skills.

## Часть 2: Анатомия пакета

Открой `node_modules/superpowers/package.json`:

```bash
cat node_modules/superpowers/package.json
```

Найди:
1. Поле `superpowers` — что указано в `skills`?
2. Поле `keywords` — есть ли `superpowers`?
3. Поле `version` — какая версия?

Открой любой skill, например `brainstorming`:

```bash
cat node_modules/superpowers/skills/brainstorming/SKILL.md
```

Запиши ответы на вопросы:
1. Какая структура frontmatter?
2. Есть ли секция Checklist?
3. Какие XML-теги используются (если есть)?
4. Есть ли ссылки на соседние файлы?

## Часть 3: Локальная модификация

Создай локальную копию skill для экспериментов:

```bash
mkdir -p .opencode/skills/my-brainstorming
cp node_modules/superpowers/skills/brainstorming/SKILL.md .opencode/skills/my-brainstorming/
```

Внеси изменения:
1. Переименуй skill: `name: my-brainstorming`
2. Сократи description до 2 предложений
3. Добавь секцию `## Common Mistakes` с 3 пунктами
4. Измени чеклист: добавь "Check existing solutions first"

Проверь, что агент видит новый skill:
```bash
# В сессии OpenCode спроси: "какие skills у тебя есть?"
# Или проверь через агента твоего CLI
```

## Часть 4: Создание собственного пакета

Создай минимальный пакет с двумя skills:

```bash
mkdir -p my-utils/skills/hello-world
mkdir -p my-utils/skills/date-helper
```

**package.json:**
```json
{
  "name": "@username/my-utils",
  "version": "1.0.0",
  "description": "My utility skills",
  "superpowers": {
    "skills": ["skills/*"]
  },
  "keywords": ["superpowers", "opencode", "utils"],
  "license": "MIT"
}
```

**skills/hello-world/SKILL.md:**
```markdown
---
name: hello-world
description: Use when the user asks for a hello world example
  or demonstration in any programming language.
---

# Hello World

Generate a "Hello, World!" program in the requested language.

Follow the language's idiomatic style and conventions.
Include a comment explaining what the code does.
```

**skills/date-helper/SKILL.md:**
```markdown
---
name: date-helper
description: Use when working with dates, date formatting,
  date arithmetic, or timezone conversions.
---

# Date Helper

Work with dates, times, and timezones.

## Instructions

1. Identify the date format the user needs
2. Use language-appropriate libraries (date-fns, moment, datetime)
3. Handle timezone conversions explicitly
4. Test with edge cases (leap years, DST boundaries)
```

Установи локально:
```bash
npm link
# или
npm install ./my-utils
```

## Часть 5: Публикация (опционально)

Если хочешь опубликовать пакет в npm registry:

```bash
cd my-utils
npm login
npm publish --access public
```

После публикации любой может установить:
```bash
npm install @username/my-utils
```

## Упражнение

1. Установи superpowers (npm install superpowers)
2. Выбери 3 skills из пакета, которые тебе непонятны
3. Разбери каждый: что делает, когда применяется, какие есть ошибки
4. Для одного из них напиши улучшенную версию в `.opencode/skills/`
5. Проверь, что агент использует твою версию, а не оригинал

## Проверь себя

1. Как переопределить skill из установленного пакета локальной версией?
2. Для чего используется `npm link` при разработке пакета skills?
3. Из каких минимальных файлов состоит публикуемый пакет skills?
4. Что произойдёт, если агент найдёт skill с одинаковым именем в локальной директории и в node_modules?
5. Какой командой можно установить пакет skills напрямую из git-репозитория?

## Ключевые выводы

- Пакет skills — обычный npm-пакет с полем `superpowers` в package.json
- Локальная модификация через `.opencode/skills/` переопределяет установленный пакет
- `npm link` — удобный способ тестировать пакет до публикации
- Минимальный пакет: package.json + skills/*/SKILL.md
- 3 files = полноценный публикуемый пакет skills

## Что дальше

→ [Пишем первый Skill](../05-writing-skills/01-first-skill.md)
