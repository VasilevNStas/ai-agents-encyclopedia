---
created: 2026-05-28
tags: [course/performance-deep, quantization, compression, gptq, awq, gguf]
status: active
---

# Урок 25.2: Quantization & Model Compression

> [!quote] Ключевая идея
> Quantization — это не «сжать модель, потеряв качество». Это выбор битности под задачу: fp16 для sensitive задач, fp8 для баланса, int4 для speed. С Rothko (fp4) и Ternary (2-bit) качество на уровне fp16 для большинства задач.

---

## 1. Quantization Methods 2026

| Метод | Битность | Память (7B) | Качество | Скорость | Когда |
|-------|----------|-------------|----------|----------|-------|
| fp16 | 16 | 14 GB | 100% | 1.0x | Baseline |
| fp8 | 8 | 7 GB | 99.5% | 1.2x | Production standard |
| int8 | 8 | 7 GB | 99.0% | 1.3x | CPU inference |
| GPTQ | 4 | 3.5 GB | 98-99% | 1.1x | GPU, batch |
| AWQ | 4 | 3.5 GB | 98-99% | 1.3x | GPU, best speed |
| GGUF (Q4) | 4.1 | 4.1 GB | 97-98% | 0.8x | CPU, universal |
| NF4 (QLoRA) | 4.1 | 3.8 GB | 97-98% | 0.9x | Training |
| Rothko | 3.8 | 3.2 GB | 97-98% | 1.4x | GPU, 2025 |
| Ternary | 2 | 1.8 GB | 95-97% | 1.8x | Edge, 2026 |
| Binary | 1 | 0.9 GB | 88-93% | 2.0x | Experimental |

---

## 2. GPTQ

```python
class GPTQQuantizer:
    """GPTQ: пост-тренировочная квантизация."""

    def __init__(self, model, calibration_dataset, bits: int = 4):
        self.model = model
        self.calibration = calibration_dataset
        self.bits = bits

    def quantize(self) -> dict:
        """GPTQ квантизация layer-by-layer."""

        quantized_layers = {}

        for name, layer in self.model.named_layers:
            if hasattr(layer, "weight"):
                # 1. Собираем статистики на calibration data
                activations = self._collect_activations(layer)

                # 2. GPTQ: оптимальная квантизация с учётом распределения
                q_weight, scale, zero_point = self._gptq_quantize(
                    layer.weight.data, activations, self.bits
                )

                quantized_layers[name] = {
                    "q_weight": q_weight,  # quantized int4
                    "scale": scale,         # fp16 scaling factor
                    "zero_point": zero_point,  # int zero point
                }

                # Memory savings
                original_mb = layer.weight.data.numel() * 2 / 1024**2
                quantized_mb = q_weight.numel() * 0.5 / 1024**2  # 4 bit = 0.5 bytes
                log(f"{name}: {original_mb:.1f}MB → {quantized_mb:.1f}MB ({quantized_mb/original_mb:.0%})")

        return quantized_layers

    def _gptq_quantize(self, weight: torch.Tensor, activations: torch.Tensor, bits: int) -> tuple:
        """GPTQ: Optimal Brain Quantization."""
        # Cholesky-based optimal quantization
        # Использует Hessian веса для минимальной ошибки
        H = activations.T @ activations  # Hessian approximation
        diag = torch.diag(H)
        # Quantize columns with smallest impact
        # (упрощённая версия, полный GPTQ сложнее)
        return weight, 1.0, 0
```

---

## 3. AWQ

