---
created: 2026-05-28
tags: [course/data, data-engineering, datasets, versioning]
status: active
---

# Урок 37: Data Engineering for AI

> [!quote] Ключевая идея
> AI-архитектор работает с данными каждый день: промпты, evaluation-сеты, feedback loops. Data engineering для AI — это не про ETL и базы данных, а про качество и версионирование датасетов, от которых зависит поведение агента.

---

## Почему data engineering — задача AI-архитектора

Традиционно data engineering занимается пайплайнами, warehouses и озёрами данных. AI-архитектору нужен другой срез:

| Тип данных | Зачем | Что хранит |
|---|---|---|
| Prompt datasets | Итерация промптов, A/B тесты | Промпты, ответы, метаданные |
| Evaluation datasets | Оценка качества агента | Вопросы, эталонные ответы, чеклисты |
| Feedback logs | Улучшение агента по real-world данным | Диалоги, оценки пользователя, исправления |
| Ground truth | Контроль регрессий | Правильные ответы для тестовых сценариев |

> [!warning]
> Если датасеты не версионируются — ты не сможешь воспроизвести ни один тест. Агент, который вчера работал идеально, сегодня может сломаться, и ты не узнаешь почему.

---

## Prompt datasets: сбор, аннотация, версионирование

Prompt-датасет — это коллекция пар (промпт, ответ) с метаданными.

```python
import json
import hashlib
from datetime import datetime
from typing import Optional

class PromptExample:
    def __init__(
        self,
        prompt: str,
        expected_behavior: str,
        tags: list[str] = None,
        system_prompt: str = "",
        model: str = "",
    ):
        self.prompt = prompt
        self.expected_behavior = expected_behavior
        self.tags = tags or []
        self.system_prompt = system_prompt
        self.model = model
        self.created_at = datetime.utcnow().isoformat()
        self.hash = self._compute_hash()

    def _compute_hash(self) -> str:
        raw = f"{self.prompt}|{self.expected_behavior}|{self.system_prompt}"
        return hashlib.sha256(raw.encode()).hexdigest()[:12]

    def to_dict(self) -> dict:
        return {
            "hash": self.hash,
            "prompt": self.prompt,
            "expected_behavior": self.expected_behavior,
            "tags": self.tags,
            "system_prompt": self.system_prompt,
            "model": self.model,
            "created_at": self.created_at,
        }


class PromptDataset:
    def __init__(self, name: str, version: str = "0.1.0"):
        self.name = name
        self.version = version
        self.examples: list[PromptExample] = []

    def add(self, example: PromptExample) -> None:
        if any(ex.hash == example.hash for ex in self.examples):
            return  # дедупликация по хешу
        self.examples.append(example)

    def filter_by_tag(self, tag: str) -> list[PromptExample]:
        return [ex for ex in self.examples if tag in ex.tags]

    def save(self, path: str) -> None:
        data = {
            "name": self.name,
            "version": self.version,
            "count": len(self.examples),
            "examples": [ex.to_dict() for ex in self.examples],
        }
        with open(path, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    @classmethod
    def load(cls, path: str) -> "PromptDataset":
        with open(path) as f:
            data = json.load(f)
        ds = cls(data["name"], data["version"])
        for item in data["examples"]:
            ex = PromptExample(
                prompt=item["prompt"],
                expected_behavior=item["expected_behavior"],
                tags=item["tags"],
                system_prompt=item["system_prompt"],
                model=item.get("model", ""),
            )
            ex.hash = item["hash"]
            ex.created_at = item["created_at"]
            ds.examples.append(ex)
        return ds


# Использование
ds = PromptDataset("agent-followup", version="1.0.0")
ds.add(PromptExample(
    prompt="Напиши краткое резюме встречи",
    expected_behavior="Должен выделить ключевые решения и action items",
    tags=["summarization", "meeting"],
    system_prompt="Ты — ассистент для заметок",
))
ds.add(PromptExample(
    prompt="What is the capital of France?",
    expected_behavior="Должен ответить Paris, без лишних деталей",
    tags=["qa", "simple"],
))
ds.save("datasets/agent-followup-v1.json")
```

---

## Evaluation datasets: ground truth для тестирования агентов

Evaluation-сет отличается от prompt-датасета тем, что содержит **критерии проверки** и **эталонные ответы**.

