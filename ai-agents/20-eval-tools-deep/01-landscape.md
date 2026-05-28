---
created: 2026-05-28
tags: [course/eval-tools-deep, evaluation, promptfoo, deepeval, ragas, landscape]
status: active
---

# Урок 20.1: Eval Tools Landscape — promptfoo vs DeepEval vs Ragas

> [!quote] Ключевая идея
> В 2026 evaluation AI-агентов — это не самописные скрипты, а специализированные фреймворки. promptfoo для prompt testing, DeepEval для unit-тестов LLM, Ragas для RAG-метрик. Каждый закрывает свой слой.

---

## 1. Три слоя evaluation

```
┌─────────────────────────────────────────────┐
│           Layer 3: Production                │
│  A/B testing, canary, drift monitoring       │
│  Инструменты: custom + LangFuse + Arize      │
├─────────────────────────────────────────────┤
│           Layer 2: System Evals              │
│  promptfoo → regression test suites          │
│  DeepEval → unit-тесты LLM-компонентов       │
│  Ragas → RAG pipeline quality                │
├─────────────────────────────────────────────┤
│           Layer 1: Prompt Development         │
│  promptfoo → rapid iteration, assertions     │
│  LLM-as-Judge → quality scoring              │
└─────────────────────────────────────────────┘
```

---

## 2. Сравнение фреймворков

| Характеристика | promptfoo | DeepEval | Ragas |
|---|---|---|---|
| Фокус | Prompt testing & red teaming | Unit-тесты LLM | RAG evaluation |
| Год создания | 2023 | 2024 | 2024 |
| Язык | JS + Python CLI | Python | Python |
| Конфиг | YAML/JSON | Python code | Python code |
| Assertions | 30+ built-in | 14+ metrics | 8 RAG metrics |
| CI/CD | GitHub Actions | GitHub Actions | GitHub Actions |
| Self-host | ✅ | ✅ | ✅ |
| Cloud | ✅ (promptfoo.app) | ❌ | ❌ |
| Red teaming | ✅ built-in | ❌ | ❌ |
| RAG metrics | ❌ (generic) | ✅ (partial) | ✅ (native) |
| LLM-as-Judge | ✅ | ✅ | ✅ |
| Caching | ✅ (disk) | ✅ (memory) | ❌ |
| Provider | 20+ | 10+ | any |

### Когда что использовать

```python
# Decision matrix
def choose_eval_tool(use_case: str) -> list[str]:
    tools = []

    if use_case in ["prompt_iteration", "red_teaming", "regression"]:
        tools.append("promptfoo")
        # promptfoo: лучший для быстрой итерации промптов
        # YAML-конфиг, 30+ ассершенов, встроенный red teaming

    if use_case in ["unit_test", "ci_pipeline", "component_test"]:
        tools.append("deepeval")
        # DeepEval: Python-native, pytest-интеграция
        # Метрики: faithfulness, relevancy, hallucination, bias, toxicity

    if use_case in ["rag_pipeline", "retrieval_quality", "rag_regression"]:
        tools.append("ragas")
        # Ragas: декомпозиция RAG-качества
        # Context precision, recall, faithfulness, answer relevancy

    if use_case in ["production_monitoring", "drift"]:
        tools.append("langfuse")
        # Production monitoring + tracing

    return tools
```

---

## 3. Быстрый старт — три инструмента рядом

### promptfoo (CLI)

```bash
# Установка
npm install -g promptfoo

# Базовый конфиг
cat > promptfooconfig.yaml << 'EOF'
prompts:
  - "Answer: {{question}}"
  - "Think step by step. Answer: {{question}}"

providers:
  - openai:gpt-4o
  - anthropic:claude-sonnet-4

tests:
  - vars:
      question: "What is 2+2?"
    assert:
      - type: contains
        value: "4"
      - type: latency
        threshold: 2000
  - vars:
      question: "Explain gravity"
    assert:
      - type: is-json
      - type: cost
        threshold: 0.01
EOF

# Запуск
npx promptfoo eval

# Результат
npx promptfoo view  # Web UI
```

### DeepEval (Python)

```python
# pip install deepeval
from deepeval import assert_test
from deepeval.test_case import LLMTestCase
from deepeval.metrics import FaithfulnessMetric, HallucinationMetric

def test_response_faithful():
    test_case = LLMTestCase(
        input="What is the capital of France?",
        actual_output="Paris is the capital of France.",
        retrieval_context=["France's capital city is Paris."]
    )
    metric = FaithfulnessMetric(threshold=0.7)
    assert_test(test_case, [metric])
```

### Ragas (Python)

```python
# pip install ragas
from ragas import evaluate
from ragas.metrics import (
    faithfulness, answer_relevancy,
    context_precision, context_recall
)

dataset = {
    "question": ["What is RAG?"],
    "answer": ["RAG retrieves documents then generates."],
    "contexts": [["RAG = Retrieval Augmented Generation."]],
    "ground_truth": ["Retrieval Augmented Generation combines retrieval with generation."],
}

results = evaluate(dataset, metrics=[
    faithfulness, answer_relevancy,
    context_precision, context_recall
])
print(results)
```

---

## 4. Интеграция в CI/CD

```yaml
# .github/workflows/eval.yml
name: LLM Evals
on: [push]

jobs:
  promptfoo:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: npx promptfoo eval --table
      - uses: promptfoo/actions/annotate@v1
        with:
          results: "promptfoo_output.json"

  deepeval:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pip install deepeval
      - run: deepeval test run test_eval.py

  ragas:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pip install ragas
      - run: python run_ragas_eval.py
```

---

## Резюме

```
Три инструмента — три слоя:

promptfoo  → Prompt layer: итерация, ассершены, red teaming
DeepEval   → Component layer: unit-тесты LLM-компонентов
Ragas      → RAG layer: качество retrieval + generation

Комбинируй все три для production-качества.
```

---

## Практическое задание

1. Установи promptfoo и напиши конфиг с 5 тестами на GPT-4o.
2. Напиши один DeepEval-тест на faithfulness.
3. Запусти Ragas на своём RAG-датасете.
4. Объедини все три в GitHub Actions workflow.

---

## Проверь себя

1. В чём разница между promptfoo, DeepEval и Ragas?
2. Какой инструмент лучше для RAG-метрик?
3. Какой слой покрывает promptfoo?
4. Зачем нужны три разных инструмента, если все делают evaluation?

---

## Ссылки

- [[02-promptfoo-deep]] — следующий урок: promptfoo deep dive
- [[../../../prompt-engineering/15-evals-benchmarks/15-evals-benchmarks]] — теория evals
- [[../../../prompt-engineering/08-evaluation-security-production/08-evaluation-security-production]] — evaluation basics
