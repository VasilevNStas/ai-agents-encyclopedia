---
created: 2026-05-09
tags: [skills, readme, index]
status: active
---

# Skills этого проекта

Этот проект использует кастомные **OpenCode skills** для специализированных задач.

## Как использовать

```python
# Загрузить skill с параметрами по умолчанию
skill("prompt-engineer")

# Загрузить skill с переопределением параметров
skill("agent-architect", {"detail_level": "quick"})
```

## Доступные skills

| Skill | Версия | Для чего | Зависимости |
|-------|--------|----------|-------------|
| [[skills/prompt-engineer.skill.md\|prompt-engineer]] | 1.1.0 | Создание и оптимизация промптов | — |
| [[skills/agent-architect.skill.md\|agent-architect]] | 1.1.0 | Чеклист архитектора агентов | — |
| [[skills/lesson-creator.skill.md\|lesson-creator]] | 1.1.0 | Шаблон для уроков курса | prompt-engineer |
| [[skills/wiki-maintainer.skill.md\|wiki-maintainer]] | 1.1.0 | Ведение LLM Wiki | — |

## Конфигурация

По умолчанию все параметры заданы в YAML frontmatter каждого skill.
Можно переопределить при загрузке (см. Config в каждом skill).

Общая конфигурация по умолчанию: `config.yaml`

## Правила

1. Один активный skill в момент времени
2. Если skill имеет `depends_on` — зависимости загружаются автоматически
3. Версионирование через semver в frontmatter
