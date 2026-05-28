---
created: 2026-05-28
tags: [course/case-studies, canary, deployment, evaluation, architect]
status: active
---

# Case Study 4: Canary-раскатка, которая сломала 30% запросов

> [!quote] Ключевая идея
> Агент недетерминирован: новый промпт может улучшить 90% сценариев и сломать 10%. Без canary, evals и автоматического rollback ты узнаешь о проблеме от пользователей. В лучшем случае — из логов через 24 часа.

---

## Инцидент

**Компания:** B2B support-платформа (2025)
**Изменение:** Обновление system prompt — добавлена инструкция «отвечай кратко, без лишних деталей»
**Раскатка:** 100% трафика, без canary, без evals
**Результат:** 30% запросов стали получать неполные/некорректные ответы. 8 часов до отката. ~$50K ущерба (репутация + поддержка).

## Почему это сработало не так

```
Старый prompt:
  "You are a support agent. Answer user questions thoroughly."

Новый prompt:
  "You are a support agent. Answer user questions thoroughly.
   Be concise. No unnecessary details."

Ожидание: все ответы станут короче
Реальность: 70% ответов стали короче и лучше,
            30% — потеряли критически важные детали
```

### Разница в поведении

| Сценарий | До | После | Результат |
|----------|----|-------|-----------|
| "Как сбросить пароль?" | 3 шага, предупреждения | 1 шаг, без контекста | OK |
| "Почему упал платёж?" | Диагностика + 5 причин | "Ошибка в платёжном шлюзе" | **BAD** |
| "Где мои данные?" | Юридическая справка + сроки | "В настройках аккаунта" | **BAD** |
| "Как настроить API?" | Пример кода + ссылки | "Смотри документацию" | **BAD** |

## Что должно было быть: release pipeline для агента

### Шаг 1: Baseline evals (до изменений)

```python
# eval_suite.py — тестовый набор
EVAL_SET = [
    {"query": "Как сбросить пароль?",
     "expected": ["шаги", "предупреждение"],
     "min_length": 50},

    {"query": "Почему упал платёж?",
     "required_topics": ["диагностика", "причины", "решение"]},

    {"query": "Где мои данные?",
     "required_topics": ["сроки хранения", "юридическая справка"]},

    {"query": "Как настроить API?",
     "expected": ["пример кода", "ссылка на docs"]},
]


def run_baseline_evals(agent_version: str) -> dict:
    """Прогон evals до изменений."""
    results = []
    for case in EVAL_SET:
        response = agent.invoke(case["query"])
        score = evaluate_response(response, case)
        results.append({"case": case, "response": response, "score": score})

    return {
        "version": agent_version,
        "timestamp": datetime.now(),
        "average_score": mean(r["score"] for r in results),
        "results": results,
    }
```

### Шаг 2: Canary-раскатка

```python
class CanaryDeploy:
    """Canary-раскатка для агента."""

    def __init__(self, baseline_evals: dict):
        self.baseline = baseline_evals
        self.phases = [
            {"name": "1% canary", "traffic": 0.01, "duration_hours": 24},
            {"name": "5% canary", "traffic": 0.05, "duration_hours": 24},
            {"name": "25% canary", "traffic": 0.25, "duration_hours": 12},
            {"name": "50% canary", "traffic": 0.50, "duration_hours": 12},
            {"name": "full rollout", "traffic": 1.0, "duration_hours": 0},
        ]

    def should_roll_forward(self, phase: dict, metrics: dict) -> bool:
        """Решение о переходе к следующей фазе."""
        # Метрики должны быть НЕ хуже baseline
        if metrics["avg_score"] < self.baseline["average_score"] * 0.95:
            return False  # провал — откат

        # Метрики качества
        if metrics["hallucination_rate"] > 0.02:  # >2% галлюцинаций
            return False

        # Метрики пользователей
        if metrics["escalation_rate"] > self.baseline["escalation_rate"] * 1.1:
            return False  # эскалаций больше — что-то пошло не так

        return True

    def rollback(self, reason: str):
        """Автоматический откат."""
        # 1. Переключаем трафик обратно на stable
        router.set_active_version("stable")

        # 2. Сохраняем failed версию для анализа
        save_artifact("failed_version", current_version)

        # 3. Алертим команду
        alert(
            severity="critical",
            message=f"Canary rolled back: {reason}",
            data={"version": current_version, "metrics": current_metrics},
        )
```

