---
created: 2026-05-28
tags: [course/context-window-deep, models, comparison, landscape]
status: active
---

# Урок 21.1: Context Window Landscape 2026

> [!quote] Ключевая идея
> 2026 — год взрыва контекстных окон. От 128K (стандарт 2024) до 10M (Llama 4 Scout) и бесконечных окон через RWKV и Infini-Attention. Выбор окна — это trade-off между длиной, качеством retrieval и cost-per-call.

---

## 1. Все модели 2026 — Context Window Size

| Модель | Context Window | Provider | Цена input/1M tok | Цена output/1M tok | Метод |
|--------|---------------|----------|-------------------|--------------------|-------|
| **Llama 4 Scout** | 10M | Meta | $0.05 | $0.25 | Sparse MoE + YaRN |
| **Gemini 2.5 Pro** | 2M | Google | $1.25-2.50 | $5-10 | Infini-Attention |
| **DeepSeek V4** | 1M | DeepSeek | $0.27 | $1.10 | MLA + Multi-token |
| **GPT-5.5** | 1M | OpenAI | $2.50 | $10.00 | Sparse Attention |
| **Claude Opus 4** | 500K | Anthropic | $15.00 | $75.00 | Sliding Window |
| **Grok 4** | 1M | xAI | $1.50 | $6.00 | Ring Attention |
| **Qwen 4** | 1M | Alibaba | $0.50 | $2.00 | YaRN + NTK |
| **Mistral Large 3** | 256K | Mistral | $2.00 | $6.00 | Sliding Window |
| **GPT-4o** | 128K | OpenAI | $2.50 | $10.00 | Standard |
| **Claude Sonnet 4** | 200K | Anthropic | $3.00 | $15.00 | Standard |
| **Llama 4 Maverick** | 1M | Meta (open) | $0.20 | $0.80 | YaRN |
| **Command R+** | 256K | Cohere | $0.50 | $1.50 | Tuned |
| **Phi-4** | 256K | Microsoft | $0.05 | $0.10 | Local (14B) |

### 1.1 Как они это делают?

```python
class ContextWindowMethods:
    """Методы расширения контекстного окна."""
    
    METHODS = {
        "YaRN": "Yet another RoPE scaling — interpolation rotary positions",
        "NTK": "Neural Tangent Kernel scaling — частотная интерполяция",
        "Sparse Attention": "O(n log n) — только релевантные токены",
        "Sliding Window": "Фиксированное окно + compression",
        "Infini-Attention": "Compressive memory + attention слияние",
        "Ring Attention": "Распределённое внимание по GPU",
        "MLA": "Multi-head Latent Attention (DeepSeek)",
        "Multi-token": "Предсказание нескольких токенов за шаг",
    }

    @staticmethod
    def efficiency(method: str, seq_len: int) -> dict:
        complexities = {
            "Standard": "O(n²)",
            "Sparse": "O(n log n)",
            "Sliding": "O(n × k)",
            "Ring": "O(n² / gpu)",
            "Infini": "O(n) (theoretically)",
        }
        
        return {
            "method": method,
            "complexity": complexities.get(method, "O(n²)"),
            "practical_max": self._practical_max(method),
        }
```

---

## 2. Качество на длинном контексте

| Модель | 128K | 256K | 512K | 1M | 2M+ |
|--------|------|------|------|-----|-----|
| GPT-5.5 | 98% | 97% | 95% | 89% | — |
| Gemini 2.5 Pro | 99% | 98% | 97% | 95% | 88% |
| Claude Opus 4 | 99% | 97% | 91% | — | — |
| DeepSeek V4 | 97% | 96% | 94% | 88% | — |
| Llama 4 Scout | 95% | 93% | 88% | 82% | 71% (10M) |
| GPT-4o | 96% | 82% | — | — | — |

> Needle-in-Haystack тесты. Первые числа — retrieval accuracy на данной длине.

---

## 3. Decision Tree: Какое окно выбрать?

```python
def choose_context_window(task_type: str, budget_cents: float, quality_min: float) -> dict:
    """Выбор оптимального контекстного окна под задачу."""

    if task_type == "code_generation":
        # Код требует высокой точности retrieval
        if budget_cents > 5:
            return {"model": "claude-opus-4", "window": 500_000, "cost": "high"}
        return {"model": "deepseek-v4", "window": 1_000_000, "cost": "low"}

    elif task_type == "document_analysis":
        if quality_min > 0.95:
            return {"model": "gemini-2.5-pro", "window": 2_000_000, "cost": "medium"}
        return {"model": "llama-4-scout", "window": 10_000_000, "cost": "very_low"}

    elif task_type == "chat":
        # Чату нужно небольшое окно, низкая latency
        return {"model": "gpt-4o-mini", "window": 128_000, "cost": "very_low"}

    elif task_type == "long_context_rag":
        # RAG с огромными документами
        return {"model": "gemini-2.5-pro", "window": 2_000_000, "cost": "medium"}

    else:
        # Default: сбалансированный выбор
        return {"model": "deepseek-v4", "window": 1_000_000, "cost": "low"}
```

