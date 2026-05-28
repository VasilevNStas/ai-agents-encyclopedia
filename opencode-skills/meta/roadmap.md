# Roadmap

## 01 — Fundamentals · 3 урока
[Что такое Skill](../01-fundamentals/01-what-is-a-skill.md). Определение, директория + SKILL.md, progressive disclosure, три категории skills.
[Skill vs prompt vs AGENTS.md](../01-fundamentals/02-skill-vs-prompt.md). Иерархия приоритетов: AGENTS.md > Skill > System Prompt.
[Сравнение экосистем](../01-fundamentals/03-ecosystem-comparison.md). OpenCode vs Claude Code vs Cline vs Gemini vs Copilot CLI.

## 02 — Anatomy of SKILL.md · 3 урока
[Спецификация формата](../02-anatomy/01-skill-file-structure.md). YAML frontmatter: name, description, опциональные поля. Правила именования. Progressive disclosure.
[Spec и валидация](../02-anatomy/02-spec-and-validation.md). Официальная спецификация agentskills.io. XML-теги (конвенции Superpowers, не часть spec). Валидация через skills-ref.
[Практикум: разбор реальных SKILL.md](../02-anatomy/03-real-world-analysis.md). Аудит marp-slide, поиск ошибок, рефакторинг.

## 03 — Mechanics & Tooling
[Skill Tool под капотом](../03-mechanics/01-skill-tool.md). Progressive disclosure на практике, вызов в разных CLI, автотриггеринг.
[Порог 1%](../03-mechanics/02-one-percent-rule.md). Правило, обоснование, red flags, eval-запросы.
[Жизненный цикл skill](../03-mechanics/03-lifecycle.md). Discovery → Activation → Execution.

## 04 — Superpowers Ecosystem · 3 урока
[Что такое Superpowers](../04-superpowers-ecosystem/01-what-is-superpowers.md). npm-экосистема, установка, структура пакета.
[Пакеты и дистрибуция](../04-superpowers-ecosystem/02-packages-and-distribution.md). Публикация, semver, changelog, альтернативы npm.
[Практикум: работа с пакетом](../04-superpowers-ecosystem/03-package-workshop.md). Установка, разбор структуры, модификация, публикация.

## 05 — Writing Skills
[Пишем первый Skill](../05-writing-skills/01-first-skill.md). 6 шагов: идея → имя → description → инструкции → сохранение → тестирование.
[Best Practices](../05-writing-skills/02-best-practices.md). Gotchas, templates, validation loops, DO/DON'T, антипаттерны.
[Tool Mapping](../05-writing-skills/03-tool-mapping.md). Адаптация под разные CLI.

## 06 — Advanced
[Композиция skills](../06-advanced/01-composition.md). Skill chaining, артефакты, conditional branching.
[Цепочки и приоритизация](../06-advanced/02-chains-and-priority.md). Релевантность, конфликты, алфавитный порядок.
[Подводные камни](../06-advanced/03-pitfalls-and-tricks.md). 5 проблем, 4 трюка, диагностика.

## 07 — Debugging
Диагностика проблем с skills.
[Почему skill не загружается](../07-debugging/01-why-skill-not-loaded.md). [Skill игнорирует инструкции](../07-debugging/02-skill-ignores-instructions.md). [Инструменты отладки](../07-debugging/03-debugging-tools.md).

## 08 — Testing & Security · 4 урока
[Тестирование skills](../08-testing-security/01-testing-skills.md). [Безопасность](../08-testing-security/02-security.md). [Sandboxing](../08-testing-security/03-sandboxing.md).
[Property-based testing](../08-testing-security/04-property-based-testing.md). Стабильность триггеринга, устойчивость к шуму, негативные тесты.

## 09 — Performance · 3 урока
[Влияние skills на context window](../09-performance/01-context-window-impact.md). Токен-кост, оптимизация.

## 10 — Fleet Management & Production · 4 урока
[CI/CD pipeline для skills](../10-fleet-management/01-ci-cd.md). Валидация, тест триггеринга, интеграция в репозиторий.
[Мониторинг skills в production](../10-fleet-management/02-monitoring.md). Логи, метрики, дашборды, алерты.
[Управление парком skills](../10-fleet-management/03-fleet-management.md). Версионирование, code review, retirement.
[Кросс-агентная совместимость](../10-fleet-management/04-cross-platform.md). OpenCode, Claude Code, Cline — tool mapping, уровни портабельности.

---

**Порядок изучения:** строго последовательный (01 → 10).
