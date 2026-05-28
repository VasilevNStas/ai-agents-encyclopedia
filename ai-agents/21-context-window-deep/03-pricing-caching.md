---
created: 2026-05-28
tags: [course/context-window-deep, pricing, caching, cost, prompt-caching]
status: active
---

# Урок 21.3: Context Window Pricing & Caching

> [!quote] Ключевая идея
> 1M токенов может стоить $0.27 (DeepSeek) или $15.00 (Claude). Context caching сокращает cost до 90%. Выбор модели под длину контекста — это главный рычаг cost optimization в 2026.

---

## 1. Pricing Deep Dive — как считаются токены

```python
class ContextCostCalculator:
    """Детальный расчёт стоимости контекстного окна."""

    PRICING_2026 = {
        "gpt-4o": {
            "input_per_1m": 2.50,
            "output_per_1m": 10.00,
            "cached_input_per_1m": 1.25,  # 50% discount
            "max_window": 128_000,
        },
        "gpt-5.5": {
            "input_per_1m": 2.50,
            "output_per_1m": 10.00,
            "cached_input_per_1m": 1.25,
            "max_window": 1_000_000,
        },
        "claude-sonnet-4": {
            "input_per_1m": 3.00,
            "output_per_1m": 15.00,
            "cached_input_per_1m": 0.30,  # 90% discount
            "max_window": 200_000,
        },
        "claude-opus-4": {
            "input_per_1m": 15.00,
            "output_per_1m": 75.00,
            "cached_input_per_1m": 1.50,  # 90% discount
            "max_window": 500_000,
        },
        "deepseek-v4": {
            "input_per_1m": 0.27,
            "output_per_1m": 1.10,
            "cached_input_per_1m": 0.07,  # 75% discount
            "max_window": 1_000_000,
        },
        "gemini-2.5-pro": {
            "input_per_1m": 1.25,
            "output_per_1m": 5.00,
            "cached_input_per_1m": 0.31,  # 75% discount
            "max_window": 2_000_000,
        },
        "llama-4-scout": {
            "input_per_1m": 0.05,
            "output_per_1m": 0.25,
            "cached_input_per_1m": 0.02,  # 60% discount
            "max_window": 10_000_000,
        },
    }

    def estimate_call_cost(
        self, model: str, input_tokens: int, output_tokens: int, cache_hit: bool = False
    ) -> dict:
        prices = self.PRICING_2026[model]
        input_price = prices["cached_input_per_1m"] if cache_hit else prices["input_per_1m"]

        cost = {
            "input_cost": (input_tokens / 1_000_000) * input_price,
            "output_cost": (output_tokens / 1_000_000) * prices["output_per_1m"],
            "total_cost": 0.0,
            "breakdown": {},
        }
        cost["total_cost"] = cost["input_cost"] + cost["output_cost"]
        cost["breakdown"] = {
            "input": f"${cost['input_cost']:.6f} ({input_tokens} tok × ${input_price}/1M)",
            "output": f"${cost['output_cost']:.6f} ({output_tokens} tok × ${prices['output_per_1m']}/1M)",
        }

        if not cache_hit:
            cost["cache_savings"] = {
                "if_cached": f"${(input_tokens / 1_000_000) * (prices['input_per_1m'] - prices['cached_input_per_1m']):.6f}",
                "discount_pct": int((1 - prices['cached_input_per_1m'] / prices['input_per_1m']) * 100),
            }

        return cost
```

### Сравнительная таблица стоимости (100K input + 1K output)

| Модель | Input | Output | Total | За 1000 вызовов |
|--------|-------|--------|-------|-----------------|
| Llama 4 Scout | $0.005 | $0.00025 | **$0.005** | $5 |
| DeepSeek V4 | $0.027 | $0.0011 | **$0.028** | $28 |
| Gemini 2.5 Pro | $0.125 | $0.005 | **$0.13** | $130 |
| GPT-5.5 | $0.25 | $0.01 | **$0.26** | $260 |
| GPT-4o | $0.25 | $0.01 | **$0.26** | $260 |
| Claude Sonnet 4 | $0.30 | $0.015 | **$0.315** | $315 |
| Claude Opus 4 | $1.50 | $0.075 | **$1.575** | $1,575 |

