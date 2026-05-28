---
created: 2026-05-28
tags: [course/performance-deep, distillation, pruning, compression, efficiency]
status: active
---

# Урок 25.4: Distillation & Pruning

> [!quote] Ключевая идея
> Distillation — не «сжать модель». Это передача поведения: student учится имитировать teacher. Pruning — не «удалить лишнее». Это хирургия: удаление нейронов/слоёв с минимальной потерей качества. В 2026 оба метода зрелые и production-ready.

---

## 1. Knowledge Distillation

```python
class KnowledgeDistillation:
    """Knowledge distillation: student → teacher imitation."""

    def __init__(self, teacher, student, temperature: float = 2.0, alpha: float = 0.5):
        self.teacher = teacher
        self.student = student
        self.t = temperature          # Temperature for softening
        self.alpha = alpha            # Balance: distillation vs student loss

    def distill_loss(self, student_logits: torch.Tensor, teacher_logits: torch.Tensor, labels: torch.Tensor) -> torch.Tensor:
        """KD loss: soft target + hard target."""

        # Soft targets (distillation)
        soft_teacher = torch.nn.functional.softmax(teacher_logits / self.t, dim=-1)
        soft_student = torch.nn.functional.log_softmax(student_logits / self.t, dim=-1)
        distill_loss = torch.nn.functional.kl_div(soft_student, soft_teacher, reduction="batchmean")
        distill_loss *= self.t ** 2  # Scale factor

        # Hard targets (student loss)
        student_loss = torch.nn.functional.cross_entropy(student_logits, labels)

        # Combined
        return self.alpha * distill_loss + (1 - self.alpha) * student_loss

    def train(self, dataset, epochs: int = 3):
        """Обучает student на dataset с teacher."""

        self.teacher.eval()
        self.student.train()
        optimizer = torch.optim.AdamW(self.student.parameters(), lr=5e-5)

        for epoch in range(epochs):
            for batch in dataset:
                # Teacher forward (no grad)
                with torch.no_grad():
                    teacher_logits = self.teacher(batch["input_ids"])

                # Student forward
                student_logits = self.student(batch["input_ids"])

                # Distillation loss
                loss = self.distill_loss(student_logits, teacher_logits, batch["labels"])

                loss.backward()
                optimizer.step()
                optimizer.zero_grad()

            log(f"Epoch {epoch+1}: loss = {loss.item():.4f}")
```

---

## 2. Distillation Strategies

```python
class DistillationStrategies:
    """Стратегии дистилляции."""

    STRATEGIES = {
        "response_based": {
            "description": "Student учится имитировать output teacher",
            "complexity": "Low",
            "quality": "Good",
            "data_needs": "Любые данные",
        },
        "feature_based": {
            "description": "Student учится имитировать intermediate representations",
            "complexity": "Medium",
            "quality": "Better",
            "data_needs": "Любые данные",
        },
        "relation_based": {
            "description": "Student учится отношениям между примерами",
            "complexity": "High",
            "quality": "Best",
            "data_needs": "Крупный датасет",
        },
        "self_distillation": {
            "description": "Модель учится у себя же (разные depths)",
            "complexity": "Low",
            "quality": "Good",
            "data_needs": "Не нужен teacher",
        },
        "progressive": {
            "description": "От большого teacher → medium → small",
            "complexity": "High",
            "quality": "Best",
            "data_needs": "Постепенно",
        },
    }

    @staticmethod
    def recommend(teacher_size: str, student_size: str, data_available: int) -> str:
        """Рекомендация стратегии."""

        if data_available < 10000:
            return "response_based"
        if teacher_size == "70B" and student_size == "7B":
            return "progressive"
        if student_size == "3B" or student_size == "1B":
            return "feature_based"
        return "response_based"
```

---

## 3. Model Pruning

```python
class ModelPruner:
    """Pruning: удаление неважных весов/нейронов."""

    METHODS = {
        "magnitude": "Удаление весов с маленькой magnitude",
        "gradient": "Удаление по gradient sensitivity",
        "movement": "Удаление по движению весов (SparseGPT)",
        "structural": "Удаление целых нейронов/каналов",
        "evolutionary": "Эволюционный поиск оптимальной архитектуры",
    }

    def prune_magnitude(self, model, sparsity: float = 0.5):
        """Magnitude pruning: удаляем веса < threshold."""
        threshold = self._find_threshold(model, sparsity)

        for name, param in model.named_parameters():
            if "weight" in name:
                mask = torch.abs(param) > threshold
                param.data *= mask

        return model

    def prune_structural(self, model, sparsity: float = 0.3):
        """Structural pruning: удаляем целые нейроны/каналы."""
        for name, layer in model.named_layers:
            if hasattr(layer, "weight") and layer.weight.dim() >= 2:
                # L2 norm каналов
                norms = torch.norm(layer.weight, dim=1)
                threshold = torch.quantile(norms, sparsity)
                mask = norms > threshold

                # Создаём новую матрицу без обнулённых каналов
                layer.weight.data = layer.weight.data[mask]

                log(f"{name}: {layer.weight.shape[1]} → {mask.sum().item()} neurons")

    def prune_gradual(self, model, target_sparsity: float, steps: int = 10):
        """Gradual pruning: увеличиваем sparsity постепенно."""
        current_sparsity = 0
        step_size = target_sparsity / steps

        scheduler = torch.optim.lr_scheduler.LambdaLR(
            optimizer, lambda step: 1 - step / steps
        )

        for step in range(steps):
            current_sparsity += step_size
            self.prune_magnitude(model, current_sparsity)

            # Fine-tune после pruning
            for batch in dataset:
                loss = model(batch)
                loss.backward()
                optimizer.step()

            log(f"Pruning step {step+1}: sparsity = {current_sparsity:.1%}")
```

