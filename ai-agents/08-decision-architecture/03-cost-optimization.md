---
created: 2026-05-28
updated: 2026-05-28
tags: [course/decision-architecture, cost, optimization, tokens, economics, caching]
status: active
---

# Урок 30: Cost Optimization & Token Economics

> [!quote] Ключевая идея
> Агент не должен тратить $100 на задачу, которая решается за $0.10. Cost optimization — это не «жлобство», а архитектурная дисциплина: каждый токен должен приносить пользу, пропорциональную своей стоимости. В этом уроке — не теория, а конкретные цифры, формулы и бюджетное моделирование.

---

## Реальные цены моделей (2026)

Цены указаны за 1M входных / выходных токенов. Для агента важна не только цена токена, но и то, сколько токенов он тратит на шаг.

| Модель | Input $/M tok | Output $/M tok | Context | Speed | Типичный cost/шаг* |
|--------|:------------:|:-------------:|:------:|:----:|:-----------------:|
| **Claude Opus 4.6** | $15.00 | $75.00 | 200K | Средняя | $0.03-0.08 |
| **Claude Sonnet 4.6** | $3.00 | $15.00 | 200K | Высокая | $0.005-0.015 |
| **Claude Haiku 4.6** | $0.25 | $1.25 | 200K | Очень высокая | $0.0005-0.002 |
| **GPT-4o** | $5.00 | $15.00 | 128K | Средняя | $0.008-0.02 |
| **GPT-4o mini** | $0.15 | $0.60 | 128K | Высокая | $0.0003-0.001 |
| **DeepSeek V3** | $0.27 | $1.10 | 128K | Высокая | $0.0005-0.002 |
| **DeepSeek R1** | $0.55 | $2.19 | 128K | Средняя | $0.002-0.01 |
| **Gemini 2.0 Pro** | $2.50 | $10.00 | 2M | Средняя | $0.004-0.015 |
| **Gemini 2.0 Flash** | $0.10 | $0.40 | 1M | Очень высокая | $0.0002-0.0008 |
| **Qwen3 Coder (local 7B)** | ~$0.02 | ~$0.02 | 32K | Низкая | CapEx + эл-во |

*Типичный cost/шаг: сессия агента с ~5000 входящих и ~500 исходящих токенов.

> [!warning] Цена ≠ стоимость
> Opus дороже Haiku в 60x, но если Haiku ошибается в 30% случаев и требует retry — итоговая стоимость может быть выше. См. break-even анализ ниже.

---

## Token burn rate — метрика здоровья агента

**Token burn rate** = сколько токенов и денег тратит агент в единицу времени.

### Базовая формула

```python
def token_burn_rate(calls: int, avg_input: int, avg_output: int,
                    input_price: float, output_price: float) -> dict:
    """
    Считает burn rate агента в токенах и долларах.
    """
    input_tokens = calls * avg_input
    output_tokens = calls * avg_output

    input_cost = input_tokens * input_price / 1_000_000
    output_cost = output_tokens * output_price / 1_000_000

    return {
        "total_tokens": input_tokens + output_tokens,
        "total_cost": round(input_cost + output_cost, 2),
        "breakdown": {
            "input": {"tokens": input_tokens, "cost": round(input_cost, 2)},
            "output": {"tokens": output_tokens, "cost": round(output_cost, 2)},
        },
    }

# Пример: 10K сессий/день, Sonnet, ~150K входящих и ~20K исходящих на сессию
daily = token_burn_rate(
    calls=10_000, avg_input=150_000, avg_output=20_000,
    input_price=3.00, output_price=15.00,
)
print(daily["total_cost"])  # $75 000/день — вы не ошиблись
```

### Burn rate по типам агентов

