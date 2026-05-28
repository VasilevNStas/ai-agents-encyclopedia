---
created: 2026-05-09
tags: [course/production, resilience, cost-control]
status: active
---

# Урок 19: Отказоустойчивость и Cost Control

> [!quote] Ключевая идея
> Агент упадёт. Это вопрос времени. **Resilience** — это способность системы продолжить работу после сбоя. **Cost Control** — это способность не обанкротиться до того, как сбой случится.

---

## Виды сбоев

| Сбой | Что происходит | Последствие |
|------|---------------|-------------|
| **API timeout** | LLM не ответила за N секунд | Агент завис |
| **Rate limit** | API вернул 429 Too Many Requests | Агент остановился |
| **Tool error** | Инструмент вернул ошибку | Агент может зациклиться |
| **Context overflow** | messages заполнили контекст | «Забывание» начала |
| **Model hallucination** | LLM выдумала факт | Неверный результат |
| **Cost spike** | Агент сжёг $50 за минуту | Финансовая боль |

---

## Retry with Backoff

```python
import time
import random

def call_llm_with_retry(prompt: str, max_retries: int = 3) -> str:
    """Вызов LLM с экспоненциальным backoff при ошибках."""

    for attempt in range(max_retries):
        try:
            return llm.generate(prompt)

        except RateLimitError:
            wait = (2 ** attempt) + random.uniform(0, 1)
            print(f"Rate limit. Жду {wait:.1f}с...")
            time.sleep(wait)

        except TimeoutError:
            wait = (2 ** attempt) + random.uniform(0, 1)
            print(f"Timeout. Жду {wait:.1f}с...")
            time.sleep(wait)

        except APIError as e:
            if attempt == max_retries - 1:
                raise  # последняя попытка — не retry, а fail
            print(f"API error: {e}. Retry {attempt + 1}/{max_retries}")

    return None  # все попытки исчерпаны
```

**Экспоненциальный backoff:** 1s → 2s → 4s → 8s (не долбим API, даём ему остыть)

---

## Fallback model

Если основная модель недоступна — переключаться на запасную:

```python
MODELS = [
    {"id": "deepseek-reasoner", "priority": 1, "cost_per_1k": 0.002},
    {"id": "deepseek-chat",     "priority": 2, "cost_per_1k": 0.0005},
    {"id": "gpt-4o-mini",       "priority": 3, "cost_per_1k": 0.00015},
]

def call_with_fallback(prompt: str) -> str:
    """Пробует модели по приоритету. Если первая упала — вторая."""

    errors = []
    for model in sorted(MODELS, key=lambda m: m["priority"]):
        try:
            return call_llm(model["id"], prompt)
        except Exception as e:
            errors.append(f"{model['id']}: {e}")
            continue

    raise Exception(f"All models failed: {errors}")
```

---

## Cost Control: лимиты

```python
class CostController:
    """Следит за бюджетом и останавливает агента при превышении."""

    def __init__(self, max_cost: float = 0.50):
        self.max_cost = max_cost
        self.total_cost = 0.0
        self.step_costs: list[float] = []

    def add_step(self, tokens_in: int, tokens_out: int, model: str):
        """Добавляет стоимость шага."""

        # Стоимость зависит от модели
        rates = {
            "deepseek-reasoner": {"input": 0.000002, "output": 0.000008},
            "deepseek-chat":     {"input": 0.0000005, "output": 0.000002},
            "gpt-4o-mini":       {"input": 0.00000015, "output": 0.0000006},
        }

        rate = rates.get(model, rates["deepseek-reasoner"])
        cost = (tokens_in * rate["input"]) + (tokens_out * rate["output"])
        self.step_costs.append(cost)
        self.total_cost += cost

    def over_budget(self) -> bool:
        """Проверка: не превышен ли лимит?"""
        return self.total_cost >= self.max_cost

    def estimate_remaining(self):
        """Сколько ещё шагов примерно можем сделать."""
        if not self.step_costs:
            return "неизвестно"
        avg_cost = sum(self.step_costs) / len(self.step_costs)
        remaining = (self.max_cost - self.total_cost) / avg_cost
        return f"~{int(remaining)} шагов"
```

---

## Circuit Breaker

Если агент постоянно ошибается — **остановить его насильно**:

```python
class CircuitBreaker:
    """Если слишком много ошибок подряд — размыкаем цепь."""

    def __init__(self, threshold: int = 5):
        self.threshold = threshold
        self.errors = 0
        self.is_open = False

    def record_success(self):
        self.errors = 0  # сброс при успехе

    def record_failure(self):
        self.errors += 1
        if self.errors >= self.threshold:
            self.is_open = True
            print(f"🔴 Circuit breaker: {self.threshold} errors. Stopping.")

    def call(self, fn, *args, **kwargs):
        if self.is_open:
            raise Exception("Circuit breaker is open — agent stopped")
        try:
            result = fn(*args, **kwargs)
            self.record_success()
            return result
        except Exception as e:
            self.record_failure()
            raise e
```

---

## Graceful Degradation

Когда всё ломается — агент должен **упасть мягко**:

```python
def agent_with_degradation(task: str) -> str:
    """Пробует лучший сценарий → дешёвый → fallback → человеку."""

    try:
        # 1. Полный цикл с ReAct + инструментами
        return full_agent_cycle(task)

    except (CostOverflowError, ContextOverflowError):
        # 2. Без инструментов, только LLM
        return llm.generate(f"Ответь на вопрос: {task}")

    except Exception as e:
        # 3. Последний шанс: сказать что не смог
        return f"Извините, я не смог выполнить задачу. Ошибка: {e}"

def run_with_safety_net(task: str, max_retries: int = 2):
    """Запуск с несколькими уровнями fallback."""
    for attempt in range(max_retries):
        try:
            return agent_with_degradation(task)
        except Exception as e:
            if attempt == max_retries - 1:
                escalate_to_human(task, str(e))
            continue
```

---

## Полная схема

```
Запрос
  │
  ▼
Input Guardrail (безопасность)
  │
  ▼
Cost Controller (бюджет)
  │
  ▼
Call LLM with Retry (API resilience)
  │
  ▼
Tool Execution with Guardrails
  │
  ▼
Output Validation
  │
  ▼
Observability (лог每一步)
  │
  ▼
Circuit Breaker (детект цикла)
  │
  ▼
Если всё сломалось → Graceful Degradation → Human
```

---

## Резюме

```
Resilience:
  Retry with backoff  — не долби API
  Fallback model      — если main модель упала
  Circuit breaker     — если слишком много ошибок
  Graceful degradation — упасть мягко

Cost Control:
  CostController      — бюджет на сессию
  Model routing       — дешёвая модель для сжатия
  Step limit          — max 20-50 шагов

Правило: проектируй отказоустойчивость до того,
         как она понадобится.
```

---

## Практическое задание

1. Реализуй функцию `call_llm_with_retry`, которая вызывает LLM с экспоненциальным backoff (1s → 2s → 4s) при ошибках `RateLimitError` и `TimeoutError`. Добавь максимум 3 попытки.

2. Напиши класс `CostController`, который останавливает агента при превышении бюджета в $0.10. Добавь метод `estimate_remaining()` для предсказания оставшегося числа шагов.

---

## Проверь себя

1. Какие виды сбоев бывают у агента (минимум 4)?
2. Что такое exponential backoff и зачем он нужен?
3. Чем circuit breaker отличается от retry?
4. Как graceful degradation помогает не потерять данные при сбое?

---

## Ссылки

- Назад: [[05-production/03-log-driven-development]]
- В начало: [[index.md]]
- Дальше: [[05-production/05-agent-testing]]
