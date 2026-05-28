---
created: 2026-05-28
tags: [course/multi-modal-deep, vision, agents, computer-vision, ui-testing]
status: active
---

# Урок 19.2: Vision Agents Deep Dive

> [!quote] Ключевая идея
> Vision-агент — это не «посмотри на картинку и опиши». Это целый пайплайн: preprocess → route → analyze → extract → validate. Умение управлять качеством, размером и стоимостью vision-запроса отличает архитектора от пользователя.

---

## 1. Image Preprocessing Pipeline

Сырое изображение от пользователя (4K фото, скриншот, PDF) никогда не должно идти напрямую в LLM.

```python
from PIL import Image
from io import BytesIO
import hashlib


class ImagePreprocessor:
    """Пайплайн оптимизации изображений перед отправкой в LLM."""

    MAX_DIMENSIONS = {
        "gpt-4o": 2048,      # max по короткой стороне
        "claude-sonnet-4": 1560,  # рекомендуемый max
        "gemini-2.0-flash": 3072,
    }

    # Рекомендуемые форматы по сценарию
    FORMAT_RECOMMENDATIONS = {
        "screenshot": {"format": "PNG", "quality": 85, "max_dim": 1024},
        "photo": {"format": "JPEG", "quality": 80, "max_dim": 1536},
        "document": {"format": "PNG", "quality": 95, "max_dim": 2048},
        "chart": {"format": "PNG", "quality": 90, "max_dim": 1536},
        "ui_element": {"format": "PNG", "quality": 90, "max_dim": 768},
    }

    def __init__(self, model: str = "gpt-4o"):
        self.model = model

    def optimize(self, image: Image.Image, scenario: str = "screenshot") -> tuple[Image.Image, dict]:
        """Оптимизирует изображение: ресайз, сжатие, обрезка."""

        original_size = image.size
        original_bytes = self._image_bytes(image)

        # 1. Определяем оптимальный размер под сценарий
        rec = self.FORMAT_RECOMMENDATIONS.get(scenario, self.FORMAT_RECOMMENDATIONS["screenshot"])
        max_dim = min(rec["max_dim"], self.MAX_DIMENSIONS.get(self.model, 2048))

        # 2. Resize с сохранением aspect ratio
        if max(image.size) > max_dim:
            ratio = max_dim / max(image.size)
            new_size = (int(image.width * ratio), int(image.height * ratio))
            image = image.resize(new_size, Image.LANCZOS)

        # 3. Оптимизация формата
        output = BytesIO()
        if rec["format"] == "JPEG":
            image = image.convert("RGB")
            image.save(output, format="JPEG", quality=rec["quality"], optimize=True)
        else:
            image.save(output, format="PNG", optimize=True)

        optimized_bytes = output.tell()

        stats = {
            "original_size": original_size,
            "original_bytes": original_bytes,
            "optimized_size": image.size,
            "optimized_bytes": optimized_bytes,
            "compression_ratio": round(original_bytes / max(optimized_bytes, 1), 1),
            "format": rec["format"],
        }

        return image, stats

    def _image_bytes(self, image: Image.Image) -> int:
        buf = BytesIO()
        image.save(buf, format="PNG")
        return buf.tell()

    def compute_hash(self, image: Image.Image) -> str:
        """Перцептивный хеш для кэширования."""
        img = image.resize((32, 32), Image.LANCZOS).convert("L")
        pixels = list(img.getdata())
        avg = sum(pixels) / len(pixels)
        bits = "".join("1" if p > avg else "0" for p in pixels)
        return hex(int(bits, 2))[2:]
```

### Production Pipeline

```python
class VisionPipeline:
    """Полный vision-пайплайн."""

    def __init__(self, model: str = "gpt-4o", cache: "VisionCache | None" = None):
        self.preprocessor = ImagePreprocessor(model)
        self.cache = cache

    async def process(self, image: Image.Image, query: str, scenario: str = "screenshot") -> dict:
        # 1. Хеш для кэша
        image_hash = self.preprocessor.compute_hash(image)
        cache_key = f"{image_hash}:{hash(query)}"

        if self.cache:
            cached = await self.cache.get(cache_key)
            if cached:
                return {**cached, "from_cache": True}

        # 2. Оптимизация
        optimized, stats = self.preprocessor.optimize(image, scenario)

        # 3. Анализ
        result = await self._analyze(optimized, query)

        # 4. Сохраняем в кэш
        output = {"result": result, "stats": stats, "from_cache": False}
        if self.cache:
            await self.cache.set(cache_key, output, ttl=3600)

        return output
```

---

## 2. Chart Understanding

Один из самых частых use-case: извлечение структурированных данных из графиков.

