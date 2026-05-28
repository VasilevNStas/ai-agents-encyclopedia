---
created: 2026-05-28
tags: [course/multi-modal-deep, multimodal, economics, architecture, routing, cost]
status: active
---

# Урок 19.1: Multi-modal Economics & Architecture

> [!quote] Ключевая идея
> Multi-modal — это не магия. Каждая лишняя модальность — это cost, latency и complexity. Архитектор multi-modal системы должен понимать экономику пикселей: сколько стоят изображения, аудио, видео — и когда их НЕ использовать.

---

## 1. Как LLM видит модальности: токенизация

Каждая модальность превращается в токены. Разные провайдеры делают это по-разному.

### 1.1 Image Tokenization

```
Изображение 1024x768:

GPT-4o:      170 токенов за тайл 512x512
            → (2×2) × 170 = 680 токенов
            + 32 базовых токена = ~712 токенов

Claude 3.5+:  ~1600 токенов за изображение (фиксированно)
              800 токенов за изображение (сжатый режим)

Gemini 2.0:  258 токенов за тайл 256x256
            → (4×3) × 258 = ~3096 токенов

Llama 4:     пропорционально размеру, ~1000 токенов за 1024x1024
```

```python
def estimate_image_tokens(width: int, height: int, model: str) -> int:
    """Рассчёт токенов для изображения по модели."""
    configs = {
        "gpt-4o":         {"tile": 512, "tokens_per_tile": 170, "base": 32},
        "gpt-4o-mini":    {"tile": 512, "tokens_per_tile": 85, "base": 16},
        "claude-sonnet-4": {"fixed": 1600},
        "claude-haiku-4":  {"fixed": 800},
        "gemini-2.0-flash": {"tile": 256, "tokens_per_tile": 258, "base": 0},
        "gemini-2.0-pro": {"tile": 256, "tokens_per_tile": 258, "base": 0},
    }

    cfg = configs.get(model)
    if not cfg:
        return 1000

    if "fixed" in cfg:
        return cfg["fixed"]

    tiles_x = (width + cfg["tile"] - 1) // cfg["tile"]
    tiles_y = (height + cfg["tile"] - 1) // cfg["tile"]
    return tiles_x * tiles_y * cfg["tokens_per_tile"] + cfg.get("base", 0)
```

**Практические стоимости:**

| Модель | 512×512 | 1024×768 | 2048×1536 |
|--------|---------|----------|-----------|
| GPT-4o | $0.0013 | $0.0026 | $0.0102 |
| Claude Sonnet 4 | $0.0048 | $0.0048 | $0.0048 |
| Gemini Flash | $0.0001 | $0.0005 | $0.0021 |
| Haiku 4 | $0.0006 | $0.0006 | $0.0006 |

> [!warning] Скрытые расходы
> Одно изображение 2K может стоить как 5000 токенов текста. Если агент анализирует 3-5 скриншотов за сессию — это может составлять 60-80% всего счёта.

### 1.2 Audio Tokenization

Аудио обрабатывается иначе: сначала STT (превращает речь в текст), потом LLM обрабатывает текст.

```
Аудио 1 минута (речь):

  GPT-4o (native audio):
    → 1 минута ≈ 1920 аудио-токенов
    → стоимость: ~$0.06/min (вход)

  Whisper → LLM (раздельно):
    → Whisper STT: $0.006/min
    → Текст (150 слов) → LLM: ~$0.0003
    → Синтез (TTS): $0.003/min
    → Итого: ~$0.009/min

  Deepgram STT → LLM → ElevenLabs TTS:
    → Deepgram: $0.004/min
    → LLM: ~$0.001
    → ElevenLabs: $0.001/min
    → Итого: ~$0.006/min
```

**Нативная аудио-поддержка (GPT-4o, Gemini) дороже, но latency ниже**, потому что нет промежуточной транскрипции.

### 1.3 Video Tokenization

Видео = последовательность кадров + аудиодорожка.

