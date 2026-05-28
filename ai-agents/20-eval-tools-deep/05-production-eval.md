---
created: 2026-05-28
tags: [course/eval-tools-deep, production, infrastructure, ci-cd, kubernetes, dashboard]
status: active
---

# Урок 20.5: Production Eval Infrastructure

> [!quote] Ключевая идея
> В production evaluation — это не «запустил тесты перед деплоем». Это конвейер: golden dataset собирается из логов, evals бегут на каждом PR, результаты хранятся в базе, дрифт детектится автоматически, качество регрессии видно на дашборде.

---

## 1. Архитектура Production Eval

```
                    ┌─────────────────────┐
                    │  Golden Dataset DB  │
                    │  (PostgreSQL + S3)  │
                    └────────┬────────────┘
                             │
PR ──► CI/CD Pipeline ──► Eval Runner ──► Results DB ──► Dashboard
          │                     │
          ▼                     ▼
    Quality Gate          Metrics Store
    (pass/fail)           (Prometheus)
```

### Компоненты

```python
class EvalInfrastructure:
    """Production eval инфраструктура."""

    def __init__(self):
        self.golden_dataset = GoldenDataset()
        self.eval_runner = EvalRunner()
        self.results_store = ResultsStore()
        self.drift_detector = DriftDetector()
        self.dashboard = Dashboard()
```

---

## 2. Golden Dataset Management

```python
import json
from datetime import datetime, timedelta
from typing import Any


class GoldenDataset:
    """Управление golden dataset для регрессионных тестов."""

    def __init__(self, connection_string: str = "postgresql://..."):
        self.db = Database(connection_string)

    async def collect_from_logs(self, days: int = 7, min_score: float = 0.8) -> list[dict]:
        """Собирает тестовые кейсы из production логов.

        Фильтр: только запросы с high-confidence (user feedback thumbs up,
        no escalations, resolved = true).
        """
        query = """
            SELECT input, output, context, metadata
            FROM agent_logs
            WHERE created_at > NOW() - INTERVAL %s
              AND (feedback_score >= %s OR resolved = true)
              AND NOT flagged
            ORDER BY RANDOM()
            LIMIT 100
        """
        raw_cases = await self.db.query(query, days, min_score)

        cases = []
        for row in raw_cases:
            cases.append({
                "question": row["input"],
                "answer": row["output"],
                "contexts": json.loads(row["context"]),
                "metadata": {
                    "source": "production",
                    "timestamp": row["created_at"],
                    "feedback_score": row.get("feedback_score"),
                },
            })

        return cases

    async def add_golden_case(self, case: dict, verified_by: str = "auto"):
        """Добавляет кейс в golden dataset с версионированием."""

        await self.db.execute("""
            INSERT INTO golden_dataset (question, answer, contexts, ground_truth, verified_by, version)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, case["question"], case["answer"], json.dumps(case["contexts"]),
            case.get("ground_truth"), verified_by, self._current_version())

    async def get_test_suite(self, version: str = "latest", count: int = 50) -> list[dict]:
        """Получает сбалансированный тестовый набор."""

        # Стратификация: 60% golden + 25% adversarial + 15% edge
        golden = await self.db.query("""
            SELECT * FROM golden_dataset
            WHERE version = %s AND category = 'golden'
            ORDER BY RANDOM() LIMIT %s
        """, version, int(count * 0.6))

        adversarial = await self.db.query("""
            SELECT * FROM golden_dataset
            WHERE version = %s AND category = 'adversarial'
            ORDER BY RANDOM() LIMIT %s
        """, version, int(count * 0.25))

        edge = await self.db.query("""
            SELECT * FROM golden_dataset
            WHERE version = %s AND category = 'edge'
            ORDER BY RANDOM() LIMIT %s
        """, version, int(count * 0.15))

        return golden + adversarial + edge

    def _current_version(self) -> str:
        return datetime.now().strftime("%Y.%m.%d")
```

---

## 3. Eval Runner

