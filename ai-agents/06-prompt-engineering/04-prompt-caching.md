---
created: 2026-05-28
tags: [course/prompt-engineering, caching, cost-optimization, latency]
status: active
---

# Урок 24: Prompt Caching — экономим 50-90% на LLM

> [!quote] Ключевая идея
> Каждый повторный вызов LLM с тем же (или похожим) промптом — деньги на ветер. Prompt caching — это техника, которая возвращает закэшированный ответ вместо нового вызова модели. В 2026 все major провайдеры поддерживают нативное кэширование на уровне API. Экономия: 50-90% стоимости input токенов, ускорение в 3-10x.

---

## Анатомия кэширования LLM

Кэширование бывает трёх уровней:

```
Уровень 1 — Prompt Caching (на стороне провайдера)
  LLM провайдер хранит KV-кэш для повторяющегося префикса промпта.
  Ты платишь 10% от цены input за cache hit.
  Никакой инженерии — просто поставь маркер в промпте.

Уровень 2 — Semantic Caching (на стороне приложения)
  Ты хранишь пары (запрос → ответ) в своей БД.
  Новый запрос сравнивается с кэшем по смыслу (через эмбеддинги).
  Если похож — возвращаешь кэш, не вызывая LLM.

Уровень 3 — Response Caching (на стороне приложения)
  Ты кэшируешь ответы на идентичные запросы в Redis.
  Только exact match (или нормализованный match).
```

```python
# Сколько можно сэкономить
CACHE_SAVINGS = {
    "prompt_caching":  {"cost_reduction": "85-90%", "latency_improvement": "3-10x"},
    "semantic_caching": {"cost_reduction": "5-15%", "latency_improvement": "50-100x"},
    "response_caching": {"cost_reduction": "1-3%",  "latency_improvement": "100x+"},
}
```

---

## Prompt Caching — на уровне провайдера (Level 1)

Как это работает технически: Transformer attention хранит Key-Value кэш для каждого токена. Когда приходит новый запрос с тем же префиксом, провайдер переиспользует KV-кэш вместо пересчёта. Ты платишь ~10% от цены за закэшированные токены.

### Anthropic (Claude)

Антропик даёт ручное управление через маркеры `cache_control`:

```python
from anthropic import Anthropic

client = Anthropic()

response = client.messages.create(
    model="claude-sonnet-4.6",
    max_tokens=1000,
    system=[
        {
            "type": "text",
            "text": SYSTEM_PROMPT,  # длинный system prompt
            "cache_control": {"type": "ephemeral"},  # ← кэшируем!
        },
    ],
    messages=[{"role": "user", "content": user_message}],
)

# cache hit: платишь 10% за system prompt + 100% за user message
# cache miss: платишь 125% (25% надбавка за запись кэша)
```

**Результаты из production (330K вызовов):**
- Hit rate: 85-90%
- Экономия: 25-35% всего workload
- TTL: 5 минут (если не продлевать heartbeat-запросами)

### OpenAI (GPT-5.4, GPT-5.5)

OpenAI использует **auto-cache** — без маркеров, автоматически:

```python
# OpenAI сам решает, что кэшировать
# Автоматически кэширует начало промпта (первые N токенов)
# Cache hit: 10% цены input
# Cache miss: 100% (нет надбавки)

import openai

response = openai.chat.completions.create(
    model="gpt-5.4",
    messages=[
        {"role": "system", "content": SYSTEM_PROMPT},  # авто-кэш
        {"role": "user", "content": user_message},
    ],
)
```

**Результаты:** 93% cache hit rate на system tokens, TTFT падает с 3.6s до 0.73s на 7K-промпте.

### Google (Gemini)

Gemini тоже auto-cache, но с implicit определением:

```python
import google.generativeai as genai

model = genai.GenerativeModel(
    model_name="gemini-2.5-flash",
    system_instruction=SYSTEM_PROMPT,  # кэшируется автоматически
)

response = model.generate_content(user_message)
```

**Результаты:** 88% cost reduction на cache hit при streaming.

### DeepSeek

Disk-backed кэш — переживает часы простоя:

```python
# DeepSeek V4 Flash: кэш на диске, а не в GPU memory
# TTL: часы (не минуты как у конкурентов)
# Экономия: 74% на cache hit
```

