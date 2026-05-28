---
created: 2026-05-28
tags: [course/fine-tuning-deep, finetuning, lora, rlhf, landscape]
status: active
---

# Урок 22.1: Fine-tuning Landscape & Decision Framework

> [!quote] Ключевая идея
> Fine-tuning в 2026 — это не «дообучить модель на своих данных». Это спектр: от LoRA за $10 до полного RLHF за $100K. Решение «делать или нет?» определяет архитектуру агента на годы вперёд.

---

## 1. Decision Framework: Prompting vs RAG vs Fine-tuning

```python
class TrainingDecisionFramework:
    """Фреймворк выбора: prompting / RAG / fine-tuning / full training."""

    DIMENSIONS = [
        "data_volume",        # Сколько данных?
        "task_specificity",   # Насколько задача специфична?
        "latency_requirement",# Требования к задержке?
        "cost_budget",        # Бюджет?
        "update_frequency",   # Как часто обновлять?
        "expertise_level",    # Уровень команды?
    ]

    def recommend(self, profile: dict) -> dict:
        """Рекомендует подход на основе профиля задачи."""

        scores = {
            "prompting": self._score_prompting(profile),
            "rag": self._score_rag(profile),
            "lora": self._score_lora(profile),
            "full_finetune": self._score_full(profile),
            "rlhf": self._score_rlhf(profile),
        }

        best = max(scores, key=scores.get)
        return {
            "recommendation": best,
            "scores": scores,
            "rationale": self._explain(best, profile),
        }

    def _score_prompting(self, p: dict) -> float:
        if p["data_volume"] < 100 and p["update_frequency"] == "daily":
            return 0.9
        if p["task_specificity"] == "general":
            return 0.8
        return 0.3

    def _score_lora(self, p: dict) -> float:
        if 100 < p["data_volume"] < 10000 and p["cost_budget"] < 1000:
            return 0.9
        if p["latency_requirement"] == "strict":
            return 0.8
        return 0.4

    def _explain(self, approach: str, p: dict) -> str:
        explanations = {
            "prompting": f"Мало данных ({p['data_volume']}) и частые обновления — fine-tuning не окупится",
            "rag": f"Динамические знания + {p['data_volume']} документов — идеально для RAG",
            "lora": f"{p['data_volume']} примеров + бюджет ${p['cost_budget']} — LoRA оптимален",
            "full_finetune": f"Большой объём ({p['data_volume']}) + высокая специфичность",
            "rlhf": f"Субъективное качество важнее — RLHF выравнивает предпочтения",
        }
        return explanations.get(approach, "")
```

---

## 2. Все методы fine-tuning 2026

| Метод | Параметров | Данных нужно | Cost | Качество | Скорость inf. |
|-------|-----------|-------------|------|----------|---------------|
| **Prompting** | 0 | 0-100 | $0 | Baseline | 1x |
| **Few-shot** | 0 | 3-10 | $0 | +5% | 1x |
| **LoRA** | 0.1-1% | 100-1K | $10-100 | +15-30% | 1x |
| **QLoRA** | 0.1-1% | 100-1K | $5-50 | +15-25% | 1x |
| **DoRA** | 0.1-1% | 100-1K | $10-100 | +20-35% | 1x |
| **Full FT** | 100% | 10K+ | $500-5K | +30-50% | 1x |
| **RLHF/DPO** | 100% | 10K+ pref | $1K-50K | +40-60% | 1x |
| **GRPO** | 100% | 10K+ pref | $2K-100K | +45-70% | 1x |
| **Full training** | 100% | 1T+ | $100K-10M | 100% | 1x |

---

## 3. Cost-Benefit Analysis

```python
class FineTuneCostAnalyzer:
    """Анализ окупаемости fine-tuning."""

    PROVIDER_PRICING = {
        "openai": {
            "lora_training_per_1k": 0.03,     # $/1000 tokens
            "lora_training_fixed": 5.00,       # $ base
            "inference_per_1m": 2.50,
        },
        "together": {
            "lora_training_per_1k": 0.02,
            "lora_training_fixed": 3.00,
            "inference_per_1m": 1.50,
        },
        "anyscale": {
            "lora_training_per_1k": 0.025,
            "lora_training_fixed": 4.00,
            "inference_per_1m": 2.00,
        },
    }

    def break_even_analysis(
        self, method: str, training_data_tokens: int, daily_calls: int, avg_tokens_per_call: int
    ) -> dict:
        """Точка безубыточности fine-tuning vs prompting."""

        training_cost = self._training_cost(method, training_data_tokens)
        prompting_cost_per_call = (avg_tokens_per_call / 1_000_000) * 2.50
        ft_cost_per_call = (avg_tokens_per_call / 1_000_000) * 2.00  # cheaper inference

        daily_savings = daily_calls * (prompting_cost_per_call - ft_cost_per_call)
        break_even_days = training_cost / daily_savings if daily_savings > 0 else float("inf")

        return {
            "training_cost": training_cost,
            "daily_savings": round(daily_savings, 2),
            "break_even_days": round(break_even_days, 1),
            "yearly_savings": round(daily_savings * 365 - training_cost, 2),
            "recommendation": "FT recommended" if break_even_days < 90 else "Stay with prompting",
        }
```

---

## 4. Decision Trees

```
Вопрос: Есть ли у вас данные?
├── Нет → Используйте prompting
└── Да → Сколько?
    ├── <100 → Few-shot prompting
    ├── 100-1K → LoRA/QLoRA
    ├── 1K-10K → Full fine-tune
    └── 10K+ → RLHF/DPO/GRPO

Вопрос: Как часто обновлять знания?
├── Daily → RAG (не fine-tuning)
├── Weekly → LoRA + RAG
├── Monthly → Full FT
└── Never → Любой метод

Вопрос: Бюджет?
├── <$100 → QLoRA
├── $100-$1K → LoRA
├── $1K-$10K → Full FT
└── $10K+ → RLHF
```

---

## Резюме

```
Fine-tuning Decision Framework:

Prompting:  0 данных, 0 cost, baseline quality
LoRA:      100-1K данных, $10-100, +20-30%
Full FT:   10K+ данных, $500-5K, +30-50%
RLHF/DPO:  10K+ предпочтений, $1K-100K, +40-70%

Ключевой вопрос: окупится ли?
  Если break-even < 90 дней → fine-tuning
  Если нет → prompting / RAG

Тренды 2026:
  — LoRA стал стандартом для дообучения
  — QLoRA — для бюджетных проектов
  — DoRA (Directional LoRA) — лучший quality/cost
  — GRPO заменяет RLHF (стабильнее, дешевле)
```

---

## Проверь себя

1. Какие 5 факторов влияют на выбор метода fine-tuning?

2. Сколько данных нужно для LoRA? Для RLHF?

3. Что такое break-even анализ и как его считать?

4. Когда fine-tuning НЕ нужен, хотя данные есть?

---

## Ссылки

- [[02-lora-deep]] — следующий урок: LoRA deep dive
- [[../../../prompt-engineering/08-evaluation-security-production/08-fine-tuning-pipeline]] — fine-tuning pipeline basics
- [[../../../prompt-engineering/08-evaluation-security-production/08b-fine-tuning-hands-on]] — LoRA практикум