```python
import asyncio
from concurrent.futures import ThreadPoolExecutor


class EvalRunner:
    """Запуск evals на CI/CD или по расписанию."""

    def __init__(self, tools: dict):
        self.tools = tools  # {"promptfoo": ..., "deepeval": ..., "ragas": ...}
        self.executor = ThreadPoolExecutor(max_workers=4)

    async def run_eval_suite(self, dataset: list[dict]) -> dict:
        """Запускает все eval инструменты на датасете."""

        tasks = []

        if "promptfoo" in self.tools:
            tasks.append(self._run_promptfoo(dataset))
        if "deepeval" in self.tools:
            tasks.append(self._run_deepeval(dataset))
        if "ragas" in self.tools:
            tasks.append(self._run_ragas(dataset))

        results = await asyncio.gather(*tasks)
        merged = self._merge_results(results)

        return merged

    async def _run_promptfoo(self, dataset: list[dict]) -> dict:
        """Запуск promptfoo на датасете."""

        config = self._build_promptfoo_config(dataset)
        with open("/tmp/promptfooconfig.yaml", "w") as f:
            yaml.dump(config, f)

        proc = await asyncio.create_subprocess_exec(
            "npx", "promptfoo", "eval",
            "--config", "/tmp/promptfooconfig.yaml",
            "--output", "/tmp/promptfoo_results.json",
            stdout=asyncio.subprocess.PIPE,
        )
        await proc.wait()

        with open("/tmp/promptfoo_results.json") as f:
            return json.load(f)

    async def _run_deepeval(self, dataset: list[dict]) -> dict:
        """Запуск DeepEval на датасете."""
        from deepeval import assert_test
        from deepeval.test_case import LLMTestCase
        from deepeval.metrics import FaithfulnessMetric, HallucinationMetric

        results = []
        for case in dataset:
            test_case = LLMTestCase(
                input=case["question"],
                actual_output=case["answer"],
                retrieval_context=case.get("contexts", []),
            )
            metric = FaithfulnessMetric(threshold=0.7)
            try:
                assert_test(test_case, [metric])
                results.append({"passed": True, "score": metric.score})
            except AssertionError:
                results.append({"passed": False, "score": metric.score})

        return {"deepeval": results}

    async def _run_ragas(self, dataset: list[dict]) -> dict:
        """Запуск Ragas на датасете."""
        from ragas import evaluate
        from ragas.metrics import faithfulness, context_recall
        from datasets import Dataset

        ds = Dataset.from_dict({
            "question": [c["question"] for c in dataset],
            "answer": [c["answer"] for c in dataset],
            "contexts": [c.get("contexts", []) for c in dataset],
            "ground_truth": [c.get("ground_truth", "") for c in dataset],
        })

        scores = evaluate(ds, metrics=[faithfulness, context_recall])
        return {"ragas": dict(scores)}
```

---

## 4. Results Store & Dashboard

```python
class ResultsStore:
    """Хранилище результатов evals с трендами."""

    def __init__(self):
        self.db = Database("postgresql://...")

    async def save_results(self, run_id: str, results: dict, metadata: dict):
        """Сохраняет результаты прогона."""

        await self.db.execute("""
            INSERT INTO eval_runs (run_id, timestamp, results, metadata)
            VALUES (%s, NOW(), %s, %s)
        """, run_id, json.dumps(results), json.dumps(metadata))

    async def get_trend(self, metric: str, days: int = 30) -> list[dict]:
        """Тренд метрики за период."""

        rows = await self.db.query("""
            SELECT timestamp, results->%s as value
            FROM eval_runs
            WHERE timestamp > NOW() - INTERVAL %s
            ORDER BY timestamp
        """, metric, timedelta(days=days))

        return [{"date": r["timestamp"], "value": r["value"]} for r in rows]

    async def get_regression_report(self, since_version: str) -> dict:
        """Сравнение текущего прогона с baseline."""

        current = await self.db.query("""
            SELECT results FROM eval_runs
            ORDER BY timestamp DESC LIMIT 1
        """)
        baseline = await self.db.query("""
            SELECT results FROM eval_runs
            WHERE metadata->>'version' = %s
            ORDER BY timestamp DESC LIMIT 1
        """, since_version)

        return self._diff_results(current[0]["results"], baseline[0]["results"])
```

### Dashboard (пример текстового дашборда)

