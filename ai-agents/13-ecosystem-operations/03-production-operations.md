---
created: 2026-05-28
tags: [course/ecosystem, production, rate-limiting, budgeting, cost-management, guardrails]
status: active
---

# Урок 48: Production Operations — rate limiting, budget, cost

> [!quote] Ключевая идея
> В production агента ломают не баги, а деньги: забытый `while True` в инструменте, экспоненциальный retry, внезапный spam-атака. Rate limiting, budget management и cost tracking — не devops-опции, а часть архитектуры. Production-ready агент = защищённый агент. Здесь три линии защиты: ограничители (не даём сжечь), бюджеты (не даём превысить), трекинг (знаем, куда ушло).

---

## Три проблемы production-агента

```python
# Проблема 1: Цена ошибки ≠ 0
"""
Обычный баг = стоимость фикса
Agent баг = вызов 10 000 раз по 500 токенов × $0.003 = $150 за час
"""

# Проблема 2: Рекурсивные циклы
"""
Агент зовёт инструмент → инструмент возвращает данные → агент решает
позвать снова → и снова → и снова. LLM не «знает», что это дорого.
Без лимита итераций — один запрос может стоить $200.
"""

# Проблема 3: Непредсказуемая стоимость
"""
Один user query → 1 вызов LLM → $0.01
Другой query → 5 вызовов + 3 tool call → $0.12
В production распределение затрат — power law:
  80% запросов дёшевы, 1% очень дороги
"""
```

---

## Архитектура защиты

```
User → [Rate Limiter] → [Budget Check] → [Guardrails] → Agent
                                                              │
                                                              ▼
                                                         [Cost Tracker] → Logs
                                                         [Alerts]
                                                         [Dashboards]
```

Три слоя, каждый решает свою задачу:

---

## Rate Limiting

```python
import time
from collections import defaultdict


class TokenBucketRateLimiter:
    """
    Token Bucket rate limiter.
    Refill: 10 tokens/min, burst: 50 tokens, per-user.
    Каждый запрос агента = 1 token.
    """

    def __init__(self, refill_rate: float, burst: int):
        self.refill_rate = refill_rate  # tokens per second
        self.burst = burst
        self.buckets: dict[str, dict] = defaultdict(
            lambda: {"tokens": burst, "last_refill": time.time()}
        )

    def allow(self, user_id: str, tokens: int = 1) -> tuple[bool, int]:
        """
        Проверяет, может ли пользователь сделать запрос.
        Возвращает (разрешено, сколько осталось).
        """
        bucket = self.buckets[user_id]
        now = time.time()

        # Refill
        elapsed = now - bucket["last_refill"]
        bucket["tokens"] = min(
            self.burst,
            bucket["tokens"] + elapsed * self.refill_rate,
        )
        bucket["last_refill"] = now

        # Check
        if bucket["tokens"] >= tokens:
            bucket["tokens"] -= tokens
            return True, bucket["tokens"]

        return False, bucket["tokens"]


# Usage
limiter = TokenBucketRateLimiter(refill_rate=10 / 60, burst=50)  # 10 requests/min, peak 50

allowed, remaining = limiter.allow("user_abc")
if not allowed:
    raise HTTPException(status_code=429, detail="Rate limit exceeded")
```

**Для LLM-агентов добавляем мультиуровневый throttle:**

```python
class AgentRateLimiter:
    """
    Многоуровневый rate limiter.
    """

    def __init__(self):
        self.per_user = TokenBucketRateLimiter(
            refill_rate=10 / 60,  # 10 requests/min per user
            burst=30,
        )
        self.global_limiter = TokenBucketRateLimiter(
            refill_rate=100 / 60,  # 100 requests/min total
            burst=200,
        )
        self.token_limiter = TokenBucketRateLimiter(
            refill_rate=5000 / 60,  # 5K tokens/min total
            burst=20000,
        )

    def check(self, user_id: str, estimated_tokens: int) -> bool:
        """Proceed only if all three checks pass."""
        return (
            self.per_user.allow(user_id, 1)[0]
            and self.global_limiter.allow("global", 1)[0]
            and self.token_limiter.allow("tokens", estimated_tokens)[0]
        )
```

---

## Budget Management

### Per-request budget

