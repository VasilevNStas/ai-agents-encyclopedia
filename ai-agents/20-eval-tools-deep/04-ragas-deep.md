---
created: 2026-05-28
tags: [course/eval-tools-deep, ragas, rag, metrics, retrieval]
status: active
---

# Урок 20.4: Ragas Deep Dive

> [!quote] Ключевая идея
> Ragas — единственный фреймворк, который декомпозирует качество RAG на 8 независимых метрик. Не просто «хороший ответ», а точность retrieval, полнота контекста, faithfulness генерации. Каждая метрика изолирует конкретный компонент пайплайна.

---

## 1. Архитектура Ragas

Ragas оценивает RAG по трём слоям:

```
RAG Pipeline:

Query ──► Retriever ──► Context ──► LLM ──► Answer
            │               │              │
     Context Precision  Context Recall   Faithfulness
     Context Relevancy                   Answer Relevancy
```

### 8 метрик Ragas

| Метрика | Слой | Что измеряет |
|---------|------|-------------|
| `faithfulness` | Generation | Ответ не противоречит контексту |
| `answer_relevancy` | Generation | Ответ релевантен вопросу |
| `answer_similarity` | Generation | Семантическая близость к эталону |
| `answer_correctness` | Generation | Фактическая правильность |
| `context_precision` | Retrieval | Все ли релевантные документы в контексте |
| `context_recall` | Retrieval | Не упущен ли важный контекст |
| `context_relevancy` | Retrieval | Нет ли шума в контексте |
| `aspect_critique` | Custom | Кастомные проверки (bias, safety) |

---

## 2. Быстрый старт

```python
# pip install ragas
from ragas import evaluate
from ragas.metrics import (
    faithfulness,
    answer_relevancy,
    context_precision,
    context_recall,
)
from datasets import Dataset

# Датасет: вопросы, ответы, контексты, эталоны
dataset = Dataset.from_dict({
    "question": [
        "What is the capital of France?",
        "Who invented Python?",
    ],
    "answer": [
        "Paris is the capital of France.",
        "Python was created by Guido van Rossum.",
    ],
    "contexts": [
        ["France's capital is Paris. It's known for the Eiffel Tower."],
        ["Guido van Rossum created Python in 1991 as a hobby project."],
    ],
    "ground_truth": [
        "Paris",
        "Guido van Rossum",
    ],
})

# Запуск всех метрик
results = evaluate(
    dataset=dataset,
    metrics=[
        faithfulness,
        answer_relevancy,
        context_precision,
        context_recall,
    ],
)

print(results)
# {'faithfulness': 0.95, 'answer_relevancy': 0.92,
#  'context_precision': 0.88, 'context_recall': 0.85}
```

---

## 3. Каждая метрика в деталях

### 3.1 Faithfulness — нет противоречий контексту

```python
from ragas.metrics import faithfulness

# Измеряет: сколько утверждений в ответе подтверждаются контекстом
# Ответ: "Paris is the capital and largest city of France."
# Контекст: "Paris is the capital of France."
# Score: 0.5 (одно утверждение не подтверждено — "largest city")

# Когда падает:
# 0.9-1.0: отлично
# 0.7-0.9: небольшие галлюцинации
# <0.7: серьёзные выдумки
```

### 3.2 Context Precision — релевантен ли контекст?

```python
from ragas.metrics import context_precision

# Измеряет: сколько документов в контексте релевантны вопросу
# Вопрос: "What is Python?"
# Контекст: ["Python is a language", "Python was created in 1991", "Snakes are reptiles"]
# Score: 0.66 (2 из 3 релевантны)

# Оптимизация:
#   Если precision низкий → улучши реранкер
#   Добавь порог схожести для фильтрации
```

### 3.3 Context Recall — ничего не упущено?

```python
from ragas.metrics import context_recall

# Измеряет: покрывает ли контекст эталонный ответ
# Вопрос: "Who created Python?"
# Контекст: ["Python is a programming language"]
# Эталон: "Guido van Rossum"
# Score: 0.0 (контекст не содержит ответа)

# Оптимизация:
#   Если recall низкий → увеличь top_k или улучши эмбеддинги
```

### 3.4 Answer Correctness — фактическая точность

```python
from ragas.metrics import answer_correctness

# Комбинирует:
#   - answer_similarity (semantic similarity to ground truth)
#   - factuality (каждый факт проверяется по ground truth)

# Лучшая метрика для end-to-end оценки RAG
# Требует ground_truth в датасете
```

---

## 4. Aspect Critique — кастомные проверки

```python
from ragas.metrics import AspectCritique

# Кастомная проверка на тон ответа
professional_metric = AspectCritique(
    name="professionalism",
    definition="Is the response professional and respectful?",
    strictness=3,  # 1-5
)

# Кастомная проверка на конфиденциальность
privacy_metric = AspectCritique(
    name="privacy",
    definition="Does the response avoid sharing personal or confidential information?",
    strictness=4,
)

dataset = Dataset.from_dict({
    "question": ["What is my account balance?"],
    "answer": ["I cannot access account information. Please contact support."],
    "contexts": [["Account balances are private."]],
})

results = evaluate(dataset, metrics=[professional_metric, privacy_metric])
```

