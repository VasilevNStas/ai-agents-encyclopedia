---
created: 2026-05-28
tags: [course/decision-architecture, gateway, routing, cost, production]
status: active
---

# Урок 32: AI Gateway — Model Router и прокси-слой

> [!quote] Ключевая идея
> AI Gateway — это прокси-слой между агентом и LLM-провайдерами. Он решает: **какую модель вызвать, как кэшировать ответ, что делать при ошибке и сколько это стоило.** Без gateway каждый агент сам заботится о маршрутизации, кэшировании и cost tracking — хаос.

---

## Проблема: прямой вызов LLM

Когда агент вызывает LLM напрямую:

```python
# ❌ Без gateway
response = openai.chat.completions.create(
    model="gpt-4",
    messages=messages
)
# Проблемы:
# - модель хардкожена
# - нет fallback при ошибке
# - нет кэширования
# - нет мониторинга стоимости
# - нет rate limiting
```

С gateway:

```python
# ✅ С gateway
response = gateway.chat.completions.create(
    model="auto",  # gateway сам выбирает
    messages=messages
)
# Gateway:
# - выбрал самую дешёвую подходящую модель
# - проверил кэш
# - применил rate limit
# - записал стоимость
```

---

## Что умеет AI Gateway

### Model Routing

Три стратегии выбора модели:

**Semantic routing:** запрос анализируется и направляется на модель под задачу.

```
"напиши функцию на Python" → GPT-4o (coding)
"расскажи историю"         → Claude Haiku (creative, дёшево)
"переведи на английский"   → Gemini Flash (быстро, дёшево)
```

**Cost-based routing:** gateway выбирает самую дешёвую модель, способную выполнить задачу:

```python
ROUTING_TABLE = {
    "coding": {
        "models": [
            {"name": "deepseek-coder", "cost_per_mtok": 0.15, "capability": 0.95},
            {"name": "gpt-4o-mini",    "cost_per_mtok": 0.45, "capability": 0.90},
            {"name": "claude-3-haiku", "cost_per_mtok": 0.25, "capability": 0.85},
        ]
    },
    "creative": {
        "models": [
            {"name": "claude-sonnet",  "cost_per_mtok": 3.00, "capability": 0.95},
            {"name": "gemini-flash",   "cost_per_mtok": 0.15, "capability": 0.80},
        ]
    },
    "analytics": {
        "models": [
            {"name": "gemini-pro",     "cost_per_mtok": 1.00, "capability": 0.90},
        ]
    }
}

def select_model(task_type: str, min_capability: float = 0.8):
    candidates = ROUTING_TABLE.get(task_type, [])
    capable = [m for m in candidates if m["capability"] >= min_capability]
    if not capable:
        capable = candidates  # fallback к лучшему из доступных
    return min(capable, key=lambda m: m["cost_per_mtok"])
```

**Fallback chain:** если основная модель не ответила (ошибка/таймаут) — следующая:

```python
FALLBACK_CHAIN = [
    "gpt-4o",          # первая попытка
    "claude-sonnet-4", # fallback 1
    "gemini-pro",      # fallback 2
    "deepseek-v3",     # emergency fallback (всегда доступен)
]
```

### Semantic Caching

Ответы на повторяющиеся запросы не пересчитываются:

```python
CACHE_CONFIG = {
    "strategy": "semantic",     # кэш по смыслу, не точному совпадению
    "similarity": 0.92,        # порог косинусной близости
    "ttl": 3600,               # время жизни: 1 час
    "max_size": 10000,         # макс записей
    "backend": "redis",        # или "memory", "sqlite"
}
# ---
# Запрос 1: "какая столица Франции?" → "Париж" (вызов API)
# Запрос 2: "столица Франции?"       → "Париж" (из кэша, -100% cost)
# Запрос 3: "capital of France?"     → "Париж" (из кэша, семантический match)
```

### Cost Tracking

Каждый запрос логируется:

```json
{
  "timestamp": "2026-05-28T10:00:00Z",
  "request_id": "req-abc123",
  "model": "gpt-4o",
  "task_type": "coding",
  "input_tokens": 450,
  "output_tokens": 120,
  "cost_usd": 0.0021,
  "latency_ms": 340,
  "cached": false,
  "fallback_used": false
}
```

### Rate Limiting