Максимум, который может потратить один запрос:

```python
class RequestBudget:
    """Бюджет на один запрос агента."""

    MAX_TOKENS = 100_000
    MAX_API_CALLS = 10
    MAX_COST_USD = 0.50
    MAX_COMPLETION_TOKENS = 4_096


class RequestBudgetEnforcer:
    """Останавливает агента, если превышен бюджет запроса."""

    def __init__(self, budget: RequestBudget):
        self.budget = budget
        self.tokens_used = 0
        self.api_calls = 0
        self.cost_spent = 0.0

    def check(self, tokens: int, cost: float) -> bool:
        self.tokens_used += tokens
        self.api_calls += 1
        self.cost_spent += cost

        if self.tokens_used > self.budget.MAX_TOKENS:
            self._escalate("Token budget exceeded")
            return False
        if self.api_calls > self.budget.MAX_API_CALLS:
            self._escalate("API call limit exceeded")
            return False
        if self.cost_spent > self.budget.MAX_COST_USD:
            self._escalate("Cost budget exceeded")
            return False
        return True

    def reset(self):
        """Для нового запроса — сбрасываем бюджет."""
        self.tokens_used = 0
        self.api_calls = 0
        self.cost_spent = 0.0

    def _escalate(self, reason: str):
        """
        Log + alert. Не просто reject — notify.
        """
        logger.warning(f"Budget exceeded: {reason}")
```

### Per-user budget

```python
class UserBudgetManager:
    """
    Дневные и месячные бюджеты на пользователя.
    """

    def __init__(self, redis_client):
        self.redis = redis_client

    async def check_daily(
        self, user_id: str, cost: float, daily_limit: float = 5.0
    ) -> bool:
        """Проверяет дневной лимит для пользователя."""
        key = f"budget:daily:{user_id}:{datetime.now().date()}"
        total = await self.redis.incrbyfloat(key, cost)
        if total > daily_limit:
            logger.warning(f"Daily budget exceeded for {user_id}: {total}")
            return False
        return True

    async def check_monthly(
        self, user_id: str, cost: float, monthly_limit: float = 100.0
    ) -> bool:
        """Проверяет месячный лимит для пользователя."""
        key = f"budget:monthly:{user_id}:{datetime.now().month}"
        total = await self.redis.incrbyfloat(key, cost)
        if total > monthly_limit:
            logger.warning(f"Monthly budget exceeded for {user_id}: {total}")
            return False
        return True
```

### Global budget (организация)

```python
class OrganizationBudget:
    """
    Общий бюджет на все запросы.
    Если превышен — все пользователи получают degraded service.
    """

    MONTHLY_BUDGET = 10_000  # $10,000/month

    def __init__(self):
        self.monthly_spent: list[float] = []  # все траты за месяц

    @property
    def total_spent(self) -> float:
        return sum(self.monthly_spent)

    @property
    def remaining(self) -> float:
        return self.MONTHLY_BUDGET - self.total_spent

    def can_spend(self, amount: float) -> bool:
        return self.remaining >= amount

    def spend(self, amount: float):
        self.monthly_spent.append(amount)

    def utilization_pct(self) -> float:
        return (self.total_spent / self.MONTHLY_BUDGET) * 100

    def forecast(self) -> dict:
        """Прогноз: хватит ли бюджета до конца месяца?"""
        days_in_month = 30
        day = datetime.now().day
        daily_rate = self.total_spent / day
        projected = daily_rate * days_in_month
        return {
            "daily_rate": daily_rate,
            "projected_total": projected,
            "budget_left": self.remaining,
            "overrun": max(0, projected - self.MONTHLY_BUDGET),
        }
```

---

## Cost Tracking

### Структура лога затрат

