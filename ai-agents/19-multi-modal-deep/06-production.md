---
created: 2026-05-28
tags: [course/multi-modal-deep, production, caching, evaluation, cost, guardrails]
status: active
---

# Урок 19.6: Production Multi-modal Systems

> [!quote] Ключевая идея
> Multi-modal в production — это не про модели, а про инфраструктуру: кэш, дедупликацию, контроль стоимости, мониторинг, A/B тесты и guardrails. Модели решают 20% проблем, инфраструктура — 80%.

---

## 1. Image Caching & Perceptual Deduplication

```python
import hashlib
from PIL import Image
import numpy as np


class PerceptualHasher:
    """Перцептивный хеш для дедупликации изображений (pHash)."""

    def __init__(self, hash_size: int = 16):
        self.hash_size = hash_size

    def compute(self, image: Image.Image) -> str:
        """Вычисляет pHash изображения."""
        # Resize to hash_size+1 x hash_size
        img = image.convert("L").resize(
            (self.hash_size + 1, self.hash_size), Image.LANCZOS
        )
        pixels = np.array(img, dtype=np.float32)

        # Разностный хеш (difference hash)
        diff = pixels[:, 1:] > pixels[:, :-1]
        bits = diff.flatten()
        return hex(int("".join(str(int(b)) for b in bits), 2))[2:]

    def hamming_distance(self, hash1: str, hash2: str) -> int:
        """Hamming distance между хешами."""
        h1 = int(hash1, 16)
        h2 = int(hash2, 16)
        return bin(h1 ^ h2).count("1")

    def is_duplicate(self, hash1: str, hash2: str, threshold: int = 10) -> bool:
        """Проверяет дубликат с порогом расстояния."""
        return self.hamming_distance(hash1, hash2) <= threshold


class ImageCache:
    """Кэш изображений с перцептивной дедупликацией."""

    def __init__(self, backend: Any, ttl: int = 3600, dedup_threshold: int = 10):
        self.backend = backend          # Redis / in-memory / disk
        self.hasher = PerceptualHasher()
        self.ttl = ttl
        self.dedup_threshold = dedup_threshold

    async def get(self, image: Image.Image) -> str | None:
        """Ищет изображение в кэше по pHash + возвращает результат если найден."""
        phash = self.hasher.compute(image)

        # Exact match
        cached = await self.backend.get(f"phash:{phash}")
        if cached:
            return cached

        # Near-duplicate search
        all_hashes = await self.backend.keys("phash:*")
        for key in all_hashes:
            existing_hash = key.split(":", 1)[1]
            if self.hasher.hamming_distance(phash, existing_hash) <= self.dedup_threshold:
                cached = await self.backend.get(key)
                if cached:
                    return cached

        return None

    async def set(self, image: Image.Image, result: str):
        """Сохраняет результат в кэш."""
        phash = self.hasher.compute(image)
        await self.backend.set(f"phash:{phash}", result, ttl=self.ttl)


class ImageDeduplicator:
    """Дедупликация изображений в батче (перед LLM)."""

    def __init__(self, threshold: float = 0.85):
        self.threshold = threshold

    def deduplicate(self, images: list[Image.Image]) -> list[Image.Image]:
        """Удаляет визуально похожие изображения."""
        unique = []
        for img in images:
            if not self._is_similar_to_any(img, unique):
                unique.append(img)
        return unique

    def _is_similar_to_any(self, img: Image.Image, candidates: list[Image.Image]) -> bool:
        import cv2
        from skimage.metrics import structural_similarity as ssim

        img_array = np.array(img.convert("L"))
        for candidate in candidates:
            cand_array = np.array(candidate.convert("L"))
            cand_array = cv2.resize(cand_array, (img_array.shape[1], img_array.shape[0]))
            similarity = ssim(img_array, cand_array)
            if similarity > self.threshold:
                return True
        return False
```

---

## 2. Resolution Management

