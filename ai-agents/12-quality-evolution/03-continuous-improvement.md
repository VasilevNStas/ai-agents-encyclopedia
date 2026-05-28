---
created: 2026-05-28
tags: [course/quality-evolution, ci-cd, feedback-loop, monitoring, versioning]
status: active
---

# Урок 45: Continuous Improvement

> [!quote] Ключевая идея
> AI-агент не заканчивается на деплое. Он начинает новую жизнь: пользователи дают обратную связь, логи накапливаются, метрики меняются. Continuous improvement — это инженерный процесс, который превращает сырые данные в улучшения агента.

---

## Feedback Loop: пользовательская обратная связь

Обратная связь — топливо для улучшений. Без неё ты не знаешь, что менять.

### Типы обратной связи

```python
@dataclass
class Feedback:
    session_id: str
    user_id: str
    score: int               # 1-5
    comment: str | None
    category: str            # "accuracy" | "speed" | "safety" | "other"
    timestamp: datetime
    agent_version: str
    task: str
    agent_response: str


class FeedbackCollector:
    def __init__(self, storage_path: str = "feedback/"):
        self.path = Path(storage_path)
        self.path.mkdir(exist_ok=True)

    def collect(self, feedback: Feedback):
        timestamp = feedback.timestamp.strftime("%Y%m%d")
        filepath = self.path / f"feedback-{timestamp}.jsonl"
        with open(filepath, "a") as f:
            f.write(feedback.to_json() + "\n")

    def get_by_category(self, category: str) -> list[Feedback]:
        results = []
        for file in self.path.glob("*.jsonl"):
            with open(file) as f:
                for line in f:
                    fb = Feedback.from_json(line.strip())
                    if fb.category == category:
                        results.append(fb)
        return results

    def satisfaction_trend(self, days: int = 30) -> list[dict]:
        cutoff = datetime.utcnow() - timedelta(days=days)
        daily_scores: dict[str, list[int]] = {}

        for file in self.path.glob("*.jsonl"):
            with open(file) as f:
                for line in f:
                    fb = Feedback.from_json(line.strip())
                    if fb.timestamp >= cutoff:
                        day = fb.timestamp.strftime("%Y-%m-%d")
                        daily_scores.setdefault(day, []).append(fb.score)

        return [
            {"date": day, "avg_score": sum(scores)/len(scores), "count": len(scores)}
            for day, scores in sorted(daily_scores.items())
        ]

    def low_score_alerts(self, threshold: int = 2) -> list[Feedback]:
        """Собирает фидбек с низкими оценками для немедленного анализа."""
        alerts = []
        for file in self.path.glob("*.jsonl"):
            with open(file) as f:
                for line in f:
                    fb = Feedback.from_json(line.strip())
                    if fb.score <= threshold:
                        alerts.append(fb)
        return alerts
```

| Тип фидбека | Источник | Действие |
|-------------|----------|----------|
| Thumbs up/down | UI агента | Немедленная метрика |
| Комментарий | Форма после сессии | Качественный анализ |
| Автоматический | LLM-as-Judge | Мониторинг качества |
| Метрики деградации | Система мониторинга | Автоматический алерт |

---

## Log Analysis: поиск проблемных паттернов

Логи — второй источник инсайтов. Автоматический анализ выявляет паттерны, которые не видны в единичных feedback.