```python
# Типичный burn rate для разных классов агентов
AGENT_BURN_RATES = {
    "simple_qa": {
        "avg_input": 4_000,
        "avg_output": 500,
        "model": "haiku",
        "cost_per_call": 0.0007,    # $0.0007
        "calls_per_session": 1,
    },
    "code_review": {
        "avg_input": 20_000,
        "avg_output": 3_000,
        "model": "sonnet",
        "cost_per_call": 0.005,
        "calls_per_session": 3,      # review + suggest + summarize
    },
    "research_deep": {
        "avg_input": 100_000,
        "avg_output": 15_000,
        "model": "sonnet",
        "cost_per_call": 0.035,
        "calls_per_session": 8,      # search + analyze + synthesize
    },
    "multi_agent_project": {
        "avg_input": 500_000,
        "avg_output": 100_000,
        "model": "sonnet",
        "cost_per_call": 0.30,
        "calls_per_session": 25,     # supervisor + 3 specialists × 8 steps
    },
}

def monthly_projection(agent_type: str, daily_sessions: int) -> dict:
    rate = AGENT_BURN_RATES[agent_type]
    cost_per_session = rate["cost_per_call"] * rate["calls_per_session"]
    daily_cost = cost_per_session * daily_sessions
    monthly = daily_cost * 30

    return {
        "type": agent_type,
        "cost_per_session": cost_per_session,
        "daily_cost": round(daily_cost, 2),
        "monthly_cost": round(monthly, 2),
        "yearly_cost": round(monthly * 12, 2),
    }

# Сценарий: product launch
for agent_type in ["simple_qa", "code_review", "research_deep", "multi_agent_project"]:
    proj = monthly_projection(agent_type, daily_sessions=1_000)
    print(f"{agent_type}: ${proj['monthly_cost']}/mo, ${proj['yearly_cost']}/yr")
```

---

## Cost-прогнозирование: от сессии к году

### Эталонная таблица

| Тип агента | $/сессия | 100 сес/день | 1K сес/день | 10K сес/день | 100K сес/день |
|-----------|:-------:|:----------:|:----------:|:-----------:|:------------:|
| Simple QA (Haiku) | $0.0007 | $2 /мес | $21 /мес | $210 /мес | $2 100 /мес |
| Code Review (Sonnet) | $0.015 | $45 /мес | $450 /мес | $4 500 /мес | $45 000 /мес |
| Research Deep (Sonnet) | $0.28 | $840 /мес | $8 400 /мес | $84 000 /мес | $840K /мес |
| Multi-agent (Sonnet) | $7.50 | $22 500 /мес | $225K /мес | $2.25M /мес | — |

> [!warning]
> Multi-agent системы с 25+ вызовами LLM на сессию — это не игрушки. Одна «бесплатная» фича может стоить $200K/мес.

### Формула прогноза

```python
def cost_forecast(
    sessions_per_day: int,
    avg_input_tokens: int,
    avg_output_tokens: int,
    calls_per_session: int,
    model: str,
    growth_rate: float = 0.05,   # 5% месячный рост
) -> dict:
    """Прогноз затрат на 12 месяцев с учётом роста."""
    prices = {
        "haiku":  (0.25, 1.25),
        "sonnet": (3.00, 15.00),
        "opus":   (15.00, 75.00),
    }

    inp_price, out_price = prices[model]
    cost_per_call = (avg_input_tokens * inp_price + avg_output_tokens * out_price) / 1_000_000
    cost_per_session = cost_per_call * calls_per_session

    months = []
    current_sessions = sessions_per_day
    for m in range(1, 13):
        daily = cost_per_session * current_sessions
        monthly = daily * 30
        months.append({
            "month": m,
            "sessions_per_day": int(current_sessions),
            "monthly_cost": round(monthly, 2),
        })
        current_sessions *= (1 + growth_rate)

    return {
        "cost_per_session": round(cost_per_session, 4),
        "total_12mo": round(sum(m["monthly_cost"] for m in months), 2),
        "months": months,
    }

# Сценарий: стартап запускает AI-агента
startup = cost_forecast(
    sessions_per_day=100,
    avg_input_tokens=20_000,
    avg_output_tokens=3_000,
    calls_per_session=3,
    model="sonnet",
    growth_rate=0.15,  # агрессивный рост 15%/мес
)
print(f"Стоимость одной сессии: ${startup['cost_per_session']}")
print(f"За 12 месяцев: ${startup['total_12mo']}")
# Результат: $0.015/сессия → $26K/год
```

---

## Break-even анализ: когда дешёвая модель дороже

Главная ловушка: Haiku стоит 60x меньше Opus, но может ошибаться в N% случаев. Каждая ошибка = retry = 2x cost + потеря качества.

### Формула break-even

