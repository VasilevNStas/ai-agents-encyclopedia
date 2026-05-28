---
created: 2026-05-28
tags: [course/quality-evolution, ab-testing, experimentation, canary]
status: active
---

# Урок 44: A/B Testing & Experimentation

> [!quote] Ключевая идея
> Изменение промпта, модели или стратегии может как улучшить, так и сломать агента. A/B-тестирование — единственный способ узнать, стало ли лучше, без гадания. Одна группа видит новую версию, другая — старую, а метрики решают.

---

## Зачем A/B тестировать агентов

В традиционном софте A/B тесты — стандарт. В мире AI-агентов это ещё важнее, потому что:

| Что меняется | Пример | Влияние |
|-------------|--------|---------|
| Промпт | «будь кратким» vs «отвечай подробно» | Длина ответа, satisfaction |
| Модель | DeepSeek vs Claude vs GPT | Качество, стоимость, latency |
| Стратегия | ReAct vs Plan-and-Solve | Число шагов, успешность |
| Инструменты | grep vs ast-grep | Скорость поиска, точность |
| Память | sliding window vs summary | Полнота контекста, cost |

Без A/B-теста ты не знаешь, что именно повлияло на результат. Могло повезти с запросом.

```python
# ❌ Нельзя: "вчера агент работал лучше, поменяем обратно"
# Нет контроля: могли измениться запросы пользователей

# ✅ Нужно: рандомизированное A/B-сравнение на одном трафике
```

---

## Экспериментальная методология

### Контрольная и тестовая группы

```python
@dataclass
class ExperimentConfig:
    name: str
    control_version: str     # например "agent-v1.2.0"
    treatment_version: str   # например "agent-v1.3.0-beta"
    traffic_split: float     # доля трафика на treatment (0.0-1.0)
    min_sample_size: int     # минимальный размер выборки
    metrics: list[str]       # целевые метрики
    duration_hours: int      # длительность эксперимента

    def validate(self):
        assert 0.0 < self.traffic_split < 1.0
        assert self.min_sample_size >= 100
        assert self.duration_hours >= 24
```

**Ключевые принципы:**
1. **Рандомизация** — каждый пользователь/сессия случайно назначается в группу
2. **Изоляция** — меняется только одна переменная за раз
3. **Достаточный размер** — выборка должна быть статистически значимой
4. **Фиксированная длительность** — минимум 24 часа (учёт суточных паттернов)

### Пример: A/B сравнение двух промптов

```python
class ABTestFramework:
    def __init__(self, config: ExperimentConfig):
        self.config = config
        self.results: dict[str, list[dict]] = {
            "control": [],
            "treatment": [],
        }

    def assign_group(self, session_id: str) -> str:
        hash_val = hash(session_id) % 1000
        if hash_val < self.config.traffic_split * 1000:
            return "treatment"
        return "control"

    def record_result(
        self,
        group: str,
        session_id: str,
        metrics: dict,
    ):
        self.results[group].append({
            "session_id": session_id,
            **metrics,
        })

    def analyze(self) -> dict:
        control_metrics = self._aggregate(self.results["control"])
        treatment_metrics = self._aggregate(self.results["treatment"])

        return {
            "experiment": self.config.name,
            "control": control_metrics,
            "treatment": treatment_metrics,
            "differences": {
                metric: treatment_metrics[metric] - control_metrics[metric]
                for metric in self.config.metrics
            },
            "is_significant": self._check_significance(
                self.results["control"],
                self.results["treatment"],
            ),
        }

    def _aggregate(self, group_data: list[dict]) -> dict:
        n = len(group_data)
        if n == 0:
            return {}
        return {
            metric: sum(d[metric] for d in group_data) / n
            for metric in self.config.metrics
        }

    def _check_significance(
        self,
        control: list[dict],
        treatment: list[dict],
    ) -> bool:
        if len(control) < self.config.min_sample_size:
            return False
        if len(treatment) < self.config.min_sample_size:
            return False
        # t-test на каждой метрике
        for metric in self.config.metrics:
            c_vals = [d[metric] for d in control]
            t_vals = [d[metric] for d in treatment]
            p_val = self._ttest(c_vals, t_vals)
            if p_val > 0.05:
                return False
        return True

    def _ttest(self, a: list[float], b: list[float]) -> float:
        """Двухвыборочный t-test. Возвращает p-value."""
        import math
        n1, n2 = len(a), len(b)
        mean1, mean2 = sum(a)/n1, sum(b)/n2
        var1 = sum((x - mean1)**2 for x in a) / (n1 - 1)
        var2 = sum((x - mean2)**2 for x in b) / (n2 - 1)
        se = math.sqrt(var1/n1 + var2/n2)
        if se == 0:
            return 1.0
        t_stat = (mean1 - mean2) / se
        df = min(n1 - 1, n2 - 1)
        # аппроксимация p-value через t-распределение
        p = self._t_cdf(-abs(t_stat), df) * 2
        return p

    def _t_cdf(self, x: float, df: int) -> float:
        """Приближённая CDF t-распределения."""
        import math
        a = df / 2.0
        b = 0.5
        z = df / (df + x*x)
        return 1 - 0.5 * self._betainc(a, b, z)

    def _betainc(self, a: float, b: float, x: float) -> float:
        """Неполная бета-функция (аппроксимация)."""
        # Упрощённая реализация. В production используй scipy.stats.betainc
        return x ** a * (1 - x) ** b / a
```