---

## 2. Context Caching Strategies

```python
class ContextCacheManager:
    """Управление кэшированием контекста."""

    def __init__(self, cache_provider: str = "redis"):
        self.cache = RedisCache() if cache_provider == "redis" else MemoryCache()
        self.hit_rate = 0.0
        self.total_requests = 0
        self.cache_hits = 0

    async def get_or_compute(
        self, key: str, compute_fn: callable, ttl: int = 3600
    ) -> str:
        """Кэш с прозрачным fallback."""
        self.total_requests += 1

        cached = await self.cache.get(key)
        if cached:
            self.cache_hits += 1
            self.hit_rate = self.cache_hits / self.total_requests
            return cached

        result = await compute_fn()
        await self.cache.set(key, result, ttl=ttl)
        return result

    def estimate_savings(self, model: str, daily_tokens: int) -> dict:
        """Оценка экономии от кэширования."""
        prices = ContextCostCalculator.PRICING_2026[model]
        hit_rate = self.hit_rate or 0.5  # Default assumption

        without_cache = (daily_tokens / 1_000_000) * prices["input_per_1m"]
        with_cache = (daily_tokens / 1_000_000) * (
            (1 - hit_rate) * prices["input_per_1m"]
            + hit_rate * prices["cached_input_per_1m"]
        )

        return {
            "daily_without_cache": round(without_cache, 2),
            "daily_with_cache": round(with_cache, 2),
            "monthly_savings": round((without_cache - with_cache) * 30, 2),
            "hit_rate": round(hit_rate * 100, 1),
        }
```

### 2.1 System Prompt Caching (Anthropic-style)

```python
class SystemPromptCaching:
    """Кэширование system prompt (Anthropic Prompt Caching)."""

    def __init__(self, cache_ttl: int = 300):
        self.cache_ttl = cache_ttl

    async def build_request(
        self, system_prompt: str, messages: list, tools: list | None = None
    ) -> dict:
        """Строит запрос с кэшированием system prompt."""

        # Anthropic: system prompt помечается как cacheable
        request = {
            "model": "claude-sonnet-4",
            "max_tokens": 4096,
            "system": [
                {
                    "type": "text",
                    "text": system_prompt,
                    "cache_control": {"type": "ephemeral"},  # ← маркер кэша
                }
            ],
            "messages": messages,
        }

        if tools:
            # Tools тоже кэшируются
            request["tools"] = [
                {**tool, "cache_control": {"type": "ephemeral"}}
                for tool in tools
            ]

        return request

    def estimate_cache_efficiency(self, system_prompt_len: int, tools_len: int, num_calls: int) -> dict:
        """Оценка эффективности кэширования."""

        cached_size = system_prompt_len + tools_len
        first_call_cost = cached_size + 100  # + user message
        subsequent_cost = 100  # Only user message (system cached)

        total_without_cache = (cached_size + 100) * num_calls
        total_with_cache = first_call_cost + 100 * (num_calls - 1)

        savings_pct = (1 - total_with_cache / total_without_cache) * 100

        return {
            "cached_tokens": cached_size,
            "first_call_tokens": first_call_cost,
            "subsequent_call_tokens": subsequent_cost,
            "total_savings_pct": round(savings_pct, 1),
        }
```

### 2.2 Conversation History Caching