```python
class LogAnalyzer:
    def __init__(self, log_dir: str = "logs/"):
        self.log_dir = Path(log_dir)

    def find_error_patterns(self, lookback_hours: int = 24) -> list[dict]:
        cutoff = datetime.utcnow() - timedelta(hours=lookback_hours)
        patterns: dict[str, int] = {}

        for file in self.log_dir.glob("agent-*.jsonl"):
            with open(file) as f:
                for line in f:
                    entry = json.loads(line.strip())
                    ts = datetime.fromisoformat(entry["timestamp"])
                    if ts < cutoff:
                        continue
                    if entry.get("error"):
                        error_type = entry["error"]["type"]
                        patterns[error_type] = patterns.get(error_type, 0) + 1

        return [
            {"type": etype, "count": count}
            for etype, count in sorted(patterns.items(), key=lambda x: -x[1])
        ]

    def find_loop_patterns(self) -> list[dict]:
        """Находит сессии, где агент зациклился (повторяет действия)."""
        loops = []
        for file in self.log_dir.glob("agent-*.jsonl"):
            with open(file) as f:
                lines = [json.loads(line.strip()) for line in f]

            # Группируем по session_id
            sessions: dict[str, list[dict]] = {}
            for entry in lines:
                sid = entry["session_id"]
                sessions.setdefault(sid, []).append(entry)

            for sid, entries in sessions.items():
                actions = [e["action"] for e in entries if "action" in e]
                if self._is_looping(actions):
                    loops.append({
                        "session_id": sid,
                        "actions": actions,
                        "count": len(actions),
                    })
        return loops

    def _is_looping(self, actions: list[str], threshold: int = 5) -> bool:
        if len(actions) < threshold * 2:
            return False
        # Проверяем, повторяется ли последние N действий
        recent = actions[-threshold:]
        return len(set(recent)) <= 2

    def generate_report(self) -> str:
        errors = self.find_error_patterns()
        loops = self.find_loop_patterns()
        return f"""
=== Log Analysis Report ===
Error patterns: {len(errors)}
{chr(10).join(f"  {e['type']}: {e['count']}" for e in errors[:5])}

Loop detections: {len(loops)}
Sessions affected: {len(set(l['session_id'] for l in loops))}
"""
```

### Анализ тональности логов

```python
def analyze_session_quality(log_entries: list[dict]) -> float:
    """Оценивает качество сессии по логам (0.0-1.0)."""
    quality_signals = {
        "tool_call_success": 0.2,
        "user_correction": -0.3,
        "repeated_action": -0.2,
        "error": -0.4,
        "task_completed": 0.3,
    }
    score = 0.5  # baseline
    for entry in log_entries:
        for signal, delta in quality_signals.items():
            if signal in entry.get("tags", []):
                score += delta
    return max(0.0, min(1.0, score))
```

---

## Iteration Cycle: Plan → Observe → Analyze → Improve → Deploy → Observe

Цикл непрерывного улучшения начинается не с наблюдения, а с **планирования**. Каждое изменение должно быть осознанным.

### Planning phase

Перед каждым изменением:

1. **Определи scope** — что именно меняем и почему
2. **Напиши acceptance criteria** — как узнаем, что стало лучше
3. **Оцени риски** — что может сломаться
4. **Задокументируй out-of-scope** — что НЕ меняем в этой итерации

```python
class ChangePlan:
    def __init__(self, title: str):
        self.title = title
        self.scope: list[str] = []
        self.out_of_scope: list[str] = []
        self.acceptance_criteria: list[str] = []
        self.risks: list[str] = []

    def add_scope(self, item: str):
        self.scope.append(item)

    def add_acceptance(self, criteria: str):
        self.acceptance_criteria.append(criteria)

    def is_ready(self) -> bool:
        return len(self.scope) > 0 and len(self.acceptance_criteria) > 0

    def summary(self) -> str:
        return f"""
Change: {self.title}
Scope: {', '.join(self.scope)}
Out of scope: {', '.join(self.out_of_scope) or 'none'}
Acceptance: {', '.join(self.acceptance_criteria)}
Risks: {', '.join(self.risks) or 'none'}
"""


plan = ChangePlan("Improve safety guardrails")
plan.add_scope("добавить проверку PII в output guardrails")
plan.add_scope("обновить тесты на PII-сценарии")
plan.add_out_of_scope("менять input guardrails")
plan.add_acceptance("hallucination rate не вырос")
plan.add_acceptance("PII detection recall > 0.95")
plan.add_risk("может увеличиться latency ответа")
print(plan.summary())
```

### Вертикальные срезы

Предпочитай вертикальные срезы (одна фича целиком: API + логика + тесты) горизонтальным (сначала весь backend — через неделю весь frontend):

```python
# ❌ Горизонтально: весь backend сразу
stage_1 = "build_all_APIs"
stage_2 = "build_all_frontend"     # интеграция сломана неделями

# ✅ Вертикально: одна фича целиком
stage_1 = "feature_search: API + UI + tests"
stage_2 = "feature_checkout: API + UI + tests"  # каждая работает
```

### Delivery philosophy

