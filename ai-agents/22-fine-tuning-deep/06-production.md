---
created: 2026-05-28
tags: [course/fine-tuning-deep, production, deployment, monitoring, evaluation]
status: active
---

# Урок 22.6: Production Fine-tuning: Deployment, Evaluation, Monitoring

> [!quote] Ключевая идея
> Fine-tuning в production — это не обучение, а конвейер: data collection → training → evaluation → deployment → monitoring → retrain. Каждый этап автоматизирован. Без этого fine-tuning — эксперимент, а не улучшение.

---

## 1. Production Pipeline

```python
class ProductionFineTunePipeline:
    """Полный production конвейер fine-tuning."""

    def __init__(self, config: dict):
        self.collector = DataCollector()
        self.trainer = FineTuneTrainer()
        self.evaluator = Evaluator()
        self.deployer = ModelDeployer()
        self.monitor = Monitor()

    async def run_pipeline(self):
        """Цикл production fine-tuning."""

        while True:
            # 1. Collect production data
            traces = await self.collector.collect_traces(days=7)

            # 2. Check if quality degraded
            drift = await self.monitor.check_drift()
            if not drift and len(traces) < 1000:
                await asyncio.sleep(3600 * 24)  # Wait a day
                continue

            # 3. Prepare dataset
            dataset = await self.collector.prepare_dataset(traces)

            # 4. Train
            model = await self.trainer.train(dataset)

            # 5. Evaluate
            scores = await self.evaluator.evaluate(model)
            if scores["overall"] < 0.8:
                log(f"Model failed evaluation: {scores}, skipping deployment")
                continue

            # 6. Canary deploy
            await self.deployer.canary_deploy(model, percentage=5)

            # 7. Monitor canary
            await self.monitor.watch_canary(hours=24)
            if await self.monitor.canary_passed():
                await self.deployer.full_rollout(model)
            else:
                await self.deployer.rollback()
```

---

## 2. Deployment Strategies

```python
class ModelDeployer:
    """Деплой fine-tuned моделей."""

    STRATEGIES = {
        "adapter_only": "LoRA adapter + base model (3-50MB)",
        "merged": "Merged model (14GB for 7B)",
        "quantized": "GGUF/AWQ quantized (4-8GB)",
        "api": "OpenAI fine-tuning API",
    }

    async def canary_deploy(self, model, percentage: int = 5):
        """Canary: 5% трафика на новую модель."""

        config = {
            "model_a": {"id": "production-current", "weight": 100 - percentage},
            "model_b": {"id": "ft-candidate", "weight": percentage},
        }

        await self.update_router_config(config)
        log(f"Canary deploy: {percentage}% traffic to ft-candidate")

    async def full_rollout(self, model):
        """Полный rollout."""

        config = {
            "model_a": {"id": "ft-candidate", "weight": 100},
        }
        await self.update_router_config(config)
        log("Full rollout complete")

    async def rollback(self):
        """Rollback до предыдущей версии."""
        config = {
            "model_a": {"id": "production-current", "weight": 100},
        }
        await self.update_router_config(config)
        log("Rollback to production-current")
```

---

## 3. A/B Evaluation

```python
class ABFineTuneEval:
    """A/B сравнение base и fine-tuned модели."""

    async def run_experiment(self, base_model, ft_model, test_set: list[dict]) -> dict:
        results = {"base": [], "ft": []}

        for test in test_set:
            for label, model in [("base", base_model), ("ft", ft_model)]:
                t_start = time.perf_counter()
                response = await model.generate(test["prompt"])
                latency = time.perf_counter() - t_start

                results[label].append({
                    "response": response,
                    "latency_ms": latency * 1000,
                    "tool_used": self._extract_tool(response),
                    "cost": self._estimate_cost(response),
                    "user_feedback": test.get("expected"),
                })

        # Статистическая значимость
        return {
            "tool_accuracy": self._compare_metric(results, "tool_correct"),
            "latency_p50": self._compare_metric(results, "latency_ms", np.median),
            "cost_per_call": self._compare_metric(results, "cost", np.mean),
            "statistical_significance": self._ttest(results),
        }

    def _ttest(self, results: dict) -> dict:
        """t-test для определения значимости."""
        from scipy import stats
        base_scores = [self._score(r) for r in results["base"]]
        ft_scores = [self._score(r) for r in results["ft"]]
        t_stat, p_value = stats.ttest_ind(ft_scores, base_scores)
        return {
            "t_statistic": round(t_stat, 3),
            "p_value": round(p_value, 4),
            "significant": p_value < 0.05,
        }
```

