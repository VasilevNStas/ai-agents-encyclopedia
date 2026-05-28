---
created: 2026-05-28
tags: [course/multi-modal-deep, video, agents, streaming, video-understanding]
status: active
---

# Урок 19.4: Video Agents Deep Dive

> [!quote] Ключевая идея
> Видео — самая дорогая модальность. 1 минута видео = 1800+ кадров = $0.50–5.00 vision cost. Задача видео-агента: выбрать правильные кадры, не переплатить, не потерять контекст.

---

## 1. Frame Extraction Strategies

```python
import cv2
import numpy as np
from enum import Enum


class FrameExtractionStrategy(Enum):
    UNIFORM = "uniform"           # Равномерно каждый N кадр
    KEYFRAME = "keyframe"         # I-кадры (сжатие видео)
    SCENE_BASED = "scene"         # По смене сцены
    MOTION_BASED = "motion"       # По движению в кадре
    HYBRID = "hybrid"             # Комбинация стратегий


class FrameExtractor:
    """Извлечение ключевых кадров из видео."""

    def __init__(self, strategy: FrameExtractionStrategy = FrameExtractionStrategy.KEYFRAME):
        self.strategy = strategy

    def extract(self, video_path: str, max_frames: int = 20) -> list[np.ndarray]:
        """Извлекает ключевые кадры из видео."""

        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / fps

        if self.strategy == FrameExtractionStrategy.UNIFORM:
            frames = self._uniform_extract(cap, total_frames, max_frames)
        elif self.strategy == FrameExtractionStrategy.KEYFRAME:
            frames = self._keyframe_extract(cap, max_frames)
        elif self.strategy == FrameExtractionStrategy.SCENE_BASED:
            frames = self._scene_extract(cap, max_frames)
        elif self.strategy == FrameExtractionStrategy.HYBRID:
            # Сначала keyframe, потом scene-based для оставшихся
            kf = self._keyframe_extract(cap, max_frames // 2)
            scene = self._scene_extract(cap, max_frames // 2)
            frames = self._deduplicate(kf + scene)[:max_frames]
        else:
            frames = self._uniform_extract(cap, total_frames, max_frames)

        cap.release()
        return frames

    def _uniform_extract(self, cap, total_frames: int, max_frames: int) -> list[np.ndarray]:
        """Равномерное извлечение кадров."""
        step = max(1, total_frames // max_frames)
        frames = []
        for i in range(0, total_frames, step):
            cap.set(cv2.CAP_PROP_POS_FRAMES, i)
            ret, frame = cap.read()
            if ret:
                frames.append(frame)
        return frames

    def _keyframe_extract(self, cap, max_frames: int) -> list[np.ndarray]:
        """Извлечение только I-кадров (intra-frames)."""
        from av import open as av_open
        container = av_open(cap)
        frames = []
        for packet in container.demux(video=0):
            if packet.is_keyframe:
                for frame in packet.decode():
                    img = frame.to_ndarray(format="bgr24")
                    frames.append(img)
                    if len(frames) >= max_frames:
                        return frames
        return frames

    def _scene_extract(self, cap, max_frames: int, threshold: float = 30.0) -> list[np.ndarray]:
        """Извлечение кадров при смене сцены (по histogram diff)."""
        frames = []
        prev_hist = None

        while len(frames) < max_frames:
            ret, frame = cap.read()
            if not ret:
                break

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            hist = cv2.calcHist([gray], [0], None, [256], [0, 256])
            hist = cv2.normalize(hist, hist).flatten()

            if prev_hist is not None:
                diff = cv2.compareHist(prev_hist, hist, cv2.HISTCMP_CHISQR)
                if diff > threshold:
                    frames.append(frame)

            prev_hist = hist

        return frames

    def _deduplicate(self, frames: list[np.ndarray], threshold: float = 0.95) -> list[np.ndarray]:
        """Удаляет визуально похожие кадры (perceptual dedup)."""
        unique = [frames[0]]
        for frame in frames[1:]:
            similarity = self._frame_similarity(unique[-1], frame)
            if similarity < threshold:
                unique.append(frame)
        return unique

    def _frame_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """Perceptual hash similarity."""
        from skimage.metrics import structural_similarity as ssim
        gray_a = cv2.cvtColor(a, cv2.COLOR_BGR2GRAY)
        gray_b = cv2.cvtColor(b, cv2.COLOR_BGR2GRAY)
        h, w = gray_a.shape
        gray_b = cv2.resize(gray_b, (w, h))
        return ssim(gray_a, gray_b)
```

