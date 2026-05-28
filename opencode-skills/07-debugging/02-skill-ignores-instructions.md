# Skill игнорирует инструкции

**Время чтения:** 8 мин

## Суть

Skill загрузился, но агент не выполняет его инструкции или выполняет не так, как задумано. Причина — в формулировках, противоречиях или отсутствии императивности в инструкциях.

## Основной материал

### Почему агент игнорирует инструкции

#### 1. Инструкция сформулирована как рекомендация

Мягкие формулировки дают агенту свободу выбора:

- "рекомендуется использовать pytest" → агент может выбрать unittest
- "лучше проверить порт перед запуском" → агент может "забыть"
- "можно запустить тесты" → агент решит, что это опционально

**Проблема:** агент оптимизирует задачу и пропускает "необязательные" шаги.

**Решение:** используй императивный стиль:
```markdown
# ❌ Мягко
You may want to run tests before deployment.

# ✅ Императивно
Run tests before deployment. Do NOT deploy if any test fails.
```

#### 2. Противоречия внутри skill

Инструкции противоречат друг другу, и агент выбирает "более удобную":

```markdown
1. Используй npm для управления пакетами
2. Убедись, что yarn.lock актуален
```

Агент запутается: если используем npm, зачем yarn.lock?

**Решение:** проверь все инструкции на согласованность. Если есть выбор — дай явное условие:
```markdown
- Если проект использует yarn → работай с yarn.lock
- Иначе → используй npm и package-lock.json
```

#### 3. Skill слишком длинный

Агент теряет фокус на середине длинного SKILL.md. Чем длиннее файл, тем выше вероятность, что часть инструкций будет пропущена.

**Решение:** держи SKILL.md до 500 строк / 5000 токенов. Детали — в reference-файлах.

#### 4. Description суммирует workflow

Если description описывает workflow, агент может следовать description вместо чтения полного SKILL.md:

```yaml
# ❌ Опасно: агент может прочитать только это
description: >-
  Use when executing plans — dispatches subagent per task with
  code review between tasks

# ✅ Безопасно: только триггер
description: >-
  Use when executing implementation plans with independent tasks
```

**Почему:** тестирование Anthropic показало, что когда description суммирует workflow, агент пропускает тело skill и следует описанию. Это приводит к потере детальных инструкций, чеклистов и gotchas.

#### 5. Агент считает свою эвристику лучше

Даже при точных инструкциях агент может переопределить их на основе своего "знания":

```
Инструкция: используй pnpm для установки зависимостей
Реальность: агент использует npm, потому что "знает" его лучше
```

**Решение:** объясни WHY. Агенты следуют инструкциям лучше, когда понимают причину:
```markdown
Use pnpm for dependency installation (faster, disk-efficient).
Do NOT use npm — it doesn't handle monorepo workspaces correctly.
```

### Gotchas как механизм compliance

Gotchas — неочевидные факты, которые агент не узнает без инструкции. Это самый эффективный способ заставить агента следовать правилам:

```markdown
## Gotchas

- The `users` table uses soft deletes — always include
  `WHERE deleted_at IS NULL`
- User ID is `user_id` in DB, `uid` in auth service, and
  `accountId` in billing API
- Port 3000 is reserved for the admin panel
```

Когда агент делает ошибку, добавь её в gotchas — это один из самых прямых способов улучшить skill итеративно.

### Checklists для гарантии выполнения

Агенты редко пропускают незаполненные чекбоксы. Используй `- [ ]` для шагов, которые нельзя пропустить:

```markdown
## Deployment checklist

- [ ] Run tests
- [ ] Build production bundle
- [ ] Verify staging deployment
- [ ] Deploy to production
```

### Validation loops

Инструктируй агента проверять свою работу в цикле:

```markdown
1. Make edits
2. Run validation: python scripts/validate.py
3. If validation fails — fix and re-run
4. Only proceed when validation passes
```

### Что НЕ работает

- Запугивания ("НАРУШЕНИЕ КОНТРАКТА") — агенты не реагируют на эмоции
- Пустые угрозы — если нет механизма проверки, угроза не работает
- Абстрактные запреты — "будь осторожен" ничего не значит

## Кейс / пример

Skill для деплоя: "Перед деплоем запусти тесты". Агент деплоит без тестов.

**Проблема:** инструкция мягкая, без gotchas и checklists. Агент решил сэкономить время.

**Решение:**
```markdown
## Deployment

1. Run tests: `pytest tests/`
2. If any test fails — STOP. Do NOT deploy.
3. Only after all tests pass — proceed to deploy.

- [ ] Tests passed
- [ ] Deploy confirmed

## Gotchas

- Skipping tests before deployment = guaranteed production incident
- "Tests take too long" is not a valid reason to skip
```
## Упражнение

Напиши инструкцию для skill "code-formatter", в которой агент ОБЯЗАН сначала запустить линтер, а потом форматировать. Используй императивный стиль и checklist.

## Проверь себя

1. Почему мягкие формулировки в инструкциях приводят к их игнорированию?
2. Какой стиль инструкций предпочтителен для гарантии выполнения?
3. Какая длина SKILL.md считается безопасной, чтобы агент не терял фокус?
4. Почему description не должен описывать workflow?
5. Какой механизм compliance наиболее эффективен для предотвращения ошибок?

## Ключевые выводы

- Мягкие формулировки = агент может проигнорировать инструкцию
- Description НЕ должен описывать workflow — иначе агент пропустит тело skill
- Противоречия в skill убивают compliance
- Gotchas — самый эффективный способ предотвратить ошибки
- Checklists гарантируют выполнение шагов
- Объясняй WHY — агенты лучше следуют инструкциям с обоснованием

## Что дальше

→ [Инструменты отладки](03-debugging-tools.md)
