# Композиция Skills

**Время чтения:** 8 мин

## Суть

Композиция — способность одного skill направлять агента к другому, формируя цепочку обработки задачи. Вместо монолитного skill сложный workflow разбивается на последовательность шагов, каждый из которых — отдельный skill.

## Основной материал

### Skill Chaining

Skill chaining — механизм, при котором один skill завершается инструкцией загрузить следующий:

> "Invoke the `<next-skill>` skill to proceed with the implementation plan."

Агент, дойдя до этой инструкции, оценивает, подходит ли указанный skill под текущий контекст (по правилу 1%), и при совпадении загружает его.

Пример реального пайплайна из Superpowers:

```
request → brainstorming → spec.md → writing-plans → plan.md
→ subagent-driven-development → verification → review → finishing
```

Каждый шаг:
1. **brainstorming** — анализ требований, выход: `spec.md`
2. **writing-plans** — декомпозиция на задачи, выход: `plan.md`
3. **subagent-driven-development** — реализация по плану
4. **verification-before-completion** — проверка
5. **requesting-code-review** — ревью
6. **finishing-a-development-branch** — merge/PR/cleanup

### Передача данных между skills

Skills не имеют общей памяти. Данные передаются через файлы-артефакты:

- `brainstorming` создаёт `spec.md` на диске
- `writing-plans` читает `spec.md`, создаёт `plan.md`
- `subagent-driven-development` читает `plan.md`, пишет код

Артефакты — единственный надёжный способ передачи контекста между разными skills.

### Conditional Branching

Цепочка может ветвиться в зависимости от контекста:

```
After completing this skill:
- If error found → invoke systematic-debugging
- Otherwise → invoke writing-plans
```

Ветвление встраивается прямо в текст SKILL.md инструкцией агенту.

### Ограничения композиции

1. **Нет программного вызова** — skill не может импортировать другой skill как библиотеку. Только текстовая инструкция агенту.
2. **Правило 1%** — агент может решить не загружать следующий skill.
3. **Контекст — только артефакты** — нельзя передать состояние через runtime.
4. **Skill не может загрузить другой skill напрямую** — только агент принимает решение.

### Skill как Middleware

Skill может проверять контекст и прерывать выполнение, если условие не выполнено:

```markdown
## HARD-GATES

- [ ] Есть spec.md
- [ ] Есть plan.md
- [ ] Все тесты проходят
```

Если условие не пройдено — skill сообщает об этом и направляет к нужному предыдущему шагу.

## Кейс / пример

Реальный пайплайн: пользователь пишет "добавь поддержку авторизации через OAuth":

1. brainstorming → spec.md
2. spec.md → writing-plans → plan.md
3. plan.md → subagent-driven-development → код
4. verification-before-completion → тесты
5. requesting-code-review → ревью
6. finishing-a-development-branch → merge

Цепочка: `brainstorming → writing-plans → subagent-dev → verification → review → finishing`

## Упражнение

Выстрой цепочку из 3 skills для задачи "написать документацию к API". Какой skill загружается первым, какой вторым, какой третьим? Что каждый производит на выходе?

## Проверь себя

1. Какой механизм позволяет одному skill направлять агента к другому?
2. Каким способом данные передаются между skills в цепочке?
3. Назови три ограничения композиции skills.
4. Как можно реализовать условное ветвление в цепочке skills?
5. Почему skill не может загрузить другой skill напрямую?

## Ключевые выводы

- Skill chaining — основной механизм композиции
- Артефакты (spec.md, plan.md) — способ передачи данных между skills
- Conditional branching — цепочка может ветвиться
- Нет программного вызова — только инструкция агенту
- Skill не может загрузить другой skill напрямую

## Что дальше

→ [Цепочки и приоритизация](02-chains-and-priority.md)