```python
@dataclass
class CostLogEntry:
    """
    Одна запись о затратах агента.
    Каждый LLM call + each tool call = одна запись.
    """
    timestamp: datetime
    request_id: str
    user_id: str
    session_id: str
    agent_version: str
    model: str
    input_tokens: int
    output_tokens: int
    total_cost: float
    latency_ms: int
    status: str  # success / error / budget_exceeded / rate_limited


class CostTracker:
    """
    Пишет каждый LLM call в cost_log.
    """

    def __init__(self, db_client):
        self.db = db_client

    async def log_call(self, entry: CostLogEntry):
        await self.db.insert("cost_log", asdict(entry))

    async def report(self, user_id: str, period: str = "day") -> dict:
        """Агрегированный отчёт по затратам за период."""
        rows = await self.db.query(
            f"""
            SELECT
                model,
                COUNT(*) as calls,
                SUM(total_cost) as total_cost,
                AVG(latency_ms) as avg_latency,
                SUM(input_tokens) as total_input,
                SUM(output_tokens) as total_output
            FROM cost_log
            WHERE user_id = :user_id
                AND timestamp >= date('now', '-1 {period}')
            GROUP BY model
            ORDER BY total_cost DESC
            """
        )
        return rows
```

### Cost attribution по пользователям

```python
class CostAttribution:
    """
    Распределение затрат: кто сколько потратил.
    """

    async def per_user(
        self, top_n: int = 10, period: str = "30 days"
    ) -> list[dict]:
        return await self.db.query(
            f"""
            SELECT
                user_id,
                SUM(total_cost) as total_spent,
                COUNT(*) as total_calls,
                SUM(total_cost) / COUNT(*) as avg_cost_per_call
            FROM cost_log
            WHERE timestamp >= date('now', '-{period}')
            GROUP BY user_id
            ORDER BY total_spent DESC
            LIMIT {top_n}
            """
        )

    async def per_session(self, session_id: str) -> list[dict]:
        return await self.db.query(
            """
            SELECT
                timestamp, model, input_tokens,
                output_tokens, total_cost
            FROM cost_log
            WHERE session_id = :session_id
            ORDER BY timestamp
            """
        )
```

---

## Alerts

```yaml
# alerts.yaml
alerts:
  - name: UnexpectedCostSpike
    condition: cost_5m > cost_1h_baseline * 3
    action: |
      if spike > 5x → block agent (rate limit to 0)
      else → notify on-call in Slack

  - name: UserBudgetThreshold
    condition: user_daily_cost > daily_limit * 0.8
    action: notify_user + send warning

  - name: LatencyBudget
    condition: p95_latency_ms > 10000
    action: downgrade model (sonnet → haiku)

  - name: DailyOrgBudget
    condition: org_budget_remaining < org_budget_total * 0.1
    action: notify admin + auto-scale down
```

---

## Cost Optimization Patterns

### 1. Semantic caching

Кешируем семантически похожие запросы:

```python
class SemanticCache:
    """
    Не exact match, а косинусная близость эмбеддингов.
    """

    def __init__(self, threshold: float = 0.92):
        self.cache: dict[str, str] = {}
        self.threshold = threshold

    def get(self, query: str, embedding: list[float]) -> str | None:
        """Check semantic similarity to cached queries."""
        for cached_emb, cached_response in self.cache.items():
            similarity = cosine_similarity(embedding, cached_emb)
            if similarity >= self.threshold:
                logger.info(f"Cache hit (similarity={similarity:.3f})")
                return cached_response
        return None

    def set(self, query: str, response: str, embedding: list[float]):
        self.cache[tuple(embedding)] = response
```

**Effect:** 30-50% reduction in spend (повторяющиеся запросы одних и тех же пользователей).

### 2. Model triage

Не все запросы одинаковы. Дешёвая модель для простых, дорогая — для сложных:

```python
class ModelRouter:
    """
    Routing: простые запросы → haiku, сложные → sonnet.
    """

    MODELS = {
        "cheap": {"model": "claude-haiku-4.6",   "cost_per_1k": 0.00025},
        "standard": {"model": "claude-sonnet-4.6", "cost_per_1k": 0.003},
        "expensive": {"model": "claude-opus-4.6",  "cost_per_1k": 0.015},
    }

    def select(self, request_features: dict) -> str:
        complexity = request_features.get("complexity", 5)
        if complexity <= 3:
            return self.MODELS["cheap"]["model"]
        elif complexity <= 7:
            return self.MODELS["standard"]["model"]
        else:
            return self.MODELS["expensive"]["model"]
```

**Effect:** 40-60% cost reduction without quality degradation.

### 3. Prompt compression

Удаляем лишние контекстные токены:

```python
class PromptCompressor:
    """
    Сжимает промпт: удаляет дублирующуюся информацию,
    сокращает историю чата до релевантной.
    """

    def compress(self, messages: list, max_context_tokens: int = 32_000):
        system = [m for m in messages if m["role"] == "system"]
        history = [m for m in messages if m["role"] != "system"]

        # Summarize old history
        if self._count_tokens(history) > max_context_tokens:
            old_history = history[:-10]  # keep last 10 messages
            summary = self._summarize(old_history)
            history = [{"role": "system",
                        "content": f"Previous conversation: {summary}"}] + history[-10:]

        return system + history
```

**Effect:** 20-40% token reduction.

---

## Production Runbook Checklist

```markdown
## Pre-launch

- [ ] Rate limiters configured (per-user, global, token-based)
- [ ] Budget limits set (per-request, daily, monthly, org)
- [ ] Cost tracking implemented (every LLM call logged)
- [ ] Alerts configured (cost spikes, budget thresholds, latency)
- [ ] Canary deployment pipeline ready
- [ ] Rollback procedure tested (including cache cleanup)
- [ ] Feature flags operational

## Daily operations

- [ ] Review cost dashboards (5 min)
- [ ] Check rate limit breach logs (5 min)
- [ ] Verify auto-scaling behavior (5 min)

## Incident response

1. Detect: Alert fires (cost spike / latency / error rate)
2. Mitigate: Apply rate limit or feature flag
3. Diagnose: Check cost_log for culprit sessions
4. Fix: Update prompt or budget
5. Verify: Confirm cost returns to baseline
6. Postmortem: Write RCA within 24h

## Monthly

- [ ] Cost optimization review (caching, routing, compression)
- [ ] Budget forecasting for next month
- [ ] Rate limit tuning based on usage patterns
```

---

## Практическое задание

Реализуй трёхуровневую защиту бюджета для агента:

1. **Per-request**: максимум 3 LLM-вызова и $0.10 на один запрос
2. **Per-user**: максимум $1.00/день на пользователя (храни в in-memory dict или Redis)
3. **Global**: максимум $10.00/день на всех пользователей

Напиши демо:
- Агент делает 5 запросов с разной стоимостью ($0.02, $0.05, $0.15, $0.30, $0.50)
- Каждый запрос проверяется через все три уровня
- Если запрос превышает бюджет — он отклоняется с сообщением и логируется
- В конце выведи отчёт: сколько потрачено, сколько отклонено, сколько осталось

Требования: три уровня изоляции, корректный подсчёт cumulative spend, логирование каждого отклонения с причиной.

---

## Проверь себя

1. Какие три уровня защиты от финансовых потерь нужны агенту?
2. Чем отличается per-request budget от per-user budget?
3. Что такое semantic caching и зачем он нужен?
4. Как работает model triage?
5. Почему стоит кешировать не exact match, а семантически похожие запросы?
6. Какие метрики нужно отслеживать в реальном времени?

---

## Резюме

```
Production Operations = Rate Limiting + Budget + Cost Tracking

Rate limiting:
  per-user Token Bucket + global throttle + token throttle
  → не даём одному пользователю сжечь всё

Budget management:
  per-request (max $0.50/call)
  + per-user ($5/day)
  + per-organization ($10K/month)
  + auto-escalation при превышении

Cost tracking:
  каждый LLM call → cost_log (who, when, model, tokens, cost)
  + daily reports + alerts + dashboards

Optimizations:
  Semantic caching (-30-50%)
  Model triage (-40-60%)
  Prompt compression (-20-40%)

Правило: три слоя защиты или production не выйдет.
         Каждый запрос логируется по стоимости.
         Оптимизация не опция — необходимость.
```

---

## Ссылки

- [[05-production/02-observability]] — observability агента
- [[../05-production/05-agent-testing]] — testing in production
- [[../21-context-window-deep/03-pricing-caching]] — кеширование для LLM
- [AI Agent Guardrails Guide 2026](https://www.alexmereu.com/posts/agent-cost-protection-guide)
- [Production Readiness Checklist for LLM Apps](https://www.zenblog.com/production-readiness-checklist-for-llm-apps-2026/)
- [Cost Management for LLM Agents](https://coresight.ai/blog/building-cost-aware-pipelines-for-llm-dspy-and-llamaindex-2026/)