```python
class ChartAnalyzer:
    """Извлекает структурированные данные из графиков и диаграмм."""

    CHART_TYPES = ["bar", "line", "pie", "scatter", "area", "heatmap", "table"]

    async def extract_data(self, chart_image: Image.Image) -> dict:
        """Извлекает данные из графика в JSON."""

        prompt = """Analyze this chart/image and extract:
1. Chart type (bar/line/pie/scatter/area/table)
2. Title and axis labels
3. All data points with values
4. Key insights: trends, max/min values, anomalies
5. If table — extract ALL rows as JSON array

Return ONLY valid JSON. Example:
{"chart_type":"bar","title":"Sales 2025","axes":{"x":"Month","y":"Revenue $"},
 "data":[{"label":"Jan","value":15000},...],
 "insights":["Peak in March: $22K","Upward trend of 12%"]}"""

        response = await self.llm.generate([
            {"type": "text", "text": prompt},
            {"type": "image", "image": chart_image},
        ], temperature=0, response_format="json")

        return json.loads(response)

    async def compare_charts(self, charts: list[Image.Image], question: str) -> str:
        """Сравнивает несколько графиков."""

        content = [{"type": "text", "text": f"Compare these charts: {question}"}]
        for chart in charts:
            content.append({"type": "image", "image": chart})

        return await self.llm.generate(content)


# === Anti-pattern: ручной OCR для графиков ===
# ❌ Не надо: OCR на графике даёт сырые пиксельные данные
text = ocr(chart_image)  # бесполезно для bar chart

# ✅ Надо: передать график vision-модели напрямую
response = llm.generate(["What's the trend?", {"type": "image", "image": chart}])
```

---

## 3. UI Screenshot Testing

Vision-агенты незаменимы для валидации UI — находят баги, которые текстовый анализатор не видит.

```python
class UIVisionTester:
    """Автоматизированное тестирование UI через vision."""

    async def validate_screenshot(self, screenshot: Image.Image, spec: dict) -> list[dict]:
        """Проверяет скриншот на соответствие спецификации."""

        prompt = f"""You are a UI testing expert. Validate this screenshot against the spec:

Specification:
{json.dumps(spec, indent=2)}

Check:
1. All required elements present? (buttons, text, inputs)
2. Correct positioning and alignment?
3. Visual defects? (overlapping, clipping, overflow)
4. Color correctness per spec?
5. Text matches expected?
6. Responsive breakpoints respected?

For each issue, return: {{"severity":"critical|major|minor","element":"...","expected":"...","actual":"...","suggestion":"..."}}"""

        response = await self.llm.generate([
            {"type": "text", "text": prompt},
            {"type": "image", "image": screenshot},
        ], temperature=0)

        return self._parse_issues(response)

    async def screenshot_diff(self, before: Image.Image, after: Image.Image, change_description: str) -> list[str]:
        """Сравнивает два скриншота и находит изменения."""

        prompt = f"""Compare these two screenshots.
Expected change: {change_description}

List ONLY unexpected differences:
1. Visual regressions (missing elements, broken layout)
2. Unintended color/text changes
3. Layout shifts

Ignore the expected change."""

        response = await self.llm.generate([
            {"type": "text", "text": prompt},
            {"type": "image", "image": before},
            {"type": "image", "image": after},
        ], temperature=0)

        return [line.strip() for line in response.split("\n") if line.strip()]

    def _parse_issues(self, response: str) -> list[dict]:
        """Парсинг/issues из ответа LLM."""
        try:
            import re
            json_match = re.search(r'\[.*\]', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except (json.JSONDecodeError, AttributeError):
            pass
        return [{"severity": "info", "description": response[:200]}]


# === Example: CI Integration ===
async def ci_visual_regression_check():
    tester = UIVisionTester()
    before = Image.open("screenshots/main-before.png")
    after = Image.open("screenshots/main-after.png")

    issues = await tester.screenshot_diff(before, after, "Update button colors to new brand")

    if any(i["severity"] == "critical" for i in issues):
        raise Exception(f"Visual regression detected! {len(issues)} issues")
    print(f"Visual check passed: {len(issues)} minor issues")
```

---

## 4. Document Extraction (Invoices, Forms, Tables)

Vision-агенты для извлечения данных из документов — альтернатива традиционному OCR.