```
Видео 1 минута, 30fps, 1080p:

  Нет native video (все провайдеры):
    → Извлекаем 1 кадр/сек = 60 кадров
    → 60 × ~2000 токенов = 120000 токенов
    → Стоимость: ~$0.36 (GPT-4o) или ~$0.29 (Claude)

  Субсемплинг (1 кадр/5 сек):
    → 12 кадров
    → ~24000 токенов
    → Стоимость: ~$0.07

  + Транскрипция аудио:
    → Whisper: $0.006
    → Итого: ~$0.076 за минуту
```

---

## 2. Modality Routing: когда какую модальность использовать

Не каждый запрос требует multi-modal. Ключевое решение архитектора — **когда отказаться от лишней модальности**.

```python
class ModalityRouter:
    """Принимает решение: какие модальности нужны для запроса."""

    TEXT_ONLY_KEYWORDS = [
        "what is", "explain", "define", "summarize",
        "translate", "rewrite", "format",
    ]
    IMAGE_REQUIRED = [
        "screenshot", "image", "picture", "photo", "chart", "graph",
        "diagram", "ui", "visual", "look at", "what do you see",
    ]
    AUDIO_REQUIRED = [
        "listen", "audio", "recording", "voice", "speech", "what did they say",
    ]

    def route(self, user_input: str, has_attachments: bool) -> dict:
        """Выбирает оптимальные модальности."""

        plan = {
            "use_vision": False,
            "use_audio": False,
            "use_video": False,
            "cost_multiplier": 1.0,
            "reason": "",
        }

        input_lower = user_input.lower()

        # Если нет вложений — скорее всего text-only
        if not has_attachments:
            if any(kw in input_lower for kw in self.IMAGE_REQUIRED):
                plan["use_vision"] = True
                plan["cost_multiplier"] = 3.0
                plan["reason"] = "user referenced visual content"
            elif any(kw in input_lower for kw in self.AUDIO_REQUIRED):
                plan["use_audio"] = True
                plan["cost_multiplier"] = 1.5
                plan["reason"] = "user referenced audio"
            else:
                plan["reason"] = "text-only query"
        else:
            # Определяем по MIME-типам
            plan["use_vision"] = True  # есть attachment = есть картинка
            plan["cost_multiplier"] = 3.0
            plan["reason"] = "attachments present"

        return plan


class CostAwareRouter(ModalityRouter):
    """Router, который учитывает бюджет."""

    def __init__(self, max_cost_per_call: float = 0.05):
        self.max_cost = max_cost_per_call

    def route(self, user_input: str, has_attachments: bool) -> dict:
        plan = super().route(user_input, has_attachments)

        # Если дорого — предлагаем text-only fallback
        if plan["cost_multiplier"] > 2.0:
            plan["suggestion"] = (
                f"This query would cost ~${plan['cost_multiplier'] * 0.01:.3f}. "
                "Consider providing a text description instead?"
            )
            plan["fallback_possible"] = True

        return plan
```

### Decision Matrix

```python
def decide_modality(query: str, attachments: list, budget_cents: float = 5) -> str:
    """Принимает решение: text-only, vision, audio или multi-modal."""

    has_image = any(getattr(a, 'type', '').startswith('image/') for a in attachments)
    has_audio = any(getattr(a, 'type', '').startswith('audio/') for a in attachments)
    cost_ceiling = budget_cents / 100

    estimated_costs = []
    if has_image:
        estimated_costs.append(("vision", 0.01))  # средняя стоимость vision
    if has_audio:
        estimated_costs.append(("audio", 0.008))  # средняя стоимость аудио

    total_estimated = sum(c for _, c in estimated_costs) + 0.002  # text base

    if total_estimated > cost_ceiling:
        return "text_only"  # fallback — описание текстом

    if has_image and has_audio:
        if "chart" in query.lower() or "graph" in query.lower():
            return "vision"  # для графиков vision важнее audio
        return "full_multi_modal"

    if has_image:
        return "vision"
    if has_audio:
        return "audio"

    return "text_only"
```

---

## 3. Multi-modal Pipeline Architecture

