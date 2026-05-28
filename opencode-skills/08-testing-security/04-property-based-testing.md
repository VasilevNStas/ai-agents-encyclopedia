# Property-based testing для skills

**Время чтения:** 10 мин

## Суть

Примерные тесты (example-based testing) проверяют, что skill работает на конкретных запросах. Property-based testing идёт дальше: он генерирует случайные варианты входных данных и проверяет, что skill ведёт себя корректно для целого класса ситуаций.

## Основной материал

### Проблема example-based тестов

Ты написал 20 eval-запросов (как в уроке 01). Все проходят. Но в production skill не загружается или даёт неверный результат, потому что пользователь сформулировал запрос не так, как в тестах.

Пример-based тесты проверяют то, что ты предусмотрел. Property-based тесты проверяют то, что ты не учёл.

### Что тестировать через свойства

Для skills есть три ключевых свойства:

#### Свойство 1: Стабильность триггеринга

Для заданного описания skill и случайных вариаций целевого запроса — skill должен стабильно загружаться.

```python
import random
import re

# Шаблоны запросов, которые должны триггерить skill "code-review"
TEMPLATES = [
    "review this code: {code}",
    "can you check {code} for bugs?",
    "code review please: {code}",
    "найди ошибки в {code}",
    "проверь код: {code}",
    "выполни ревью {code}",
]

CODE_SNIPPETS = [
    "function sum(a,b){return a+b}",
    "def calculate(x,y): return x/y",
    "const result = await fetch(url)",
    "for i in range(10): print(i)",
    "SELECT * FROM users WHERE id = ?",
]

def generate_test_cases(n: int = 100):
    """Генерирует n случайных комбинаций шаблон+код."""
    cases = []
    for _ in range(n):
        template = random.choice(TEMPLATES)
        code = random.choice(CODE_SNIPPETS)
        cases.append(template.format(code=code))
    return cases

# Проверка: для каждой комбинации skill должен загрузиться
# (запускается в эмуляторе агента или через eval-фреймворк)
def test_trigger_stability(agent_emulator, skill_name: str, cases: list[str]):
    failures = []
    for i, case in enumerate(cases):
        loaded = agent_emulator.check_skill_trigger(skill_name, case)
        if not loaded:
            failures.append(f"Case {i}: {case[:50]}...")
    return {
        "total": len(cases),
        "passed": len(cases) - len(failures),
        "failed": len(failures),
        "failures": failures[:5],  # только первые 5
    }
```

#### Свойство 2: Устойчивость description к шуму

Description не должен ломаться от незначительных вариаций в запросе:

| Вариант запроса | Ожидание |
|----------------|----------|
| "review code" | trigger |
| "REVIEW THE CODE" | trigger |
| "review!!! code" | trigger |
| "подскажи по коду" | trigger |
| "напиши код" | NOT trigger |

```python
NOISE_PATTERNS = [
    ("lowercase", lambda s: s.lower()),
    ("uppercase", lambda s: s.upper()),
    ("extra spaces", lambda s: re.sub(r"\s+", "  ", s)),
    ("punctuation", lambda s: s.replace(" ", "!!!")),
]

def test_description_robustness(agent_emulator, skill_name: str, base_query: str):
    results = {}
    for noise_name, noise_fn in NOISE_PATTERNS:
        noisy = noise_fn(base_query)
        loaded = agent_emulator.check_skill_trigger(skill_name, noisy)
        results[noise_name] = loaded
    return results
```

#### Свойство 3: Не-триггеринг на негативных запросах

Skill не должен загружаться на запросы, не относящиеся к его области:

```python
NEGATIVE_TEMPLATES = [
    "напиши hello world на python",
    "как установить npm?",
    "что такое Docker?",
    "переведи на английский",
    "создай маркдаун-файл",
]

def test_negative_queries(agent_emulator, skill_name: str):
    false_positives = []
    for query in NEGATIVE_TEMPLATES:
        loaded = agent_emulator.check_skill_trigger(skill_name, query)
        if loaded:
            false_positives.append(query)
    return {
        "total": len(NEGATIVE_TEMPLATES),
        "false_positives": len(false_positives),
        "details": false_positives,
    }
```

### Интеграция в eval-набор

Добавь property-based тесты как отдельный файл рядом с evals.json:

```
my-skill/
├── SKILL.md
├── evals/
│   ├── evals.json              # example-based тесты
│   └── property-tests.py       # property-based тесты
└── run_tests.sh                # запуск всех тестов
```

**run_tests.sh:**
```bash
#!/bin/bash
echo "=== Example-based tests ==="
# ... запуск evals.json через skill-creator

echo "=== Property-based tests ==="
python3 evals/property-tests.py --skill my-skill --iterations 200

echo "=== Результат ==="
# агрегировать оба отчёта
```

### Антипаттерны property-based testing для skills

1. **Генерация бессмысленных запросов** — "asdf qwerty 123" не проверяет ничего полезного. Генерируй осмысленные вариации реальных запросов.
2. **Слишком много итераций** — 1000 итераций для skill с description на 50 токенов избыточно. 100-200 достаточно.
3. **Игнорирование false negatives** — если skill не загрузился на вариации запроса, это может быть проблема description, а не теста.
4. **Тестирование без baseline** — запусти property-based тесты на "пустом" description (без skill) для понимания baseline.

## Упражнение

1. Возьми любой установленный skill (например, brainstorming из superpowers)
2. Напиши property-based тест на стабильность триггеринга (10 шаблонов, 50 итераций)
3. Найди хотя бы один запрос, на котором skill не загружается, хотя должен
4. Исправь description в локальной копии skill
5. Проверь, что после исправления тест проходит

## Проверь себя

1. В чём ключевое отличие property-based тестов от example-based?
2. Назови три ключевых свойства, которые тестируются через property-based подход.
3. Сколько итераций достаточно для property-based теста skill?
4. Какой антипаттерн описан для генерации тестовых запросов?
5. Почему комбинация example-based и property-based тестов даёт максимальное покрытие?

## Ключевые выводы

- Example-based тесты проверяют конкретные случаи, property-based — классы случаев
- Три ключевых свойства: стабильность триггеринга, устойчивость к шуму, не-триггеринг на негативных запросах
- Генерируй осмысленные вариации, не случайный шум
- 100-200 итераций достаточно для уверенности
- Property-based тесты находят то, что вы не учли в example-based тестах
- Комбинация обоих подходов даёт максимальное покрытие

## Что дальше

→ [Sandboxing skills](03-sandboxing.md)