```python
class DocumentExtractor:
    """Извлечение структурированных данных из документов."""

    DOCUMENT_TYPES = {
        "invoice": {
            "fields": ["invoice_number", "date", "vendor", "total", "tax", "line_items"],
            "schema": {
                "invoice_number": "string",
                "date": "date",
                "vendor": {"name": "string", "address": "string", "tax_id": "string"},
                "line_items": [{"description": "string", "quantity": "number", "unit_price": "number", "total": "number"}],
                "subtotal": "number",
                "tax": "number",
                "total": "number",
                "currency": "string",
            },
        },
        "receipt": {
            "fields": ["merchant", "date", "items", "total", "payment_method"],
        },
        "form": {
            "fields": ["form_type", "filled_fields"],
        },
    }

    async def extract(self, document: Image.Image, doc_type: str = "invoice") -> dict:
        """Извлекает структурированные данные из документа."""

        schema = self.DOCUMENT_TYPES.get(doc_type, self.DOCUMENT_TYPES["invoice"])
        prompt = f"""Extract data from this {doc_type}.

Return ONLY valid JSON matching this schema:
{json.dumps(schema['schema'], indent=2)}

Rules:
- Extract ALL visible text
- Preserve numbers exactly as shown (including decimals)
- If a field is not visible, use null
- Do NOT infer missing values"""

        # Preprocessing for documents: higher resolution, better contrast
        processed = self._enhance_for_document(document)

        response = await self.llm.generate([
            {"type": "text", "text": prompt},
            {"type": "image", "image": processed},
        ], temperature=0)

        return self._validate_extraction(response, schema)

    def _enhance_for_document(self, image: Image.Image) -> Image.Image:
        """Улучшает читаемость документа: контраст, резкость, бинаризация."""
        from PIL import ImageEnhance, ImageFilter
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(1.5)
        enhancer = ImageEnhance.Sharpness(image)
        image = enhancer.enhance(2.0)
        return image

    def _validate_extraction(self, response: str, schema: dict) -> dict:
        try:
            data = json.loads(self._extract_json(response))
            required = schema.get("fields", [])
            missing = [f for f in required if f not in data]
            return {
                "data": data,
                "confidence": "high" if not missing else "partial",
                "missing_fields": missing if missing else None,
            }
        except json.JSONDecodeError:
            return {"data": {"raw": response}, "confidence": "low"}
```

---

## 5. Visual RAG

Поиск не только по тексту, но и по изображениям.

```python
class VisualRAG:
    """RAG с поддержкой поиска по изображениям."""

    def __init__(self, text_encoder: Any, image_encoder: Any):
        self.text_enc = text_encoder     # embedding model (text)
        self.image_enc = image_encoder   # CLIP or similar
        self.vector_db = ChromaCollection()

    async def search_by_text(self, query: str, top_k: int = 5) -> list[dict]:
        """Текстовый поиск по документам + изображениям."""
        query_emb = self.text_enc.encode(query)
        return self.vector_db.search(query_emb, top_k=top_k)

    async def search_by_image(self, query_image: Image.Image, top_k: int = 5) -> list[dict]:
        """Поиск похожих изображений + связанных документов."""
        image_emb = self.image_enc.encode(query_image)
        return self.vector_db.search(image_emb, top_k=top_k)

    async def hybrid_search(self, query: str, query_image: Image.Image | None = None, top_k: int = 5) -> list[dict]:
        """Гибридный поиск: объединение текстового и визуального."""

        results = []

        # Text search
        text_emb = self.text_enc.encode(query)
        text_results = self.vector_db.search(text_emb, top_k=top_k // 2)
        results.extend(text_results)

        # Image search (если есть)
        if query_image:
            image_emb = self.image_enc.encode(query_image)
            image_results = self.vector_db.search(image_emb, top_k=top_k // 2)
            results.extend(image_results)

        # De-duplicate and re-rank
        seen = set()
        unique = []
        for r in results:
            if r["id"] not in seen:
                seen.add(r["id"])
                unique.append(r)

        return unique[:top_k]
```

---

## Резюме

```
Vision Agent Pipeline:

1. Preprocess:  resize + compress + enhance (до 10x экономии)
2. Classify:    chart? screenshot? document? photo?
3. Analyze:     специализированный промт под тип
4. Extract:     структурированные данные (JSON)
5. Validate:    проверка на галлюцинации

Экономика:
  — Скриншот 4K → 1024px: экономия 80% токенов
  — PNG для UI, JPEG для фото
  — Кэш перцептивных хешей: повторные запросы бесплатно

Anti-patterns:
  ❌ OCR на графиках (бесполезно)
  ❌ 4K изображение напрямую в LLM (дорого)
  ❌ Слепая вера vision (chart может галлюцинировать тренды)
```

---

## Практическое задание

1. Напиши VisionPipeline с preprocessor, который принимает скриншот 4K и оптимизирует его для GPT-4o.

2. Реализуй ChartAnalyzer, который извлекает данные из bar chart и возвращает JSON.

3. Собери UIVisionTester для CI: принимает скриншот и spec, возвращает список багов.

4. Добавь Visual RAG: поиск по скриншотам через CLIP-эмбеддинги.

---

## Проверь себя

1. Какие 4 шага проходит изображение в vision-пайплайне?
2. Почему скриншот 4K нужно ресайзить до 1024px?
3. Какой формат лучше для скриншота UI? Для фотографии?
4. Чем visual RAG отличается от обычного RAG?
5. Как проверить, что vision-модель не галлюцинирует тренд на графике?

---

## Ссылки

- [[01-economics-architecture]] — экономика модальностей
- [[../09-advanced-rag-agents/05-vision-agents]] — vision basics (урок 35b)
- [[03-audio-deep]] — следующий урок: audio deep dive