```python
class AWQQuantizer:
    """AWQ: Activation-aware Weight Quantization."""

    def quantize(self, model, calibration_data, bits: int = 4):
        """AWQ: сохраняет важные (активированные) весы."""

        quantized = {}

        for name, layer in model.named_layers:
            if hasattr(layer, "weight"):
                # 1. Измеряем важность по активациям
                importance = self._compute_importance(layer, calibration_data)

                # 2. Масштабируем: важные весы → выше точность
                # AWQ: per-channel scaling
                scales = self._compute_scales(layer.weight, importance)

                # 3. Quantize с пер-чаннельными scale
                q_weight = self._quantize_with_scales(layer.weight, scales)

                quantized[name] = {
                    "q_weight": q_weight,
                    "scales": scales,
                }

        return quantized

    def _compute_importance(self, layer, calibration_data) -> torch.Tensor:
        """Важность каналов по активациям."""
        # Каналы с большими активациями → важнее
        layer.eval()
        with torch.no_grad():
            output = layer(calibration_data)
        importance = torch.norm(output, dim=0)
        return importance
```

---

## 4. Evaluation After Quantization

```python
class QuantizationEvaluator:
    """Оценка качества после квантизации."""

    def evaluate(self, original_model, quantized_model, test_set: list[dict]) -> dict:
        """Сравнение original vs quantized."""

        metrics = {}
        for name, test in test_set.items():
            original_output = original_model.generate(test["input"])
            quantized_output = quantized_model.generate(test["input"])

            metrics[name] = {
                "similarity": self._semantic_similarity(original_output, quantized_output),
                "original_ppl": self._perplexity(original_model, test["input"]),
                "quantized_ppl": self._perplexity(quantized_model, test["input"]),
            }

        avg_drop = sum(
            1 - m["similarity"] for m in metrics.values()
        ) / len(metrics)

        return {
            "per_metric": metrics,
            "avg_quality_drop": f"{avg_drop:.2%}",
            "memory_gb_original": self._model_memory(original_model),
            "memory_gb_quantized": self._model_memory(quantized_model),
            "memory_savings": f"{(1 - self._model_memory(quantized_model) / self._model_memory(original_model)):.0%}",
        }
```

---

## 5. Quantization Decision Tree

```python
def choose_quantization(gpu_memory_gb: float, quality_needed: str, use_case: str) -> str:
    """Выбор метода квантизации."""

    if use_case == "training":
        return "NF4" if gpu_memory_gb < 24 else "fp16"

    if gpu_memory_gb >= 80:  # A100, H100
        return "fp8" if quality_needed == "max" else "AWQ"

    if gpu_memory_gb >= 24:  # RTX 4090, A10
        return "AWQ" if quality_needed == "high" else "GGUF_Q4"

    if gpu_memory_gb >= 12:  # RTX 3060, MPS
        return "GPTQ" if quality_needed == "medium" else "GGUF_Q4"

    if gpu_memory_gb >= 8:  # Apple Silicon, RTX 2060
        return "GGUF_Q4" if quality_needed == "medium" else "GGUF_Q2"

    # Edge / CPU
    return "Ternary" if quality_needed == "medium" else "GGUF_Q2"
```

---

## Резюме

```
Quantization: выбор битности

fp16 (16 bit) → 14GB/7B — максимальное качество
fp8  (8 bit)  → 7GB/7B — production standard 2026
AWQ  (4 bit)  → 3.5GB/7B — лучший speed/quality
GGUF (4 bit)  → 4.1GB/7B — универсальный (CPU/GPU)
Ternary (2 bit) → 1.8GB/7B — edge devices

Ключевые метрики:
  Quality drop: <3% для 4-bit
  Memory savings: 75% для 4-bit
  Speed gain: 1.3-1.8x для 4-bit
```

---

## Практическое задание

1. Примени GPTQ (4-bit) к 7B модели, измерь quality drop.

2. Сравни AWQ vs GPTQ на одном датасете.

3. Настрой QuantizationEvaluator с semantic similarity.

4. Построй decision tree для выбора под своё железо.

---

## Проверь себя

1. Чем AWQ отличается от GPTQ?

2. Какой метод лучше для GPU? Для CPU?

3. Сколько памяти экономит 4-bit квантизация на 7B?

4. Как оценить quality drop после квантизации?

---

## Ссылки

- [[01-inference-optimization]] — inference optimization
- [[03-speculative-decoding]] — следующий урок: speculative decoding