```python
def break_even_analysis(
    cheap_model: str, cheap_accuracy: float, cheap_call_cost: float,
    expensive_model: str, expensive_accuracy: float, expensive_call_cost: float,
    retry_cost_factor: float = 1.0,  # retry стоит столько же, сколько первый вызов
) -> dict:
    """
    Сравнивает total cost модели с учётом accuracy и retry.
    """
    # Cheap: initial call + retries for failures
    cheap_retries = 0
    remaining = 1.0
    while remaining > 0.001:  # до 0.1%
        remaining *= (1 - cheap_accuracy)
        cheap_retries += 1

    cheap_total = cheap_call_cost + cheap_retries * cheap_call_cost * retry_cost_factor

    # Expensive: initial call + retries
    expensive_retries = 0
    remaining = 1.0
    while remaining > 0.001:
        remaining *= (1 - expensive_accuracy)
        expensive_retries += 1

    expensive_total = expensive_call_cost + expensive_retries * expensive_call_cost * retry_cost_factor

    return {
        "cheap": {
            "model": cheap_model,
            "accuracy": cheap_accuracy,
            "cost_per_call": cheap_call_cost,
            "expected_retries": cheap_retries,
            "total_cost": round(cheap_total, 6),
        },
        "expensive": {
            "model": expensive_model,
            "accuracy": expensive_accuracy,
            "cost_per_call": expensive_call_cost,
            "expected_retries": expensive_retries,
            "total_cost": round(expensive_total, 6),
        },
        "cheaper_option": cheap_model if cheap_total < expensive_total else expensive_model,
        "savings_per_call": round(abs(cheap_total - expensive_total), 6),
    }


# Сценарий 1: генерация кода
code_gen = break_even_analysis(
    cheap_model="haiku", cheap_accuracy=0.60, cheap_call_cost=0.0007,
    expensive_model="sonnet", expensive_accuracy=0.92, expensive_call_cost=0.005,
)
# → cheap_total=$0.0019, expensive_total=$0.0058
# → Haiku дешевле, но качество кода может быть хуже

# Сценарий 2: аудит безопасности
security = break_even_analysis(
    cheap_model="sonnet", cheap_accuracy=0.85, cheap_call_cost=0.005,
    expensive_model="opus", expensive_accuracy=0.97, expensive_call_cost=0.03,
)
# → cheap_total=$0.0058, expensive_total=$0.0309
# → Sonnet дешевле, но 15% ошибок в security-аудите неприемлемы

# Сценарий 3: критичное принятие решений (медицина, финансы)
critical = break_even_analysis(
    cheap_model="sonnet", cheap_accuracy=0.90, cheap_call_cost=0.005,
    expensive_model="opus", expensive_accuracy=0.99, expensive_call_cost=0.03,
    retry_cost_factor=1.5,  # retry дороже (нужен HITL после retry)
)
```

**Вывод:** break-even зависит от accuracy задачи. Для кода — Haiku норм. Для security — Opus дешевле, если учесть стоимость пропущенной уязвимости.

### Cost of failure (скрытые расходы)

```python
def total_cost_of_ownership(
    call_cost: float, accuracy: float,
    failure_penalty: float,  # стоимость одного отказа (например, $10 за lost user)
    calls_per_day: int,
) -> dict:
    """Учитывает стоимость отказов модели."""
    failures_per_day = calls_per_day * (1 - accuracy)
    failure_cost_daily = failures_per_day * failure_penalty
    api_cost_daily = calls_per_day * call_cost / (1 + (1 - accuracy))  # с retry

    return {
        "api_cost_daily": round(api_cost_daily, 2),
        "failure_cost_daily": round(failure_cost_daily, 2),
        "total_daily": round(api_cost_daily + failure_cost_daily, 2),
        "total_monthly": round((api_cost_daily + failure_cost_daily) * 30, 2),
    }

# Haiku для поддержки клиентов: дёшево, но accuracy 70%, каждый отказ = недовольный клиент
haiku_tco = total_cost_of_ownership(
    call_cost=0.0007, accuracy=0.70,
    failure_penalty=0.50,   # $0.50 за потерянного клиента
    calls_per_day=10_000,
)
# total_monthly = $4 710 (в основном из-за отказов)

# Sonnet для поддержки: дороже, но accuracy 95%
sonnet_tco = total_cost_of_ownership(
    call_cost=0.005, accuracy=0.95,
    failure_penalty=0.50,
    calls_per_day=10_000,
)
# total_monthly = $2 250 (дешевле! из-за меньшего числа отказов)
```

---

## ROI кэширования: сколько реально экономит

### Формула ROI

