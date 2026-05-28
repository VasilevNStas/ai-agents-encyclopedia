---
created: 2026-05-28
tags: [course/fine-tuning-deep, lora, qlora, dora, peft]
status: active
---

# Урок 22.2: LoRA/QLoRA/DoRA Deep Dive

> [!quote] Ключевая идея
> LoRA — не просто «дешёвый fine-tuning». Это архитектурное решение: ты не меняешь модель, ты добавляешь параллельные пути. QLoRA делает это на 4-bit моделях. DoRA — разделяет направление и magnitude. Каждый следующий — эволюция идеи.

---

## 1. LoRA — Low-Rank Adaptation

```python
import torch
import torch.nn as nn
from peft import LoraConfig, get_peft_model


class LoRAAdapter:
    """LoRA: низкоранговая адаптация."""

    @staticmethod
    def apply_lora(model, rank: int = 16, alpha: int = 32, target_modules: list[str] = None):
        """Применяет LoRA к модели."""

        config = LoraConfig(
            r=rank,                    # Ранг разложения (4-64)
            lora_alpha=alpha,          # Scaling factor (обычно 2x rank)
            target_modules=target_modules or ["q_proj", "v_proj"],
            lora_dropout=0.05,
            bias="none",
            task_type="CAUSAL_LM",
        )

        model = get_peft_model(model, config)
        trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
        total = sum(p.numel() for p in model.parameters())

        log(f"Trainable: {trainable:,} / {total:,} ({100 * trainable / total:.2f}%)")
        return model

    @staticmethod
    def rank_sweep(model, data_loader, ranks: list[int] = [4, 8, 16, 32, 64]) -> dict:
        """Подбор оптимального ранга через sweep."""

        results = {}
        for rank in ranks:
            lora_model = LoRAAdapter.apply_lora(model, rank=rank)
            score = LoRAAdapter._train_and_evaluate(lora_model, data_loader)
            param_count = sum(p.numel() for p in lora_model.parameters() if p.requires_grad)
            results[rank] = {
                "score": score,
                "params": param_count,
                "params_mb": param_count * 4 / 1024 / 1024,  # MB (fp32)
            }

        # Pareto: лучший rank по quality/params
        best_rank = max(results, key=lambda r: results[r]["score"] / results[r]["params"])
        return {"rank_sweep": results, "pareto_optimal": best_rank}
```

### Выбор ранга

| Rank | Параметров (7B) | Качество | Память | Когда |
|------|-----------------|----------|--------|-------|
| 4 | 2.1M | 85% | +10MB | Мало данных, быстрая адаптация |
| 8 | 4.2M | 90% | +20MB | Стандартный выбор |
| 16 | 8.4M | 94% | +40MB | Рекомендуемый для агентов |
| 32 | 16.8M | 96% | +80MB | Максимальное качество |
| 64 | 33.6M | 97% | +160MB | Избыточно для большинства задач |

---

## 2. QLoRA — Quantized LoRA

```python
class QLoRAAdapter:
    """QLoRA: LoRA на 4-bit квантованной модели."""

    @staticmethod
    def apply_qlora(model_name: str = "mistralai/Mistral-7B-v0.3", rank: int = 16):
        """Загружает 4-bit модель + LoRA."""

        from transformers import BitsAndBytesConfig, AutoModelForCausalLM

        bnb_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",          # NormalFloat4
            bnb_4bit_compute_dtype=torch.bfloat16,
            bnb_4bit_use_double_quant=True,     # Double Quantization
        )

        model = AutoModelForCausalLM.from_pretrained(
            model_name,
            quantization_config=bnb_config,
            device_map="auto",
            torch_dtype=torch.bfloat16,
        )

        # LoRA поверх 4-bit модели
        lora_config = LoraConfig(
            r=rank,
            lora_alpha=32,
            target_modules=["q_proj", "v_proj", "k_proj", "o_proj"],
            lora_dropout=0.05,
            bias="none",
            task_type="CAUSAL_LM",
        )

        model = get_peft_model(model, lora_config)
        return model

    @staticmethod
    def memory_savings(model_name: str = "Mistral-7B") -> dict:
        """Сравнение памяти: full vs 4-bit vs QLoRA."""
        return {
            "full_fp16": {"memory_gb": 14.0, "speed": "1.0x"},
            "8bit": {"memory_gb": 7.5, "speed": "0.95x"},
            "4bit_nf4": {"memory_gb": 4.5, "speed": "0.85x"},
            "4bit_dq": {"memory_gb": 3.8, "speed": "0.82x"},
            "qlora_rank16": {"memory_gb": 4.8, "speed": "0.80x", "trainable_params_m": 8.4},
        }
```

---

## 3. DoRA — Directional LoRA (2025-2026)

DoRA разлагает вес на **direction** (нормализованный) и **magnitude** (скаляр):

