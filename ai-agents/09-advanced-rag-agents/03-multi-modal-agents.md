---
created: 2026-05-28
tags: [course/advanced-rag, multi-modal, vision, audio, agents]
status: active
---

# Урок 35: Multi-Modal Agents

> [!quote] Ключевая идея
> 2026 — год, когда "только текст" — это ограничение. Современные агенты видят скриншоты, слушают аудио, смотрят видео. Multi-modal становится стандартом, а не опцией.

---

## Что такое Multi-Modal Agent

**Multi-Modal Agent** — агент, который работает с несколькими типами данных одновременно:

| Модальность | Вход (понимание) | Выход (генерация) |
|-------------|-----------------|-------------------|
| Текст | Чтение, анализ | Письмо, ответ |
| Изображение | Распознавание, OCR, описание | Генерация (DALL-E, Stable Diffusion) |
| Аудио | Распознавание речи (STT) | Синтез речи (TTS) |
| Видео | Анализ кадров, понимание сцен | Генерация (Sora, Veo) |
| Код | Чтение, выполнение | Написание, дебаг |

```
                  ┌──────────┐
    Text ────────►│          │
    Image ───────►│   Agent  │───► Text
    Audio ───────►│  (LLM)   │───► Image
    Video ───────►│          │───► Audio
                  └──────────┘
                        │
                    ┌───┴───┐
                    │ Tools │
                    └───────┘
```

### Архитектура multi-modal агента

```python
from enum import Enum
from typing import Any
from dataclasses import dataclass
from PIL import Image
import io
import base64


class Modality(Enum):
    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    CODE = "code"


@dataclass
class MultiModalMessage:
    """Сообщение, содержащее данные разных модальностей."""

    role: str  # user | assistant | system
    content: str  # текстовое содержимое
    images: list[bytes] | None = None
    audio: bytes | None = None
    metadata: dict | None = None


class MultiModalRouter:
    """Роутер: определяет, какие инструменты нужны для запроса."""

    def __init__(self, llm: Any):
        self.llm = llm

    def detect_modalities(self, query: str, attachments: list) -> set[Modality]:
        """Определить, какие модальности задействованы."""

        modalities = {Modality.TEXT}

        for att in attachments:
            if att.type.startswith("image/"):
                modalities.add(Modality.IMAGE)
            elif att.type.startswith("audio/"):
                modalities.add(Modality.AUDIO)
            elif att.type.startswith("video/"):
                modalities.add(Modality.VIDEO)

        # Текстовые подсказки о модальностях
        hints = {
            "изображени": Modality.IMAGE,
            "скриншот": Modality.IMAGE,
            "картинк": Modality.IMAGE,
            "график": Modality.IMAGE,
            "диаграмм": Modality.IMAGE,
            "аудио": Modality.AUDIO,
            "звук": Modality.AUDIO,
            "голос": Modality.AUDIO,
            "запись": Modality.AUDIO,
            "видео": Modality.VIDEO,
            "посмотр": Modality.VIDEO,
        }

        for word, modality in hints.items():
            if word in query.lower():
                modalities.add(modality)

        return modalities

    def route(self, query: str, attachments: list) -> dict:
        """Определить план обработки запроса."""

        modalities = self.detect_modalities(query, attachments)

        plan = {
            "steps": [],
            "primary_modality": Modality.TEXT,
        }

        if Modality.IMAGE in modalities:
            plan["steps"].append({
                "tool": "vision",
                "action": "analyze_image",
            })

        if Modality.AUDIO in modalities:
            plan["steps"].append({
                "tool": "audio",
                "action": "transcribe",
            })

        if Modality.VIDEO in modalities:
            plan["steps"].extend([
                {"tool": "video", "action": "extract_frames"},
                {"tool": "vision", "action": "analyze_frames"},
            ])

        plan["steps"].append({
            "tool": "llm",
            "action": "synthesize",
        })

        if not attachments and not any(
            m in modalities for m in (Modality.IMAGE, Modality.VIDEO)
        ):
            plan["primary_modality"] = Modality.TEXT

        return plan
```