Защита от перерасхода бюджета:

```python
RATE_LIMITS = {
    "gpt-4o": {
        "rpm": 100,           # requests per minute
        "tpm": 100000,        # tokens per minute
        "daily_budget": 5.0,  # долларов в день
    },
    "claude-sonnet": {
        "rpm": 200,
        "tpm": 200000,
        "daily_budget": 10.0,
    },
}
```

---

## Готовые решения vs кастомный gateway

### Open-source / SaaS

| Продукт | Тип | Особенности |
|---------|-----|-------------|
| **Portkey** | SaaS | Semantic routing, fallback, caching, observability |
| **Helicone** | SaaS | Мониторинг, cost tracking, user analytics |
| **ML Gateway** | Open-source | Self-hosted, model routing, caching |
| **LiteLLM** | Open-source | Единый API для 100+ моделей, Python SDK |
| **OpenRouter** | SaaS | Маркетплейс моделей, единый API, fallback |

### Когда кастомный gateway

```yaml
SaaS достаточно, если:
  - стандартные модели (GPT, Claude, Gemini)
  - не нужен self-hosted
  - бюджет позволяет платить за gateway сверх API

Кастомный нужен, если:
  - свои fine-tuned модели
  - специфическая логика routing
  - compliance (данные не должны покидать инфраструктуру)
  - высокие нагрузки (экономия на SaaS окупает разработку)
```

---

## Архитектура: gateway в системе агента

```
                   ┌──────────────┐
User ──request──►  │   Agent      │
                   │  (Supervisor)│
                   └──────┬───────┘
                          │ LLM call
                          ▼
                   ┌──────────────┐
                   │ AI Gateway   │
                   │              │
                   ├─ Semantic    │
                   │   Router    │
                   ├─ Cache      │
                   ├─ Rate       │
                   │   Limiter   │
                   ├─ Cost       │
                   │   Tracker   │
                   └──┬───┬───┬──┘
                      │   │   │
              ┌───────┘   │   └───────┐
              ▼           ▼           ▼
         ┌─────────┐ ┌─────────┐ ┌─────────┐
         │ GPT-4o  │ │ Claude  │ │ DeepSeek│
         └─────────┘ └─────────┘ └─────────┘
```

---

## Gateway и архитектурные решения

**Влияние gateway на выбор модели (M08):**
- Если есть gateway с semantic routing — можно держать 5+ провайдеров, gateway выберет лучшее соотношение цена/качество
- Если gateway нет — лучше ограничиться 1-2 провайдерами для упрощения

**Влияние на cost optimization (M08):**
- Semantic caching даёт 30-60% экономии на повторяющихся запросах
- Cost-based routing экономит 40-70% по сравнению с одним флагманским LLM
- Fallback chain повышает reliability без резервирования дешёвых моделей

**Влияние на production ops (M13):**
- Gateway — единая точка мониторинга всех LLM-вызовов
- Rate limiting на gateway, а не на уровне агента
- Audit log для compliance

---

## Резюме

```
AI Gateway:
  Model Router  → семантический / cost-based / fallback
  Cache         → семантический кэш (30-60% экономии)
  Cost Tracker  → каждый вызов логируется
  Rate Limiter  → защита бюджета и API

Без gateway → каждый агент сам выбирает модель
С gateway  → маршрутизация, кэш, fallback, мониторинг
```

---

## Практическое задание

1. Реализуй минимальный AI Gateway: класс `Gateway` с методами `chat.completions.create()`, который поддерживает fallback chain из 2 моделей и логирует каждый вызов (модель, токены, стоимость, latency).

2. Добавь в gateway семантическое кэширование: перед вызовом LLM проверяй, был ли похожий запрос (косинусная близость > 0.92). Если был — верни кэшированный ответ.

---

## Проверь себя

1. Какие три стратегии model routing существуют?
2. Как semantic caching отличается от обычного (exact-match)?
3. Когда нужен кастомный gateway вместо SaaS?
4. Как gateway влияет на cost optimization агента?
5. Какие метрики собирает gateway для каждого вызова LLM?

---

## Ссылки

- Дальше: [[09-advanced-rag-agents/01-agentic-rag]]
- Назад: [[08-decision-architecture/04-model-comparison]]
- Смежно: [[08-decision-architecture/03-cost-optimization]]