```python
class DoRAAdapter:
    """DoRA: Weight-Decomposed Low-Rank Adaptation."""

    @staticmethod
    def apply_dora(base_model, rank: int = 16):
        """DoRA: разделяем direction и magnitude.

        W' = magnitude * (W + ΔW) / ||W + ΔW||
        """
        from peft import LoraConfig, get_peft_model

        config = LoraConfig(
            r=rank,
            lora_alpha=rank * 2,
            target_modules=["q_proj", "v_proj", "k_proj", "o_proj", "gate_proj"],
            lora_dropout=0.05,
            use_dora=True,  # ← DoRA activation
            bias="none",
        )

        model = get_peft_model(base_model, config)
        return model

    @staticmethod
    def compare_lora_vs_dora(base_model, dataset) -> dict:
        """Сравнение LoRA vs DoRA на одном датасете."""

        scores = {}
        for method, use_dora in [("LoRA", False), ("DoRA", True)]:
            config = LoraConfig(
                r=16, lora_alpha=32, use_dora=use_dora,
                target_modules=["q_proj", "v_proj"],
            )
            model = get_peft_model(base_model, config)
            scores[method] = DoRAAdapter._evaluate(model, dataset)

        return {
            "lora": scores.get("LoRA", 0),
            "dora": scores.get("DoRA", 0),
            "improvement": f"+{((scores.get('DoRA', 0) - scores.get('LoRA', 0)) / scores.get('LoRA', 1) * 100):.1f}%",
        }
```

---

## 4. Training Loop

```python
class LoRATrainer:
    """Production training loop для LoRA."""

    def __init__(self, model, tokenizer, learning_rate: float = 2e-4):
        self.model = model
        self.tokenizer = tokenizer
        self.optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate)

    def train(self, dataset, epochs: int = 3, batch_size: int = 4):
        """Обучает LoRA адаптер."""

        model = self.model.train()
        for epoch in range(epochs):
            for batch in dataset.batch(batch_size):
                inputs = self.tokenizer(batch["text"], return_tensors="pt", padding=True, truncation=True)
                inputs = {k: v.to(model.device) for k, v in inputs.items()}

                outputs = model(**inputs, labels=inputs["input_ids"])
                loss = outputs.loss
                loss.backward()

                torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
                self.optimizer.step()
                self.optimizer.zero_grad()

            log(f"Epoch {epoch+1}/{epochs} — loss: {loss.item():.4f}")

    def save_adapter(self, path: str):
        """Сохраняет только LoRA веса (~10-50MB)."""
        self.model.save_pretrained(path)
        self.tokenizer.save_pretrained(path)
        log(f"Adapter saved to {path}")

    def merge_and_unload(self):
        """Сливает LoRA веса с base моделью для инференса."""
        return self.model.merge_and_unload()
```

---

## 5. Multi-adapter Routing

```python
class MultiAdapterRouter:
    """Роутинг между несколькими LoRA адаптерами."""

    def __init__(self, base_model, adapters: dict[str, str]):
        self.base_model = base_model
        self.adapters = adapters        # {"code": "/path/to/code-lora", "chat": "...", "rag": "..."}
        self.current_adapter = None

    def route(self, task_type: str):
        """Переключает адаптер под задачу."""
        if task_type != self.current_adapter:
            adapter_path = self.adapters.get(task_type)
            if adapter_path:
                from peft import PeftModel
                self.base_model = PeftModel.from_pretrained(self.base_model, adapter_path)
                self.current_adapter = task_type
                log(f"Switched to {task_type} adapter")

    def generate(self, prompt: str, task_type: str = "chat") -> str:
        self.route(task_type)
        return self.base_model.generate(prompt)
```

---

## Резюме

```
LoRA Family Comparison:

           Память  Качество  Скорость  Сложность
LoRA:      +40MB   94%       1.0x      ★☆☆
QLoRA:     +5MB    90%       0.82x     ★★☆  (4-bit base)
DoRA:      +40MB   +3-5%     0.95x     ★★☆

Правила выбора:
  — Есть GPU (24GB+): LoRA rank 16
  — Есть GPU (12GB): QLoRA rank 16
  — Нет GPU: API fine-tuning (OpenAI, Together)
  — Максимум качества: DoRA rank 32

Anti-patterns:
  ❌ Rank > 64 (избыточно)
  ❌ LoRA на все слои (дорого, не нужно)
  ❌ Нет evaluation до/после (не видно эффекта)
  ❌ Слишком высокая lora_alpha (дестабилизация)
```

---

## Практическое задание

1. Примени LoRA rank 16 к Mistral-7B, обучи на 500 примерах.

2. Сравни LoRA vs DoRA на одном датасете — какая разница?

3. Настрой QLoRA на 4-bit модели, измерь memory savings.

4. Реализуй MultiAdapterRouter с 3 адаптерами (code, chat, rag).

---

## Проверь себя

1. Как LoRA уменьшает число обучаемых параметров?

2. Чем QLoRA отличается от LoRA? Сколько экономит памяти?

3. Что делает DoRA по-другому?

4. Какой rank выбрать для 7B модели?

---

## Ссылки

- [[01-landscape]] — decision framework
- [[03-rlhf-dpo]] — следующий урок: RLHF/DPO/GRPO
- [[../../../prompt-engineering/08-evaluation-security-production/08b-fine-tuning-hands-on]] — LoRA практикум