```python
class ResolutionManager:
    """Автоматическое управление разрешением под каждую модель."""

    MODEL_SPECS = {
        "gpt-4o": {"max_dim": 2048, "tile_size": 156, "cost_per_tile": 0.00215},
        "claude-sonnet-4": {"max_dim": 1560, "cost": 0.003},
        "gemini-2.0-flash": {"max_dim": 3072, "tile_size": 156, "cost_per_tile": 0.00015},
        "claude-3-haiku": {"max_dim": 1024, "cost": 0.0005},
    }

    PRESETS = {
        "thumbnail": {"max_dim": 256, "quality": 70},
        "preview": {"max_dim": 512, "quality": 80},
        "full": {"max_dim": 1024, "quality": 90},
        "original": {"max_dim": 4096, "quality": 100},
    }

    def __init__(self, model: str = "gpt-4o", preset: str = "full"):
        self.model = model
        self.preset = preset

    def optimize(self, image: Image.Image) -> Image.Image:
        """Оптимизирует изображение под модель."""

        spec = self.MODEL_SPECS.get(self.model, self.MODEL_SPECS["gpt-4o"])
        preset = self.PRESETS.get(self.preset, self.PRESETS["full"])

        target_dim = min(spec["max_dim"], preset["max_dim"])

        # Resize
        if max(image.size) > target_dim:
            ratio = target_dim / max(image.size)
            new_size = (int(image.width * ratio), int(image.height * ratio))
            image = image.resize(new_size, Image.LANCZOS)

        # Auto-downscale для экономии: если модель не выигрывает от high-res
        if self._should_downscale(image, spec):
            image = image.resize(
                (min(image.width, 1024), min(image.height, 1024)),
                Image.LANCZOS,
            )

        return image

    def _should_downscale(self, image: Image.Image, spec: dict) -> bool:
        """Определяет, можно ли уменьшить без потери качества."""
        # Если изображение — UI скриншот с большим текстом, не уменьшаем
        # Если фото или документ — можно уменьшить
        w, h = image.size
        total_pixels = w * h

        # Если tile-based модель:
        if "tile_size" in spec:
            num_tiles = ((w + spec["tile_size"] - 1) // spec["tile_size"]) * \
                        ((h + spec["tile_size"] - 1) // spec["tile_size"])
            cost = num_tiles * spec["cost_per_tile"]
            # Если стоимость > $0.05 за кадр — downscale
            return cost > 0.05

        return total_pixels > 1024 * 1024  # > 1MP
```

---

## 3. Cost Tracking Per Modality

```python
class MultiModalCostTracker:
    """Трекинг стоимости по модальностям."""

    COST_TABLE = {
        "gpt-4o": {
            "text_input": 0.0000025,     # per token
            "text_output": 0.00001,      # per token
            "image_tile": 0.00215,       # per 156x156 tile (high_detail)
            "image_low": 0.000085,       # low_detail
            "audio_input": 0.0001,       # per token (Whisper)
        },
        "claude-sonnet-4": {
            "text_input": 0.000003,
            "text_output": 0.000015,
            "image_cost": 0.003,         # flat per image
        },
        "gemini-2.0-flash": {
            "text_input": 0.0000001,
            "text_output": 0.0000004,
            "image_tile": 0.00015,
        },
    }

    def __init__(self, model: str = "gpt-4o", budget_usd: float = 1.0):
        self.model = model
        self.budget = budget_usd
        self.session = {
            "total_cost": 0.0,
            "by_modality": {"text": 0.0, "image": 0.0, "audio": 0.0, "video": 0.0},
            "calls": 0,
        }

    def track_text(self, input_tokens: int, output_tokens: int):
        """Трекинг стоимости текста."""

        prices = self.COST_TABLE[self.model]
        cost = input_tokens * prices["text_input"] + output_tokens * prices["text_output"]
        self._add_cost("text", cost)

    def track_image(self, image: Image.Image, detail: str = "high"):
        """Трекинг стоимости изображения."""

        prices = self.COST_TABLE[self.model]

        if detail == "high" and "image_tile" in prices:
            w, h = image.size
            tiles = ((w + 155) // 156) * ((h + 155) // 156)
            cost = 85 / 1000000 + tiles * prices["image_tile"]  # base + tiles
        elif "image_cost" in prices:
            cost = prices["image_cost"]
        else:
            cost = prices.get("image_tile", 0.00215)

        self._add_cost("image", cost)

    def track_video(self, num_frames: int, resolution: tuple[int, int]):
        """Трекинг стоимости видео."""
        frame_cost = 0.0
        for _ in range(num_frames):
            mock_image = Image.new("RGB", resolution)
            self.track_image(mock_image)
        self._add_cost("video", frame_cost)

    def _add_cost(self, modality: str, cost: float):
        self.session["total_cost"] += cost
        self.session["by_modality"][modality] += cost
        self.session["calls"] += 1

        if self.session["total_cost"] > self.budget:
            raise BudgetExceededError(
                f"Budget {self.budget}$ exceeded: {self.session['total_cost']:.4f}$"
            )

    def get_report(self) -> dict:
        """Отчёт о стоимости сессии."""
        report = {**self.session}
        for mod, cost in report["by_modality"].items():
            if cost > 0:
                report["by_modality"][mod] = round(cost, 6)
        report["total_cost"] = round(report["total_cost"], 6)

        if report["total_cost"] > 0:
            report["breakdown_pct"] = {
                mod: round(cost / report["total_cost"] * 100, 1)
                for mod, cost in report["by_modality"].items()
                if cost > 0
            }

        return report
```