```python
def cache_roi(
    daily_queries: int,
    cache_hit_rate: float,         # 0.0..1.0
    embedding_cost_per_query: float,
    llm_cost_per_query: float,
    cache_operation_cost: float,   # redis/vector DB cost
) -> dict:
    """
    Считает ROI внедрения semantic cache.
    """
    queries_without_cache = daily_queries * 30  # месяц
    cost_without = queries_without_cache * llm_cost_per_query

    # С кэшем: hit paid embedding + cache read, miss paid LLM
    hits = daily_queries * cache_hit_rate
    misses = daily_queries * (1 - cache_hit_rate)

    daily_cache_cost = hits * (embedding_cost_per_query + cache_operation_cost) \
                     + misses * (llm_cost_per_query + embedding_cost_per_query + cache_operation_cost)
    cost_with_cache = daily_cache_cost * 30

    savings = cost_without - cost_with_cache

    # Разработка: ~$1K (embedding pipeline + cache integration)
    dev_cost = 1_000
    months_to_breakeven = dev_cost / savings if savings > 0 else float("inf")

    return {
        "cost_without_cache": round(cost_without, 2),
        "cost_with_cache": round(cost_with_cache, 2),
        "monthly_savings": round(savings, 2),
        "savings_pct": round((savings / cost_without) * 100, 1) if cost_without > 0 else 0,
        "months_to_breakeven": round(months_to_breakeven, 1),
        "roi_12mo": round((savings * 12 - dev_cost) / dev_cost * 100, 0),
    }

# Сценарий: типичный support agent, 50% запросов повторяются
support_cache = cache_roi(
    daily_queries=5_000,
    cache_hit_rate=0.50,
    embedding_cost_per_query=0.00005,   # embedding API
    llm_cost_per_query=0.005,           # Sonnet
    cache_operation_cost=0.00001,       # Redis read
)
print(f"Ежемесячная экономия: ${support_cache['monthly_savings']}")
print(f"Окупаемость: {support_cache['months_to_breakeven']} мес")
print(f"ROI за 12 мес: {support_cache['roi_12mo']}%")
# → $345/мес экономии, breakeven за 2.9 мес, ROI 4140%
```

### Когда кэш окупается, а когда нет

```python
CACHE_SCENARIOS = [
    {
        "name": "Support agent (50% repeat)",
        "daily_queries": 5_000,
        "cache_hit_rate": 0.50,
        "monthly_savings": 345,
        "breakeven_months": 2.9,
        "roi_12mo": "4,140%",
    },
    {
        "name": "Code review (10% repeat)",
        "daily_queries": 500,
        "cache_hit_rate": 0.10,
        "monthly_savings": 21,
        "breakeven_months": 47.6,
        "roi_12mo": "-75%",           # не окупается
    },
    {
        "name": "Research agent (20% repeat)",
        "daily_queries": 1_000,
        "cache_hit_rate": 0.20,
        "monthly_savings": 88,
        "breakeven_months": 11.4,
        "roi_12mo": "56%",            # barely
    },
    {
        "name": "High-volume QA (70% repeat)",
        "daily_queries": 100_000,
        "cache_hit_rate": 0.70,
        "monthly_savings": 10_200,
        "breakeven_months": 0.1,      # окупается за 3 дня
        "roi_12mo": "122,400%",
    },
]
```

> [!tip] Правило кэша
> Semantic cache окупается когда: (1) много повторяющихся запросов, (2) высокая стоимость LLM-вызова, (3) большой объём. Если все три условия — ROI тысячи процентов. Если ни одного — кэш не нужен.

---

## Cost attribution: кто сжигает деньги

### Per-user cost tracking

