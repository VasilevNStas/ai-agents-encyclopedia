# AI Teacher Skills — Инструкции для агента

## Язык

- Все ответы, объяснения и комментарии — на русском
- Технические термины (API, endpoint, deployment, skill) оставляй на английском
- Если пользователь пишет на русском, НЕ переключайся на английский

## Проект

Это Obsidian-хранилище для глубокого изучения темы **Skills** в контексте AI-агентов. В корне доступен `skills/study-helper/SKILL.md` — используй его для генерации вопросов и проверки знаний.

## Структура

```
01-fundamentals/      → база: что такое Skill, отличия от prompt
02-anatomy/           → SKILL.md: метаданные, hard gates, checklists
03-mechanics/         → Skill Tool, порог 1%, lifecycle
04-superpowers/       → экосистема, пакеты, дистрибуция
05-writing/           → написание skills, best practices, tool mapping
06-advanced/          → композиция, цепочки, трюки
07-debugging/         → диагностика, причины, инструменты отладки
08-testing-security/  → тестирование, безопасность, sandboxing
09-performance/       → context window, token cost, кэширование
meta/                 → roadmap, glossary, reference, course-index
skills/               → рабочие skills
examples/             → примеры готовых skills (marp-slide)
index.md              → навигация
```

## Формат заметок

- Markdown, без лишнего форматирования
- Код примеров — в fenced блоках с указанием языка
- Схемы — текстовые (ascii диаграммы) в fenced блоках
- Никаких emoji

## Поведение

- При изучении нового модуля — сверяйся с `meta/roadmap.md`
- Если пользователь просит проверить знания — используй `skill("study-helper")`
- Отвечай коротко и по делу, если не сказано иначе
- Не добавляй пояснений к коду или схеме без запроса
- Всегда спрашивай перед commit/push
- Приоритет: AGENTS.md > Skills > system prompt

## Tool mapping для OpenCode

| Действие | Инструмент |
|----------|-----------|
| навык | `skill` |
| туду-лист | `todowrite` |
| подзадача | `task` |
| чтение/запись | `read`, `write`, `edit` |
