# Tool Mapping для Разных CLI

**Время чтения:** 5 мин

## Суть

Skills пишутся для экосистемы Superpowers, но исполняются в разных CLI. Не все инструменты называются одинаково. Чтобы skill работал везде, нужен маппинг инструментов.

## Основной материал

### OpenCode

| Superpowers / Claude Code | OpenCode tool |
|---|---|
| `TodoWrite` | `todowrite` |
| `Task` (subagent) | `task` |
| `Skill` | `skill` |
| `Read`, `Write`, `Edit` | native tools |
| `Bash` | `bash` |
| `Grep`, `Glob` | native search tools |

### Claude Code

Использует оригинальные имена из Superpowers.

### Gemini CLI

Использует `activate_skill`. GEMINI.md содержит полный маппинг.

### GitHub Copilot CLI

| Skill name | Copilot CLI tool |
|---|---|
| `TodoWrite` | `todowrite` |
| `Task` | `gh copilot` с подзадачами |
| `Skill` | встроенный `skill` |

### Правило

Если skill пишется для экосистемы — используй имена Superpowers. Каждый CLI сам маппит их на свои. Если адаптируешь для конкретной платформы — используй её native-имена.

### Где живут skills в разных CLI

| Платформа | Путь для проектных skills | Путь для глобальных |
|-----------|--------------------------|-------------------|
| Claude Code | `.claude/skills/` | `~/.claude/skills/` |
| OpenCode | `.opencode/skills/` | `~/.cache/opencode/packages/` |
| Gemini CLI | `.gemini/skills/` | `~/.gemini/skills/` |
| GitHub Copilot | `.agents/skills/` | `~/.agents/skills/` |
| Cursor | `.cursor/skills/` | `~/.cursor/skills/` |

## Упражнение

Возьми любой skill из superpowers, в котором используются `TodoWrite`, `Task`, `Skill` (например, `writing-plans`). Найди эти вызовы и перепиши для OpenCode.

Пример:
```markdown
<!-- Было -->
Use TodoWrite to create checklist items

<!-- Стало для OpenCode -->
Use todowrite to create checklist items
```

## Проверь себя

1. Как называется инструмент для создания подзадач (subagent) в OpenCode? А в Claude Code?
2. Какое правило следует соблюдать при написании skill для экосистемы Superpowers?
3. Где хранятся глобальные skills в Claude Code и OpenCode?
4. Какой универсальный путь поддерживается несколькими платформами?
5. Что нужно изменить в skill при адаптации с Claude Code на OpenCode?

## Ключевые выводы

- Разные платформы → разные имена инструментов, но концепция единая
- Если skill пишется для Superpowers — используй оригинальные имена
- Если адаптируешь для конкретной платформы — замени имена согласно таблице
- Пути хранения skills различаются, но структура (директория + SKILL.md) одинакова