---

## 4. Needle-in-Haystack тесты — что реально работает?

```python
class NeedleInHaystackTest:
    """Тест качества retrieval на длинном контексте."""

    def __init__(self, model_fn, haystack_lengths: list[int] = None):
        self.model = model_fn
        self.lengths = haystack_lengths or [1000, 10000, 50000, 100000, 500000]

    async def run_test(self, num_trials: int = 10) -> list[dict]:
        results = []
        for length in self.lengths:
            successes = 0
            for _ in range(num_trials):
                # Вставляем иголку в случайную позицию стога сена
                haystack = self._build_haystack(length)
                needle_position, needle = self._insert_needle(haystack)
                
                response = await self.model(
                    haystack + f"\nQuestion: What was the magic number?\nAnswer:"
                )
                
                if needle in response:
                    successes += 1

            accuracy = successes / num_trials
            results.append({
                "context_length": length,
                "accuracy": accuracy,
                "position_bias": self._check_position_bias(length),
            })
            
        return results

    def _build_haystack(self, length: int) -> str:
        """Генерирует стог сена — нейтральный текст."""
        sentences = [
            "The quick brown fox jumps over the lazy dog.",
            "Python is a high-level programming language.",
            "Paris is the capital of France.",
        ] * (length // 50)
        return " ".join(sentences[:length])
    
    def _insert_needle(self, haystack: str) -> tuple[int, str]:
        """Вставляет уникальную иголку в случайную позицию."""
        needle = f"The magic number is {random.randint(10000, 99999)}."
        pos = random.randint(0, len(haystack.split()) - 1)
        words = haystack.split()
        words.insert(pos, needle)
        return pos, needle
```

---

## 5. Position Bias — проблема середины

```
2024: U-shape bias (модели лучше помнят начало и конец)
2026: V-shape (улучшился retrieval середины, но всё ещё проблема)

GPT-5.5:   начало 99% → середина 85% → конец 97%
DeepSeek V4:  начало 98% → середина 88% → конец 96%
Llama 4 Scout: начало 95% → середина 71% → конец 89%
```

### Mitigation стратегии

```python
class PositionBiasMitigator:
    """Стратегии борьбы с position bias."""

    @staticmethod
    def shuffle_evidence(contexts: list[str]) -> str:
        """Перемешивание контекстов для равномерного внимания."""
        random.shuffle(contexts)
        return "\n".join(contexts)

    @staticmethod
    def query_aware_reordering(contexts: list[str], query: str) -> str:
        """Реорганизация контекстов по релевантности запросу."""
        scored = [(self._relevance(c, query), c) for c in contexts]
        scored.sort(key=lambda x: x[0], reverse=True)
        return "\n".join(c for _, c in scored)

    @staticmethod
    def multi_pass_retrieval(contexts: list[str], query: str, model_fn) -> str:
        """Multi-pass: модель сама выбирает какие части контекста важны."""
        # Pass 1: найти релевантные секции
        prompt = f"Find relevant sections for: {query}\nContext: {contexts[:5000]}"
        relevant_indices = model_fn(prompt)
        # Pass 2: ответ только по найденным секциям
        selected = [contexts[i] for i in relevant_indices]
        return "\n".join(selected)
```

---

## Резюме

```
Context Window Landscape 2026:

Лидеры по длине:
  Llama 4 Scout (10M) — open-weight, дешёвый
  Gemini 2.5 Pro (2M) — лучшее качество на длине
  DeepSeek V4 (1M) — лучший price/quality

Лидеры по качеству:
  GPT-5.5, Claude Opus 4 — до 500K
  Gemini 2.5 Pro — до 2M

Стратегия выбора:
  — До 128K: любая современная модель
  — 128K-500K: GPT-5.5 / Claude Opus 4
  — 500K-2M: Gemini 2.5 Pro
  — 2M+: Llama 4 Scout (с потерей качества)

Проблемы:
  — O(n²) cost: 1M токенов ≈ $0.27-15.00
  — Position bias: середина контекста ~85% accuracy
  — Needle-in-Haystack: не все модели честно «видят» весь контекст
```

---

## Практическое задание

1. Собери таблицу 10 моделей 2026 с их контекстными окнами и ценами.

2. Напиши NeedleInHaystackTest для GPT-4o на 128K: какая реальная точность?

3. Построй decision tree для выбора окна под задачу.

---

## Проверь себя

1. Какая модель имеет самое большое контекстное окно? Какая — лучшее качество на длине?

2. Что такое position bias и почему середина контекста хуже?

3. Какие методы расширения окон существуют?

4. Как выбрать окно под задачу: код, документы, чат?

---

## Ссылки

- [[02-optimization]] — следующий урок: оптимизация контекста
- [[03-pricing-caching]] — pricing & caching
- [[../../08-decision-architecture/04-model-comparison]] — model comparison
- [[../../08-decision-architecture/02-model-selection]] — model selection
- [[../../01-fundamentals/01-how-llms-work]] — как работают LLM
