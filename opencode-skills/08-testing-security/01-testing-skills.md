# Тестирование skills

**Время чтения:** 10 мин

## Суть

Skill — это код. Как и любой код, его нужно тестировать. Официальная методология Anthropic предлагает eval-driven подход: набор тестовых запросов, assertions, градация результатов и итеративное улучшение.

## Основной материал

### Три уровня тестирования

#### Уровень 1: Триггеринг (загружается ли skill?)

Проверяет, что description правильно срабатывает на целевые запросы.

**Метод:** eval-запросы (см. [урок 03-02](../03-mechanics/02-one-percent-rule.md)).

Создай 20 запросов:
- 10 должны триггерить skill (should_trigger = true)
- 10 не должны (should_trigger = false)

Каждый запрос прогони 3 раза (модель недетерминирована). Вычисли trigger rate. Цель: > 0.5 для should-trigger, < 0.5 для should-not-trigger.

**Разделение на train/validation (чтобы избежать overfitting):**
- Train set (60%) — на нём ты меняешь description
- Validation set (40%) — только для финальной проверки

#### Уровень 2: Выполнение (правильно ли работает?)

Проверяет, что инструкции в SKILL.md приводят к ожидаемому результату.

**Метод:** запусти skill на реальной задаче и проверь assertions:

```json
{
  "skill_name": "csv-analyzer",
  "evals": [
    {
      "id": 1,
      "prompt": "I have a CSV of sales data. Find top 3 months by revenue.",
      "expected_output": "A bar chart showing top 3 months with labeled axes",
      "assertions": [
        "Output includes a bar chart image file",
        "Chart shows exactly 3 months",
        "Both axes are labeled",
        "Chart title mentions revenue"
      ]
    }
  ]
}
```

**Правила хороших assertions:**
- Проверяемы: "файл существует", "ось X подписана"
- Конкретны: "отчёт содержит минимум 3 рекомендации"
- Не слишком хрупки: не привязывайся к точным формулировкам

#### Уровень 3: Сравнение с базовой линией (лучше ли, чем без skill?)

Запусти тот же запрос дважды: с skill и без него. Сравни:

```json
{
  "run_summary": {
    "with_skill": {
      "pass_rate": 0.83,
      "time_seconds": 45,
      "tokens": 3800
    },
    "without_skill": {
      "pass_rate": 0.33,
      "time_seconds": 32,
      "tokens": 2100
    },
    "delta": {
      "pass_rate": 0.50,
      "time_seconds": 13,
      "tokens": 1700
    }
  }
}
```

Skill полезен, если pass_rate заметно выше. Если разницы нет — skill не добавляет ценности.

### Структура eval-набора

```
my-skill/
├── SKILL.md
└── evals/
    └── evals.json          # запросы + assertions

my-skill-workspace/
└── iteration-1/
    ├── eval-task-1/
    │   ├── with_skill/
    │   │   ├── outputs/
    │   │   └── grading.json
    │   └── without_skill/
    │       ├── outputs/
    │       └── grading.json
    └── benchmark.json       # агрегированная статистика
```

### Инструмент: skill-creator

Официальный skill от Anthropic автоматизирует весь цикл:
1. Создаёт eval-набор на основе твоего skill
2. Запускает тесты в параллель
3. Градирует результаты по assertions
4. Предлагает улучшения description
5. Генерирует HTML-отчёт

Установка:
```bash
npx skills add anthropics/claude-code --skill skill-creator
```

### Типы тестов для разных категорий skills

**Discipline-enforcing skills (правила):** TDD, verification-before-completion
- Тест: академические вопросы (понимает ли правила?)
- Тест: pressure scenarios (соблюдает ли под давлением?)
- Success: агент следует правилу при максимальном давлении

**Technique skills (how-to):** condition-based-waiting, debugging
- Тест: application scenarios (применяет ли технику?)
- Тест: variation scenarios (обрабатывает ли граничные случаи?)
- Success: агент успешно применяет технику к новому сценарию

**Reference skills (документация):** API guides
- Тест: retrieval scenarios (находит ли нужную информацию?)
- Тест: application scenarios (использует ли найденное?)
- Success: агент находит и применяет информацию

### Градация результатов

После каждого прогона записывай grading.json:

```json
{
  "assertion_results": [
    {
      "text": "Output includes chart file",
      "passed": true,
      "evidence": "Found chart.png in outputs"
    },
    {
      "text": "Chart shows exactly 3 months",
      "passed": false,
      "evidence": "Chart shows 4 months instead of 3"
    }
  ],
  "summary": {
    "passed": 3,
    "failed": 1,
    "total": 4,
    "pass_rate": 0.75
  }
}
```

## Кейс / пример

Skill «systematic-debugging»:
- Тест 1 (норма): "У меня падает тест" → skill загружается, агент идёт по шагам
- Тест 2 (граница): "Почему код не работает?" → частичный match, skill может загрузиться
- Тест 3 (отрицательный): "Напиши функцию" → skill НЕ должен загрузиться

После прогона: assertions показывают, что в 30% случаев skill не следует чеклисту. Добавляем gotchas — pass_rate растёт до 90%.

## Упражнение

Придумай 3 тест-кейса для любого установленного skill: нормальный, граничный, негативный. Опиши ожидаемое поведение для каждого.

## Проверь себя

1. Назови три уровня тестирования skills.
2. Сколько eval-запросов рекомендуется создать и с какой пропорцией should-trigger?
3. Почему нужно разделять train и validation set для eval-запросов?
4. Какие метрики сравниваются при тестировании с skill и без него?
5. Какой инструмент автоматизирует весь цикл тестирования?

## Ключевые выводы

- Три уровня тестирования: триггеринг, выполнение, сравнение с baseline
- Eval-запросы: 20 запросов, 3 прогона каждый, trigger rate
- Assertions должны быть проверяемы и конкретны
- Skill полезен, если pass_rate заметно выше, чем без него
- skill-creator автоматизирует весь цикл тестирования

## Что дальше

→ [Безопасность Skills](02-security.md)