### Сравнение стратегий

| Стратегия | Кадров/мин | Информативность | Cost/мин | Use-case |
|-----------|-----------|-----------------|----------|----------|
| Uniform (1fps) | 60 | Низкая (дубли) | $0.30 | Бекап, любой сценарий |
| Keyframe | 5-15 | Высокая | $0.05-0.15 | Видео со сжатием |
| Scene-based | 3-10 | Очень высокая | $0.03-0.10 | Фильмы, лекции, ролики |
| Motion-based | 5-20 | Высокая | $0.05-0.20 | Спорт, экшн, вебка |
| Hybrid | 10-20 | Максимальная | $0.10-0.20 | Production |

---

## 2. Video Understanding Pipeline

```python
class VideoUnderstandingPipeline:
    """Полный пайплайн понимания видео."""

    def __init__(self, frame_extractor: FrameExtractor, vision_model: Any):
        self.extractor = frame_extractor
        self.vision = vision_model

    async def analyze_video(self, video_path: str, queries: list[str]) -> dict:
        """Анализирует видео по заданным вопросам."""

        # 1. Extract frames
        frames = self.extractor.extract(video_path, max_frames=20)
        duration = self._get_duration(video_path)

        # 2. Analyze each frame with timestamps
        frame_analyses = []
        for i, frame in enumerate(frames):
            timestamp = self._get_timestamp(video_path, i)
            analysis = await self._analyze_frame(frame, timestamp, queries)
            frame_analyses.append(analysis)

        # 3. Temporal reasoning across frames
        temporal_summary = await self._temporal_reasoning(frame_analyses, queries)

        return {
            "duration": duration,
            "frames_analyzed": len(frames),
            "frame_analyses": frame_analyses,
            "temporal_summary": temporal_summary,
            "cost_estimate": self._estimate_cost(len(frames)),
        }

    async def _analyze_frame(self, frame: np.ndarray, timestamp: float, queries: list[str]) -> dict:
        """Анализ отдельного кадра."""

        # Preprocess: resize для экономии
        h, w = frame.shape[:2]
        if max(w, h) > 1024:
            scale = 1024 / max(w, h)
            new_size = (int(w * scale), int(h * scale))
            frame = cv2.resize(frame, new_size)

        prompt = f"""Analyze this frame at timestamp {timestamp:.1f}s.

Answer these questions:
{chr(10).join(f'- {q}' for q in queries)}

Return as JSON with keys for each question."""

        response = await self.vision.analyze(prompt, image=frame)
        return {"timestamp": timestamp, "analysis": response}

    async def _temporal_reasoning(self, frame_analyses: list[dict], queries: list[str]) -> str:
        """Временное рассуждение: что изменилось между кадрами."""

        timeline = "\n".join(
            f"[{a['timestamp']:.1f}s]: {a['analysis']}"
            for a in frame_analyses
        )

        prompt = f"""Based on these timestamps of a video, provide a temporal analysis:

{timeline}

Answer:
1. What happens over time?
2. Key transitions and changes?
3. Summary of the video
4. Answers to original questions:
{chr(10).join(f'  - {q}' for q in queries)}"""

        return await self.vision.analyze(prompt)
```

### Audio-Video Synchronization

```python
class AVSyncAnalyzer:
    """Анализ аудио-видео синхронизации."""

    async def extract_audio_timeline(self, video_path: str) -> list[dict]:
        """Извлекает аудио-события с таймстемпами."""

        # 1. Extract audio from video
        audio_path = self._extract_audio(video_path)

        # 2. STT with timestamps
        transcript = await self.stt.transcribe_with_timestamps(audio_path)

        # 3. Speaker diarization
        speakers = await self.diarizer.diarize(audio_path)

        # 4. Align with video frames
        timeline = self._align_audio_with_frames(transcript, speakers)
        return timeline

    def _align_audio_with_frames(self, transcript: list[dict], speakers: list[dict]) -> list[dict]:
        """Сопоставляет аудио-события с временной шкалой видео."""
        timeline = []
        for segment in transcript:
            timeline.append({
                "start": segment["start"],
                "end": segment["end"],
                "text": segment["text"],
                "speaker": self._find_speaker(segment["start"], speakers),
            })
        return timeline
```