---

## 4. Monitoring Fine-tuned Models

```python
class FineTuneMonitor:
    """Мониторинг качества fine-tuned модели."""

    def __init__(self):
        self.metrics = {
            "tool_accuracy": RollingMetric(window=1000),
            "user_satisfaction": RollingMetric(window=1000),
            "latency_ms": RollingMetric(window=1000),
            "cost_per_call": RollingMetric(window=1000),
            "hallucination_rate": RollingMetric(window=1000),
        }

    async def observe(self, trace: dict):
        """Записывает метрику из production трассы."""

        self.metrics["tool_accuracy"].update(
            1 if trace["tool_used"] == trace["expected_tool"] else 0
        )
        self.metrics["latency_ms"].update(trace.get("latency_ms", 0))
        self.metrics["cost_per_call"].update(trace.get("cost", 0))
        self.metrics["user_satisfaction"].update(
            1 if trace.get("feedback") == "positive" else 0
        )

    async def check_drift(self, threshold: float = 0.05) -> bool:
        """Проверка дрифта: не упало ли качество."""

        current = self.metrics["tool_accuracy"].mean()
        baseline = self.metrics["tool_accuracy"].baseline()

        drift = baseline - current
        if drift > threshold:
            log(f"⚠️ Tool accuracy drift: {drift:.1%} (baseline: {baseline:.1%}, current: {current:.1%})")
            return True
        return False
```

---

## 5. Cost Tracking

```python
class FineTuneCostTracker:
    """Total cost of ownership для fine-tuning."""

    def tco(self, model_size: str = "7B", method: str = "lora") -> dict:
        """Total cost of ownership за 12 месяцев."""

        costs = {
            "7B": {
                "lora": {"training": 50, "inference_per_1m": 0.50},
                "full": {"training": 1000, "inference_per_1m": 1.00},
                "api_ft": {"training": 500, "inference_per_1m": 2.00},
            },
            "70B": {
                "lora": {"training": 500, "inference_per_1m": 5.00},
                "full": {"training": 10000, "inference_per_1m": 10.00},
                "api_ft": {"training": 5000, "inference_per_1m": 8.00},
            },
        }

        model_costs = costs.get(model_size, costs["7B"])
        method_costs = model_costs.get(method, model_costs["lora"])
        monthly_inference_calls = 100000

        monthly_inference = (monthly_inference_calls * 2000 / 1_000_000) * method_costs["inference_per_1m"]
        yearly = method_costs["training"] + monthly_inference * 12

        return {
            "training_cost": method_costs["training"],
            "monthly_inference": round(monthly_inference, 2),
            "yearly_total": round(yearly, 2),
            "cost_per_call": round(monthly_inference / monthly_inference_calls, 6),
        }
```

---

## Резюме

```
Production Fine-tuning Pipeline:

Collect ──► Prepare ──► Train ──► Eval ──► Canary ──► Full ──► Monitor
   │          │          │        │          │         │        │
  logs      filter    LoRA/     A/B       5%       100%     drift
  traces    augment   QLoRA     test                            + auto-
                                                               retrain

Checklist:
  ☐ Data collection из production логов
  ☐ Quality gates перед деплоем
  ☐ Canary: 5% → 100%
  ☐ A/B сравнение с base моделью
  ☐ Мониторинг дрифта
  ☐ Auto-rollback при падении метрик
  ☐ TCO tracking
```

---

## Практическое задание

1. Реализуй ProductionFineTunePipeline с canary deploy.

2. Настрой A/B evaluation: base vs fine-tuned, t-test.

3. Добавь drift detection с auto-retrain trigger.

4. Рассчитай TCO для LoRA на 7B модели (100K calls/day).

---

## Проверь себя

1. Какие этапы включает production fine-tuning pipeline?

2. Как работает canary deploy для моделей?

3. Как определить статистическую значимость улучшения?

4. Что делать при обнаружении дрифта?

---

## Ссылки

- [[02-lora-deep]] — LoRA deep dive
- [[03-rlhf-dpo]] — RLHF/DPO/GRPO
- [[04-data-preparation]] — data preparation
- [[05-agent-finetuning]] — fine-tuning для агентов
- [[../../../08-decision-architecture/03-cost-optimization]] — cost optimization