```python
class ConversationCache:
    """Кэширование истории диалога."""

    def __init__(self, max_history_tokens: int = 50000):
        self.max_history = max_history_tokens

    def optimize_history(self, messages: list[dict]) -> list[dict]:
        """Оптимизирует историю: сохраняет system prompt, обрезает старое."""

        system_prompt = [m for m in messages if m.get("role") == "system"]
        conversation = [m for m in messages if m["role"] != "system"]

        # Token count
        total_tokens = sum(self.count_tokens(m["content"]) for m in messages)

        if total_tokens <= self.max_history:
            return messages

        # Удаляем старые сообщения, сохраняя последние
        while len(conversation) > 2:
            candidate = system_prompt + conversation[2:]  # keep first exchange
            if sum(self.count_tokens(m["content"]) for m in candidate) <= self.max_history:
                conversation = conversation[2:]
            else:
                break

        # Если всё ещё превышает — summarization
        if sum(self.count_tokens(m["content"]) for m in system_prompt + conversation) > self.max_history:
            summary = self._summarize_old_history(conversation[:-10])
            conversation = [
                {"role": "system", "content": f"Previous conversation summary: {summary}"}
            ] + conversation[-10:]

        return system_prompt + conversation
```

---

## 3. Model Router по длине контекста

```python
class ContextAwareRouter:
    """Роутинг запросов по длине контекста."""

    TIERS = [
        {"name": "short", "max_tokens": 8000, "model": "gpt-4o-mini", "cost_per_1m": 0.15},
        {"name": "medium", "max_tokens": 32000, "model": "deepseek-v4", "cost_per_1m": 0.27},
        {"name": "long", "max_tokens": 128000, "model": "gpt-4o", "cost_per_1m": 2.50},
        {"name": "xl", "max_tokens": 500000, "model": "gemini-2.5-pro", "cost_per_1m": 1.25},
        {"name": "xxl", "max_tokens": 2000000, "model": "gemini-2.5-pro", "cost_per_1m": 1.25},
        {"name": "unlimited", "max_tokens": 10000000, "model": "llama-4-scout", "cost_per_1m": 0.05},
    ]

    def route(self, input_tokens: int, output_tokens: int, quality: str = "high") -> dict:
        """Выбирает модель под длину контекста и качество."""

        total_tokens = input_tokens + output_tokens

        for tier in self.TIERS:
            if total_tokens <= tier["max_tokens"]:
                if quality == "high" and tier["name"] in ["short", "medium"]:
                    continue  # Skip to higher quality tier
                return tier

        return self.TIERS[-1]  # Fallback to xxl

    def estimate_optimal(self, input_tokens: int, output_tokens: int, calls_per_day: int) -> dict:
        """Сравнение стоимости с/без роутинга."""

        routed = self.route(input_tokens, output_tokens)

        # Without routing (always uses GPT-4o)
        gpt4o = self.TIERS[2]
        cost_no_router = (
            (input_tokens / 1_000_000) * gpt4o["cost_per_1m"]
            + (output_tokens / 1_000_000) * 10.00
        ) * calls_per_day * 30

        # With routing
        cost_with_router = (
            (input_tokens / 1_000_000) * routed["cost_per_1m"]
            + (output_tokens / 1_000_000) * 1.10
        ) * calls_per_day * 30

        return {
            "routed_to": routed["name"],
            "model": routed["model"],
            "monthly_cost_no_router": round(cost_no_router, 2),
            "monthly_cost_with_router": round(cost_with_router, 2),
            "monthly_savings": round(cost_no_router - cost_with_router, 2),
            "savings_pct": round((1 - cost_with_router / cost_no_router) * 100, 1),
        }
```

---

## 4. Cost Optimization Workflow

