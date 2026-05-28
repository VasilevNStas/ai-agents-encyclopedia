# Структура SKILL.md

**Время чтения:** 10 мин

## Суть

`SKILL.md` — единственный обязательный файл в директории skill. Агент читает его целиком при активации и следует инструкциям. Файл состоит из YAML frontmatter (метаданные) и Markdown-тела (инструкции).

## Основной материал

### Полная структура

```
skill-name/
├── SKILL.md              # Основной файл (обязательно)
├── scripts/              # Исполняемый код (опционально)
├── references/           # Документация (опционально)
└── assets/               # Шаблоны, ресурсы (опционально)
```

### SKILL.md изнутри

```markdown
---
name: skill-name                           # YAML frontmatter
description: Use when [условия применения]
license: MIT                               # опционально
compatibility: Requires Python 3.14+       # опционально
metadata:
  author: username
  version: "1.0"
---

# Skill Name

## Overview

Коротко: что делает skill, ключевой принцип.

## Инструкции

Пошаговое руководство.

## When to Use

Когда применять, а когда — нет.

## Common Mistakes

Что идёт не так и как это чинить.
```

### Frontmatter (YAML)

Два обязательных поля и несколько опциональных:

| Поле | Обязательно | Описание |
|------|-------------|----------|
| `name` | Да | Макс 64 символа. lowercase, цифры, дефисы. Должен совпадать с именем директории |
| `description` | Да | Макс 1024 символа. Что делает skill и когда его использовать |
| `license` | Нет | Название лицензии |
| `compatibility` | Нет | Системные требования (макс 500 символов) |
| `metadata` | Нет | Произвольные ключ-значение (author, version) |
| `allowed-tools` | Нет | Экспериментально: разрешённые инструменты |

### Правила для `name`

- Только lowercase (`a-z`), цифры (`0-9`) и дефисы (`-`)
- Не может начинаться или заканчиваться дефисом
- Без двойных дефисов (`--`)
- Макс 64 символа
- **Обязательно совпадает с именем родительской директории**

```yaml
# ✅ Правильно
name: pdf-processing
name: data-analysis
name: code-review

# ❌ Неправильно
name: PDF-Processing  # заглавные
name: -pdf            # начинается с дефиса
name: pdf--processing # двойной дефис
```

### Правила для `description`

- Макс 1024 символа
- Описывает **что делает skill** и **когда его использовать**
- Должен содержать ключевые слова, по которым агент найдёт skill
- Начинается с "Use when..." для фокуса на условиях триггера
- **НЕ должен описывать внутренний процесс skill** (иначе агент может следовать description вместо чтения полного SKILL.md)

```yaml
# ✅ Правильно
description: >-
  Extract text and tables from PDF files, fill PDF forms, and merge
  multiple PDFs. Use when working with PDF documents or when the user
  mentions PDFs, forms, or document extraction.

# ❌ Слишком обще
description: Helps with PDFs.

# ❌ Суммирует workflow — агент может пропустить тело skill
description: >-
  Use when executing plans — dispatches subagent per task with code
  review between tasks.

# ✅ Только условия триггера
description: >-
  Use when executing implementation plans with independent tasks in
  the current session.
```

### Body: тело инструкций

После frontmatter идёт Markdown любого формата. Рекомендуемые секции:

- **Overview** — ключевой принцип в 1-2 предложениях
- **When to Use** — когда применять / не применять
- **Инструкции** — пошаговое руководство
- **Примеры** — ввод/вывод
- **Common Mistakes** — частые ошибки
- **Gotchas** — неочевидные подводные камни

Нет жёсткого формата. Пиши то, что поможет агенту выполнить задачу.

### Progressive disclosure

Skills загружаются поэтапно, чтобы экономить контекст:

1. **Метаданные** (~100 токенов): name + description читаются при старте для всех skills
2. **Инструкции** (< 5000 токенов): полный SKILL.md загружается только при активации
3. **Ресурсы**: файлы из scripts/, references/, assets/ загружаются по необходимости

Рекомендация: держать SKILL.md до 500 строк. Детальные референсы выносить в отдельные файлы.

### Опциональные директории

**scripts/** — исполняемый код (Python, Bash, JS):
```bash
scripts/extract.py
scripts/validate.sh
```

**references/** — дополнительная документация, подгружаемая по необходимости:
```
references/REFERENCE.md
references/api-errors.md
```

**assets/** — статические ресурсы:
```
assets/templates/report-template.docx
assets/schemas/data-model.json
```

### File references

Ссылки на файлы — относительные пути от корня skill:

```markdown
See [reference guide](references/REFERENCE.md) for details.

Run the extraction script:
scripts/extract.py
```

Держи вложенность не глубже одного уровня от SKILL.md.

### Пример: минимальный skill

```
roll-dice/
└── SKILL.md
```

```markdown
---
name: roll-dice
description: >-
  Roll dice using a random number generator. Use when asked to roll
  a die (d6, d20, etc.) or generate a random dice roll.
---

To roll a die, run one of these commands using <sides> from the user's
request:

```bash
echo $((RANDOM % <sides> + 1))
```

```powershell
Get-Random -Minimum 1 -Maximum (<sides> + 1)
```
```

### Пример: skill из Superpowers

```markdown
---
name: brainstorming
description: >-
  You MUST use this before any creative work - creating features,
  building components, adding functionality, or modifying behavior.
  Explores user intent, requirements and design before implementation.
---

## Checklist

1. Explore project context — check files, docs, recent commits
2. Ask clarifying questions — one at a time
3. Propose 2-3 approaches — with trade-offs and your recommendation
4. ...

## Процесс

Детальные инструкции по брейнштормингу.

## Key Principles

- One question at a time
- YAGNI ruthlessly
- Incremental validation
```

## Упражнение

Открой файл `node_modules/superpowers/skills/brainstorming/SKILL.md`. Разбери его по элементам: YAML frontmatter (name, description), секции, чеклисты, ссылки на соседние файлы. Запиши в одну строку — что делает этот skill?

## Проверь себя

1. Какие требования к полю `name` в YAML frontmatter?
2. Почему description не должен описывать внутренний процесс skill?
3. Что такое progressive disclosure и зачем он нужен?
4. Какие опциональные директории могут быть в skill и для чего они используются?
5. Какой максимальный размер SKILL.md рекомендуется?

## Ключевые выводы

- Skill — директория, обязательно содержащая `SKILL.md` с YAML frontmatter
- Frontmatter: `name` (обязательно, kebab-case, совпадает с именем папки) и `description` (обязательно, макс 1024 символа)
- Progressive disclosure: метаданные → инструкции → ресурсы
- Офпционально: `scripts/`, `references/`, `assets/`
- Body — свободный Markdown, рекомендуемые секции: Overview, When to Use, инструкции, примеры
- Description описывает условия триггера, НЕ workflow внутри skill

## Что дальше

→ [Spec и валидация skills](02-spec-and-validation.md)