---

## 3. Long Video Handling

Видео >30 минут требует специальной обработки:

```python
class LongVideoProcessor:
    """Обработка длинных видео (>30 минут)."""

    CHUNK_DURATION = 300  # 5 минут на чанк

    async def process_long_video(self, video_path: str, task: str) -> dict:
        """Обрабатывает длинное видео по чанкам."""

        duration = self._get_duration(video_path)
        chunks = self._split_into_chunks(video_path, self.CHUNK_DURATION)

        log(f"Video duration: {duration:.0f}s → {len(chunks)} chunks of {self.CHUNK_DURATION}s")

        # Process each chunk
        chunk_results = []
        for i, chunk in enumerate(chunks):
            log(f"Processing chunk {i+1}/{len(chunks)}")
            result = await self._process_chunk(chunk, task)
            chunk_results.append({
                "chunk": i + 1,
                "start_time": i * self.CHUNK_DURATION,
                "result": result,
            })

        # Hierarchical summarization
        summary = await self._hierarchical_summarize(chunk_results, task)

        return {
            "total_chunks": len(chunks),
            "chunk_results": chunk_results,
            "summary": summary,
        }

    async def _hierarchical_summarize(self, chunk_results: list[dict], task: str) -> str:
        """Многоуровневое суммирование результатов чанков."""

        # Level 1: summarize each chunk
        chunk_summaries = []
        for cr in chunk_results:
            prompt = f"Summarize this chunk (minute {cr['start_time']//60}-{(cr['start_time']+300)//60}): {cr['result']}"
            summary = await self.llm.generate(prompt, max_tokens=100)
            chunk_summaries.append(summary)

        # Level 2: combine chunk summaries (если >5 чанков, идём рекурсивно)
        while len(chunk_summaries) > 5:
            batch_summaries = []
            for i in range(0, len(chunk_summaries), 5):
                batch = chunk_summaries[i:i+5]
                prompt = f"Combine these summaries:\n" + "\n".join(f"- {s}" for s in batch)
                batch_summaries.append(await self.llm.generate(prompt, max_tokens=200))
            chunk_summaries = batch_summaries

        # Final summary
        prompt = f"Final summary for task '{task}':\n" + "\n".join(chunk_summaries)
        return await self.llm.generate(prompt, max_tokens=300)
```

---

## 4. Real-time Video Streaming

```python
class RealTimeVideoAgent:
    """Обработка видео в реальном времени (RTSP, WebRTC)."""

    def __init__(self, frame_interval: float = 1.0):
        self.frame_interval = frame_interval
        self.last_process_time = 0

    async def process_stream(self, stream_url: str, callbacks: dict):
        """Обрабатывает RTSP/WebRTC поток в реальном времени."""

        cap = cv2.VideoCapture(stream_url)
        if not cap.isOpened():
            raise RuntimeError(f"Cannot open stream: {stream_url}")

        log(f"Streaming from {stream_url}")

        while True:
            ret, frame = cap.read()
            if not ret:
                await asyncio.sleep(0.1)
                continue

            now = time.time()
            if now - self.last_process_time < self.frame_interval:
                continue

            self.last_process_time = now

            # Обработка кадра
            tasks = []

            if "on_object_detected" in callbacks:
                tasks.append(self._detect_objects(frame, callbacks["on_object_detected"]))
            if "on_motion" in callbacks:
                tasks.append(self._detect_motion(frame, callbacks["on_motion"]))
            if "on_anomaly" in callbacks:
                tasks.append(self._detect_anomaly(frame, callbacks["on_anomaly"]))

            if tasks:
                await asyncio.gather(*tasks)

            # Frame dropping: не скапливаем очередь
            cap.grab()  # Пропускаем следующий кадр

    async def _detect_objects(self, frame: np.ndarray, callback):
        """Обнаружение объектов через YOLO или vision-модель."""
        # Быстрый классификатор, не LLM
        detections = self.yolo_model(frame)
        if detections:
            await callback(detections)

    async def _detect_motion(self, frame: np.ndarray, callback):
        """Motion detection через background subtractor."""
        mask = self.mog2.apply(frame)
        movement = np.sum(mask > 0)
        if movement > self.motion_threshold:
            await callback({"movement_pixels": int(movement)})

    async def _detect_anomaly(self, frame: np.ndarray, callback):
        """Аномалии через vision-модель (редко, раз в N кадров)."""
        if random.random() < 0.05:  # 5% кадров
            response = await self.vision.analyze(
                "Any anomaly, danger, or unusual activity?", image=frame
            )
            if "anomaly" in response.lower():
                await callback({"anomaly": response})
```