```
Favor:                         Over:
  small stages                  giant rewrites
  explicit assumptions          implicit decisions
  visible progress              hidden complexity
  stable contracts              unverified output
  end-to-end validation         layer-by-layer delivery
```

### Полный цикл

```
┌──────────────────────────────────────────────┐
│  PLAN                                         │
│  └─ scope, criteria, risks, out-of-scope     │
│         │                                     │
│         ▼                                     │
│  OBSERVE                                      │
│  └─ логи, feedback, метрики, алерты          │
│         │                                     │
│         ▼                                     │
│  ANALYZE                                      │
│  └─ LogAnalyzer, тренды, приоритеты          │
│         │                                     │
│         ▼                                     │
│  IMPROVE                                      │
│  └─ промпт, модель, стратегия, код           │
│         │                                     │
│         ▼                                     │
│  DEPLOY                                       │
│  └─ canary, A/B test, rollout               │
│         │                                     │
│         ▼                                     │
│  OBSERVE (снова)                              │
│  └─ метрики не деградировали? → цикл         │
└──────────────────────────────────────────────┘
```

```python
class IterationCycle:
    def __init__(
        self,
        feedback_collector: FeedbackCollector,
        log_analyzer: LogAnalyzer,
        regression_tests: RegressionTestSuite,
        deployer: CanaryDeployer,
    ):
        self.feedback = feedback_collector
        self.log_analyzer = log_analyzer
        self.regression = regression_tests
        self.deployer = deployer

    def run_cycle(self, agent_version: str, improvement: str):
        print(f"=== CYCLE: {improvement} ===")

        # OBSERVE
        alerts = self.feedback.low_score_alerts(threshold=2)
        errors = self.log_analyzer.find_error_patterns()
        loops = self.log_analyzer.find_loop_patterns()
        print(f"  Observe: {len(alerts)} alerts, {len(errors)} errors, {len(loops)} loops")

        # ANALYZE
        prioritized = self._prioritize(alerts, errors, loops)
        print(f"  Analyze: top priority = {prioritized[0] if prioritized else 'none'}")

        # IMPROVE & DEPLOY
        if prioritized:
            self.regression.run_all()
            result = self.deployer.deploy(
                agent_version,
                ExperimentConfig(
                    name=improvement[:30],
                    control_version="current",
                    treatment_version=agent_version,
                    traffic_split=0.1,
                    min_sample_size=100,
                    metrics=["completion_rate", "cost"],
                    duration_hours=24,
                ),
            )
            return result

    def _prioritize(self, alerts, errors, loops) -> list[str]:
        # Приоритет: safety > accuracy > efficiency
        priorities = []
        if any("safety" in str(a) for a in alerts):
            priorities.append("safety issues detected")
        if errors:
            priorities.append(f"top error: {errors[0]['type']}")
        if loops:
            priorities.append(f"{len(loops)} loop patterns")
        return priorities
```

> [!important] Цикл не должен быть ручным
> Observe, analyze, deploy — каждый этап может и должен быть автоматизирован. Чем короче цикл, тем быстрее агент эволюционирует.

---

## Regression Testing: не сломай старое

Каждое изменение — риск сломать то, что работало. Regression-тесты защищают от регрессий.

```python
class RegressionTestSuite:
    def __init__(self, test_cases: list[dict], eval_pipeline: EvalPipeline):
        self.test_cases = test_cases
        self.eval_pipeline = eval_pipeline

    def run_all(self) -> dict:
        results = self.eval_pipeline.run()
        regressions = [
            r for r in results["evaluations"]
            if r["evaluation"]["score"] < 0.7
        ]

        report = {
            "total": len(results["evaluations"]),
            "passed": sum(1 for r in results["evaluations"] if r["evaluation"]["score"] >= 0.7),
            "regressions": len(regressions),
            "failed_cases": [
                {
                    "task": r["task"],
                    "score": r["evaluation"]["score"],
                    "explanation": r["evaluation"]["explanation"],
                }
                for r in regressions
            ],
            "quality_gates_passed": results["passed"],
        }

        if report["regressions"] > 0:
            print(f"WARNING: {report['regressions']} regressions detected")
        return report

    def run_quick(self) -> dict:
        """Быстрый прогон (только golden dataset, без judge)."""
        passed = 0
        for case in self.test_cases[:10]:  # только первые 10
            result = self.eval_pipeline.agent.run(case["task"])
            if case["expected"] in result:
                passed += 1
        return {"quick_passed": passed, "quick_total": min(10, len(self.test_cases))}
```