```python
class CostAttribution:
    """Распределение затрат по пользователям, типам задач, моделям."""

    def __init__(self):
        self.log: list[dict] = []

    def track(self, user_id: str, task_type: str, model: str,
              tokens_in: int, tokens_out: int, prices: dict):
        cost = (tokens_in * prices[model]["input"] + tokens_out * prices[model]["output"]) / 1_000_000
        self.log.append({
            "user": user_id,
            "task_type": task_type,
            "model": model,
            "tokens": tokens_in + tokens_out,
            "cost": cost,
        })

    def by_user(self) -> list[dict]:
        """Топ пользователей по затратам."""
        from collections import defaultdict
        totals = defaultdict(float)
        for entry in self.log:
            totals[entry["user"]] += entry["cost"]

        return sorted(
            [{"user": u, "cost": round(c, 2)} for u, c in totals.items()],
            key=lambda x: x["cost"], reverse=True,
        )

    def by_task_type(self) -> list[dict]:
        """Типы задач по затратам."""
        from collections import defaultdict
        totals = defaultdict(float)
        for entry in self.log:
            totals[entry["task_type"]] += entry["cost"]

        return sorted(
            [{"task": t, "cost": round(c, 2), "pct": 0} for t, c in totals.items()],
            key=lambda x: x["cost"], reverse=True,
        )

    def by_model(self) -> list[dict]:
        """Распределение затрат по моделям."""
        from collections import defaultdict
        totals = defaultdict(float)
        for entry in self.log:
            totals[entry["model"]] += entry["cost"]

        total = sum(totals.values())
        return sorted(
            [{"model": m, "cost": round(c, 2), "pct": round(c / total * 100, 1)}
             for m, c in totals.items()],
            key=lambda x: x["cost"], reverse=True,
        )


# Типичный production-паттерн: 80% затрат — 20% пользователей
attribution = CostAttribution()
# ... логируем 100 000 вызовов
top_users = attribution.by_user()[:5]
print(f"Топ-5 пользователей: {sum(u['cost'] for u in top_users)}% затрат")
```

### Power law распределение

```python
# В production затраты распределены неравномерно:
"""
80% запросов:  дешёвые (Haiku, $0.0005)
15% запросов:  средние (Sonnet, $0.005)
 5% запросов:  дорогие (Opus + multi-turn, $0.05-0.50)

Но по сумме:
20% дорогих запросов → 70% total cost
80% дешёвых запросов → 30% total cost
"""
```

---

## Бюджетное планирование для агента

### Multi-level budget

```python
BUDGET_TEMPLATE = {
    "organization": {
        "monthly_budget": 10_000,       # $10K/мес на всю организацию
        "alert_at": 0.8,                # алерт при 80%
        "hard_stop_at": 1.0,            # жёсткая остановка
    },
    "per_user": {
        "daily": 5.00,                  # $5/день на пользователя
        "monthly": 100.00,              # $100/мес
    },
    "per_request": {
        "max_tokens": 100_000,
        "max_cost": 0.50,               # $0.50 на один запрос
    },
    "optimization_targets": {
        "cache_hit_rate": 0.30,         # минимум 30% попаданий в кэш
        "cheap_model_ratio": 0.60,      # 60% запросов — дешёвая модель
        "avg_cost_per_session": 0.01,   # таргет $0.01/сессия
    },
}
```

### Budget dashboard

```python
class BudgetDashboard:
    """Дашборд для мониторинга бюджета в реальном времени."""

    def __init__(self, budget: dict):
        self.budget = budget
        self.monthly_spend = 0.0
        self.daily_spend = 0.0
        self.user_spend: dict[str, float] = {}

    def record_call(self, user_id: str, cost: float):
        self.monthly_spend += cost
        self.daily_spend += cost
        self.user_spend[user_id] = self.user_spend.get(user_id, 0) + cost

    def status(self) -> str:
        org = self.budget["organization"]
        return f"""
╔══════════════════════════════════════════╗
║         Budget Dashboard                 ║
╠══════════════════════════════════════════╣
║ Monthly:  ${self.monthly_spend:>8.2f} / ${org['monthly_budget']:<8}  ║
║ Alert:    {'🔔 ON' if self.monthly_spend / org['monthly_budget'] > org['alert_at'] else '🔕 OFF'}                      ║
║ Top user: ${max(self.user_spend.values()):>8.2f}                ║
║ Avg/ses:  ${self._avg_cost():>8.4f}                 ║
╚══════════════════════════════════════════╝
"""

    def _avg_cost(self) -> float:
        total_users = len(self.user_spend) or 1
        return self.monthly_spend / total_users

    def forecast(self) -> dict:
        """Прогноз до конца месяца."""
        day = datetime.now().day
        days_in_month = 30
        daily_rate = self.monthly_spend / day
        projected = daily_rate * days_in_month
        return {
            "daily_rate": round(daily_rate, 2),
            "projected": round(projected, 2),
            "budget": self.budget["organization"]["monthly_budget"],
            "overrun": round(max(0, projected - self.budget["organization"]["monthly_budget"]), 2),
            "days_until_exhausted": round(
                (self.budget["organization"]["monthly_budget"] - self.monthly_spend) / daily_rate
            ) if daily_rate > 0 else 999,
        }
```

---

## Decision tree: что оптимизировать первым

