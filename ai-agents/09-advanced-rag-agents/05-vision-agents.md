---
created: 2026-05-28
tags: [course/advanced-rag, multimodal, vision, architect]
status: active
---

# Урок 35b: Vision Agents — работа с изображениями

> [!quote] Ключевая идея
> Современные LLM (GPT-4o, Claude 3.5+, Gemini 2.0+) принимают изображения как часть контекста. Но vision для агента — это не «посмотреть на картинку». Это архитектура: как извлекать данные из изображений, как платить за пиксели, как кешировать визуальный контент.

---

## 1. Как LLM видит изображения

Изображение токенизируется: конвертируется в последовательность визуальных токенов (patches), которые модель обрабатывает как текст:

```python
# Упрощённо: сколько токенов в изображении
def image_tokens(width: int, height: int, model: str) -> int:
    if model.startswith("gpt-4o"):
        # GPT-4o: 170 токенов за 512x512 тайл
        tiles = math.ceil(width / 512) * math.ceil(height / 512)
        return tiles * 170
    elif model.startswith("claude-3"):
        # Claude 3: фиксированно ~1500 токенов за изображение
        return 1500
    elif model.startswith("gemini"):
        # Gemini: 258 токенов за 256x256 тайл
        tiles = math.ceil(width / 256) * math.ceil(height / 256)
        return tiles * 258
    return 1000  # fallback
```

**Стоимость:** изображение 1024x768 может стоить как 1000-5000 токенов текста. Передавать изображения без необходимости = жечь бюджет.

---

## 2. Паттерны vision-агентов

### Паттерн A: Screenshot → анализ

Агент делает скриншот интерфейса и анализирует его:

```python
@tool
def analyze_screenshot(url: str, question: str) -> str:
    """Take a screenshot of a webpage and analyze it."""
    screenshot = take_screenshot(url)
    response = llm.invoke([
        {"role": "user", "content": [
            {"type": "image", "image_url": {"url": f"data:image/png;base64,{screenshot}"}},
            {"type": "text", "text": question},
        ]}
    ])
    return response.content
```

**Проблемы:**
- Большие изображения = много токенов
- Нет фокуса: модель обрабатывает весь скриншот
- Конфиденциальность: скриншот может содержать чувствительные данные

**Решение:** предварительная обработка изображения:

```python
class ImagePreprocessor:
    """Оптимизирует изображения перед отправкой в LLM."""

    def optimize(self, image: bytes, max_size: tuple = (1024, 768)) -> bytes:
        """Сжимает и ресайзит изображение."""
        img = Image.open(BytesIO(image))
        img.thumbnail(max_size, Image.LANCZOS)
        # Сохраняем с оптимизированным качеством
        buf = BytesIO()
        img.save(buf, format="PNG", optimize=True, quality=85)
        return buf.getvalue()

    def crop_to_region(self, image: bytes, region: tuple) -> bytes:
        """Обрезает изображение до указанной области (x, y, w, h)."""
        img = Image.open(BytesIO(image))
        cropped = img.crop(region)
        buf = BytesIO()
        cropped.save(buf, format="PNG")
        return buf.getvalue()
```

### Паттерн B: Document extraction

Агент извлекает данные из отсканированных документов, графиков, диаграмм:

```python
@tool
def extract_table_from_chart(chart_image: bytes) -> str:
    """Extract data from a chart image and return as structured data."""
    # 1. Оптимизация
    img = ImagePreprocessor().optimize(chart_image)

    # 2. Извлечение через vision LLM
    response = llm.invoke([
        {"role": "system", "content": "Extract all data from this chart."
                                      "Return as JSON array of objects."},
        {"role": "user", "content": [
            {"type": "image", "image_url": f"data:image/png;base64,{base64.b64encode(img).decode()}"},
        ]},
    ])

    # 3. Валидация результата
    try:
        data = json.loads(response.content)
        return json.dumps(data, indent=2, ensure_ascii=False)
    except json.JSONDecodeError:
        return f"Failed to parse: {response.content}"
```

---

## 3. Image caching для экономии

```python
class VisionCache:
    """Кеширует результаты vision-запросов."""

    def __init__(self, redis_client):
        self.redis = redis_client
        self.ttl = 3600  # 1 час

    def get_or_analyze(self, image_hash: str, analyze_fn: callable) -> str:
        """Возвращает кешированный результат или анализирует."""
        cached = self.redis.get(f"vision:{image_hash}")
        if cached:
            return cached.decode()

        result = analyze_fn()
        self.redis.setex(f"vision:{image_hash}", self.ttl, result)
        return result

    def compute_hash(self, image: bytes) -> str:
        """Хеш изображения (перцептивный, а не точный)."""
        return hashlib.sha256(image).hexdigest()[:16]
```

---

## 4. Практика

Собери агента, который:
1. Принимает URL веб-страницы
2. Делает скриншот
3. Оптимизирует изображение (max 1024x768)
4. Извлекает текст из скриншота (OCR через vision LLM)
5. Отвечает на вопрос пользователя о содержимом

```python
# TODO: собери vision-агента
```

---

## Ссылки

- [[03-multi-modal-agents]] — обзор мультимодальности (урок 35)
- [[06-audio-agents]] — следующий урок: аудио-агенты