```python
from enum import Enum
from typing import Callable

class EvalMetric(Enum):
    EXACT_MATCH = "exact_match"
    CONTAINS_KEY = "contains_key"
    SEMANTIC_SIMILARITY = "semantic_similarity"
    FUNCTIONAL_CHECK = "functional_check"

class EvalExample:
    def __init__(
        self,
        task: str,
        ground_truth: str,
        metric: EvalMetric,
        context: dict = None,
        tags: list[str] = None,
    ):
        self.task = task
        self.ground_truth = ground_truth
        self.metric = metric
        self.context = context or {}
        self.tags = tags or []

class EvaluationSet:
    def __init__(self, name: str, agent_version: str):
        self.name = name
        self.agent_version = agent_version
        self.examples: list[EvalExample] = []

    def add(self, example: EvalExample) -> None:
        self.examples.append(example)

    def run(self, agent_fn: Callable[[str, dict], str]) -> dict:
        results = []
        passed = 0
        for ex in self.examples:
            response = agent_fn(ex.task, ex.context)
            ok = self._check(ex, response)
            results.append({
                "task": ex.task,
                "expected": ex.ground_truth,
                "got": response,
                "passed": ok,
            })
            if ok:
                passed += 1
        total = len(self.examples)
        return {
            "total": total,
            "passed": passed,
            "failed": total - passed,
            "score": passed / total if total else 0,
            "results": results,
        }

    def _check(self, ex: EvalExample, response: str) -> bool:
        if ex.metric == EvalMetric.EXACT_MATCH:
            return response.strip() == ex.ground_truth.strip()
        if ex.metric == EvalMetric.CONTAINS_KEY:
            return ex.ground_truth in response
        return False


# Пример использования
eval_set = EvaluationSet("agent-v1-tests", agent_version="1.0.0")
eval_set.add(EvalExample(
    task="Переведи на английский: Привет, как дела?",
    ground_truth="Hello, how are you?",
    metric=EvalMetric.CONTAINS_KEY,
    tags=["translation"],
))

def dummy_agent(task: str, ctx: dict) -> str:
    return "Hello, how are you?"

report = eval_set.run(dummy_agent)
print(f"Score: {report['score']:.0%}")  # Score: 100%
```

---

## Data curation: чистка, дедупликация, балансировка

> [!important]
> Грязный датасет хуже, чем отсутствие датасета. Он создаёт ложное чувство безопасности: тесты проходят, а в production агент ведёт себя непредсказуемо.

```python
import random

class DatasetCurator:
    def __init__(self, examples: list[dict]):
        self.examples = examples

    def deduplicate(self, key: str = "prompt") -> "DatasetCurator":
        seen = set()
        unique = []
        for ex in self.examples:
            val = ex.get(key, "")
            h = hashlib.sha256(val.encode()).hexdigest()
            if h not in seen:
                seen.add(h)
                unique.append(ex)
        self.examples = unique
        return self

    def remove_short(self, min_length: int = 5, key: str = "prompt") -> "DatasetCurator":
        self.examples = [
            ex for ex in self.examples
            if len(ex.get(key, "")) >= min_length
        ]
        return self

    def balance_labels(
        self, label_key: str = "label", max_per_class: int = 100
    ) -> "DatasetCurator":
        groups: dict[str, list] = {}
        for ex in self.examples:
            label = ex.get(label_key, "unknown")
            groups.setdefault(label, []).append(ex)
        balanced = []
        for label, group in groups.items():
            sampled = random.sample(group, min(max_per_class, len(group)))
            balanced.extend(sampled)
        random.shuffle(balanced)
        self.examples = balanced
        return self

    def stats(self) -> dict:
        total = len(self.examples)
        avg_len = sum(len(ex.get("prompt", "")) for ex in self.examples) / total
        labels = {}
        for ex in self.examples:
            label = ex.get("label", "unknown")
            labels[label] = labels.get(label, 0) + 1
        return {
            "total": total,
            "avg_prompt_length": round(avg_len, 1),
            "labels": labels,
        }


# Пример
raw = [
    {"prompt": "Привет", "label": "greeting"},
    {"prompt": "Привет", "label": "greeting"},  # дубликат
    {"prompt": "Как дела?", "label": "greeting"},
    {"prompt": "Что такое AI?", "label": "qa"},
    {"prompt": "", "label": "empty"},  # слишком короткий
]

curator = DatasetCurator(raw)
curator.deduplicate().remove_short(min_length=3)
print(curator.stats())
# {'total': 3, 'avg_prompt_length': 8.0, 'labels': {'greeting': 2, 'qa': 1}}
```

---

## Data pipeline: feedback loop для агента

Real-world данные от пользователей должны превращаться в улучшения агента:

```python
class FeedbackPipeline:
    """
    Пайплайн сбора feedback в production и конвертации в evaluation-сеты.
    """
    def __init__(self, dataset: PromptDataset, eval_set: EvaluationSet):
        self.dataset = dataset
        self.eval_set = eval_set
        self.feedback_log: list[dict] = []

    def record_interaction(
        self,
        prompt: str,
        response: str,
        user_rating: int,  # 1-5
        corrected_response: str = "",
    ) -> None:
        entry = {
            "prompt": prompt,
            "response": response,
            "rating": user_rating,
            "corrected": corrected_response,
            "timestamp": datetime.utcnow().isoformat(),
        }
        self.feedback_log.append(entry)

        if user_rating >= 4:
            return  # хороший ответ — не добавляем

        # Плохой ответ → добавляем в prompt dataset как негативный пример
        self.dataset.add(PromptExample(
            prompt=prompt,
            expected_behavior=corrected_response or response,
            tags=["feedback", "needs-improvement"],
        ))

        # Добавляем в eval set для регрессионного теста
        if corrected_response:
            self.eval_set.add(EvalExample(
                task=prompt,
                ground_truth=corrected_response,
                metric=EvalMetric.CONTAINS_KEY,
                tags=["regression", "user-feedback"],
            ))

    def export_feedback(self, path: str) -> None:
        with open(path, "w") as f:
            json.dump(self.feedback_log, f, indent=2, ensure_ascii=False)


# Цикл улучшения:
# 1. Собрать feedback → 2. Обновить dataset → 3. Перетестировать → 4. Улучшить промпт
pipeline = FeedbackPipeline(
    dataset=PromptDataset("production-v2", version="2.1.0"),
    eval_set=EvaluationSet("regression-v2", agent_version="2.1.0"),
)

pipeline.record_interaction(
    prompt="Напиши письмо клиенту",
    response="Дорогой клиент, спасибо за обращение",
    user_rating=2,
    corrected_response="Уважаемый клиент, спасибо за ваше обращение.",
)
```

---

## Anti-patterns

### 1. Data leakage (тестовые данные в обучении)

```python
# ❌ Датасет разбит неправильно — тестовые данные просочились в train
all_data = load_all()  # одни и те же данные
random.shuffle(all_data)
train = all_data[:80]
test = all_data[80:]
# test может содержать те же промпты, что и train!

# ✅ Правильное разбитие: по уникальным задачам или хешам
from sklearn.model_selection import train_test_split

unique_tasks = list({ex["prompt"]: ex for ex in all_data}.values())
train, test = train_test_split(unique_tasks, test_size=0.2, random_state=42)
```

### 2. Грязные датасеты

```python
# ❌ Нет валидации — можно добавить что угодно
dataset.examples.append({"prompt": None, "response": 123})

# ✅ Валидация при добавлении
class ValidatedExample:
    def __init__(self, prompt: str, response: str):
        if not prompt or not isinstance(prompt, str):
            raise ValueError(f"Invalid prompt: {prompt!r}")
        if not response or not isinstance(response, str):
            raise ValueError(f"Invalid response: {response!r}")
        self.prompt = prompt
        self.response = response
```

### 3. Отсутствие версионирования

```python
# ❌ Нет версии — непонятно, какой датасет использовался
dataset.save("dataset.json")

# ✅ Версия в имени файла и в метаданных
dataset.version = "2.1.0"
dataset.save(f"dataset-v{dataset.version}.json")
```

---

## Проверь себя

1. Чем evaluation dataset отличается от prompt dataset? Какие метрики проверки существуют?
2. Почему дедупликация датасета критична для evaluation? Что произойдёт, если 30% датасета — дубликаты?
3. Как data leakage влияет на результаты тестирования агента? Приведи пример.
4. Зачем нужен feedback loop между production и dataset? Как плохой ответ пользователя превращается в тест?

---

## Практическое задание

Собери evaluation dataset для агента, который отвечает на вопросы по документации. Реализуй:

1. Класс `DocQAEvaluator`, который загружает JSON с парами (вопрос, эталонный ответ, URL документации)
2. Метод `run(agent_fn)` — вызывает агента, сравнивает ответы по exact match и contains_key
3. Метод `report()` — выводит статистику: всего, passed, failed, score
4. Функцию `curate(raw_data)` — удаляет дубликаты и вопросы короче 10 символов

---

## Резюме

```
Data Engineering для AI:
- Prompt datasets: пары (промпт, поведение) для итерации
- Evaluation datasets: (задача, ground truth, метрика) для тестов
- Data curation: дедупликация, чистка, балансировка — обязательны
- Feedback loop: production → dataset → тесты → улучшение

Ключевые правила:
- Всегда версионируй датасеты (semver)
- Никогда не смешивай train и test
- Валидируй каждый пример при добавлении
- Храни feedback от пользователей — это gold mine
```

---

## Ссылки

- [[06-prompt-engineering/01-system-prompts]] — промпты как данные
- [[08-decision-architecture/01-fine-tuning-rag-prompting]] — выбор подхода на основе данных
- [[10-data-communication/02-agent-communication]] — как агенты обмениваются данными
- [[10-data-communication/03-human-in-the-loop]] — человек оценивает ответы агента