```python
class Dashboard:
    """Текстовый дашборд для CI/CD вывода."""

    def render(self, store: ResultsStore) -> str:
        last_run = store.get_last_run()
        trends = store.get_trends()

        return f"""
┌─ Eval Dashboard ──────────────────────────────────────┐
│ Last run: {last_run['timestamp']}                          │
│ Suite:    {last_run['suite_name']:<20s}                 │
│                                                         │
│ Metrics:                                                │
│   Faithfulness:     {trends['faithfulness']:.2f} (Δ{trends['faithfulness_delta']:+.2f})    │
│   Answer Relevancy: {trends['relevancy']:.2f} (Δ{trends['relevancy_delta']:+.2f})      │
│   Context Recall:   {trends['recall']:.2f} (Δ{trends['recall_delta']:+.2f})        │
│   Cost per call:    ${trends['cost']:.4f} (Δ{trends['cost_delta']:+.4f})          │
│                                                         │
│ Quality Gate: {'✅ PASSED' if last_run['passed'] else '❌ FAILED'}                               │
│ Failures: {last_run['failures']} / {last_run['total']} tests                            │
└─────────────────────────────────────────────────────────┘"""
```

---

## 5. Drift Detection

```python
class DriftDetector:
    """Автоматическое обнаружение дрифта качества."""

    def __init__(self, window: int = 7, threshold: float = 0.1):
        self.window = window
        self.threshold = threshold

    async def check_drift(self, store: ResultsStore) -> list[dict]:
        """Проверяет дрифт по всем метрикам за последнюю неделю."""

        metrics = ["faithfulness", "answer_relevancy", "context_recall", "cost"]
        drifts = []

        for metric in metrics:
            trend = await store.get_trend(metric, days=self.window)
            if len(trend) < 2:
                continue

            # Линейная регрессия для определения тренда
            scores = [t["value"] for t in trend]
            slope = self._linear_slope(scores)

            if abs(slope) > self.threshold:
                drifts.append({
                    "metric": metric,
                    "slope": slope,
                    "direction": "declining" if slope < 0 else "improving",
                    "severity": "critical" if abs(slope) > self.threshold * 2 else "warning",
                    "recommendation": self._get_recommendation(metric, slope),
                })

        return drifts

    def _linear_slope(self, values: list[float]) -> float:
        """Приблизительный наклон (first-last / N)."""
        if len(values) < 2:
            return 0.0
        return (values[-1] - values[0]) / len(values)

    def _get_recommendation(self, metric: str, slope: float) -> str:
        recs = {
            "faithfulness": "Проверь качество retrieval или обнови промпт",
            "answer_relevancy": "Проверь system prompt на деградацию",
            "context_recall": "Увеличь top_k или обнови эмбеддинги",
            "cost": "Оптимизируй model tier или настрой кэш",
        }
        return recs.get(metric, "Проверь компонент")
```

---

## 6. Kubernetes CronJob

```yaml
# eval-cronjob.yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: nightly-eval
spec:
  schedule: "0 6 * * *"   # Каждый день в 6:00
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: eval-runner
            image: eval-runner:latest
            env:
            - name: OPENAI_API_KEY
              valueFrom:
                secretKeyRef:
                  name: api-keys
                  key: openai
            command:
            - python
            - run_nightly_evals.py
            resources:
              requests:
                memory: "2Gi"
                cpu: "1"
              limits:
                memory: "4Gi"
                cpu: "2"
          restartPolicy: OnFailure
```

---

## Резюме

```
Production Eval Infrastructure:

1. Golden Dataset — сбор из production логов + версионирование
2. Eval Runner — promptfoo + DeepEval + Ragas параллельно
3. Results Store — PostgreSQL, тренды, история
4. Drift Detection — автоматическое обнаружение деградации
5. Dashboard — CI/CD output + Grafana
6. CronJob — ежедневный прогон
```

---

## Практическое задание

1. Реализуй GoldenDataset со сбором кейсов из логов (минимум 20).

2. Настрой EvalRunner для параллельного запуска трёх инструментов.

3. Создай ResultsStore с трекингом трендов за 7 дней.

4. Добавь DriftDetector с алертом при падении faithfulness >10%.

---

## Проверь себя

1. Как собирается golden dataset из production логов?
2. Какие 3 слоя eval runner запускает параллельно?
3. Как детектится дрифт качества?
4. Зачем нужен Kubernetes CronJob для evals?

---

## Ссылки

- [[01-landscape]] — обзор инструментов
- [[02-promptfoo-deep]] — promptfoo deep dive
- [[03-deepeval-deep]] — DeepEval deep dive
- [[04-ragas-deep]] — Ragas deep dive
- [[06-eval-pipeline]] — следующий урок: building eval pipeline
- [[../../../12-quality-evolution/01-agent-evaluation]] — теория evaluation
