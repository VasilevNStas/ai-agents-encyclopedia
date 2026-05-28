---
created: 2026-05-28
tags: [course/eval-tools-deep, deepeval, metrics, pytest, unit-testing]
status: active
---

# Урок 20.3: DeepEval Deep Dive

> [!quote] Ключевая идея
> DeepEval — это pytest для LLM. Те же паттерны (fixtures, assertions, parametrize), но метрики специфичны для LLM: faithfulness, hallucination, bias, toxicity. Если promptfoo — для итерации промптов, то DeepEval — для регрессии компонентов.

---

## 1. Установка и базовая структура

```bash
pip install deepeval
```

### Структура проекта

```
eval-project/
├── .deepeval/              # Конфиг и кэш
├── test_*.py               # Тесты (pytest-совместимые)
├── run_evals.py            # Точка входа
└── deepeval.conf.py        # Конфиг (опционально)
```

### Первый тест

```python
# test_basic.py
from deepeval import assert_test
from deepeval.test_case import LLMTestCase
from deepeval.metrics import AnswerRelevancyMetric


def test_answer_relevancy():
    test_case = LLMTestCase(
        input="What is the capital of France?",
        actual_output="Paris is the capital of France.",
    )
    metric = AnswerRelevancyMetric(threshold=0.7)
    assert_test(test_case, [metric])
```

### Запуск

```bash
# Все тесты
deepeval test run test_basic.py

# С отчетом
deepeval test run test_basic.py --report

# В CI формате
deepeval test run test_basic.py --junit-xml results.xml
```

---

## 2. Метрики DeepEval

### 2.1 FaithfulnessMetric — соответствует ли ответ контексту?

```python
from deepeval.metrics import FaithfulnessMetric

def test_faithfulness():
    test_case = LLMTestCase(
        input="What is Python?",
        actual_output="Python is a programming language created in 1991.",
        retrieval_context=[
            "Python was created by Guido van Rossum in 1991.",
            "Python is a high-level programming language.",
        ],
    )
    metric = FaithfulnessMetric(
        threshold=0.8,
        include_reason=True,  # Возвращает объяснение
    )
    assert_test(test_case, [metric])
    # metric.score → 0.0-1.0
    # metric.reason → "The output is faithful to the context..."
```

### 2.2 HallucinationMetric — галлюцинирует ли?

```python
from deepeval.metrics import HallucinationMetric

def test_no_hallucination():
    test_case = LLMTestCase(
        input="What is the population of Tokyo?",
        actual_output="Tokyo has a population of 14 million.",
        retrieval_context=[
            "Tokyo's population is approximately 14 million within the 23 wards.",
        ],
    )
    metric = HallucinationMetric(threshold=0.8)
    assert_test(test_case, [metric])
```

### 2.3 BiasMetric — есть ли предвзятость?

```python
from deepeval.metrics import BiasMetric

def test_no_bias():
    test_case = LLMTestCase(
        input="Describe a typical software engineer.",
        actual_output="A software engineer writes and maintains code, "
                      "collaborates with teams, and solves technical problems.",
    )
    metric = BiasMetric(threshold=0.9)
    assert_test(test_case, [metric])
```

### 2.4 ToxicityMetric — токсичность?

```python
from deepeval.metrics import ToxicityMetric

def test_not_toxic():
    test_case = LLMTestCase(
        input="Why is this feature broken?",
        actual_output="I understand your frustration. Let me help "
                      "troubleshoot the issue step by step.",
    )
    metric = ToxicityMetric(threshold=0.9)
    assert_test(test_case, [metric])
```

### Полный список метрик

| Метрика | Измеряет | Когда использовать |
|---------|----------|-------------------|
| Faithfulness | Соответствие контексту | RAG pipelines |
| AnswerRelevancy | Релевантность ответа | QA системы |
| Hallucination | Галлюцинации | Любой LLM output |
| Bias | Предвзятость | Safety-critical |
| Toxicity | Токсичность | Customer-facing |
| ContextualPrecision | Точность retrieval | RAG |
| ContextualRecall | Полнота retrieval | RAG |
| ContextualRelevancy | Релевантность контекста | RAG |
| GEval | Кастомная метрика | Любая |

---

## 3. Кастомные метрики через GEval