> [!warning] Статистическая значимость ≠ практическая значимость
> P-value < 0.05 говорит, что разница не случайна. Но разница в 0.1% completion rate может быть неважна для бизнеса. Смотри на effect size.

---

## Метрики сравнения

| Метрика | Что измеряет | A/B | Когда значимо |
|---------|-------------|-----|---------------|
| Win rate | Доля побед treatment над control | `wins / total` | > 55% |
| Cost difference | Изменение стоимости | `cost_t - cost_c` | > $0.01 |
| Latency delta | Изменение времени ответа | `lat_t - lat_c` | > 200ms |
| User retention | Возвращаемость пользователей | `retention_t - retention_c` | > 5% |
| Hallucination lift | Изменение уровня галлюцинаций | `hal_c - hal_t` | > 2% |

```python
class ExperimentTracker:
    def __init__(self, experiment_name: str):
        self.name = experiment_name
        self.events: list[dict] = []

    def log_event(self, session_id: str, group: str, metric: str, value: float):
        self.events.append({
            "experiment": self.name,
            "session_id": session_id,
            "group": group,
            "metric": metric,
            "value": value,
            "timestamp": datetime.utcnow().isoformat(),
        })

    def summary(self) -> dict:
        from collections import defaultdict
        grouped: dict = defaultdict(lambda: defaultdict(list))
        for event in self.events:
            grouped[event["group"]][event["metric"]].append(event["value"])

        report = {}
        for group, metrics in grouped.items():
            report[group] = {}
            for metric, values in metrics.items():
                report[group][metric] = {
                    "mean": sum(values) / len(values),
                    "count": len(values),
                    "min": min(values),
                    "max": max(values),
                }
        return report
```

---

## Постепенная раскатка: Canary Deployment для агентов

Canary deployment — это A/B-тест с постепенным увеличением доли трафика на новую версию.

```python
class CanaryDeployer:
    def __init__(self, stages: list[float]):
        self.stages = stages            # [0.05, 0.10, 0.25, 0.50, 1.0]
        self.current_stage = 0
        self.ab_test = None

    def deploy(self, agent_version: str, config: ExperimentConfig):
        self.ab_test = ABTestFramework(config)

        for stage_pct in self.stages:
            config.traffic_split = stage_pct
            result = self._run_stage(stage_pct)
            self.current_stage = self.stages.index(stage_pct)

            if not result["is_significant"] and self.current_stage > 0:
                self._rollback(f"Stage {stage_pct:.0%}: no significance")
                return False

            print(f"Stage {stage_pct:.0%}: {result['differences']}")

        print(f"Deploy {agent_version}: full rollout")
        return True

    def _run_stage(self, split: float) -> dict:
        # Симуляция: собираем N сэмплов
        n_samples = max(100, int(1000 * split))
        for i in range(n_samples):
            group = "treatment" if random.random() < split else "control"
            self.ab_test.record_result(
                group=group,
                session_id=f"session-{i}",
                metrics={
                    "completion_rate": random.gauss(0.90, 0.05),
                    "cost": random.gauss(0.05, 0.01),
                },
            )
        return self.ab_test.analyze()

    def _rollback(self, reason: str):
        print(f"Rollback: {reason}")
```