---

## Vision Agents

**Vision Agent** — агент, который видит и анализирует изображения. Самый востребованный тип multi-modal агентов в 2026.

### Возможности

- Распознавание текста на изображениях (OCR)
- Анализ графиков и диаграмм
- Описание содержимого
- Понимание UI/UX скриншотов
- Валидация визуальных элементов

```python
class VisionAgent:
    """Агент для анализа изображений."""

    def __init__(self, llm: Any, vision_model: Any):
        self.llm = llm
        self.vision = vision_model

    def analyze_image(self, image: Image.Image, query: str) -> str:
        """Проанализировать изображение по запросу."""

        # Современные LLM (GPT-4o, Claude 3.5, Gemini 2.0)
        # принимают изображения напрямую
        response = self.llm.generate(
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": query},
                        {"type": "image", "image": image},
                    ],
                }
            ]
        )
        return response

    def extract_text(self, image: Image.Image) -> str:
        """Извлечь текст с изображения (OCR через LLM)."""

        response = self.llm.generate(
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "Извлеки весь текст с изображения. "
                                "Сохрани форматирование: "
                                "заголовки, списки, таблицы."
                            ),
                        },
                        {"type": "image", "image": image},
                    ],
                }
            ],
            temperature=0,
        )
        return response

    def describe_chart(self, image: Image.Image) -> dict:
        """Описать график/диаграмму: тренды, значения, выводы."""

        response = self.llm.generate(
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "Опиши график на изображении. "
                                "Формат ответа — JSON:\n"
                                "{\n"
                                '  "chart_type": "bar|line|pie|...",\n'
                                '  "title": "название",\n'
                                '  "axes": {"x": "...", "y": "..."},\n'
                                '  "trends": ["тренд 1", "..."],\n'
                                '  "values": {"max": val, "min": val},\n'
                                '  "insights": ["вывод 1", "..."]\n'
                                "}"
                            ),
                        },
                        {"type": "image", "image": image},
                    ],
                }
            ],
            response_format="json",
        )
        return response
```

### Скриншот-тестинг

Vision Agent находит баги, которые не видит текстовый анализатор:

```python
class UIVisionAgent(VisionAgent):
    """Агент для анализа UI скриншотов."""

    def validate_screenshot(
        self, screenshot: Image.Image, spec: dict
    ) -> list[str]:
        """Проверить скриншот на соответствие спецификации."""

        prompt = f"""
        Спецификация интерфейса:
        {spec}

        Проверь скриншот на следующие аспекты:
        1. Все ли элементы из спецификации присутствуют?
        2. Правильное ли расположение?
        3. Нет ли визуальных дефектов (наложение, обрезание)?
        4. Корректные ли цвета и шрифты?
        5. Соответствует ли текст на скриншоте ожидаемому?

        Перечисли ТОЛЬКО найденные проблемы.
        Если проблем нет — ответь "ALL_OK".
        """

        response = self.llm.generate(
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image", "image": screenshot},
                    ],
                }
            ],
            temperature=0,
        )

        if response == "ALL_OK":
            return []
        return [line.strip() for line in response.split("\n") if line.strip()]

    def compare_screenshots(
        self, before: Image.Image, after: Image.Image, query: str
    ) -> str:
        """Сравнить два скриншота (до/после изменений)."""

        return self.llm.generate(
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                f"Сравни два изображения. {query}"
                            ),
                        },
                        {"type": "image", "image": before},
                        {"type": "image", "image": after},
                    ],
                }
            ]
        )
```

> [!important] Multi-modal vision ≠ просто OCR
> Современные vision-модели понимают контекст изображения: могут объяснить мем, прочитать график, найти баг в UI. OCR — лишь малая часть их возможностей.

