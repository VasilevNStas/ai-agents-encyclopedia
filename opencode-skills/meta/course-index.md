# Course Index — AI Teacher Skills

> Полная карта курса. Статус: `[ ]` не начато, `[/]` в работе, `[x]` пройдено.

---

## 01 — Fundamentals

| # | Файл | Тема | Статус |
|---|------|------|--------|
| 1.1 | [01-fundamentals/01-what-is-a-skill.md](../01-fundamentals/01-what-is-a-skill.md) | Что такое Skill — директория + SKILL.md, progressive disclosure, три категории | [ ] |
| 1.2 | [01-fundamentals/02-skill-vs-prompt.md](../01-fundamentals/02-skill-vs-prompt.md) | Skill vs System Prompt vs AGENTS.md — иерархия, когда что использовать | [ ] |
| 1.3 | [01-fundamentals/03-ecosystem-comparison.md](../01-fundamentals/03-ecosystem-comparison.md) | Сравнение экосистем Skill и подходов к инструкциям | [ ] |

**Практика:** открыть любой SKILL.md из Superpowers, найти name и description

---

## 02 — Anatomy of SKILL.md

| # | Файл | Тема | Статус |
|---|------|------|--------|
| 2.1 | [02-anatomy/01-skill-file-structure.md](../02-anatomy/01-skill-file-structure.md) | YAML frontmatter, name, description, опциональные поля, progressive disclosure | [ ] |
| 2.2 | [02-anatomy/02-spec-and-validation.md](../02-anatomy/02-spec-and-validation.md) | Официальная спецификация agentskills.io, валидация skills-ref | [ ] |
| 2.3 | [02-anatomy/03-real-world-analysis.md](../02-anatomy/03-real-world-analysis.md) | Разбор реальных SKILL.md из экосистемы | [ ] |

**Практика:** проверить любой SKILL.md через `skills-ref validate`

---

## 03 — Mechanics & Tooling

| # | Файл | Тема | Статус |
|---|------|------|--------|
| 3.1 | [03-mechanics/01-skill-tool.md](../03-mechanics/01-skill-tool.md) | Skill Tool, progressive disclosure, вызов в разных CLI | [ ] |
| 3.2 | [03-mechanics/02-one-percent-rule.md](../03-mechanics/02-one-percent-rule.md) | Порог 1%, eval-запросы, качество триггеринга | [ ] |
| 3.3 | [03-mechanics/03-lifecycle.md](../03-mechanics/03-lifecycle.md) | Discovery → Activation → Execution | [ ] |

**Практика:** проследить lifecycle skill в реальном диалоге

---

## 04 — Superpowers Ecosystem

| # | Файл | Тема | Статус |
|---|------|------|--------|
| 4.1 | [04-superpowers-ecosystem/01-what-is-superpowers.md](../04-superpowers-ecosystem/01-what-is-superpowers.md) | Суть, установка, структура пакета | [ ] |
| 4.2 | [04-superpowers-ecosystem/02-packages-and-distribution.md](../04-superpowers-ecosystem/02-packages-and-distribution.md) | Публикация, версионирование, дистрибуция | [ ] |
| 4.3 | [04-superpowers-ecosystem/03-package-workshop.md](../04-superpowers-ecosystem/03-package-workshop.md) | Практикум: сборка и публикация пакета | [ ] |

**Практика:** изучить node_modules/superpowers — структуру реального пакета

---

## 05 — Writing Skills

| # | Файл | Тема | Статус |
|---|------|------|--------|
| 5.1 | [05-writing-skills/01-first-skill.md](../05-writing-skills/01-first-skill.md) | Пишем первый Skill: 6 шагов, три подхода | [ ] |
| 5.2 | [05-writing-skills/02-best-practices.md](../05-writing-skills/02-best-practices.md) | DO/DON'T, gotchas, антипаттерны, checklist | [ ] |
| 5.3 | [05-writing-skills/03-tool-mapping.md](../05-writing-skills/03-tool-mapping.md) | OpenCode, Claude Code, Gemini, Copilot — маппинг | [ ] |