---

## 4. Evaluation of Multi-modal Agents

```python
class MultiModalEvaluator:
    """Оценка качества multi-modal агентов."""

    METRICS = [
        "text_accuracy",       # Точность текстового ответа
        "visual_grounding",    # Ответ соответствует изображению
        "chart_faithfulness",  # Данные графика не искажены
        "format_compliance",   # Возврат в правильном формате (JSON)
        "cost_efficiency",     # Стоимость на задачу
        "latency",             # Время ответа
    ]

    async def evaluate(self, test_cases: list[dict], agent_fn: callable) -> dict:
        """Прогоняет тестовые случаи и собирает метрики."""

        results = []
        for tc in test_cases:
            t_start = time.perf_counter()
            response = await agent_fn(tc["input"])
            latency = time.perf_counter() - t_start

            evaluation = await self._evaluate_single(tc, response)
            evaluation["latency_sec"] = round(latency, 2)
            results.append(evaluation)

        # Агрегация
        aggregated = self._aggregate(results)
        aggregated["num_cases"] = len(test_cases)

        return aggregated

    async def _evaluate_single(self, tc: dict, response: str) -> dict:
        """Оценка одного кейса."""

        prompt = f"""Evaluate this agent response.

Task: {tc.get("task", "")}
Expected: {tc.get("expected", "")}
Actual: {response[:1000]}

Rate each metric 0.0-1.0:
- text_accuracy: is the text correct?
- visual_grounding: does the answer match the image context (if any)?
- chart_faithfulness: if chart, are values correct?
- format_compliance: correct output format?

Return as JSON: {{"text_accuracy": 0.95, "visual_grounding": 0.8, ...}}"""

        evaluation = await self.judge_llm.generate(prompt)

        try:
            scores = json.loads(self._extract_json(evaluation))
        except json.JSONDecodeError:
            scores = {"text_accuracy": 0.5, "visual_grounding": 0.5}

        return {"scores": scores, "response": response[:200]}

    def _aggregate(self, results: list[dict]) -> dict:
        """Агрегирует результаты по метрикам."""

        metrics = {}
        for metric in self.METRICS:
            values = [r["scores"].get(metric, 0) for r in results]
            metrics[metric] = {
                "mean": round(np.mean(values), 3),
                "std": round(np.std(values), 3),
                "min": round(min(values), 3),
                "max": round(max(values), 3),
            }

        metrics["pass_rate"] = round(
            sum(1 for r in results if r["scores"].get("text_accuracy", 0) > 0.8)
            / len(results),
            3,
        )

        return metrics
```

---

## 5. Testing Strategies