| Провайдер | Тип кэша | TTL | Cost hit | Cost miss | Экономия |
|-----------|:--------:|:---:|:--------:|:---------:|:--------:|
| Anthropic | Ручной (`cache_control`) | 5 мин | 10% | 125% | 25-35% |
| OpenAI | Автоматический | 5-10 мин | 10% | 100% | 50-90%* |
| Gemini | Автоматический | 5 мин | 10% | 100% | ~88% |
| DeepSeek | Disk-backed | Часы | 26% | 100% | ~74% |

*OpenAI: 50-90% на input токенах при стабильном system prompt.

---

## Semantic Caching — на уровне приложения (Level 2)

Когда провайдерское кэширование не помогло (user message уникален), семантический кэш ловит **похожие по смыслу** запросы.

```python
import numpy as np
from redis import Redis

class SemanticCache:
    """
    Кэширует ответы на похожие запросы.
    Новый запрос → эмбеддинг → поиск в векторной БД →
    если похож > threshold → возвращаем кэшированный ответ.
    """
    def __init__(self, embed_model, redis_client: Redis, threshold: float = 0.92):
        self.embed = embed_model
        self.redis = redis_client
        self.threshold = threshold

    def get(self, query: str) -> str | None:
        query_vec = self.embed.encode(query)

        # Ищем похожие запросы в кэше
        # (упрощённо: перебор всех ключей — в production используй векторную БД)
        for key in self.redis.scan_iter("sem_cache:*"):
            cached_vec = np.frombuffer(self.redis.get(key))
            similarity = cosine_similarity(query_vec, cached_vec)

            if similarity > self.threshold:
                cached_response = self.redis.get(f"sem_resp:{key.split(':')[1]}")
                return cached_response.decode()

        return None

    def set(self, query: str, response: str, ttl: int = 3600):
        query_vec = self.embed.encode(query)
        key = hash(query)

        self.redis.setex(f"sem_cache:{key}", ttl, query_vec.tobytes())
        self.redis.setex(f"sem_resp:{key}", ttl, response)

    def stats(self) -> dict:
        total = len(list(self.redis.scan_iter("sem_cache:*")))
        return {"entries": total}


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))
```

**Реальная статистика из production (Anthropic, 330K вызовов):**
- Hit rate: ~12% (только на парсинг-шаге)
- Экономия: ~5% всего workload
- ROI окупается только при >10K запросов/месяц

> [!warning]
> Semantic caching — сложная инженерия. Нужно: модель эмбеддингов → векторная БД → тюнинг threshold. Окупается только на scale. Для маленьких проектов — только prompt caching провайдера.

---

## Response Caching — exact match (Level 3)

Для идемпотентных запросов — обычный Redis:

```python
class ResponseCache:
    """Кэш для точных совпадений (normalized query → response)."""

    def __init__(self, redis_client: Redis, ttl: int = 3600):
        self.redis = redis_client
        self.ttl = ttl

    def _normalize(self, query: str) -> str:
        """Нормализуем запрос: нижний регистр, без лишних пробелов."""
        return " ".join(query.lower().split())

    def get(self, query: str) -> str | None:
        key = f"resp:{self._normalize(query)}"
        result = self.redis.get(key)
        return result.decode() if result else None

    def set(self, query: str, response: str):
        key = f"resp:{self._normalize(query)}"
        self.redis.setex(key, self.ttl, response)
```

**Когда полезно:** Повторяющиеся запросы (например, «статус сервера», «погода в Москве»).
**Экономия:** 1-3% — почти бесполезно для LLM, полезно для идемпотентности.

---

## Комбинированная стратегия

Максимальная экономия — когда работают все три уровня:

```python
class CachedAgent:
    """
    Три уровня кэша:
    1. Response cache (exact match) — ~1ms
    2. Semantic cache (похожие запросы) — ~50ms
    3. Prompt cache (провайдер) — автоматически
    """

    def __init__(self, llm_client, embed_model, redis_client):
        self.llm = llm_client
        self.response_cache = ResponseCache(redis_client, ttl=3600)
        self.semantic_cache = SemanticCache(embed_model, redis_client)
        self.stats = {"hits": 0, "misses": 0}

    async def generate(self, query: str) -> str:
        # Level 3: Exact match
        cached = self.response_cache.get(query)
        if cached:
            self.stats["hits"] += 1
            return f"[cache:response] {cached}"

        # Level 2: Semantic match
        cached = self.semantic_cache.get(query)
        if cached:
            self.stats["hits"] += 1
            return f"[cache:semantic] {cached}"

        # Level 1: LLM call (provider caches system prompt automatically)
        response = await self.llm.generate(query)
        self.stats["misses"] += 1

        self.response_cache.set(query, response)
        self.semantic_cache.set(query, response)
        return response
```

