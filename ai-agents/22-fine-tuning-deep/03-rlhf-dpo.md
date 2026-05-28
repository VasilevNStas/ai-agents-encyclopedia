---
created: 2026-05-28
tags: [course/fine-tuning-deep, rlhf, dpo, grpo, alignment]
status: active
---

# Урок 22.3: RLHF / DPO / GRPO — Alignment

> [!quote] Ключевая идея
> SFT учит модель отвечать. Alignment учит модель _хотеть_ отвечать правильно. RLHF — 2024 стандарт, DPO — 2025 упрощение, GRPO — 2026 эволюция (без reward model). Каждый следующий — дешевле и стабильнее.

---

## 1. Эволюция Alignment методов

```python
class AlignmentMethod:
    """Сравнение alignment методов."""

    METHODS = {
        "RLHF": {
            "year": 2022,
            "components": ["SFT → Reward Model → PPO"],
            "cost": "$$$$ ($10K-100K)",
            "complexity": "Очень высокая",
            "stability": "Нестабильный (PPO)",
            "data_needs": "10K+ comparisons",
        },
        "DPO": {
            "year": 2024,
            "components": ["SFT → Direct Preference Optimization"],
            "cost": "$$ ($1K-10K)",
            "complexity": "Средняя",
            "stability": "Стабильный",
            "data_needs": "10K+ preferences",
        },
        "GRPO": {
            "year": 2025,
            "components": ["Group-based PPO (no reward model)"],
            "cost": "$ ($500-5K)",
            "complexity": "Средняя",
            "stability": "Стабильный",
            "data_needs": "5K+ prompts (no preferences needed)",
        },
        "SimPO": {
            "year": 2025,
            "components": ["Simple Preference Optimization"],
            "cost": "$ ($500-2K)",
            "complexity": "Низкая",
            "stability": "Очень стабильный",
            "data_needs": "5K+ preferences",
        },
        "KTO": {
            "year": 2024,
            "components": ["Kahneman-Tversky Optimization"],
            "cost": "$ ($500-2K)",
            "complexity": "Низкая",
            "stability": "Стабильный",
            "data_needs": "Бинарные оценки (👍/👎)",
        },
    }

    def recommend(self, budget: float, data_type: str, stability_required: bool) -> str:
        if budget < 1000 and data_type == "binary":
            return "KTO"
        elif budget < 5000:
            return "GRPO" if stability_required else "SimPO"
        elif data_type == "comparisons":
            return "DPO"
        return "RLHF"  # Full power, full cost
```

---

## 2. DPO — Direct Preference Optimization

```python
class DPOTrainer:
    """Direct Preference Optimization: без reward model."""

    def __init__(self, model, ref_model, beta: float = 0.1):
        self.model = model          # Policy model (обучаемая)
        self.ref_model = ref_model  # Reference model (заморожена)
        self.beta = beta            # KL penalty coefficient

    def dpo_loss(self, chosen_logps: torch.Tensor, rejected_logps: torch.Tensor) -> torch.Tensor:
        """DPO loss: πθ(y_w | x) > πθ(y_l | x) с KL constraint."""

        # Log ratios: πθ / πref
        chosen_ratio = chosen_logps[:, 0] - chosen_logps[:, 1]   # log πθ(y_w) - log πref(y_w)
        rejected_ratio = rejected_logps[:, 0] - rejected_logps[:, 1]  # log πθ(y_l) - log πref(y_l)

        # DPO loss = -log σ(β * (chosen_ratio - rejected_ratio))
        logits = self.beta * (chosen_ratio - rejected_ratio)
        loss = -torch.nn.functional.logsigmoid(logits).mean()

        return loss

    def train_step(self, batch: dict) -> dict:
        """Один шаг DPO обучения."""

        # Forward через policy и reference
        chosen_logps = self._get_logprobs(self.model, batch["chosen"])
        rejected_logps = self._get_logprobs(self.model, batch["rejected"])
        ref_chosen_logps = self._get_logprobs(self.ref_model, batch["chosen"])
        ref_rejected_logps = self._get_logprobs(self.ref_model, batch["rejected"])

        # Pack: [πθ, πref]
        chosen = torch.stack([chosen_logps, ref_chosen_logps], dim=1)
        rejected = torch.stack([rejected_logps, ref_rejected_logps], dim=1)

        loss = self.dpo_loss(chosen, rejected)

        return {"loss": loss.item(), "chosen_reward": chosen_logps.mean().item()}

    def _get_logprobs(self, model, input_ids: torch.Tensor, attention_mask: torch.Tensor) -> torch.Tensor:
        """Логарифмы вероятностей для completion."""
        outputs = model(input_ids=input_ids, attention_mask=attention_mask)
        logits = outputs.logits[:, :-1, :]
        labels = input_ids[:, 1:]

        log_probs = torch.nn.functional.log_softmax(logits, dim=-1)
        token_log_probs = log_probs.gather(dim=-1, index=labels.unsqueeze(-1)).squeeze(-1)
        return token_log_probs.sum(dim=-1)
```

---

## 3. GRPO — Group Relative Policy Optimization