### Шаг 3: LLM-as-Judge в canary

```python
JUDGE_PROMPT = """You are evaluating a support agent's response.
Compare the response to the expected answer.

Query: {query}
Expected: {expected}
Got: {response}

Score (0-10):
- 10: perfect — covers all expected points
- 7-9: good — covers most, misses minor details
- 4-6: acceptable — covers main points, but misses context
- 1-3: poor — misses critical information
- 0: harmful — incorrect or dangerous

Score:"""


def evaluate_response(response: str, case: dict) -> float:
    """LLM-as-Judge оценка ответа."""
    prompt = JUDGE_PROMPT.format(
        query=case["query"],
        expected=case.get("expected", ""),
        response=response,
    )
    judge_response = judge_llm.invoke(prompt)
    try:
        return float(judge_response.content.strip())
    except ValueError:
        return 0.0
```

### Шаг 4: Semantic diff — что изменилось в поведении

```python
class SemanticDiff:
    """Сравнивает ответы старой и новой версии агента."""

    def compare(self, query: str, old_response: str, new_response: str) -> dict:
        prompt = f"""
        Compare these two agent responses to the same query.

        Query: {query}

        Version A (stable):
        {old_response}

        Version B (canary):
        {new_response}

        Analyse:
        1. What information present in A is MISSING in B?
        2. What information present in B is MISSING in A?
        3. Which version is more helpful?
        4. Is version B potentially dangerous?
        """
        analysis = judge_llm.invoke(prompt)

        return {
            "query": query,
            "lost_info": extract_lost(analysis),
            "gained_info": extract_gained(analysis),
            "verdict": "safe" if "dangerous" not in analysis.content else "dangerous",
        }


# Прогон на 50 репрезентативных запросах
semantic_diff = SemanticDiff()
changes = [semantic_diff.compare(q, stable, canary) for q in sample_queries]

# Если >5% запросов показывают потерю информации — rollback
dangerous = [c for c in changes if c["verdict"] == "dangerous"]
if len(dangerous) / len(changes) > 0.05:
    canary.rollback(f"{len(dangerous)}/{len(changes)} queries lost critical info")
```

## Production release pipeline

```
[1] Baseline evals on stable
    ↓
[2] New system prompt / model
    ↓
[3] Evals on new version (offline)
    ↓ PASS
[4] Canary 1% → 24h monitoring
    ↓ PASS
[5] Canary 5% → 24h monitoring
    ↓ PASS
[6] Canary 25% → 12h monitoring
    ↓ PASS
[7] Full rollout
    ↓
[8] Continuous monitoring (always-on)
    ↓ если метрики падают
[9] Auto-rollback
```

## Ключевые выводы

| Ошибка | Решение |
|--------|---------|
| Раскатка 100% без canary | Canary deploy: 1% → 5% → 25% → 100% |
| Нет evals до изменения | Baseline evals перед каждым релизом |
| Нет LLM-as-Judge в пайплайне | Автоматическая оценка каждого canary-шага |
| Нет auto-rollback | Метрики + пороги + автоматический откат |
| Нет semantic diff | Сравнение поведения: было → стало |

> [!warning] Агент — это не код
> Одно слово в system prompt может изменить поведение агента сильнее, чем 1000 строк кода. Относись к изменению промпта как к изменению архитектуры: evals, canary, monitoring, rollback.

---

## Проверь себя

1. Почему юнит-тесты не спасают при изменении system prompt?
2. Какие метрики нужно мониторить в canary-фазе?
3. Сколько трафика пускать на canary и на сколько?
4. Спроектируй auto-rollback триггеры для агента поддержки.
5. Как semantic diff отличается от обычного A/B теста?

---

## Ссылки

- [[03-indirect-injection]] — предыдущий case study
- [[05-context-poisoning]] — следующий case study
- [[../../../12-quality-evolution/02-ab-testing]] — A/B тестирование (урок 44)
- [[../../../12-quality-evolution/01-agent-evaluation]] — agent evaluation (урок 43)