**Практика:** написать и протестировать свой первый skill

---

## 06 — Advanced

| # | Файл | Тема | Статус |
|---|------|------|--------|
| 6.1 | [06-advanced/01-composition.md](../06-advanced/01-composition.md) | Композиция: skill chaining, артефакты | [ ] |
| 6.2 | [06-advanced/02-chains-and-priority.md](../06-advanced/02-chains-and-priority.md) | Релевантность, конфликты, алфавитный порядок | [ ] |
| 6.3 | [06-advanced/03-pitfalls-and-tricks.md](../06-advanced/03-pitfalls-and-tricks.md) | Типовые проблемы, трюки, диагностика | [ ] |

**Практика:** выстроить цепочку из 3 skills для комплексной задачи

---

## 07 — Skill Debugging

| # | Файл | Тема | Статус |
|---|------|------|--------|
| 7.1 | [07-debugging/01-why-skill-not-loaded.md](../07-debugging/01-why-skill-not-loaded.md) | Почему skill не загрузился: диагностика | [ ] |
| 7.2 | [07-debugging/02-skill-ignores-instructions.md](../07-debugging/02-skill-ignores-instructions.md) | Skill игнорирует инструкции: причины и решения | [ ] |
| 7.3 | [07-debugging/03-debugging-tools.md](../07-debugging/03-debugging-tools.md) | Инструменты отладки | [ ] |

---

## 08 — Testing & Security

| # | Файл | Тема | Статус |
|---|------|------|--------|
| 8.1 | [08-testing-security/01-testing-skills.md](../08-testing-security/01-testing-skills.md) | Как тестировать skill до публикации | [ ] |
| 8.2 | [08-testing-security/02-security.md](../08-testing-security/02-security.md) | Безопасность: что может пойти не так | [ ] |
| 8.3 | [08-testing-security/03-sandboxing.md](../08-testing-security/03-sandboxing.md) | Sandboxing и изоляция | [ ] |
| 8.4 | [08-testing-security/04-property-based-testing.md](../08-testing-security/04-property-based-testing.md) | Property-based тестирование skills | [ ] |

---

## 09 — Performance & Optimization

| # | Файл | Тема | Статус |
|---|------|------|--------|
| 9.1 | [09-performance/01-context-window-impact.md](../09-performance/01-context-window-impact.md) | Влияние skills на context window | [ ] |
| 9.2 | [09-performance/02-token-cost.md](../09-performance/02-token-cost.md) | Токен-кост загрузки vs польза | [ ] |
| 9.3 | [09-performance/03-caching.md](../09-performance/03-caching.md) | Кэширование и ленивая загрузка | [ ] |

---

---

## 10 — Skill Fleet & Production

| # | Файл | Тема | Статус |
|---|------|------|--------|
| 10.1 | [10-fleet-management/01-ci-cd.md](../10-fleet-management/01-ci-cd.md) | CI/CD: валидация + тест триггеринга + интеграция | [ ] |
| 10.2 | [10-fleet-management/02-monitoring.md](../10-fleet-management/02-monitoring.md) | Мониторинг и observability usage | [ ] |
| 10.3 | [10-fleet-management/03-fleet-management.md](../10-fleet-management/03-fleet-management.md) | Управление парком: версионирование, code review, retirement | [ ] |
| 10.4 | [10-fleet-management/04-cross-platform.md](../10-fleet-management/04-cross-platform.md) | Кросс-агентная совместимость (OpenCode, Claude Code, Cline) | [ ] |

---

## Meta

| Файл | Назначение |
|------|-----------|
| [README.md](../README.md) | Карта курса (сводка) |
| [meta/roadmap.md](roadmap.md) | Порядок изучения |
| [meta/glossary.md](glossary.md) | Словарь терминов |
| [meta/reference.md](reference.md) | Фундаментальный справочник |
| [meta/course-index.md](course-index.md) | Полный индекс |

**Прогресс:** 0 / 32 темы