---

## Audio Agents

**Audio Agent** — агент, который слышит и говорит. Два ключевых компонента:

- **Speech-to-Text (STT)** — преобразование речи в текст (Whisper, Deepgram)
- **Text-to-Speech (TTS)** — синтез речи из текста (ElevenLabs, OpenAI TTS)

```python
class AudioAgent:
    """Агент для работы с аудио."""

    def __init__(
        self,
        llm: Any,
        stt_model: Any = None,  # Whisper, Deepgram
        tts_model: Any = None,  # ElevenLabs, OpenAI TTS
    ):
        self.llm = llm
        self.stt = stt_model
        self.tts = tts_model

    def transcribe(self, audio: bytes, language: str = "ru") -> str:
        """Преобразовать аудио в текст."""

        if self.stt:
            # Выделенный STT (Whisper, Deepgram)
            result = self.stt.transcribe(audio, language=language)
            return result["text"]

        # Некоторые LLM (GPT-4o) поддерживают аудио напрямую
        response = self.llm.generate(
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Распознай речь в аудио.",
                        },
                        {
                            "type": "audio",
                            "audio": audio,
                        },
                    ],
                }
            ]
        )
        return response

    def speak(self, text: str, voice: str = "alloy") -> bytes:
        """Синтезировать речь из текста."""

        if self.tts:
            return self.tts.synthesize(text, voice=voice)

        raise NotImplementedError("TTS model not configured")

    def transcribe_and_act(self, audio: bytes) -> str:
        """Транскрибировать и выполнить команду."""

        # Шаг 1: распознать речь
        text = self.transcribe(audio)
        print(f"[Распознано]: {text}")

        # Шаг 2: выполнить как команду
        return self.llm.generate(
            f"Выполни команду: {text}"
        )

    def converse(self, audio_input: bytes) -> bytes:
        """Полный цикл: слушаем → думаем → отвечаем."""

        # 1. Распознать
        text = self.transcribe(audio_input)

        # 2. Ответить текстом
        response = self.llm.generate(text)

        # 3. Озвучить ответ
        audio_output = self.speak(response)

        return audio_output


class VoiceAssistant(AudioAgent):
    """Голосовой ассистент с контекстом диалога."""

    def __init__(self, llm: Any, stt: Any, tts: Any):
        super().__init__(llm, stt, tts)
        self.conversation_history: list[dict] = []
        self.max_history = 20

    async def process_voice_command(
        self, audio: bytes, wake_word_detected: bool = False
    ) -> bytes:
        """Обработать голосовую команду."""

        if not wake_word_detected:
            # Режим прослушивания wake word
            # (обычно обрабатывается отдельным детектором)
            return b""

        # Транскрипция
        text = self.transcribe(audio)
        self.conversation_history.append({
            "role": "user",
            "content": text,
        })

        # Обрезать историю
        if len(self.conversation_history) > self.max_history:
            self.conversation_history = (
                self.conversation_history[-self.max_history:]
            )

        # Генерация ответа
        response = self.llm.generate(
            messages=self.conversation_history
        )
        self.conversation_history.append({
            "role": "assistant",
            "content": response,
        })

        # Озвучивание
        return self.speak(response)

    def detect_wake_word(self, audio: bytes, wake_word: str = "ассистент") -> bool:
        """Детекция wake word (упрощённо)."""

        text = self.transcribe(audio)
        return wake_word.lower() in text.lower()
```

### Аудио в реальном времени