```python
class MultiModalTester:
    """Стратегии тестирования multi-modal агентов."""

    TEST_TYPES = {
        "unit": "Отдельные компоненты (preprocessor, extractor)",
        "integration": "Пайплайн целиком",
        "regression": "Повторная прогонка старых кейсов",
        "edge_cases": "Граничные случаи",
        "cost": "Контроль стоимости на батче",
        "chaos": "Подача мусора, битых файлов",
    }

    def __init__(self):
        self.test_suite = []

    def add_test(self, name: str, input_data: Any, expected: Any, test_type: str = "unit"):
        self.test_suite.append({
            "name": name,
            "input": input_data,
            "expected": expected,
            "type": test_type,
        })

    async def run_tests(self, pipeline: Any) -> list[dict]:
        """Прогоняет тесты и возвращает результаты."""

        results = []
        for test in self.test_suite:
            try:
                t_start = time.perf_counter()
                response = await pipeline.process(test["input"])
                latency = time.perf_counter() - t_start

                passed = await self._check_result(response, test["expected"])

                results.append({
                    "name": test["name"],
                    "type": test["type"],
                    "passed": passed,
                    "latency_sec": round(latency, 2),
                })
            except Exception as e:
                results.append({
                    "name": test["name"],
                    "type": test["type"],
                    "passed": False,
                    "error": str(e),
                })

        return results

    def generate_edge_cases(self) -> list[dict]:
        """Генерация граничных случаев для multi-modal."""
        return [
            {"name": "empty_image", "input": Image.new("RGB", (1, 1)), "expected": "no content"},
            {"name": "huge_image", "input": Image.new("RGB", (10000, 10000)), "expected": "resized"},
            {"name": "corrupted_file", "input": b"not an image", "expected": "error"},
            {"name": "all_black", "input": Image.new("RGB", (512, 512), (0, 0, 0)), "expected": "dark"},
            {"name": "no_speech_audio", "input": self._generate_silence(), "expected": "no speech"},
            {"name": "video_no_frames", "input": "/dev/null", "expected": "error"},
        ]
```

---

## 6. Multi-modal Guardrails

```python
class MultiModalGuardrail:
    """Валидация multi-modal входов и выходов."""

    RULES = {
        "no_people": "Не анализируем изображения с людьми (privacy)",
        "no_nsfw": "Отклоняем NSFW контент",
        "max_resolution": "Максимальное разрешение 4096x4096",
        "max_file_size": "Макс 20MB на файл",
        "allowed_formats": ["PNG", "JPEG", "WEBP", "GIF", "MP4", "WAV", "MP3"],
        "text_only_if_image_unclear": "При неясном изображении — текстовая альтернатива",
    }

    async def validate_input(self, modality: str, content: Any) -> dict:
        """Валидирует входные данные."""

        if modality == "image":
            return self._validate_image(content)
        elif modality == "audio":
            return self._validate_audio(content)
        elif modality == "video":
            return self._validate_video(content)

        return {"valid": True}

    def _validate_image(self, image: Image.Image) -> dict:
        issues = []

        # Resolution
        if max(image.size) > 4096:
            issues.append({"rule": "max_resolution", "severity": "error", "message": "Image too large"})

        # NSFW
        nsfw_score = self._check_nsfw(image)
        if nsfw_score > 0.8:
            issues.append({"rule": "no_nsfw", "severity": "block", "message": "NSFW content"})

        # People detection (privacy)
        people_count = self._detect_people(image)
        if people_count > 0:
            issues.append({"rule": "no_people", "severity": "warn", "message": f"Detected {people_count} people"})

        return {"valid": len([i for i in issues if i["severity"] == "error"]) == 0, "issues": issues}

    def _detect_people(self, image: Image.Image) -> int:
        """HAAR cascade или HOG для детекции лиц."""
        import cv2
        face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )
        gray = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.1, 4)
        return len(faces)

    def _check_nsfw(self, image: Image.Image) -> float:
        """NSFW detection через lightweight classifier."""
        # В production: NSFW API или модель-классификатор
        return 0.0  # stub
```

---

## 7. Production Monitoring

