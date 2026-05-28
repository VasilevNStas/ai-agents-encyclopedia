---
created: 2026-05-28
tags: [course/performance-deep, speculative-decoding, draft-model, speed]
status: active
---

# Урок 25.3: Speculative Decoding

> [!quote] Ключевая идея
> Speculative decoding — единственная техника, которая ускоряет inference без потери качества. Маленький «draft» модель генерирует несколько токенов, большая модель их верифицирует за один forward pass. До 3x ускорения без изменения архитектуры.

---

## 1. Как это работает

```python
class SpeculativeDecoder:
    """Спекулятивное декодирование: draft → verify."""

    def __init__(self, target_model, draft_model, gamma: int = 5):
        self.target = target_model        # Большая модель (верификатор)
        self.draft = draft_model          # Маленькая модель (черновик)
        self.gamma = gamma                # Сколько токенов генерирует draft

    def generate(self, prompt: str, max_tokens: int = 100) -> str:
        """Генерация со спекулятивным декодированием."""

        output = prompt

        while len(output) < max_tokens:
            # 1. Draft: генерируем gamma токенов
            draft_tokens = self._draft_generate(output, self.gamma)
            if not draft_tokens:
                break

            # 2. Target: верифицируем все за один forward pass
            # Одновременно вычисляем логиты для всех draft позиций
            verified = self._verify(output, draft_tokens)

            # 3. Принимаем до первого rejection
            accepted = self._accept_tokens(draft_tokens, verified)
            output += "".join(accepted)

            if len(accepted) < len(draft_tokens):
                # Target сгенерировала замену для rejection
                output += verified[len(accepted)]

        return output

    def _draft_generate(self, context: str, n: int) -> list[str]:
        """Draft: быстрая генерация n токенов (без KV-cache)."""
        tokens = []
        for _ in range(n):
            token = self.draft.generate(context + "".join(tokens), max_tokens=1)
            tokens.append(token)
        return tokens

    def _verify(self, context: str, draft_tokens: list[str]) -> list[float]:
        """Target: верификация всех draft токенов за один forward."""
        # Строим полную последовательность
        full_sequence = context + "".join(draft_tokens)

        # Один forward pass → логиты для всех позиций
        logits = self.target.forward(full_sequence)

        # Вероятности для draft токенов
        probabilities = []
        for i, token in enumerate(draft_tokens):
            position_logits = logits[len(context) + i]
            prob = torch.softmax(position_logits, dim=-1)
            token_id = self.target.tokenizer.encode(token)[0]
            probabilities.append(prob[token_id].item())

        return probabilities

    def _accept_tokens(self, draft_tokens: list[str], probabilities: list[float]) -> list[str]:
        """Rejection sampling: принимаем токены с вероятностью p/q."""
        accepted = []
        for token, prob in zip(draft_tokens, probabilities):
            # Rejection: accept с вероятностью min(1, p_target / p_draft)
            draft_prob = self.draft.probability(token)
            accept_prob = min(1.0, prob / draft_prob)
            if random.random() < accept_prob:
                accepted.append(token)
            else:
                break
        return accepted
```

---

## 2. Draft Model Selection

```python
class DraftModelSelector:
    """Выбор draft модели для speculative decoding."""

    PAIRS = [
        # (target, draft, speedup)
        ("claude-opus-4", "claude-haiku-3", 2.5),
        ("gpt-5.5", "gpt-4o-mini", 2.0),
        ("deepseek-v4", "deepseek-v2-lite", 3.0),
        ("llama-4-70b", "llama-4-scout", 2.2),
        ("mistral-large-3", "mistral-7b", 2.8),
    ]

    @staticmethod
    def recommend(target_model: str, latency_target_ms: int = 500) -> dict:
        """Рекомендация draft пары."""

        for target, draft, speedup in DraftModelSelector.PAIRS:
            if target == target_model:
                baseline_latency = DraftModelSelector._baseline_latency(target)
                estimated = baseline_latency / speedup
                return {
                    "target": target,
                    "draft": draft,
                    "estimated_latency_ms": int(estimated),
                    "meets_target": estimated <= latency_target_ms,
                    "speedup": speedup,
                }

        return {"error": f"No draft model found for {target_model}"}
```

---

## 3. Multi-token Prediction (MTP)

