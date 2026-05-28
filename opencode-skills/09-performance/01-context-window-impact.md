# Влияние на контекстное окно

**Время чтения:** 7 мин

## Суть

Каждый загруженный skill занимает место в контекстном окне. Понимание progressive disclosure и token-коста помогает проектировать skills так, чтобы они приносили пользу, не перегружая контекст.

## Основной материал

### Progressive disclosure и контекст

Skills используют трёхэтапную загрузку (progressive disclosure), чтобы минимизировать влияние на контекст:

1. **Метаданные** (~100 токенов на skill) — name + description загружаются при старте сессии для **всех** зарегистрированных skills
2. **Инструкции** (< 5000 токенов) — полный SKILL.md загружается только при активации skill
3. **Ресурсы** — файлы из scripts/, references/, assets/ — загружаются по необходимости

Это значит:
- 100 установленных skills занимают в контексте ~10K токенов (только метаданные)
- Полный SKILL.md загружается только для 1-4 релевантных skills
- Ресурсы — только если агент решил, что они нужны

### Сколько места занимают skills

Типичный SKILL.md из Superpowers:

| Skill | Слов | Токенов (EN) | % окна 100K |
|-------|------|-------------|-------------|
| brainstorming | ~400 | ~530 | 0.5% |
| systematic-debugging | ~350 | ~470 | 0.5% |
| writing-plans | ~500 | ~670 | 0.7% |
| subagent-driven-dev | ~600 | ~800 | 0.8% |

**Сценарии загрузки:**

| Сценарий | Загружено skills | Токенов | % окна 100K |
|----------|-----------------|---------|-------------|
| Простой запрос | 0-1 | 0-1000 | 0-1% |
| Средняя задача | 2-4 | 2000-5000 | 2-5% |
| Сложная задача | 4-8 | 8000-15000 | 8-15% |
| Перегрузка | 10+ | 20000+ | 20%+ |

### Когда skills начинают вредить

Признаки перегрузки контекста skills:
- Агент начинает "забывать" инструкции из ранних skills
- Падает качество выполнения чеклистов
- Агент пропускает шаги
- Растёт токен-кост без роста качества

Официальная рекомендация: не превышать **20-50 зарегистрированных skills** одновременно, иначе снижается качество триггеринга.

### Оптимизация размера SKILL.md

**1. Сокращай без потери смысла**

```markdown
# ❌ Многословно
PDF (Portable Document Format) is a common file format that contains
text, images, etc. To extract text from a PDF, you'll need to use a
library. We recommend pdfplumber because it handles most cases well.

# ✅ Компактно
Use pdfplumber for text extraction.
For scanned documents, use pdf2image + pytesseract.
```

**2. Выноси детали в reference-файлы**

В SKILL.md оставляй только то, что нужно на каждом запуске:
- Цель
- Gotchas
- Checklist
- Ссылки на reference

В `references/REFERENCE.md` — детали, примеры, таблицы.

**3. Используй кросс-ссылки вместо повторов**

```markdown
# ❌ Повторяет workflow из другого skill
[20 lines of repeated instructions]

# ✅ Ссылается на другой skill
REQUIRED: Use [other-skill-name] for detailed workflow.
```

**4. Сжимай примеры**

```markdown
# ❌ Многословный пример (42 слова)
Your human partner: "How did we handle authentication errors in React Router?"
You: I'll search past conversations for React Router authentication patterns.
[Dispatch subagent with search query: "React Router authentication error handling"]

# ✅ Компактный пример (20 слов)
Partner: "How did we handle auth errors in React Router?"
You: Searching...
[Dispatch subagent → synthesis]
```

### Целевые метрики

| Тип skill | Целевой размер |
|-----------|---------------|
| getting-started / frequently loaded | < 150 слов / < 200 токенов |
| Обычные skills | < 500 слов / < 700 токенов |
| SKILL.md целиком | < 500 строк / < 5000 токенов |

## Кейс / пример

Пользователь установил 50 skills. При старте сессии загружено ~5000 токенов метаданных (5% окна). При запросе "напиши тесты" загружаются 3 skills (TDD, writing-tests, code-review) — ещё ~2000 токенов (2%). Итого 7% окна занято skills, остальное — диалог. Нормально.

Если бы все 50 skills загрузили полные SKILL.md сразу — это было бы 25K+ токенов (25% окна). Progressive disclosure предотвращает это.

## Упражнение

Возьми SKILL.md из brainstorming (Superpowers). Подсчитай примерное количество слов. Оцени, сколько процентов контекстного окна (100K) он занимает. Рассчитай, сколько займут 10 таких skills одновременно.

## Проверь себя

1. Сколько токенов занимают метаданные одного skill при старте сессии?
2. Сколько процентов окна (100K) занимают 2-4 skills в типичном сценарии?
3. Назови три признака перегрузки контекста skills.
4. Как progressive disclosure помогает экономить контекст?
5. Какая рекомендуемая максимальная длина SKILL.md в строках?

## Ключевые выводы

- Progressive disclosure: метаданные (~100 токенов) vs инструкции (< 5000 токенов)
- Типичный сценарий: 2-4 skills занимают 2-5% окна
- Признаки перегрузки: забывание инструкций, пропуск шагов
- Оптимизация: сокращай, выноси в reference, используй кросс-ссылки
- Не превышай 20-50 зарегистрированных skills

## Что дальше

→ [Токен-кост](02-token-cost.md)