**Когда прогонять регрессию:**

| Триггер | Тип прогона | Время |
|---------|-------------|-------|
| Каждый коммит | Quick (golden only) | < 5 min |
| PR в main | Full (все сценарии) | < 30 min |
| Перед релизом | Full + judge | < 1h |
| Ночной прогон | Полный + adversarial | < 2h |

---

## Versioning агентов

Агент — это код + промпты + конфиги + модель. Всё это должно версионироваться.

```python
class AgentVersionManager:
    def __init__(self, storage_path: str = "agents/"):
        self.path = Path(storage_path)
        self.path.mkdir(exist_ok=True)

    def create_version(
        self,
        major: int,
        minor: int,
        patch: int,
        config: dict,
        prompt: str,
        model: str,
        changelog: str,
    ) -> str:
        version = f"v{major}.{minor}.{patch}"
        version_dir = self.path / version
        version_dir.mkdir(exist_ok=True)

        with open(version_dir / "config.json", "w") as f:
            json.dump(config, f, indent=2)
        with open(version_dir / "prompt.md", "w") as f:
            f.write(prompt)
        with open(version_dir / "manifest.json", "w") as f:
            json.dump({
                "version": version,
                "model": model,
                "changelog": changelog,
                "created": datetime.utcnow().isoformat(),
            }, f, indent=2)

        return version

    def get_version(self, version: str) -> dict | None:
        version_dir = self.path / version
        if not version_dir.exists():
            return None
        with open(version_dir / "manifest.json") as f:
            return json.load(f)

    def list_versions(self) -> list[str]:
        return sorted(
            [d.name for d in self.path.iterdir() if d.is_dir()],
            key=lambda v: [int(x) for x in v.lstrip("v").split(".")],
        )
```

### Семантическое версионирование для агента

```
vMAJOR.MINOR.PATCH

MAJOR — меняется стратегия (ReAct → Plan-and-Solve), модель, архитектура
MINOR — меняется промпт, добавляются инструменты, конфигурация
PATCH — меняется temperature, исправляются баги промпта

Пример:
  v1.0.0  → ReAct + DeepSeek + базовые guardrails
  v1.1.0  → + инструмент search, изменён system prompt
  v1.1.1  → понижен temperature с 0.7 до 0.3
  v2.0.0  → миграция на Plan-and-Solve
```

```python
def bump_version(current: str, change_type: str) -> str:
    """Автоматическое увеличение версии."""
    major, minor, patch = map(int, current.lstrip("v").split("."))
    if change_type == "major":
        return f"v{major + 1}.0.0"
    elif change_type == "minor":
        return f"v{major}.{minor + 1}.0"
    elif change_type == "patch":
        return f"v{major}.{minor}.{patch + 1}"
    else:
        raise ValueError(f"Unknown change type: {change_type}")
```

---

## Monitoring Dashboard

Метрики в реальном времени и алерты — глаза continuous improvement.

```python
class MonitoringDashboard:
    def __init__(self, metrics_store: str = "metrics/"):
        self.store = Path(metrics_store)
        self.store.mkdir(exist_ok=True)
        self.metrics: list[dict] = []

    def record_metric(self, name: str, value: float, tags: dict | None = None):
        entry = {
            "metric": name,
            "value": value,
            "tags": tags or {},
            "timestamp": datetime.utcnow().isoformat(),
        }
        self.metrics.append(entry)
        # Каждый час пишем в файл
        hour = datetime.utcnow().strftime("%Y%m%d-%H")
        with open(self.store / f"metrics-{hour}.jsonl", "a") as f:
            f.write(json.dumps(entry) + "\n")

    def get_current_metrics(self) -> dict:
        """Последние значения ключевых метрик."""
        last_hour = self.metrics[-100:] if len(self.metrics) > 100 else self.metrics
        result = {}
        for entry in last_hour:
            name = entry["metric"]
            if name not in result:
                result[name] = entry["value"]
        return result

    def check_alerts(self, thresholds: dict[str, float]) -> list[str]:
        alerts = []
        current = self.get_current_metrics()
        for metric, threshold in thresholds.items():
            if metric in current and current[metric] < threshold:
                alerts.append(f"ALERT: {metric} = {current[metric]:.3f} < {threshold}")
        return alerts


class AlertManager:
    def __init__(self, dashboard: MonitoringDashboard):
        self.dashboard = dashboard
        self.alert_config = {
            "completion_rate": 0.80,
            "hallucination_rate": 0.10,
            "avg_cost": 0.15,
            "p95_latency": 5.0,
        }

    def check_and_notify(self):
        alerts = self.dashboard.check_alerts(self.alert_config)
        for alert in alerts:
            self._send_notification(alert)
        return alerts

    def _send_notification(self, message: str):
        # В production: Slack, PagerDuty, email
        print(f"[NOTIFICATION] {message}")
```