**Ожидаемая экономия:**
| Уровень | Hit rate | Экономия на workload |
|---------|:--------:|:--------------------:|
| Response cache | ~3% | ~1% |
| Semantic cache | ~12% | ~5% |
| Provider cache | ~88% | ~30% |
| **Всего** | ~90% | **~36%** |

---

## Антипаттерны

### 1. Кэш возвращает устаревшие данные
```python
# ❌ Нет TTL — вчерашние данные сегодня неактуальны
cache.set("price_of_bitcoin", "100K", ttl=None)

# ✅ TTL пропорционален частоте обновления данных
cache.set("price_of_bitcoin", "100K", ttl=60)  # 1 минута
```

### 2. Semantic кэш с низким threshold
```python
# ❌ threshold=0.70 — возвращает непохожие ответы
# Пользователь спросил "как вернуть товар?" → получил ответ про "статус заказа"

# ✅ threshold=0.92 — безопасно, но меньше hit rate
```

### 3. Кэшировать уникальные запросы
```python
# ❌ Каждый запрос — уникальный (личные данные, время, контекст)
# Кэш никогда не бьёт, только тратит память

# ✅ Кэшировать только повторяющиеся паттерны
# System prompt, инструкции, частые вопросы
```

### 4. Не учитывать кэш при rollback
```python
# ❌ Откатили модель, но старые ответы в semantic cache
# Пользователи получают ответы от старой модели ещё часы

# ✅ При деплое сбрасывать semantic cache
def deploy(version: str):
    semantic_cache.clear()
    deploy_model(version)
```

---

## Практическое задание

1. Настрой кэширование system prompt для твоего провайдера (Anthropic — добавь `cache_control`, OpenAI — убедись, что system prompt стабилен). Замерь разницу в latency и cost до и после.

2. Реализуй простой `ResponseCache` на Redis (или in-memory dict) с TTL=3600. Добавь нормализацию запроса (нижний регистр, обрезка пробелов). Проверь, что повторный запрос возвращает кэш.

---

## Проверь себя

1. Какие три уровня кэширования LLM существуют?
2. Чем отличается ручной cache control (Anthropic) от auto-cache (OpenAI)?
3. Когда semantic caching окупается, а когда нет?
4. Что такое KV-кэш и почему провайдер может его переиспользовать?
5. Какой антипаттерн опаснее всего при semantic caching?
6. Почему при rollback нужно чистить semantic cache?

---

## Резюме

```
Prompt Caching = 3 уровня экономии

Level 1 — Provider cache (85-90% cost reduction на input)
  Anthropic: cache_control маркеры, TTL=5min
  OpenAI:   auto-cache, TTL=5-10min
  Gemini:   auto-cache, TTL=5min
  DeepSeek: disk-backed, TTL=часы

Level 2 — Semantic cache (5-15% экономии)
  Запрос → эмбеддинг → поиск похожих
  Threshold 0.92+ для безопасности
  Окупается от 10K запросов/мес

Level 3 — Response cache (1-3%)
  Exact match, Redis
  Только для идемпотентных запросов

Правило: provider cache — всегда (бесплатно, 0 инженерии)
         semantic cache — на scale (сложно, но окупается)
         response cache — для идемпотентности
         чистка кэша при rollback — обязательно
```

---

## Ссылки

- [[08-decision-architecture/03-cost-optimization]] — cost optimization общего агента
- [[08-decision-architecture/04-model-comparison]] — сравнение моделей
- [LLM Prompt Caching Complete Guide 2026](https://dev.to/synthorai/llm-prompt-caching-the-complete-2026-guide-3mmb)
- [Anthropic Prompt Caching — 330 production calls](https://dev.to/rikuq/anthropic-prompt-caching-real-numbers-from-330-production-calls-2eg4)