```python
import asyncio
import pyaudio


class RealtimeAudioAgent:
    """Агент с обработкой аудио в реальном времени."""

    def __init__(
        self,
        audio_agent: AudioAgent,
        sample_rate: int = 16000,
        chunk_duration: float = 0.5,  # полсекунды
    ):
        self.agent = audio_agent
        self.sample_rate = sample_rate
        self.chunk_size = int(sample_rate * chunk_duration)
        self.is_listening = False

    async def start_listening(self):
        """Запуск прослушивания микрофона."""

        audio = pyaudio.PyAudio()
        stream = audio.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=self.sample_rate,
            input=True,
            frames_per_buffer=self.chunk_size,
        )

        self.is_listening = True
        buffer = b""

        print("[Слушаю...]")

        try:
            while self.is_listening:
                data = stream.read(self.chunk_size)
                buffer += data

                # Каждые 3 секунды — проверка на команду
                if len(buffer) >= self.sample_rate * 3:
                    print("[Обработка...]")

                    response = await asyncio.to_thread(
                        self.agent.transcribe_and_act,
                        buffer,
                    )
                    print(f"[Ответ]: {response}")

                    buffer = b""  # сброс буфера

                    # Опционально: синтез ответа
                    audio_response = await asyncio.to_thread(
                        self.agent.speak, response
                    )

        except KeyboardInterrupt:
            pass
        finally:
            stream.close()
            audio.terminate()

    def stop_listening(self):
        self.is_listening = False
```

---

## Объединение: Multi-Modal Agent целиком

```python
class MultiModalAgent:
    """Полноценный multi-modal агент."""

    def __init__(
        self,
        llm: Any,
        vision_model: Any = None,
        stt_model: Any = None,
        tts_model: Any = None,
        image_gen_model: Any = None,
    ):
        self.router = MultiModalRouter(llm)
        self.vision = VisionAgent(llm, vision_model)
        self.audio = AudioAgent(llm, stt_model, tts_model)
        self.image_gen = image_gen_model
        self.llm = llm

    def process(
        self,
        query: str,
        attachments: list | None = None,
    ) -> dict:
        """Обработка запроса с любыми модальностями."""

        attachments = attachments or []
        plan = self.router.route(query, attachments)
        context = {"query": query, "results": {}}

        for step in plan["steps"]:
            action = step["action"]

            if action == "analyze_image":
                image = self._load_image(attachments)
                context["results"]["image_description"] = (
                    self.vision.analyze_image(
                        image,
                        f"Что изображено? Ответь в контексте запроса: {query}",
                    )
                )

            elif action == "transcribe":
                audio = self._load_audio(attachments)
                context["results"]["transcription"] = (
                    self.audio.transcribe(audio)
                )

            elif action == "analyze_frames":
                frames = self._extract_frames(attachments)
                context["results"]["video_analysis"] = (
                    self._analyze_video_frames(frames, query)
                )

            elif action == "synthesize":
                context["results"]["final_answer"] = self._synthesize(
                    query, context["results"]
                )

            elif action == "generate_image":
                context["results"]["generated_image"] = (
                    self._generate_image(query)
                )

        return context

    def _load_image(self, attachments: list) -> Image.Image:
        for att in attachments:
            if hasattr(att, "type") and "image" in att.type:
                return Image.open(io.BytesIO(att.content))
        raise ValueError("No image attachment found")

    def _load_audio(self, attachments: list) -> bytes:
        for att in attachments:
            if hasattr(att, "type") and "audio" in att.type:
                return att.content
        raise ValueError("No audio attachment found")

    def _extract_frames(self, attachments: list) -> list[Image.Image]:
        """Извлечение кадров из видео (упрощённо)."""
        return []

    def _analyze_video_frames(
        self, frames: list[Image.Image], query: str
    ) -> str:
        descriptions = []
        for i, frame in enumerate(frames):
            desc = self.vision.analyze_image(
                frame, f"Опиши кадр {i + 1}/{len(frames)}"
            )
            descriptions.append(desc)
        return "\n".join(descriptions)

    def _synthesize(self, query: str, results: dict) -> str:
        prompt = f"""
        Запрос пользователя: {query}

        Результаты анализа:
        {results}

        Сформулируй полный ответ на запрос,
        используя все доступные модальности.
        """

        return self.llm.generate(prompt)

    def _generate_image(self, prompt: str) -> bytes:
        if self.image_gen:
            return self.image_gen.generate(prompt)
        return b""
```