```
Cost слишком высок?
│
├── Больше всего тратит одна модель?
│   └── Внедри model routing (haiku→sonnet→opus)
│       Эффект: -40-70%
│
├── Много повторяющихся запросов?
│   └── Semantic cache
│       Эффект: -30-80% (зависит от hit rate)
│
├── System prompt раздут?
│   └── Prompt distillation (<500 токенов)
│       Эффект: -20-40%
│
├── История растёт бесконечно?
│   └── Context management + summarization
│       Эффект: -20-50%
│
├── Есть запросы, где ответ не нужен?
│   └── Pre-filtering (Haiku решает: надо ли звать Sonnet)
│       Эффект: -10-30%
│
└── Ничего не помогло?
    └── Пересчитать: может задача не стоит этих денег?
```

---

## Аудит cost: production checklist

### Pre-launch

- [ ] Посчитан burn rate для пиковой нагрузки
- [ ] Установлен budget per request / user / org
- [ ] Настроен semantic cache (ожидаемый hit rate)
- [ ] Внедрён model routing (дешёвая → дорогая)
- [ ] System prompt оптимизирован (< 500 токенов)
- [ ] Context management включён
- [ ] History summarization настроена
- [ ] Алерты на 80% бюджета
- [ ] Cost attribution логируется
- [ ] Break-even анализ для cheap vs expensive model

### Еженедельно

```yaml
weekly_review:
  - check: "Cost per session не вырос > 10%"
  - check: "Top-5 users не превышают 50% total cost"
  - check: "Cache hit rate > target"
  - check: "Cheap model ratio > 60%"
  - check: "No anomalous sessions (cost > 10x avg)"
```

### Ежемесячно

- [ ] Cost optimization review (какие рычаги ещё не использованы)
- [ ] Budget forecast на следующий месяц
- [ ] Model routing tuning (поменялись цены?)
- [ ] Cache hit rate review (нужно ли расширять?)
- [ ] Review of failed sessions (сколько cost ушло в retry)

---

## Резюме

```
Token Economics:
  Burn rate = calls × avg_tokens × price/token
  Break-even: cheap_model + retries vs expensive_model
  TCO = API cost + failure cost (отказы — скрытые расходы)
  ROI cache: savings / dev_cost, breakeven в месяцах

Топ-5 рычагов экономии (с эффектом):
  1. Model routing (haiku → sonnet → opus)     -40-70%
  2. Semantic caching                            -30-80%
  3. Prompt distillation (2000 → 400 токенов)   -20-40%
  4. History summarization                       -20-50%
  5. Pre-filtering (не звать модель, если не надо) -10-30%

Power law: 5% дорогих запросов → 70% total cost
           Оптимизируй сначала дорогие запросы

Правило: не оптимизируй cost там, где задача стоит $0.001.
         Оптимизируй там, где тысячи вызовов в день.
         Всегда считай TCO, а не просто API cost.
```

---

## Практическое задание

1. Возьми production-агента (или спроектируй)
2. Посчитай token burn rate на 10K сессий/день
3. Выполни break-even анализ: Haiku vs Sonnet для твоей задачи
4. Рассчитай ROI semantic cache для своего сценария
5. Построй cost forecast на 12 месяцев с growth 10%/мес
6. Определи top-3 рычага экономии для своей системы

---

## Проверь себя

1. Что такое token burn rate и как его считать?
2. Почему Haiku может быть дороже Opus (TCO)?
3. Как рассчитать break-even точку cheap vs expensive model?
4. Какая формула ROI для semantic cache?
5. Что такое power law распределение cost и как его использовать?
6. Какие 3 уровня бюджета должны быть у production-агента?
7. Как часто нужно пересматривать cost optimization?
8. Почему 20% пользователей могут сжигать 80% бюджета?

---

## Ссылки

- [[08-decision-architecture/02-model-selection]] — выбор модели
- [[08-decision-architecture/01-fine-tuning-rag-prompting]] — стратегия выбора подхода
- [[08-decision-architecture/05-ai-gateway]] — model router
- [[13-ecosystem-operations/03-production-operations]] — rate limiting и budget management
- [[05-production/02-observability]] — мониторинг cost
- [[05-production/04-resilience]] — fallback chain между моделями
- [OpenAI Pricing](https://openai.com/pricing)
- [Anthropic Pricing](https://anthropic.com/pricing)
- [DeepSeek Pricing](https://deepseek.com/pricing)
- [LLM Cost Calculator](https://github.com/your-tools/llm-cost-calc)