---

## Anti-patterns Continuous Improvement

### 1. Чинить то, что не сломалось
```python
# ❌ "Давай обновим промпт, а то давно не меняли"
# Изменение без причины = риск регрессии

# ✅ Изменение на основе данных
alerts = feedback_collector.low_score_alerts(threshold=2)
if alerts:
    improve_prompt(alerts)
```

### 2. Отсутствие приоритизации
```python
# ❌ Чинить всё подряд, что нашёл LogAnalyzer
# Распыление ресурсов, ничего не доведено до конца

# ✅ Приоритет: safety > accuracy > cost > latency
priorities = [
    ("safety", stop_prompt_injection),
    ("accuracy", fix_hallucination_patterns),
    ("cost", optimize_model_selection),
]
```

### 3. Нет регрессии перед деплоем
```python
# ❌ Изменил промпт → задеплоил → сломал старые сценарии
# Пользователи страдают, пока ты чинишь

# ✅ RegressionTestSuite.run_all() перед каждым деплоем
```

### 4. Ручной цикл улучшений
```
❌ Читаешь логи руками → думаешь → правишь → деплоишь
→ Цикл занимает дни, теряются инсайты

✅ Автоматизированный цикл
→ LogAnalyzer сам находит паттерны
→ Алерты приходят в Slack
→ Regression прогоняется в CI
→ Версионирование автоматическое
```

---

## Проверь себя

1. Из каких 6 этапов состоит iteration cycle? Что добавилось?
2. Зачем нужен planning phase перед каждым изменением?
3. Что такое вертикальный срез и почему он предпочтительнее горизонтального?
4. Как работает семантическое версионирование для агентов (major.minor.patch)?
5. Какие метрики нужно мониторить в реальном времени?
6. Какой антипаттерн самый дорогой в continuous improvement?

---

## Практическое задание

1. Реализуй `FeedbackCollector`, который собирает оценки (1-5) и сохраняет в JSONL
2. Реализуй `LogAnalyzer`, который находит зацикливания в логах
3. Реализуй `RegressionTestSuite`, которая запускается перед деплоем
4. Настрой `AlertManager` на метрики: completion_rate < 0.8, avg_cost > 0.15
5. Пропиши changelog для перехода с v1.0.0 на v2.0.0

---

## Резюме

```
Continuous Improvement = planning + feedback + log analysis + regression + versioning + monitoring

Цикл:  Plan → Observe → Analyze → Improve → Deploy → Observe
Plan:      scope, acceptance criteria, risks, out-of-scope
Feedback:  thumbs, комментарии, автоматическая оценка
Logs:      error patterns, loops, quality score
Regression: quick (каждый коммит) + full (каждый PR)
Versioning: major (стратегия) / minor (промпт) / patch (параметры)
Monitoring: real-time метрики + алерты

Правило: планируй перед каждым изменением.
         Вертикальные срезы вместо горизонтальных.
         Приоритет: safety > accuracy > cost > latency.
         Цикл должен быть автоматическим.
         Регрессия — обязательна.
```

---

## Ссылки

- [[12-quality-evolution/01-agent-evaluation]] — метрики и eval pipeline
- [[12-quality-evolution/02-ab-testing]] — A/B тестирование и canary
- [[05-production/02-observability]] — observability и трассировка
- [[05-production/03-log-driven-development]] — LDD подход
- [[12-quality-evolution/01-agent-evaluation]] — code quality и review process