---

## Тренды 2026: Multi-modal как стандарт

### 1. Native multi-modal LLM

Больше нет отдельных моделей под каждую модальность. GPT-4o, Gemini 2.0, Claude 4 принимают **текст + изображения + аудио** в одном вызове API:

```python
# 2026: один API — все модальности
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Опиши график"},
                {"type": "image_url", "image_url": chart_url},
                {"type": "audio_url", "audio_url": narration_url},
            ],
        }
    ],
)
```

### 2. Agent-to-agent multi-modal communication

Агенты обмениваются не только текстом, но и изображениями, диаграммами, аудио:

```
Агент-аналитик: (отправляет скриншот дашборда)
Агент-разработчик: (анализирует скриншот → находит проблему)
Агент-документатор: (создаёт инструкцию с картинками)
```

### 3. Multi-modal RAG

Поиск работает не только по тексту, но и по изображениям:

| Тип поиска | Индекс | Пример |
|------------|--------|--------|
| Text→Text | Text embeddings | "Найди документ про X" |
| Text→Image | CLIP embeddings | "Найди изображение кота" |
| Image→Text | CLIP + LLM | "Опиши этот скриншот" |
| Image→Image | Visual embeddings | "Найди похожие изображения" |
| Audio→Text | Whisper + search | "Найди упоминания по аудио" |

```python
class MultiModalRAG:
    """RAG с поиском по всем модальностям."""

    def __init__(self, text_encoder: Any, image_encoder: Any, audio_encoder: Any):
        self.text_enc = text_encoder  # text-embedding-3
        self.image_enc = image_encoder  # CLIP
        self.audio_enc = audio_encoder  # Whisper embedding

    def search(self, query: str | Image.Image | bytes, top_k: int = 5) -> list:
        """Поиск по любой модальности."""

        if isinstance(query, str):
            embedding = self.text_enc.encode(query)
        elif isinstance(query, Image.Image):
            embedding = self.image_enc.encode(query)
        elif isinstance(query, bytes):
            embedding = self.audio_enc.encode(query)
        else:
            raise ValueError(f"Unsupported query type: {type(query)}")

        return self.vector_db.search(embedding, top_k=top_k)
```

### 4. Агенты для видео

```python
class VideoAnalysisAgent:
    """Агент для анализа видео (тренд 2026)."""

    def __init__(self, llm: Any, vision: VisionAgent):
        self.llm = llm
        self.vision = vision

    def analyze_video(self, video_path: str, query: str) -> dict:
        """Анализ видео: ключевые сцены, транскрипт, сюжет."""

        # 1. Извлечение аудиодорожки
        audio = self._extract_audio(video_path)

        # 2. Транскрипция
        transcript = self.audio.transcribe(audio)

        # 3. Извлечение ключевых кадров (scene detection)
        key_frames = self._extract_key_frames(video_path, interval=2.0)

        # 4. Анализ каждого кадра
        frame_analyses = []
        for frame in key_frames:
            analysis = self.vision.analyze_image(frame, query)
            frame_analyses.append(analysis)

        # 5. Синтез
        prompt = f"""
        Видео: {video_path}
        Запрос: {query}

        Транскрипт: {transcript}

        Анализ кадров:
        {chr(10).join(frame_analyses)}

        Дай подробный ответ на запрос.
        """

        return {
            "transcript": transcript,
            "frame_count": len(key_frames),
            "analysis": self.llm.generate(prompt),
        }

    def _extract_audio(self, video_path: str) -> bytes:
        return b""

    def _extract_key_frames(
        self, video_path: str, interval: float = 1.0
    ) -> list[Image.Image]:
        """FFmpeg: один кадр каждые interval секунд."""
        return []
```

---

## Anti-patterns Multi-modal агентов