```
User Request + Attachments
        │
        ▼
┌───────────────────────┐
│  Modality Detector    │  ← MIME types + NLP hints
│  (image? audio? text?)│
└───────┬───────────────┘
        │
        ▼
┌───────────────────────┐
│  Cost-Benefit Router  │  ← бюджет/латенси/качество
│  (is it worth it?)    │
└───────┬───────────────┘
        │
    ┌───┴───┐
    ▼       ▼
┌────────┐ ┌──────────┐
│ Vision │ │  Audio   │
│ Agent  │ │  Agent   │
│        │ │          │
│• resize│ │• VAD     │
│• cache │ │• STT     │
│• OCR   │ │• TTS     │
└───┬────┘ └─────┬────┘
    │            │
    └────┬───────┘
         ▼
┌───────────────────────┐
│  Multi-modal Fusion   │  ← объединение результатов
│  (LLM synthesis)      │
└───────┬───────────────┘
         │
         ▼
┌───────────────────────┐
│  Output Guardrail     │  ← проверка всех модальностей
└───────────────────────┘
```

### Fusion Strategies

```python
class ModalityFusion:
    """Стратегии объединения multi-modal результатов."""

    @staticmethod
    def late_fusion(results: dict[str, str]) -> str:
        """Поздняя фикция: каждый анализатор работает отдельно, потом синтез."""
        prompt = "Synthesize the following multi-modal analysis into a unified response:\n\n"
        for modality, result in results.items():
            prompt += f"[{modality.upper()}]\n{result}\n\n"
        return prompt

    @staticmethod
    def early_fusion(modalities: list, llm) -> str:
        """Ранняя фикция: все данные передаются LLM в одном вызове."""
        content = [{"type": "text", "text": "Analyze all provided media:"}]
        for mod in modalities:
            if mod["type"] == "image":
                content.append({"type": "image", "image": mod["data"]})
            elif mod["type"] == "audio":
                content.append({"type": "audio", "audio": mod["data"]})
        response = llm.generate(content)
        return response

    @staticmethod
    def hierarchical_fusion(results: dict[str, str], priority: list[str]) -> str:
        """Иерархическая: ответ строится от приоритетной модальности."""
        for modality in priority:
            if modality in results:
                return f"[Primary: {modality}]\n{results[modality]}"
        return "No results available"
```

| Стратегия | Когда | Плюсы | Минусы |
|-----------|-------|-------|--------|
| Early fusion | LLM поддерживает native multi-modal | Меньше latency, контекст вместе | Дорого, не все модели поддерживают |
| Late fusion | Раздельные модели под модальности | Гибкость, дешевле | Потеря cross-modal контекста |
| Hierarchical | Одна модальность важнее других | Простота, предсказуемость | Потеря второстепенных данных |

---

## 4. Graceful Fallback

Multi-modal агент должен работать, даже если одна из модальностей недоступна.

```python
class MultiModalPipeline:
    """Pipeline с graceful fallback для каждой модальности."""

    async def process(self, query: str, attachments: list) -> dict:
        results = {"text": query}
        errors = []

        # 1. Пробуем vision
        if self._has_images(attachments):
            try:
                results["vision"] = await self.vision_agent.analyze(attachments)
            except VisionModelError as e:
                errors.append(f"Vision unavailable: {e}")
                # Fallback: просим пользователя описать текстом
                results["vision"] = "[Vision unavailable. Please describe the image.]"

        # 2. Пробуем audio
        if self._has_audio(attachments):
            try:
                results["audio"] = await self.audio_agent.transcribe(attachments)
            except AudioModelError as e:
                errors.append(f"Audio unavailable: {e}")
                results["audio"] = "[Audio unavailable. Please provide text transcript.]"

        # 3. Синтез — даже если часть модальностей упала
        response = await self.synthesize(results)

        return {
            "response": response,
            "modalities_used": [k for k in results if k != "text"],
            "fallbacks": errors if errors else None,
        }
```

---

## 5. Cost Budget для multi-modal