---

## 5. Cost Optimization for Video

```python
class VideoCostOptimizer:
    """Оптимизация стоимости анализа видео."""

    COST_PER_FRAME = {
        "gpt-4o": 0.00215,       # $ per 156x156 tile (high_detail)
        "claude-sonnet-4": 0.003, # $ per 156x156 tile
        "gemini-2.0-flash": 0.00015,
    }

    def __init__(self, model: str = "gpt-4o", budget_cents: float = 10.0):
        self.model = model
        self.budget_cents = budget_cents

    def optimize(self, video_duration_sec: float) -> dict:
        """Рассчитывает оптимальную стратегию под бюджет."""

        cost_per_frame = self.COST_PER_FRAME[self.model]
        max_frames_under_budget = int((self.budget_cents / 100) / cost_per_frame)

        # Как часто брать кадр
        frame_interval = max(1, video_duration_sec / max_frames_under_budget)

        strategies = {
            "budget": self.budget_cents,
            "max_frames": max_frames_under_budget,
            "frame_interval_sec": frame_interval,
            "recommended_strategy": self._recommend_strategy(max_frames_under_budget),
            "estimated_cost": min(
                max_frames_under_budget * cost_per_frame,
                self.budget_cents / 100,
            ),
        }

        return strategies

    def _recommend_strategy(self, frames: int) -> str:
        if frames >= 100:
            return "uniform (high density)"
        elif frames >= 30:
            return "scene_based"
        elif frames >= 10:
            return "keyframe"
        else:
            return "hybrid (max info per frame)"
```

---

## Резюме

```
Видео-анализ: стратегии и экономика

1. Выбор кадров:
   — Keyframe: лучший ratio информация/стоимость
   — Scene-based: для контента с монтажом
   — Uniform: fallback, когда ничего не знаем о видео

2. Длинные видео:
   — Чанки по 5 минут
   — Hierarchical summarization (O(log n))
   — Избегаем повторного анализа похожих кадров

3. Real-time:
   — Frame dropping (не accumulate очередь)
   — Motion detection до LLM (фильтр)
   — Vision LLM только на 5% кадров

4. Cost control:
   — Resize: 1024px достаточно
   — Perceptual dedup: до 60% экономии
   — Frame interval под бюджет
```

---

## Практическое задание

1. Реализуй FrameExtractor с hybrid стратегией (keyframe + scene).

2. Собери VideoUnderstandingPipeline: extract frames → analyze → temporal reasoning.

3. Добавь обработку 1-часового видео через LongVideoProcessor.

4. Оптимизируй пайплайн для бюджета $0.10 на 10-минутное видео.

---

## Проверь себя

1. Какие 4 стратегии извлечения кадров существуют?
2. Почему keyframe — лучший ratio качества к стоимости?
3. Как работает hierarchical summarization для длинных видео?
4. Зачем нужен frame dropping в real-time обработке?
5. Как рассчитать число кадров под заданный бюджет?

---

## Ссылки

- [[01-economics-architecture]] — экономика модальностей
- [[02-vision-deep]] — vision deep dive
- [[03-audio-deep]] — audio deep dive
- [[05-multimodal-rag]] — следующий урок: мультимодальный RAG
