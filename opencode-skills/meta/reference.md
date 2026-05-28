# Мастер-референс: Skills-инжиниринг

> **Назначение:** Фундаментальный справочник по созданию skills для работы с AI-агентами. Май 2026.

## 1. Что такое skill

**Skill** — директория с файлом `SKILL.md`, содержащим инструкции для AI-агента. Агент загружает skill по необходимости через механизм автотриггеринга (совпадение поля `description` с задачей пользователя).

### Ментальная модель

Skill = должностная инструкция для агента.

## 2. Структура SKILL.md

### YAML frontmatter (обязательно)

```yaml
---
name: skill-name
description: Use when [условия применения]
---
```

| Поле | Статус | Описание |
|------|--------|----------|
| `name` | Обязательно | lowercase, дефисы, макс 64 символа, совпадает с именем папки |
| `description` | Обязательно | макс 1024 символа, условия триггера, НЕ workflow |
| `license` | Опционально | Название лицензии |
| `compatibility` | Опционально | Системные требования |
| `metadata` | Опционально | author, version и т.д. |

### Body (свободный Markdown)

Рекомендуемые секции: Overview, When to Use, Инструкции, Примеры, Common Mistakes, Gotchas.

### Опциональные директории

- `scripts/` — исполняемый код (Python, Bash, JS)
- `references/` — дополнительная документация
- `assets/` — шаблоны, схемы, изображения

## 3. Progressive disclosure

1. Метаданные (~100 токенов) — при старте сессии
2. Инструкции (< 5000 токенов) — при активации skill
3. Ресурсы — по необходимости

## 4. Жизненный цикл

Discovery (метаданные) → Activation (SKILL.md) → Execution (инструкции)

## 5. Priority

AGENTS.md > Skills (по релевантности) > System Prompt

## 6. Composition & Chains

Skill chaining — один skill направляет агента к другому через инструкцию. Композиция (Skill Composition) позволяет собирать сложные workflow из простых skills.

- **Skill chaining** — последовательная активация: skill A завершает свою задачу и делегирует агенту использование skill B
- **SUBAGENT-STOP** — инструкция в SKILL.md, запрещающая subagent'ам загружать данный skill, предотвращая рекурсивную или нежелательную активацию
- **Dependency management** — контроль порядка и условий активации skills в цепочке; один skill может требовать предварительной загрузки другого

## 7. Testing & Evaluation

Три уровня тестирования skills:

- **Trigger testing** — проверка, что skill срабатывает на релевантные запросы (цель: 90%+ точность). Используются eval-запросы — набор тестовых промптов
- **Execution testing** — проверка корректности выполнения инструкций skill-а: агент следует шагам, результат соответствует ожидаемому
- **Baseline testing** — сравнение результатов с эталонным ответом (baseline); расхождение фиксируется как регрессия

Дополнительно: **Property-based Testing** — тестирование на случайных входных данных с проверкой инвариантов (свойств, которые должны сохраняться независимо от входных данных). Eval-driven подход означает, что разработка skill ведётся через итеративное улучшение результатов на eval-наборе.

## 8. Security & Sandboxing

- **Allowed-tools** — поле в SKILL.md (или внешняя конфигурация), ограничивающее набор инструментов, доступных skill-у (read, write, bash и т.д.)
- **Dangerous patterns** — инструкции, которые могут привести к нежелательным действиям: удаление файлов, выполнение произвольного кода, сетевые запросы без верификации. Рекомендуется выносить в `scripts/` с явной проверкой
- **Sandboxing** — изоляция выполнения skill в ограниченной среде: контейнер (Docker), subprocess с ограниченными правами, виртуальная файловая система. Снижает риск при загрузке skills из ненадёжных источников

## 9. CI/CD & Fleet Management

Управление парком skills (Fleet) в организации:

- **Validation pipeline** — автоматическая проверка SKILL.md при commit/PR: корректность YAML frontmatter, наличие обязательных полей (Hard Gates), валидность description, соответствие нейминга
- **Monitoring** — отслеживание метрик использования каждого skill: частота триггеринга, Trigger Quality, Token ROI, количество ошибок. Данные используются для retirement-решений
- **Retirement policies** — автоматическое удаление или архивация skills с низкой Trigger Quality, устаревшими инструкциями или нулевым использованием за период
- **Cross-platform portability** — адаптация skills под разные AI-агенты (OpenCode, Claude Code, Cursor) через Tool Mapping и совместимость формата SKILL.md

## 10. Performance

- **Context window impact** — каждый загруженный skill потребляет токены контекста (метаданные ~100 токенов, инструкции до 5000 токенов). При множественной загрузке может вытеснять другие данные из контекста
- **Token cost calculation** — оценка стоимости выполнения skill: `trigger_cost + execution_cost`. Trigger_cost — токены на хранение metadata всех skills в сессии; execution_cost — токены инструкций при активации
- **Caching strategies** — кэширование метаданных и инструкций после первой загрузки; Progressive disclosure минимизирует объём до момента активации
- **Skill Budgeting** — установка лимитов на суммарное потребление токенов skills в рамках одной сессии. Позволяет контролировать расходы и предотвращать исчерпание контекста

## 11. Ресурсы

- [Спецификация Agent Skills](https://agentskills.io/specification)
- [GitHub репозиторий](https://github.com/agentskills/agentskills)
- [Официальные skills от Anthropic](https://github.com/anthropics/skills)
- [Superpowers](https://github.com/obra/superpowers)
- [Best practices](https://agentskills.io/skill-creation/best-practices)
- [Оптимизация description](https://agentskills.io/skill-creation/optimizing-descriptions)
- [Оценка качества skills](https://agentskills.io/skill-creation/evaluating-skills)
- [Статья на русском: 15 скиллов для AI-агентов](https://thecode.media/agent-skills-dlya-ii-agentov/)