```python
from deepeval.metrics import GEval
from deepeval.test_case import LLMTestCaseParams

def test_custom_metric():
    metric = GEval(
        name="Professional Tone",
        criteria="Determine if the response maintains a professional "
                 "and respectful tone.",
        evaluation_steps=[
            "Check for polite language",
            "Ensure no slang or informal terms",
            "Verify constructive feedback",
        ],
        evaluation_params=[
            LLMTestCaseParams.INPUT,
            LLMTestCaseParams.ACTUAL_OUTPUT,
        ],
    )

    test_case = LLMTestCase(
        input="Your code has a bug.",
        actual_output="Thank you for reporting this. I've identified "
                      "the issue and will provide a fix shortly.",
    )
    assert_test(test_case, [metric])
```

---

## 4. Conversational & Multi-turn тесты

```python
from deepeval.test_case import ConversationalTestCase

def test_multi_turn_support():
    messages = [
        {"role": "user", "content": "I need help with my order."},
        {"role": "assistant", "content": "I'd be happy to help. "
         "Can you provide your order number?"},
        {"role": "user", "content": "It's #12345."},
        {"role": "assistant", "content": "Thank you. Let me check "
         "the status of order #12345."},
    ]

    test_case = ConversationalTestCase(messages=messages)

    # Проверка: агент запросил номер заказа
    assert any("order number" in m["content"].lower()
               for m in messages if m["role"] == "assistant")
```

---

## 5. CI/CD и Production

### GitHub Actions

```yaml
name: LLM Unit Tests
on: [push, pull_request]

jobs:
  deepeval:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: pip install deepeval
      - run: deepeval test run test_evals.py --junit-xml results.xml
      - uses: dorny/test-reporter@v1
        if: always()
        with:
          name: DeepEval Results
          path: results.xml
          reporter: java-junit
```

### ConfTest и fixtures

```python
# conftest.py
import pytest
from deepeval import assert_test
from deepeval.metrics import BaseMetric


@pytest.fixture
def rag_context():
    return [
        "Paris is the capital of France.",
        "France is in Western Europe.",
    ]


@pytest.fixture
def faithfulness_metric():
    return FaithfulnessMetric(threshold=0.7)


def test_with_fixtures(rag_context, faithfulness_metric):
    test_case = LLMTestCase(
        input="What is the capital of France?",
        actual_output="Paris.",
        retrieval_context=rag_context,
    )
    assert_test(test_case, [faithfulness_metric])
```

### Production мониторинг

```python
# monitor.py
from deepeval.monitor import monitor

@monitor(
    metrics=[FaithfulnessMetric(threshold=0.8)],
    enable_cloud=False,
)
def agent_response(input_text: str) -> str:
    # Production agent
    response = llm.generate(input_text)
    return response

# DeepEval автоматически:
# 1. Логирует input/output
# 2. Вычисляет метрики
# 3. Трекинг latency
# 4. Детектит drift
```

---

## 6. Anti-patterns

```python
# ❌ Слепая вера в метрики
metric = FaithfulnessMetric(threshold=0.7)
# 0.7 ≠ гарантия качества — всегда проверяй примеры

# ❌ Тесты без контекста для RAG
test_case = LLMTestCase(
    input="What is X?",
    actual_output="X is Y.",
    # No retrieval_context — Faithfulness не работает
)

# ❌ Слишком высокий threshold
metric = BiasMetric(threshold=0.99)  # Никогда не пройдёт
# ✅ Разумный threshold: 0.7-0.9

# ❌ Одна метрика на всё
# ✅ Комбинируй: Faithfulness + Hallucination + Toxicity
```

---

## Резюме

```
DeepEval = pytest для LLM

Метрики:
  — Faithfulness: ответ соответствует контексту
  — Hallucination: нет выдуманных фактов
  — Bias/Toxicity: безопасность
  — GEval: кастомные критерии
  — Conversational: multi-turn

Интеграции:
  — pytest (fixtures, parametrize)
  — GitHub Actions (JUnit XML)
  — Production monitoring (drift detection)
```

---

## Практическое задание

1. Напиши 3 теста DeepEval: faithfulness, relevancy, toxicity.

2. Создай кастомную метрику через GEval («Professional Tone»).

3. Добавь ConversationalTestCase для поддержки (multi-turn диалог).

4. Настрой production monitoring для агента.

---

## Проверь себя

1. Какие метрики DeepEval специфичны для RAG?
2. Как создать кастомную метрику?
3. Чем ConversationalTestCase отличается от LLMTestCase?
4. Как работает production monitoring?

---

## Ссылки

- [[01-landscape]] — обзор инструментов
- [[02-promptfoo-deep]] — promptfoo deep dive
- [[04-ragas-deep]] — следующий урок: Ragas deep dive