---

## 5. RAG Pipeline Integration

```python
class RagasEvalPipeline:
    """Интеграция Ragas в RAG пайплайн."""

    def __init__(self, retriever, llm):
        self.retriever = retriever
        self.llm = llm

    async def query_and_evaluate(self, question: str, ground_truth: str) -> dict:
        """Запрос к RAG + автоматическая оценка."""

        # 1. Retrieve
        contexts = await self.retriever.retrieve(question)

        # 2. Generate
        context_text = "\n".join(c["content"] for c in contexts)
        answer = await self.llm.generate(
            f"Context: {context_text}\n\nQuestion: {question}"
        )

        # 3. Evaluate
        dataset = Dataset.from_dict({
            "question": [question],
            "answer": [answer],
            "contexts": [[c["content"] for c in contexts]],
            "ground_truth": [ground_truth],
        })

        scores = evaluate(dataset, metrics=[
            faithfulness, answer_relevancy,
            context_precision, context_recall,
            answer_correctness,
        ])

        # 4. Quality gate
        if scores["faithfulness"] < 0.7:
            # Retry с другим промптом или контекстом
            log(f"Low faithfulness: {scores['faithfulness']}, retrying...")
            answer = await self.llm.generate(
                f"Context: {context_text}\n\nQuestion: {question}\n"
                f"IMPORTANT: Only answer based on the context provided."
            )
            scores = evaluate(...)  # Re-evaluate

        return {
            "answer": answer,
            "scores": scores,
            "contexts": contexts,
        }
```

---

## 6. CI/CD Regression Suite

```python
# tests/rag_regression.py
import json
from ragas import evaluate
from datasets import Dataset


class RAGRegressionSuite:
    """Регрессионный тест RAG пайплайна."""

    def __init__(self, test_file: str = "rag_test_set.json"):
        with open(test_file) as f:
            self.test_cases = json.load(f)

    def run(self, rag_pipeline) -> dict:
        results = []

        for tc in self.test_cases:
            # Run RAG
            answer, contexts = rag_pipeline(tc["question"])

            # Evaluate
            dataset = Dataset.from_dict({
                "question": [tc["question"]],
                "answer": [answer],
                "contexts": [contexts],
                "ground_truth": [tc["ground_truth"]],
            })

            scores = evaluate(dataset, metrics=[
                faithfulness, answer_relevancy,
                context_precision, context_recall,
            ])

            results.append({
                "question": tc["question"],
                "faithfulness": scores["faithfulness"],
                "relevancy": scores["answer_relevancy"],
                "precision": scores["context_precision"],
                "recall": scores["context_recall"],
                "passed": scores["faithfulness"] > 0.7
                         and scores["context_recall"] > 0.7,
            })

        return {
            "total": len(results),
            "passed": sum(1 for r in results if r["passed"]),
            "avg_faithfulness": sum(r["faithfulness"] for r in results) / len(results),
            "avg_recall": sum(r["recall"] for r in results) / len(results),
            "results": results,
        }
```

---

## 7. Anti-patterns

```python
# ❌ Тестировать RAG без ground_truth
scores = evaluate(dataset, metrics=[faithfulness])
# Faithfulness не требует GT, но correctness — требует

# ❌ Игнорировать контекстные метрики
metrics = [faithfulness, answer_relevancy]
# Пропущен context_precision — retrieval может быть плохим

# ❌ Один тест на всё
# ✅ Минимум 50 тестов для статистической значимости

# ❌ Не обновлять датасет
# ✅ RAG тесты должны отражать реальные production-запросы
```

---

## Резюме

```
Ragas: 8 метрик для RAG

Retrieval layer:
  - context_precision: нет лишнего в контексте
  - context_recall: всё ли нужное в контексте
  - context_relevancy: контекст релевантен вопросу

Generation layer:
  - faithfulness: ответ по контексту
  - answer_relevancy: ответ по вопросу
  - answer_correctness: фактическая точность
  - answer_similarity: семантическая близость

Custom:
  - aspect_critique: tone, safety, bias, privacy
```

---

## Практическое задание

1. Установи Ragas и запусти на своём RAG-датасете 5 метрик.

2. Напиши AspectCritique для проверки «нет личного мнения».

3. Реализуй RAGRegressionSuite с 20 тестовыми кейсами.

4. Добавь quality gate: если faithfulness < 0.7 → retry с другим контекстом.

---

## Проверь себя

1. Какие 3 слоя RAG оценивает Ragas?
2. Чем context_precision отличается от context_recall?
3. Зачем нужна метрика answer_correctness?
4. Как работает AspectCritique?

---

## Ссылки

- [[01-landscape]] — обзор инструментов
- [[03-deepeval-deep]] — DeepEval deep dive
- [[05-production-eval]] — следующий урок: production eval инфраструктура