```python
class MultiModalBudget:
    """Бюджетирование multi-modal запросов."""

    MODALITY_COSTS = {
        "text":     {"input_per_1k": 0.00015, "output_per_1k": 0.0006},
        "vision":   {"input_per_image": 0.002, "multiplier": 3.0},
        "audio_ai": {"input_per_min": 0.06, "output_per_min": 0.03},
        "audio_stt": {"input_per_min": 0.006},
        "audio_tts": {"output_per_min": 0.003},
        "video":    {"input_per_frame": 0.002, "frames_per_min": 12},
    }

    def estimate_request(self, modalities: list[str], params: dict) -> dict:
        """Оценивает стоимость запроса до его выполнения."""

        total = 0.0
        breakdown = {}

        for mod in modalities:
            if mod == "text":
                input_tokens = params.get("text_length", 500) // 4
                cost = (input_tokens / 1000) * self.MODALITY_COSTS["text"]["input_per_1k"]
                breakdown["text"] = round(cost, 6)

            elif mod == "vision":
                num_images = params.get("num_images", 1)
                cost = num_images * self.MODALITY_COSTS["vision"]["input_per_image"]
                breakdown["vision"] = round(cost, 6)

            elif mod == "audio":
                duration_min = params.get("audio_duration_min", 1)
                cost_stt = duration_min * self.MODALITY_COSTS["audio_stt"]["input_per_min"]
                cost_tts = duration_min * self.MODALITY_COSTS["audio_tts"]["output_per_min"]
                cost_llm = 0.002
                breakdown["audio"] = round(cost_stt + cost_tts + cost_llm, 6)

            total += cost

        return {
            "estimated_cost": round(total, 6),
            "breakdown": breakdown,
            "recommendation": "proceed" if total < params.get("budget_max", 0.10) else "warn",
        }
```

---

## Резюме

```
Multi-modal Architecture:

1. Tokenization:  картинка ≠ картинке
   — GPT-4o: 170 токенов/тайл 512×512
   — Claude: ~1600 фиксированно за изображение
   — Gemini: 258 токенов/тайл 256×256

2. Cost: vision в 3-5x дороже текста
   — Изображение 2K может стоить как 5000 токенов текста
   — Аудио 1 мин: $0.006-0.06 в зависимости от подхода
   — Видео 1 мин: $0.07-0.36 в зависимости от субсемплинга

3. Routing: не каждому запросу нужен multi-modal
   — Text-only если нет вложений и нет визуальных ключевых слов
   — Vision для скриншотов, графиков, UI
   — Audio для голосовых команд, транскрипций
   — Fallback text-only когда бюджет превышен

4. Fusion: early vs late vs hierarchical
   — Early: всё в один LLM-вызов (дорого, но контекстно)
   — Late: раздельные анализаторы + синтез (дёшево, гибко)
   — Hierarchical: одна главная модальность

5. Graceful degradation: каждая модальность может упасть
   — Всегда иметь text-only fallback
   - Уметь объяснить пользователю, почему недоступна модальность
```

---

## Практическое задание

1. Посчитай стоимость: пользователь прислал 2 скриншота 1920×1080 и 30-секундную аудиозапись. Сколько это будет стоить на GPT-4o? На Claude Sonnet 4?

2. Реализуй ModalityRouter, который определяет нужные модальности по тексту запроса и MIME-типам вложений.

3. Добавь CostAwareRouter, который предупреждает, если стоимость запроса превышает $0.05.

---

## Проверь себя

1. Сколько токенов потребуется для изображения 1024×768 на GPT-4o? На Claude?
2. Почему vision-запрос дороже текстового в 3-5 раз?
3. Какая стратегия fusion минимально дорогая?
4. Как сделать graceful fallback для аудио-модальности?
5. В каком сценарии multi-modal не нужен, хотя есть вложение?

---

## Ссылки

- [[../09-advanced-rag-agents/03-multi-modal-agents]] — основы multi-modal (урок 35)
- [[../09-advanced-rag-agents/05-vision-agents]] — vision (урок 35b)
- [[../09-advanced-rag-agents/06-audio-agents]] — audio (урок 35c)
- [[02-vision-deep]] — следующий урок: vision deep dive
- [OpenAI Vision Pricing](https://openai.com/pricing)
- [Anthropic Vision Pricing](https://docs.anthropic.com/en/docs/build-with-claude/vision)
