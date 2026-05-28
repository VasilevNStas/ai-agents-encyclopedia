# Сравнение skill-экосистем: OpenCode, Claude Code, Cline, Gemini

**Время чтения:** 10 мин

## Суть

Skill-система — не монополия OpenCode. Каждая AI-агентная платформа реализует свой механизм кастомных инструкций. Понимание различий помогает выбирать платформу под задачу и портировать skills между средами.

## Основной материал

### OpenCode

**Механизм:** `~/.config/opencode/skills/` + `node_modules/` (Superpowers) + `.opencode/skills/`

**Принцип:**
- Progressive disclosure: метаданные (100 токенов) → полный SKILL.md (5K токенов) → ресурсы
- Порог 1%: skill загружается если совпадение description >= 1%
- AGENTS.md — проектные инструкции, выше skill по приоритету
- Источники: npm (Superpowers), локальные директории

**Сильные стороны:**
- Экономия контекста через progressive disclosure
- Гибкая иерархия: AGENTS.md > Skill > System Prompt
- npm-экосистема для дистрибуции

**Слабые стороны:**
- Меньше готовых skills, чем у Claude Code
- Superpowers — сторонний проект, не часть ядра

### Claude Code (Anthropic)

**Механизм:** `~/.claude/skills/` + `CLAUDE.md`

**Принцип:**
- Skills загружаются по match description (аналогично OpenCode)
- CLAUDE.md — проектные инструкции (аналог AGENTS.md)
- Anthropic поддерживает официальный реестр skills: `github.com/anthropics/skills`
- Установка: `npx skills add anthropics/claude-code --skill <name>`

**Сильные стороны:**
- Большая библиотека готовых skills от Anthropic
- `skill-creator` — официальный инструмент для тестирования
- Стабильный API

**Слабые стороны:**
- Нет progressive disclosure (весь SKILL.md загружается сразу)
- Нет системы пакетов (skills ставятся поштучно)
- Привязка к экосистеме Anthropic

### Cline (open-source)

**Механизм:** MCP-серверы + `.clinerules`

**Принцип:**
- Skills реализуются как MCP-серверы (запускаемый код, не markdown)
- `.clinerules` — аналог AGENTS.md для проекта
- Полная открытость: любой может написать MCP-сервер

**Сильные стороны:**
- Модельно-независимый (работает с любым LLM-провайдером)
- Полный контроль над реализацией (код, не промпт)
- Активное open-source сообщество

**Слабые стороны:**
- Выше порог входа (нужно писать код, не markdown)
- Нет стандартизированного формата SKILL.md
- Меньше готовых решений

### Gemini CLI (Google)

**Механизм:** `GEMINI.md` + `~/.gemini/skills/`

**Принцип:**
- GEMINI.md — проектные инструкции
- Skills — markdown-файлы с инструкциями
- Интеграция с Google AI Studio

**Сильные стороны:**
- Интеграция с экосистемой Google
- Простая модель (один файл = один skill)

**Слабые стороны:**
- Нет progressive disclosure
- Маленькая экосистема
- Ограниченная документация

### GitHub Copilot CLI

**Механизм:** Встроенные команды, нет кастомных skills

**Принцип:**
- Copilot CLI работает как набор предопределённых команд (`gh copilot suggest`, `gh copilot explain`)
- Нет механизма пользовательских skills
- Всё управляется через Copilot Chat API

**Сильные стороны:**
- Глубокая интеграция с GitHub (PRs, issues, actions)
- Нулевая конфигурация

**Слабые стороны:**
- Нет кастомных skills
- Нет AGENTS.md-эквивалента
- Закрытая экосистема

### Сравнительная таблица

| Характеристика | OpenCode | Claude Code | Cline | Gemini CLI | Copilot CLI |
|---------------|----------|-------------|-------|------------|-------------|
| Формат skills | SKILL.md | SKILL.md | MCP-сервер | .md файлы | Нет |
| Progressive disclosure | Да | Нет | Н/Д | Нет | Н/Д |
| Пакетный менеджер | npm | Поштучно | MCP | Нет | Нет |
| AGENTS.md-эквивалент | AGENTS.md | CLAUDE.md | .clinerules | GEMINI.md | Нет |
| Порог загрузки | 1% | match | явный вызов | match | Н/Д |
| Open Source | Нет | Нет | Да | Нет | Нет |
| Реестр skills | npm/Superpowers | anthropics/skills | MCP registry | Нет | Нет |

### Портирование skill между платформами

Большинство skills можно перенести между OpenCode и Claude Code с минимальными изменениями:

```
OpenCode SKILL.md → Claude Code SKILL.md
  Изменения:
    1. Убрать XML-теги (конвенция Superpowers)
    2. Адаптировать tool mapping
    3. Проверить description (разные модели ищут по-разному)

OpenCode SKILL.md → Cline MCP-сервер
  Изменения:
    1. Переписать на TypeScript/Python
    2. Реализовать как MCP-сервер с инструментами
    3. Опубликовать через MCP registry
```

## Упражнение

1. Выбери платформу, которой ещё не пользовался (Claude Code, Cline, или Gemini CLI)
2. Установи её и проверь, есть ли встроенный механизм skills
3. Напиши один и тот же skill для OpenCode и для выбранной платформы
4. Сравни: какой потребовал больше усилий? Где результат качественнее?

## Проверь себя

1. Какие две платформы используют наиболее близкий формат SKILL.md?
2. В чём преимущество OpenCode перед Claude Code с точки зрения экономии контекста?
3. Чем Cline отличается от OpenCode и Claude Code в реализации skills?
4. Сколько времени занимает портирование skill между OpenCode и Claude Code?
5. Какая платформа не поддерживает кастомные skills?

## Ключевые выводы

- OpenCode и Claude Code — самые близкие конкуренты с похожим форматом SKILL.md
- Cline идёт другим путём: skills = код, не маркдаун
- Gemini CLI и Copilot CLI не имеют полноценной skill-системы
- Портирование между OpenCode и Claude Code — 15 минут
- Выбор платформы = выбор между экономией контекста (OpenCode) и готовой библиотекой (Claude Code)

## Что дальше

→ [Структура SKILL.md](../02-anatomy/01-skill-file-structure.md)