### 1. Передача сырых данных без обработки

```python
# ❌ Картинка 4K → base64 → LLM (дорого, медленно)
image = load_4k_image()
response = llm.generate(f"Что на картинке? {image_base64(image)}")

# ✅ Ресайз до разумного размера
image = resize_image(image, max_size=1024)
response = llm.generate(f"Что на картинке? {image_base64(image)}")
```

### 2. Игнорирование текстовой альтернативы

```python
# ❌ Принудительный vision, даже когда OCR + text дешевле
response = vision_agent.analyze_image(image, "прочитай текст")

# ✅ Роутинг: если только текст → OCR → text LLM
if only_text_on_image(image):
    text = ocr(image)
    response = llm.generate(text)
else:
    response = vision_agent.analyze_image(image, query)
```

> [!warning] Cost multi-modal
> Vision-вызовы в 5-20x дороже текстовых. Аудио — ещё дороже. Всегда оценивай: **нужна ли эта модальность** для ответа?

### 3. Отсутствие graceful fallback

```python
# ❌ Упал vision model — агент умер
result = vision_agent.analyze_image(...)

# ✅ Fallback на текстовое описание (если есть alt-text)
try:
    result = vision_agent.analyze_image(...)
except APIError:
    result = f"Image not available. Alt text: {alt_text}"
```

### 4. Слепая вера в multi-modal

```python
# ❌ Vision модель "видит" то, чего нет (галлюцинации изображений)
vision_agent.analyze_image(chart, "какой тренд?")
# → "восходящий тренд" (а на самом деле нисходящий)

# ✅ Всегда перепроверять факты
text_analysis = extract_actual_values(chart)
vision_analysis = vision_agent.analyze_image(chart, query)
answer = reconcile(text_analysis, vision_analysis)
```

---

## Практическое задание

1. Реализуй `VisionAgent`, который:
   - Принимает скриншот интерфейса
   - Определяет, какие элементы UI есть на странице
   - Возвращает JSON со списком элементов и их состоянием

2. Для голосового интерфейса:
   - Используй библиотеку `speech_recognition` или API Whisper
   - Напиши цикл: слушаем → распознаём → выполняем → озвучиваем

3. Объедини всё в `MultiModalAgent`, который:
   - Определяет модальность запроса (текст/изображение/аудио)
   - Выбирает нужный инструмент
   - Возвращает ответ в той же модальности (если возможно)

---

## Проверь себя

1. Какие 5 основных модальностей поддерживает multi-modal агент?
2. Чем отличается Vision Agent от простого OCR?
3. Какие два ключевых компонента нужны для Audio Agent?
4. Почему в 2026 году multi-modal становится стандартом, а не опцией?
5. Какой главный anti-pattern при работе с multi-modal агентами (с точки зрения cost)?

---

## Резюме

```
Multi-modal Agent = Agent + Vision + Audio + Video + Code

Vision:  скриншоты, графики, UI, OCR
Audio:   STT (слушать) + TTS (говорить)
Video:   кадры + транскрипт + сюжет

Роутинг: запрос → определение модальности → выбор инструмента → синтез

Тренд 2026: native multi-modal LLM (GPT-4o, Gemini 2.0, Claude 4)
Все модальности в одном API, один агент.

Золотое правило: multi-modal — это сила, но за каждую модальность
              ты платишь. Используй только нужные.
```

---

## Ссылки

- [[09-advanced-rag-agents/01-agentic-rag]] — Agentic RAG
- [[09-advanced-rag-agents/02-long-running-agents]] — состояние и checkpointing
- [[03-memory-and-rag/02-rag-advanced]] — RAG 2.0 пайплайн
- [[06-prompt-engineering/01-system-prompts]] — системные промпты для агентов
- [[01-fundamentals/03-react-pattern]] — ReAct: цикл агента
- [[13-ecosystem-operations/01-agent-frameworks]] — фреймворки для реализации