```python
class MultiModalMonitor:
    """Мониторинг multi-modal production системы."""

    def __init__(self):
        self.metrics = {
            "total_requests": 0,
            "requests_by_modality": {"text": 0, "image": 0, "audio": 0, "video": 0},
            "latency_p50": 0.0,
            "latency_p95": 0.0,
            "latency_p99": 0.0,
            "error_rate": 0.0,
            "cost_total": 0.0,
            "cache_hit_rate": 0.0,
        }
        self.latencies: list[float] = []

    def record_request(self, modality: str, latency_ms: float, cost: float, cache_hit: bool, error: bool = False):
        """Записывает метрики запроса."""

        self.metrics["total_requests"] += 1
        self.metrics["requests_by_modality"][modality] += 1
        self.metrics["cost_total"] += cost

        self.latencies.append(latency_ms)

        if error:
            self.metrics["error_rate"] = (
                self.metrics["error_rate"] * (self.metrics["total_requests"] - 1) + 1
            ) / self.metrics["total_requests"]
        else:
            self.metrics["error_rate"] *= (self.metrics["total_requests"] - 1) / self.metrics["total_requests"]

        # Latency percentiles
        if len(self.latencies) >= 100:
            sorted_lat = sorted(self.latencies[-1000:])
            n = len(sorted_lat)
            self.metrics["latency_p50"] = sorted_lat[int(n * 0.5)]
            self.metrics["latency_p95"] = sorted_lat[int(n * 0.95)]
            self.metrics["latency_p99"] = sorted_lat[int(n * 0.99)]

        # Cache rate
        self._update_cache_rate(cache_hit)

    def _update_cache_rate(self, hit: bool):
        if not hasattr(self, "_cache_total"):
            self._cache_total = 0
            self._cache_hits = 0
        self._cache_total += 1
        if hit:
            self._cache_hits += 1
        self.metrics["cache_hit_rate"] = self._cache_hits / max(self._cache_total, 1)

    def get_dashboard(self) -> str:
        """Форматирует дашборд для вывода."""
        m = self.metrics
        return f"""
┌─ Multi-modal Production Dashboard ──────────────────────┐
│ Total requests: {m['total_requests']:<8d}                       │
│ By modality:  Text: {m['requests_by_modality']['text']:<5d}     │
│              Image: {m['requests_by_modality']['image']:<5d}    │
│              Audio: {m['requests_by_modality']['audio']:<5d}    │
│              Video: {m['requests_by_modality']['video']:<5d}    │
│ Latency p50:  {m['latency_p50']:<8.1f}ms                        │
│ Latency p95:  {m['latency_p95']:<8.1f}ms                        │
│ Latency p99:  {m['latency_p99']:<8.1f}ms                        │
│ Error rate:   {m['error_rate']:<8.4%}                           │
│ Total cost:   ${m['cost_total']:<8.4f}                          │
│ Cache rate:   {m['cache_hit_rate']:<8.1%}                       │
└──────────────────────────────────────────────────────────┘"""
```

---

## Резюме

```
Production Multi-modal Checklist:

☐ Image preprocessing pipeline (resize → compress → cache)
☐ Perceptual hashing for deduplication
☐ Resolution management per model
☐ Cost tracking per modality
☐ Budget enforcement
☐ Evaluation suite (accuracy, grounding, cost, latency)
☐ Edge case coverage (empty, corrupted, huge)
☐ Guardrails (privacy, NSFW, size limits)
☐ Monitoring dashboard (p50/p95/p99, error rate, cache rate)

Cost saving strategies:
  — Cache perceptual hashes: 40-60% hit rate
  — Auto-downscale: 2-5x cost reduction
  — Dedup near-identical frames: 30-50% fewer images
  — Low_detail mode for non-critical images: 20x cheaper
```

---

## Практическое задание

1. Реализуй PerceptualHasher для дедупликации повторяющихся изображений.

2. Собери MultiModalCostTracker с трекингом по модальностям и бюджетом.

3. Напиши Evaluation Suite: 10 тестовых кейсов с разными модальностями.

4. Добавь guardrails: NSFW check + privacy (face blur).

5. Подключи MultiModalMonitor и собери дашборд с latency percentiles.

---

## Проверь себя

1. Как работает perceptual hashing и чем отличается от MD5?

2. Какие 3 стратегии экономии на изображениях самые эффективные?

3. Как оценить качество multi-modal ответа (метрики)?

4. Какие guardrails нужны для multi-modal production?

5. Как определить p95 latency и зачем он нужен?

---

## Ссылки

- [[01-economics-architecture]] — экономика модальностей
- [[02-vision-deep]] — vision deep dive
- [[03-audio-deep]] — audio deep dive
- [[04-video-deep]] — video agents
- [[05-multimodal-rag]] — multi-modal RAG
- [[../12-quality-evolution/01-agent-evaluation]] — evaluation patterns
- [[../05-production/01-guardrails]] — guardrails basics