```python
class MultiTokenPrediction:
    """Multi-token prediction: предсказание нескольких токенов за шаг (DeepSeek)."""

    def __init__(self, num_predictions: int = 2):
        self.num_predictions = num_predictions

    def train_mtp_head(self, base_model, dataset):
        """Добавляет MTP головы к модели."""

        # DeepSeek V4: 1 main head + 2 MTP heads
        heads = []
        for i in range(self.num_predictions):
            head = nn.Linear(base_model.hidden_size, base_model.vocab_size)
            heads.append(head)

        # Training: predict next N tokens simultaneously
        loss = 0
        for batch in dataset:
            for i, head in enumerate(heads):
                # Predict token at position t+i+1
                target = batch["labels"][:, i + 1:]  # Shift by i+1
                logits = head(batch["hidden_states"][:, :-i - 1])
                loss += F.cross_entropy(logits, target)

        return loss / len(heads)

    def generate(self, model, prompt: str, max_tokens: int) -> str:
        """Генерация с MTP: каждый шаг выдаёт несколько токенов."""

        output = prompt
        with torch.no_grad():
            while len(output) < max_tokens:
                hidden = model.encode(output)
                # Main head
                main_token = model.head(hidden[:, -1:])
                output += main_token
                # MTP heads: дополнительные токены
                for head in self.mtp_heads:
                    next_token = head(hidden[:, -1:])
                    output += next_token
                    if len(output) >= max_tokens:
                        break
        return output

    @staticmethod
    def efficiency(num_tokens: int, mtp_n: int) -> dict:
        """Сравнение числа forward passes."""
        standard_steps = num_tokens
        mtp_steps = math.ceil(num_tokens / (mtp_n + 1))  # +1 for main head
        return {
            "standard_forward_passes": standard_steps,
            "mtp_forward_passes": mtp_steps,
            "reduction": f"{standard_steps / mtp_steps:.1f}x",
        }
```

---

## 4. Performance Measurement

```python
class SpecDecodeBenchmark:
    """Бенчмарк speculative decoding."""

    def benchmark(self, target_model, draft_model, prompts: list[str]) -> dict:
        """Сравнение: standard vs speculative decoding."""

        standard_times = []
        spec_times = []
        acceptance_rates = []

        for prompt in prompts:
            # Standard
            t0 = time.perf_counter()
            target_model.generate(prompt, max_tokens=100)
            standard_times.append(time.perf_counter() - t0)

            # Speculative
            decoder = SpeculativeDecoder(target_model, draft_model)
            t0 = time.perf_counter()
            decoder.generate(prompt, max_tokens=100)
            spec_times.append(time.perf_counter() - t0)

            # Acceptance rate
            rate = self._measure_acceptance(target_model, draft_model, prompt)
            acceptance_rates.append(rate)

        return {
            "standard_avg_ms": np.mean(standard_times) * 1000,
            "spec_avg_ms": np.mean(spec_times) * 1000,
            "speedup": np.mean(standard_times) / np.mean(spec_times),
            "avg_acceptance_rate": np.mean(acceptance_rates),
            "max_speedup_possible": 1 / (1 - np.mean(acceptance_rates)),
        }
```

---

## Резюме

```
Speculative Decoding:

Draft (small) → generate N tokens (fast)
Target (big)  → verify all tokens (one forward pass)
Accept        → rejection sampling (p_target / p_draft)

Speedup: 2-3x (зависит от acceptance rate)
Quality: identical to target (mathematically proven)

Draft model selection:
  Target          Draft           Speedup
  Claude Opus 4   Claude Haiku 3  2.5x
  GPT-5.5         GPT-4o-mini     2.0x
  DeepSeek V4     DeepSeek V2     3.0x
  Llama 4 70B     Llama 4 Scout   2.2x

Multi-token prediction:
  DeepSeek V4: 2 дополнительных токена
  -40% forward passes
```

---

## Практическое задание

1. Реализуй SpeculativeDecoder с draft → verify циклом.

2. Настрой DraftModelSelector для своей пары моделей.

3. Измерь speedup на 10 промптах (100 токенов каждый).

4. Реализуй MTP голову с multi-token prediction.

---

## Проверь себя

1. Как speculative decoding сохраняет качество target модели?

2. Как работает rejection sampling в accept шаге?

3. Как выбрать draft модель?

4. Чем multi-token prediction отличается от speculative decoding?

---

## Ссылки

- [[02-quantization]] — quantization
- [[04-distillation]] — следующий урок: distillation & pruning