```python
class ContextCostOptimizer:
    """Полный cost optimization для контекстного окна."""

    def __init__(self, model: str = "gpt-4o", daily_budget_cents: float = 100.0):
        self.model = model
        self.budget = daily_budget_cents

    async def optimize_request(self, request: dict) -> dict:
        """Оптимизирует запрос до отправки в модель."""

        optimizations_applied = []

        # 1. Trim conversation history
        if "messages" in request:
            original_tokens = self._count_messages(request["messages"])
            request["messages"] = self._trim_history(request["messages"])
            trimmed = original_tokens - self._count_messages(request["messages"])
            if trimmed:
                optimizations_applied.append(f"trimmed_history: -{trimmed} tokens")

        # 2. Compress system prompt
        if "system" in request:
            original = len(request["system"])
            request["system"] = self._compress_prompt(request["system"])
            if len(request["system"]) < original:
                optimizations_applied.append("compressed_system_prompt")

        # 3. Enable caching
        if self._supports_caching(self.model):
            request = await self._add_cache_control(request)
            optimizations_applied.append("enabled_context_caching")

        # 4. Estimate cost
        input_tokens = self._count_request_tokens(request)
        output_tokens = request.get("max_tokens", 4096)
        cost = ContextCostCalculator().estimate_call_cost(self.model, input_tokens, output_tokens)

        # 5. Budget check
        if cost["total_cost"] * 100 > self.budget * 0.1:  # Single call > 10% daily budget
            log(f"⚠️ This call is ${cost['total_cost']:.4f} ({cost['total_cost']*100/self.budget:.1f}% of daily budget)")

        return {
            "optimized_request": request,
            "optimizations": optimizations_applied,
            "estimated_cost": cost,
            "budget_remaining": self.budget - cost["total_cost"] * 100,
        }
```

---

## 5. Monthly Cost Scenarios

| Сценарий | Вызовов/день | Средние токены | Без оптимизации | С кэшем | С роутингом | Итого |
|----------|-------------|---------------|-----------------|---------|-------------|-------|
| Чат-бот (GPT-4o) | 10,000 | 4K | $3,000 | $1,500 | $300 | **$300** |
| RAG агент (DeepSeek) | 5,000 | 25K | $675 | $338 | $338 | **$338** |
| Код-ассистент (Claude) | 2,000 | 50K | $3,000 | $600 | $300 | **$300** |
| Документ-анализ (Gemini) | 500 | 500K | $3,125 | $1,563 | $313 | **$313** |
| Пакетная обработка (Llama) | 50,000 | 10K | $250 | $175 | $250 | **$175** |

---

## Резюме

```
Стоимость контекстного окна:

1. Цены 2026: разброс от $0.05/M (Llama 4) до $15.00/M (Claude Opus 4)
   → Выбор модели = 50-300x разница в стоимости

2. Context caching:
   — System prompt: 90% discount (Anthropic)
   — Conversation history: caching первых N токенов
   — Cache hit rate: 40-80% в production

3. Model routing:
   — Короткие запросы: gpt-4o-mini ($0.15/M)
   — Средние: DeepSeek V4 ($0.27/M)
   — Длинные: Gemini 2.5 Pro ($1.25/M)
   — Огромные: Llama 4 Scout ($0.05/M)
   → До 50x экономии без потери качества

4. Оптимизации:
   — Trim history: -30-60% токенов
   — Compress system prompt: -20-40%
   — Context caching: -50-90% стоимости input
   — Model routing: -80-98% общей стоимости
```

---

## Практическое задание

1. Рассчитай стоимость 10,000 вызовов в день для GPT-4o vs DeepSeek V4 при среднем контексте 50K токенов.

2. Реализуй ContextAwareRouter с 6 tiers.

3. Подключи SystemPromptCaching для своего агента.

4. Построй cost projection на месяц с/без оптимизаций.

---

## Проверь себя

1. У какой модели лучшая цена за токен? У какой — лучшее quality/price?

2. Как работает context caching у Anthropic? Сколько экономит?

3. Как model routing по длине контекста снижает cost?

4. Какие 4 оптимизации контекста самые эффективные?

---

## Ссылки

- [[01-landscape]] — контекстные окна 2026
- [[02-optimization]] — оптимизация контекста
- [[../../08-decision-architecture/03-cost-optimization]] — cost optimization
- [[../../08-decision-architecture/04-model-comparison]] — model comparison
- [[../../08-decision-architecture/05-ai-gateway]] — AI Gateway
