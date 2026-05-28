# Спецификация и валидация skills

**Время чтения:** 7 мин

## Суть

Skills — открытый формат, поддерживаемый Anthropic и сообществом. Спецификация доступна на [agentskills.io/specification](https://agentskills.io/specification). Для валидации используется эталонная библиотека `skills-ref`.

## Основной материал

### Официальная спецификация

Формат Agent Skills определён в открытом репозитории [github.com/agentskills/agentskills](https://github.com/agentskills/agentskills) (18k+ звёзд, Apache 2.0).

Ключевые требования:

1. Skill — это **директория**, содержащая `SKILL.md`
2. `SKILL.md` — YAML frontmatter + Markdown body
3. `name` обязателен, совпадает с именем директории
4. `description` обязателен, до 1024 символов
5. Тело инструкций — свободный Markdown
6. Опциональные директории: `scripts/`, `references/`, `assets/`

Спецификация не определяет XML-теги, секции `## Checklist` или другие внутренние конструкции — это соглашения экосистемы, а не требования формата.

### Хранилище skills

Skills могут лежать в разных местах в зависимости от CLI:

| Платформа | Путь для проектных skills | Путь для глобальных |
|-----------|--------------------------|-------------------|
| Claude Code | `.claude/skills/` | `~/.claude/skills/` |
| OpenCode | `.opencode/skills/` | `~/.cache/opencode/packages/` |
| Gemini CLI | `.gemini/skills/` | `~/.gemini/skills/` |
| GitHub Copilot | `.agents/skills/` | `~/.agents/skills/` |
| Cursor | `.cursor/skills/` | `~/.cursor/skills/` |

Универсальный путь `.agents/skills/` поддерживается несколькими платформами.

### Валидация skills

Для проверки корректности skill используется `skills-ref`:

```bash
# Установка
npm install -g @agentskills/skills-ref

# Валидация
skills-ref validate ./my-skill
```

Проверяет:
- Frontmatter: name, description, лимиты символов
- Имя: lowercase, дефисы, без спецсимволов
- Директория: имя совпадает с name
- Размер description не превышает 1024 символов

### XML-теги в SKILL.md

В официальной спецификации нет XML-тегов. Однако в реальных skills из Superpowers встречаются:

- `<HARD-GATE>` — неформальный тег для абсолютного запрета. Используется в `brainstorming`, `writing-plans`. Агент считывает его как часть Markdown.
- `<CRITICAL_INSTRUCTION>` — неформальный тег для указаний высокой важности.
- `<SUBAGENT-STOP>` — запрещает subagent'ам загружать этот skill. Используется в `using-superpowers`.
- `<EXTREMELY-IMPORTANT>` — аналогично.

Это соглашения конкретного пакета (Superpowers), а не часть спецификации Agent Skills. При написании skills с нуля можешь их использовать, но они не обязательны и не гарантируют особого поведения.

### Отличия реального формата от распространённых заблуждений

| Что говорят в интернете | Реальность |
|--------------------------|-----------|
| Метаданные в XML-тегах `<name>` | Только YAML frontmatter |
| `<HARD-GATE>` — часть спецификации | Неформальная конвенция Superpowers |
| `<CRITICAL_INSTRUCTION>` — часть спецификации | Неформальная конвенция |
| `## Checklist` гарантирует todo | Нет в спецификации, но многие агенты превращают `- [ ]` в todo |
| Skill — это один файл | Skill — директория с SKILL.md внутри |
| Название файла `*.skill.md` | Только `SKILL.md`, только так |

### Пример валидации

```
my-skill/
├── SKILL.md
```

Проверка:

```yaml
# ✅ Пройдёт валидацию
name: my-skill
description: Use when doing X — processes Y with Z constraints
```

```yaml
# ❌ Не пройдёт валидацию
name: My Skill       # заглавные, пробел
description: Helps   # слишком короткое, нет контекста
```

## Кейс / пример

Ситуация: ты написал skill, но OpenCode его не видит.

**Диагностика:**
1. Проверь имя директории: `ls -d skills/my-skill/`
2. Проверь файл: `ls skills/my-skill/SKILL.md`
3. Проверь frontmatter: YAML валиден? name совпадает с именем папки?
4. Запусти `skills-ref validate skills/my-skill/`

**Типовые ошибки:**
- Папка называется `my-skill`, а name — `my_skill` (подчёркивание вместо дефиса)
- Description длиннее 1024 символов
- Нет пустой строки после `---` (YAML не распарсился)

## Упражнение

Напиши валидный SKILL.md для минимального skill и проверь его `skills-ref validate`.

## Проверь себя

1. Какие требования к skill предъявляет официальная спецификация Agent Skills?
2. Какой инструмент используется для валидации skill?
3. Являются ли XML-теги (`<HARD-GATE>`, `<CRITICAL_INSTRUCTION>`) частью официальной спецификации?
4. Какая самая частая ошибка, из-за которой OpenCode не видит skill?
5. Какие поля проверяет `skills-ref validate`?

## Ключевые выводы

- Формат определён спецификацией на [agentskills.io](https://agentskills.io/specification)
- Основные требования: директория + SKILL.md с YAML frontmatter
- XML-теги (HARD-GATE, CRITICAL_INSTRUCTION) — конвенции Superpowers, не часть спецификации
- Для валидации используется `skills-ref validate`
- Имя директории обязательно совпадает с `name` в frontmatter

## Что дальше

→ [Skill Tool под капотом](../03-mechanics/01-skill-tool.md)
