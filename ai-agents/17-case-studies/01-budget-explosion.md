---
created: 2026-05-28
tags: [course/case-studies, production, budget, cost, architect]
status: active
---

# Case Study 1: Бесконечный ReAct-цикл на $15,000

> [!quote] Ключевая идея
> Агент без budget control — это касса с открытым доступом. Этот case study — реальная история (2024, Fortune 500): агент для анализа логов зациклился и сжёг $15,000 за ночь. Проблема была не в модели — **в архитектуре**.

---

## Инцидент

**Компания:** Крупная fintech-компания (называть не буду)
**Задача:** Агент анализирует логи транзакций и находит аномалии
**Модель:** GPT-4-turbo (2024, $0.01/1K input, $0.03/1K output)
**Длительность:** 8 часов (noчь, пятница)
**Потери:** ~$15,000
**Обнаружение:** Утром DevOps увидел spike в дашборде затрат

## Хронология

```
23:00 — Агент получил задачу: "анализируй логи за сегодня"
23:02 — Агент начал читать логи (500K строк)
23:05 — LLM ответила: "слишком много данных, нужно фильтровать"
23:06 — Агент вызвал grep для фильтрации
23:07 — LLM: "результатов много, давай группировать"
     → бесконечный цикл: "слишком много" → "давай уточним" → "всё ещё много"
04:32 — Команда LLM-вызовов: ~4500 вызовов
04:33 — Context window poisoning: каждый новый вызов добавлял историю
07:00 — Agent OOM: контекст переполнен, ответы бессвязны
07:15 — API key rate limit: временная блокировка
     → Agent retry: ждёт → снова вызывает → снова block → ...
09:15 — DevOps заметил spike: $15,000, ~12,000 LLM вызовов
```

## Root Cause Analysis

### Причина 1: Нет budget control

```python
# Было — без защиты
def agent_loop(task: str):
    context = []
    while True:
        response = llm.invoke(context + [task])
        if response.tool_calls:
            for tc in response.tool_calls:
                context.append(execute(tc))
        else:
            return response

# Должно было быть
MAX_COST = 0.50  # $0.50 на сессию

def agent_loop_with_budget(task: str):
    context = []
    total_cost = 0.0

    while total_cost < MAX_COST:
        response = llm.invoke(context + [task])
        cost = calculate_cost(response)
        total_cost += cost

        if total_cost >= MAX_COST:
            return {"error": "Budget exceeded", "partial_result": response}

        if response.tool_calls:
            for tc in response.tool_calls:
                result = execute(tc)
                context.append(result)
        else:
            return response

    return {"error": "Budget exceeded"}
```

### Причина 2: Нет лимита шагов

```python
# Было: бесконечный цикл
while True:
    ...

# Должно было быть: лимит итераций
MAX_ITERATIONS = 10

for step in range(MAX_ITERATIONS):
    response = llm.invoke(...)
    if not response.tool_calls:
        return response

return {"error": f"Max iterations ({MAX_ITERATIONS}) reached", "state": state}
```

### Причина 3: Нет детекции зацикливания

```python
def detect_loop(history: list[dict]) -> bool:
    """
    Детектит зацикливание: одинаковые паттерны action+observation.
    """
    if len(history) < 6:
        return False

    # Сравниваем последние 3 шага с предыдущими 3
    recent = [(h["action"], h["observation"]) for h in history[-3:]]
    previous = [(h["action"], h["observation"]) for h in history[-6:-3]]

    if recent == previous:
        return True  # зациклились

    # Альтернатива: одинаковые действия, но разные наблюдения
    recent_actions = [h["action"] for h in history[-5:]]
    if len(set(recent_actions)) == 1:
        return True  # одно и то же действие 5 раз подряд

    return False


# В графе агента
if detect_loop(agent_state["step_history"]):
    return {
        "error": "Loop detected",
        "action": "escalate_to_human",
        "state_summary": summarize_state(agent_state),
    }
```

### Причина 4: Нет алерта на аномальные паттерны

```python
# Monitoring: что должно было сработать
ANOMALY_ALERTS = [
    {"metric": "cost_per_session", "threshold": 1.00, "action": "block"},
    {"metric": "llm_calls_per_session", "threshold": 50, "action": "warn"},
    {"metric": "latency_p99", "threshold": "30s", "action": "alert"},
    {"metric": "same_action_repeated", "threshold": 5, "action": "block"},
]

# Если бы мониторинг был:
# 00:15 — cost_per_session > $1.00 → block, notify on-call
# Потери: $15,000 → $1.00
```

## Что должно было быть: budget control architecture

```python
class BudgetController:
    """
    Многослойный контроль бюджета.
    Каждый слой может остановить агента.
    """

    def __init__(self, session_budget: float = 0.50):
        self.session_budget = session_budget
        self.spent = 0.0
        self.call_count = 0
        self.max_calls = 50

    def check(self, step_cost: float) -> str:
        """Check budget. Returns 'allow', 'warn', 'block'."""
        self.spent += step_cost
        self.call_count += 1

        if self.spent >= self.session_budget:
            return "block"  # budget exhausted
        if self.call_count >= self.max_calls:
            return "block"  # too many calls
        if self.spent > self.session_budget * 0.8:
            return "warn"  # approaching limit

        return "allow"

    def get_report(self) -> dict:
        return {
            "spent": round(self.spent, 4),
            "budget": self.session_budget,
            "remaining": round(self.session_budget - self.spent, 4),
            "calls": self.call_count,
        }


# Guardrail-узел в графе
def budget_guardrail(state: AgentState) -> AgentState:
    controller: BudgetController = state["budget_controller"]
    step_cost = calculate_cost(state["messages"][-1])

    status = controller.check(step_cost)
    if status == "block":
        return {
            "messages": [{
                "role": "system",
                "content": f"Budget exhausted: {controller.get_report()}"
            }],
            "should_stop": True,
        }

    if status == "warn":
        state["messages"].append({
            "role": "system",
            "content": f"Warning: approaching limit ({controller.get_report()})"
        })

    return {"budget_report": controller.get_report()}
```

## Ключевые выводы

| Ошибка | Решение | Приоритет |
|--------|---------|-----------|
| Нет budget limit | BudgetController с hard limit | Critical |
| Нет лимита шагов | max_iterations в цикле | Critical |
| Нет детекции loop | pattern-matching на истории | High |
| Нет алертов | Anomaly detection в мониторинге | High |
| Нет canary deploy | Раскатка на 1% трафика | Medium |

> [!warning] Цена доверия к LLM
> Модель не знает, сколько стоят её токены. Если ты не скажешь ей «стоп», она не остановится никогда. **Budget control — не опция, а обязательный слой архитектуры.**

---

## Проверь себя

1. Какие четыре ошибки в архитектуре привели к инциденту?
2. Напиши `BudgetController`, который учитывает стоимость input и output токенов отдельно.
3. Почему rate limit API не остановил потерю денег?
4. Как бы ты детектил зацикливание, если агент каждый раз вызывает РАЗНЫЕ инструменты?

---

## Ссылки

- [[../../../08-decision-architecture/03-cost-optimization]] — cost optimization (урок 30)
- [[../../../05-production/04-resilience]] — resilience (урок 19)
- [[../../../05-production/01-guardrails]] — guardrails (урок 16)
- [[02-production-db-deletion]] — следующий case study