**Схема canary развёртывания:**

```
Step 1: 5% трафика на новую версию → 24h наблюдения
Step 2: 25% → 24h наблюдения          (если метрики стабильны)
Step 3: 50% → 12h наблюдения          (если метрики стабильны)
Step 4: 100% → полный rollout         (если метрики стабильны)
                                     (иначе — rollback)
```

> [!important] Canary требует автоматического отката
> Если completion rate падает ниже порога — rollback должен происходить без участия человека. Время реакции — минуты, не часы.

---

## Online vs Offline Evaluation

| Характеристика | Online evaluation | Offline evaluation |
|---------------|------------------|--------------------|
| Данные | Реальный трафик | Исторические логи |
| Риск | Реальные пользователи страдают | Нет риска |
| Скорость | Часы-дни | Минуты |
| Обратная связь | Поведение пользователей | Labeled датасет |
| Достоверность | Высокая (реальные условия) | Средняя (replay bias) |
| Когда использовать | Финальное решение | Быстрое прототипирование |

```python
def choose_eval_mode(change_type: str) -> str:
    """Выбирает режим оценки в зависимости от типа изменения."""
    risk_map = {
        "prompt_tweak":      "offline",    # низкий риск, быстрая итерация
        "model_switch":      "online",     # высокий риск, нужны реальные данные
        "strategy_change":   "online",     # высокий риск
        "tool_addition":     "offline",    # средний риск, можно на логах
        "guardrail_change":  "online",     # критично: безопасность
    }
    return risk_map.get(change_type, "offline")
```

---

## Anti-patterns A/B тестирования

### 1. Тестировать слишком много переменных сразу
```python
# ❌ A/B тест: новый промпт + другая модель + изменённый RAG
# Невозможно понять, что именно повлияло на результат

# ✅ Изолированные эксперименты
exp1 = ABTestFramework(config_for_prompt)
exp2 = ABTestFramework(config_for_model)
```

### 2. Не учитывать сезонность
```python
# ❌ Сравнение понедельника и воскресенья
# В понедельник пользователи активнее — метрики выше

# ✅ Сравнение одинаковых периодов
# Понедельник vs понедельник, утро vs утро
```

### 3. Прекращать тест рано
```python
# ❌ "После 50 запросов treatment выигрывает, откатываем control"
# Слишком малая выборка — результат может быть случайным

# ✅ Дождаться min_sample_size и min_duration
```

### 4. Игнорировать cost
```python
# ❌ Treatment даёт +5% accuracy, но стоит в 3 раза дороже
# В production cost может перевесить улучшение качества

# ✅ Всегда включай cost в метрики A/B теста
```

---

## Проверь себя

1. Какие 4 принципа экспериментальной методологии нужно соблюдать?
2. Чем A/B тест отличается от canary deployment?
3. Когда использовать online evaluation, а когда offline?
4. Почему p-value < 0.05 — это необходимое, но не достаточное условие?
5. Какой антипаттерн чаще всего встречается в A/B тестировании агентов?

---

## Практическое задание

1. Реализуй `ABTestFramework`, который сравнивает две версии агента по completion_rate и cost
2. Настрой canary deployment с этапами `[0.1, 0.3, 0.5, 1.0]`
3. Проведи A/B тест: замени модель с `deepseek-chat` на `claude-sonnet-4` на 100 запросах
4. Определи, значима ли разница (p-value < 0.05)

---

## Резюме

```
A/B тестирование агента:

Методология:
  - контрольная vs тестовая группа
  - рандомизация + изоляция + размер + длительность

Метрики:
  win rate, cost delta, latency delta, retention, hallucination lift

Canary deployment:
  5% → 25% → 50% → 100% с автоматическим откатом

Online vs Offline:
  offline — быстрое прототипирование
  online — финальное решение с реальным трафиком

Правило: одна переменная за раз,
         достаточная выборка,
         cost всегда в метриках.
```

---

## Ссылки

- [[12-quality-evolution/01-agent-evaluation]] — метрики и quality gates
- [[12-quality-evolution/03-continuous-improvement]] — continuous improvement
- [[05-production/04-resilience]] — circuit breaker для canary