---

## 4. Distillation + Pruning Pipeline

```python
class CompressionPipeline:
    """Полный пайплайн: distillation → pruning → quantization."""

    async def compress(self, teacher, dataset, target_size: str = "7B") -> dict:
        """Сжимает teacher до target_size."""

        steps = []

        # 1. Distill: teacher → student
        log("Step 1: Knowledge distillation...")
        student = self._create_student(teacher.config, target_size)
        distiller = KnowledgeDistillation(teacher, student)
        distiller.train(dataset)
        steps.append("distillation")

        # 2. Prune: удаляем неважные нейроны
        log("Step 2: Structural pruning...")
        pruner = ModelPruner()
        pruner.prune_structural(student, sparsity=0.2)
        steps.append("pruning")

        # 3. Quantize: 4-bit
        log("Step 3: Quantization...")
        quantizer = AWQQuantizer()
        quantized = quantizer.quantize(student, dataset)
        steps.append("quantization")

        # 4. Evaluate
        log("Step 4: Evaluation...")
        evaluator = QuantizationEvaluator()
        results = evaluator.evaluate(teacher, quantized, dataset)

        return {
            "steps": steps,
            "original_size_gb": self._model_size(teacher),
            "compressed_size_gb": self._model_size(quantized),
            "compression_ratio": self._model_size(teacher) / self._model_size(quantized),
            "quality_drop": results.get("avg_quality_drop", "N/A"),
            "speedup": results.get("speedup", 1.0),
        }
```

---

## 5. Comparison: Distillation vs Pruning vs Quantization

```python
class CompressionComparison:
    """Сравнение методов компрессии."""

    @staticmethod
    def compare(teacher_size: str = "70B") -> dict:
        return {
            "distillation": {
                "final_size": f"{int(teacher_size[:-1]) * 0.1}B",  # 10x smaller
                "quality": "95-98%",
                "training_cost": "$$$",
                "inference_speed": "3-10x",
                "best_for": "Production replacement",
            },
            "pruning": {
                "final_size": f"{int(teacher_size[:-1]) * 0.6}B",  # 40% smaller
                "quality": "97-99%",
                "training_cost": "$",
                "inference_speed": "1.5-2x",
                "best_for": "Fine-tuning budget",
            },
            "quantization": {
                "final_size": f"{int(teacher_size[:-1]) * 0.25}B",  # 4x smaller
                "quality": "97-99%",
                "training_cost": "$",
                "inference_speed": "1.3-1.8x",
                "best_for": "Quick deployment",
            },
            "all_three": {
                "final_size": f"{int(teacher_size[:-1]) * 0.05}B",  # 20x smaller
                "quality": "93-96%",
                "training_cost": "$$$",
                "inference_speed": "5-15x",
                "best_for": "Edge devices",
            },
        }
```

---

## Резюме

```
Distillation: teacher → student
  70B → 7B: 95-98% качества, 10x быстрее
  Лучшая стратегия: progressive (70B → 13B → 7B)

Pruning: удаление неважного
  Magnitude: просто, 40% спарсити
  Structural: удаление целых нейронов
  Gradual: prune + fine-tune

Pipeline: Distill → Prune → Quantize
  Итог: 20x компрессия, 93-96% качества

Выбор:
  Есть GPU, нужно качество → Distillation
  Есть бюджет на fine-tune → Pruning
  Нет времени/денег → Quantization
  Edge device → All three
```

---

## Практическое задание

1. Реализуй KnowledgeDistillation: teacher → student (response-based).

2. Добавь ModelPruner с magnitude и structural pruning.

3. Настрой CompressionPipeline: distill → prune → quantize.

4. Сравни результат: quality vs size vs speed.

---

## Проверь себя

1. Чем distillation отличается от quantization?

2. Какие 5 стратегий дистилляции существуют?

3. Как работает structural pruning?

4. Какой pipeline компрессии даёт максимальный результат?

---

## Ссылки

- [[01-inference-optimization]] — inference optimization
- [[02-quantization]] — quantization
- [[03-speculative-decoding]] — speculative decoding
- [[../../22-fine-tuning-deep/02-lora-deep]] — LoRA (альтернатива сжатию)