```python
class GRPOTrainer:
    """GRPO: Group-based PPO без reward model.

    DeepSeek-R1 метод: группа ответов → relative advantage.
    """

    def __init__(self, model, group_size: int = 8, epsilon: float = 0.2):
        self.model = model
        self.group_size = group_size
        self.epsilon = epsilon  # Clipping для стабильности

    def train_step(self, prompts: list[str]) -> dict:
        """GRPO шаг: группа ответов → relative rewards."""

        # 1. Генерируем group_size ответов на каждый prompt
        all_responses = []
        for prompt in prompts:
            responses = self._generate_group(prompt, self.group_size)
            all_responses.extend(responses)

        # 2. Оцениваем каждую пару (prompt, response)
        scores = [self._rule_based_reward(p, r) for p, r in all_responses]

        # 3. Normalize: relative advantage внутри группы
        grouped = torch.tensor(scores).reshape(-1, self.group_size)
        advantages = (grouped - grouped.mean(dim=1, keepdim=True)) / (grouped.std(dim=1, keepdim=True) + 1e-8)

        # 4. PPO-style clipped loss
        loss = self._clipped_surrogate_loss(all_responses, advantages.flatten())

        return {"loss": loss.item(), "mean_reward": float(grouped.mean())}

    def _rule_based_reward(self, prompt: str, response: str) -> float:
        """Reward на основе правил (не модель!)."""
        score = 0.0
        if self._is_correct_format(response): score += 1.0
        if self._has_reasoning(response): score += 0.5
        if len(response) > 1000: score -= 0.3  # Penalty for verbosity
        return score

    def _clipped_surrogate_loss(self, responses, advantages):
        """Clipped surrogate loss (PPO-style)."""

        log_probs = torch.stack([r["log_prob"] for r in responses])
        old_log_probs = torch.stack([r["old_log_prob"] for r in responses])

        ratio = torch.exp(log_probs - old_log_probs)
        clipped_ratio = torch.clamp(ratio, 1 - self.epsilon, 1 + self.epsilon)

        loss = -torch.min(ratio * advantages, clipped_ratio * advantages).mean()
        return loss
```

---

## 4. Сравнение: RLHF vs DPO vs GRPO

```python
class AlignmentComparison:
    """Объективное сравнение методов alignment."""

    @staticmethod
    def compare_on_dataset(dataset, methods: list[str]) -> dict:
        results = {}
        for method in methods:
            if method == "DPO":
                model = DPOTrainer(base_model, ref_model)
            elif method == "GRPO":
                model = GRPOTrainer(base_model)
            elif method == "RLHF":
                model = RLHFTrainer(base_model, reward_model)

            metrics = model.train_and_evaluate(dataset)
            results[method] = {
                "reward_score": metrics.reward,
                "training_cost": metrics.cost,
                "training_time": metrics.time,
                "stability": metrics.variance,
            }

        return results
```

### Таблица сравнения

| Метод | Quality | Cost | Данных | Стабильность | Сложность |
|-------|---------|------|--------|-------------|-----------|
| RLHF (PPO) | 95% | $$$ | 50K+ | ❌ | 🔴🔴🔴 |
| DPO | 93% | $$ | 10K+ | ✅ | 🟡🟡 |
| GRPO | 91% | $ | 5K+ | ✅ | 🟡 |
| SimPO | 90% | $ | 5K+ | ✅✅ | 🟢 |
| KTO | 87% | $ | 3K+ 👍/👎 | ✅✅ | 🟢 |

---

## 5. Data Preparation for Alignment

```python
class AlignmentDataset:
    """Подготовка данных для alignment."""

    FORMATS = {
        "comparison": {"chosen": str, "rejected": str},       # DPO
        "binary": {"prompt": str, "feedback": bool},           # KTO
        "prompt_only": {"prompt": str},                        # GRPO
        "scoring": {"prompt": str, "response": str, "score": float},  # RLHF
    }

    def prepare_dpo_dataset(self, raw_data: list[dict]) -> list[dict]:
        """Конвертирует сырые данные в DPO формат."""

        dpo_data = []
        for item in raw_data:
            dpo_data.append({
                "prompt": item["question"],
                "chosen": item["good_answer"],
                "rejected": item["bad_answer"],
            })
        return dpo_data

    def augment_preferences(self, dataset: list[dict], model) -> list[dict]:
        """Аугментация: генерируем дополнительные rejected ответы."""

        augmented = []
        for item in dataset:
            # Генерируем плохие ответы (разные уровни качества)
            for _ in range(3):
                bad_response = model.generate(item["prompt"], temperature=0.9)
                augmented.append({
                    "prompt": item["prompt"],
                    "chosen": item["chosen"],
                    "rejected": bad_response,
                })
        return augmented
```

---

## Резюме

```
Alignment Methods 2026:

RLHF (PPO):     Трёхэтапный, дорогой, нестабильный → Legacy
DPO:            Без reward model, проще, стабильнее → Current standard
GRPO:           Групповой relative reward, без preference data → Rising
SimPO:          Простейший, самый стабильный → Best for production
KTO:            Только 👍/👎 feedback → Best for minimal data

Выбор:
  Есть 10K+ сравнений → DPO
  Есть prompts без ответов → GRPO
  Есть бинарные оценки → KTO
  Есть $50K бюджет → RLHF (если нужно максимум качества)
```

---

## Практическое задание

1. Реализуй DPO loss с нуля (10 строк).

2. Собери датасет из 20 примеров (chosen/rejected).

3. Обучи DPO на LoRA-адаптированной модели.

4. Сравни DPO vs GRPO на одном датасете.

---

## Проверь себя

1. Чем DPO отличается от RLHF? Что убрали?

2. Как GRPO получает reward без reward model?

3. Какой метод alignment самый дешёвый?

4. Сколько данных нужно для DPO? Для KTO?

---

## Ссылки

- [[02-lora-deep]] — LoRA deep dive
- [[04-data-preparation]] — следующий урок: data preparation
- [[../../../prompt-engineering/08-evaluation-security-production/08-fine-tuning-pipeline]] — fine-tuning pipeline
