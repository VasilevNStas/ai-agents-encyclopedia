---
created: 2026-05-28
tags: [course/multi-modal-deep, audio, voice, agents, stt, tts]
status: active
---

# Урок 19.3: Audio & Voice Agents Deep Dive

> [!quote] Ключевая идея
> Голосовой агент — это не просто STT → LLM → TTS. Это real-time распределённая система с VAD, barge-in, turn-taking и управлением латентностью. Каждый миллисекунда задержки — это падение retention.

---

## 1. Voice Pipeline Architecture

Полный пайплайн голосового агента:

```python
import asyncio
import time
from enum import Enum


class VoicePipelineState(Enum):
    LISTENING = "listening"          # VAD активен, ждём речь
    SPEAKING = "speaking"           # Пользователь говорит
    PROCESSING = "processing"       # STT + LLM
    RESPONDING = "responding"       # TTS + playback
    INTERRUPTED = "interrupted"     # Barge-in случился


class VoicePipeline:
    """Real-time голосовой пайплайн."""

    def __init__(self, stt: Any, llm: Any, tts: Any, vad: Any):
        self.stt = stt          # Speech-to-Text (Whisper, Deepgram)
        self.llm = llm          # Language Model
        self.tts = tts          # Text-to-Speech (ElevenLabs, Cartesia)
        self.vad = vad          # Voice Activity Detection
        self.state = VoicePipelineState.LISTENING
        self.barge_in = True

        # Performance metrics
        self.metrics = {
            "vad_to_stt_ms": 0,
            "stt_to_llm_ms": 0,
            "llm_to_tts_ms": 0,
            "total_response_ms": 0,
        }

    async def process_audio_stream(self, audio_stream: AsyncIterator[bytes]):
        """Обрабатывает аудио в реальном времени."""

        buffer = b""
        response_playing = False

        async for chunk in audio_stream:
            t_start = time.perf_counter()

            # 1. VAD: определяем, говорит ли пользователь
            if self.vad.is_speech(chunk):
                buffer += chunk
                if self.state == VoicePipelineState.RESPONDING and self.barge_in:
                    await self._handle_barge_in()
            else:
                if buffer:
                    # 2. STT
                    t0 = time.perf_counter()
                    text = await self.stt.transcribe(buffer)
                    self.metrics["vad_to_stt_ms"] = (time.perf_counter() - t0) * 1000

                    if not text.strip():
                        buffer = b""
                        continue

                    # 3. LLM
                    t0 = time.perf_counter()
                    response = await self.llm.generate(text)
                    self.metrics["stt_to_llm_ms"] = (time.perf_counter() - t0) * 1000

                    # 4. TTS
                    t0 = time.perf_counter()
                    audio = await self.tts.synthesize(response)
                    self.metrics["llm_to_tts_ms"] = (time.perf_counter() - t0) * 1000

                    self.metrics["total_response_ms"] = (time.perf_counter() - t_start) * 1000

                    # 5. Отправляем аудио-ответ
                    yield audio
                    buffer = b""

    async def _handle_barge_in(self):
        """Обрабатывает прерывание от пользователя."""
        # Останавливаем TTS playback
        await self.tts.stop()
        self.state = VoicePipelineState.LISTENING
        log("Barge-in detected: user interrupted response")
```

---

## 2. STT Deep Dive

### Сравнение провайдеров

| Провайдер | Модель | WER | Латенти. (500ms audio) | Цена | Streaming | Языки |
|-----------|--------|-----|----------------------|------|-----------|-------|
| Whisper (local) | large-v3 | 4.5% | 150-300ms | 0 | Да | 100+ |
| Deepgram | nova-2 | 4.0% | 150-500ms | $0.0043/min | Да | 99+ |
| OpenAI | whisper-1 | 4.8% | 500-2000ms | $0.006/min | Нет | 100+ |
| AssemblyAI | best | 4.3% | 400-1500ms | $0.009/min | Да | 50+ |

### Production STT с локальным Whisper

```python
class WhisperSTT:
    """Production-ready STT with local Whisper."""

    def __init__(self, model_size: str = "large-v3", device: str = "auto"):
        import whisper
        self.model = whisper.load_model(model_size, device=device)

        # Buffering для streaming
        self.buffer = b""
        self.sample_rate = 16000
        self.min_audio_length = 0.5  # сек
        self.max_audio_length = 30.0  # сек

    async def transcribe(self, audio_bytes: bytes, language: str | None = None) -> str:
        """Транскрибация аудио через Whisper."""

        # Подготовка аудио: декодируем в numpy
        audio = self._decode_audio(audio_bytes)
        duration = len(audio) / self.sample_rate

        if duration < self.min_audio_length:
            return ""  # short utterance — not speech

        options = {"language": language} if language else {}
        result = await asyncio.get_event_loop().run_in_executor(
            None, lambda: self.model.transcribe(audio, **options)
        )
        return result["text"].strip()

    def _decode_audio(self, audio_bytes: bytes) -> np.ndarray:
        """Декодирует аудио-байты в numpy array."""
        import io
        import soundfile as sf
        audio, sr = sf.read(io.BytesIO(audio_bytes))
        if sr != self.sample_rate:
            # Resample
            import librosa
            audio = librosa.resample(audio, orig_sr=sr, target_sr=self.sample_rate)
        return audio


class DeepgramSTT:
    """STT через Deepgram API с поддержкой streaming."""

    def __init__(self, api_key: str, model: str = "nova-2"):
        from deepgram import DeepgramClient
        self.client = DeepgramClient(api_key)
        self.model = model
        self.smart_format = True  # Авто-капитализация, пунктуация, числа

    async def transcribe_streaming(self, audio_stream: AsyncIterator[bytes]) -> AsyncIterator[str]:
        """Streaming-транскрибация в реальном времени."""

        options = {
            "model": self.model,
            "smart_format": self.smart_format,
            "interim_results": True,
            "utterance_end_ms": 1000,
        }

        async for text in self.client.listen.rest.async_stream(audio_stream, options):
            if text.is_final:
                yield text.channel.alternatives[0].transcript

    async def transcribe_file(self, audio_path: str) -> str:
        with open(audio_path, "rb") as f:
            audio = f.read()
        response = await self.client.listen.rest.async_transcribe(
            {"buffer": audio}, {"model": self.model, "smart_format": self.smart_format}
        )
        return response.results.channels[0].alternatives[0].transcript
```

---

## 3. TTS Deep Dive

### Сравнение провайдеров

| Провайдер | Модель | MOS (quality) | Latency | Цена | Voice Cloning | Emotions |
|-----------|--------|--------------|---------|------|---------------|----------|
| ElevenLabs | turbo v2.5 | 4.6 | 200-500ms | $0.30/char | Да | Да |
| Cartesia | sonic | 4.5 | 75-150ms | $0.15/min | Нет | Да |
| OpenAI | tts-1-hd | 4.3 | 300-800ms | $0.015/min | Нет | Да |
| PlayHT | 3.0 | 4.4 | 200-500ms | $0.20/min | Да | Да |

### TTS с Voice Parameters

```python
class TTSManager:
    """Управление TTS с поддержкой параметров голоса."""

    VOICE_BANK = {
        "support": {
            "elevenlabs": {"voice_id": "21m00Tcm4TlvDq8ikWAM", "name": "Rachel"},
            "cartesia": {"voice_id": "79e5c0e4-b00e-44b1-8e1a-9953212d9af5"},
        },
        "sales": {
            "elevenlabs": {"voice_id": "AZnzlk1XvdvUeBnXmlld", "name": "Adam"},
        },
        "default": {
            "elevenlabs": {"voice_id": "EXAVITQu4vrVxn66eGVC", "name": "Bella"},
        },
    }

    def __init__(self, provider: str = "elevenlabs", api_key: str = ""):
        self.provider = provider
        self.api_key = api_key
        self.synthesis_queue = asyncio.Queue()
        self.current_utterance = None

    async def synthesize(
        self, text: str, voice_role: str = "support",
        speed: float = 1.0, emotion: str = "neutral"
    ) -> bytes:
        """Синтезирует речь с заданными параметрами."""

        voice = self.VOICE_BANK.get(voice_role, self.VOICE_BANK["default"])

        if self.provider == "elevenlabs":
            return await self._elevenlabs_tts(text, voice["elevenlabs"]["voice_id"], speed, emotion)
        elif self.provider == "cartesia":
            return await self._cartesia_tts(text, voice["cartesia"]["voice_id"], speed, emotion)
        elif self.provider == "openai":
            return await self._openai_tts(text, speed, emotion)

    async def _elevenlabs_tts(self, text: str, voice_id: str, speed: float, emotion: str) -> bytes:
        from elevenlabs import generate, Voice, VoiceSettings

        # Emotion через voice settings
        stability = 0.5 if emotion == "neutral" else 0.3
        similarity = 0.8

        audio = generate(
            text=text,
            voice=Voice(
                voice_id=voice_id,
                settings=VoiceSettings(stability=stability, similarity_boost=similarity)
            ),
            model="eleven_turbo_v2_5",
        )
        return audio

    async def _cartesia_tts(self, text: str, voice_id: str, speed: float, emotion: str) -> bytes:
        # Cartesia Sonic: sub-100ms latency
        from cartesia import Cartesia
        client = Cartesia(api_key=self.api_key)

        emotion_map = {"neutral": "a0a2e0f0", "happy": "b1b3c2", "urgent": "c2c4d3"}

        response = client.tts.bytes(
            model_id="sonic-2",
            transcript=text,
            voice_id=voice_id,
            output_format={"container": "wav", "encoding": "pcm_f32le", "sample_rate": 24000},
            language="en",
            emotion=emotion_map.get(emotion, emotion_map["neutral"]),
        )
        return response

    async def stream_synthesize(self, text: str, voice_role: str = "support"):
        """Streaming TTS: выдаёт аудио чанками для real-time воспроизведения."""

        voice = self.VOICE_BANK.get(voice_role, self.VOICE_BANK["default"])

        if self.provider == "elevenlabs":
            async for chunk in self._elevenlabs_stream(text, voice["elevenlabs"]["voice_id"]):
                yield chunk
```

---

## 4. Voice UX Patterns

```python
class VoiceUXAgent:
    """Голосовой UX: turn-taking, interruptions, backchanneling."""

    def __init__(self):
        self.turn_state = "user"
        self.interruption_buffer = []
        self.backchannel_enabled = True  # "mhm", "uh-huh"

    async def handle_turn(self, user_audio: bytes, conversation_history: list) -> bytes:
        """Управление turn-taking в голосовом диалоге."""

        # 1. Определяем, закончил ли пользователь говорить
        if self._has_finished_turn(user_audio):
            self.turn_state = "agent"

            # 2. Если пользователь прерывал нас — адаптируем ответ
            if self.interruption_buffer:
                response = await self._generate_with_interruption_context(
                    conversation_history, self.interruption_buffer
                )
                self.interruption_buffer = []
            else:
                response = await self._generate_response(conversation_history)

            # 3. Добавляем backchanneling если надо
            if self.backchannel_enabled and self._needs_backchannel(response):
                response = f"[shorter version] {response}"

            # 4. TTS с учётом латентности (используем streaming)
            return await self.tts.stream_synthesize(response)

        else:
            self.turn_state = "user"
            # Backchanneling во время паузы пользователя
            if self.backchannel_enabled and self._user_considering(conversation_history):
                await self._play_backchannel()
            return b""

    def _has_finished_turn(self, audio: bytes) -> bool:
        """Определяет конец очереди пользователя (по VAD + silence)."""
        duration = len(audio) / 16000  # 16kHz
        silence_ratio = self.vad.silence_ratio(audio)
        return silence_ratio > 0.6 and duration > 1.0

    async def _play_backchannel(self):
        """Воспроизводит короткий звук согласия (mhm, uh-huh)."""
        backchannel_audio = await self.tts.synthesize("mhm", voice_role="support")
        await self.audio_output.play(backchannel_audio)


# === Barge-in ===
class BargeInDetector:
    """Детекция прерывания пользователем."""

    def __init__(self, energy_threshold: float = 0.08):
        self.energy_threshold = energy_threshold
        self.is_speaking = False

    def detect_barge_in(self, audio_chunk: bytes) -> bool:
        """Определяет, говорит ли пользователь, пока агент отвечает."""
        energy = self._compute_energy(audio_chunk)
        if energy > self.energy_threshold:
            self.is_speaking = True
            return True
        return False

    def _compute_energy(self, audio: bytes) -> float:
        """RMS energy аудио-чанка."""
        import numpy as np
        samples = np.frombuffer(audio, dtype=np.int16).astype(np.float32)
        return float(np.sqrt(np.mean(samples ** 2)))
```

---

## 5. Multi-speaker Scenarios

```python
class SpeakerDiarizer:
    """Определение говорящего (speaker diarization) для multi-speaker audio."""

    def __init__(self, model: str = "pyannote/speaker-diarization-3.1"):
        from pyannote.audio import Pipeline
        self.pipeline = Pipeline.from_pretrained(model)

    async def diarize(self, audio_path: str) -> list[dict]:
        """Определяет, кто когда говорит."""

        result = await asyncio.get_event_loop().run_in_executor(
            None, lambda: self.pipeline(audio_path)
        )

        speakers = []
        for turn, _, speaker in result.itertools.tracks():
            speakers.append({
                "speaker": speaker,
                "start": turn.start,
                "end": turn.end,
                "duration": turn.end - turn.start,
            })

        return speakers

    async def transcribe_with_speakers(self, audio_path: str) -> str:
        """Транскрибация с указанием говорящего."""

        # 1. Diarization
        speakers = await self.diarize(audio_path)

        # 2. STT
        full_transcript = await self.stt.transcribe_file(audio_path)

        # 3. Align: назначаем текст на спикеров
        aligned = self._align_speakers(full_transcript, speakers)

        transcript_lines = []
        for seg in aligned:
            transcript_lines.append(f"[{seg['speaker']}]: {seg['text']}")

        return "\n".join(transcript_lines)
```

---

## 6. Voice Pipeline — Performance Optimization

```python
class VoicePipelineOptimizer:
    """Оптимизация латентности голосового пайплайна."""

    def __init__(self):
        self.target_latency_ms = 300  # Целевая end-to-end задержка

    async def optimize_pipeline(self, audio: bytes) -> dict:
        """Динамический выбор стратегий для соблюдения latency SLO."""

        strategies = []

        # Если аудио короткое — используем быстрый STT
        if len(audio) < 16000 * 3:  # < 3 секунд
            strategies.append("fast_stt")
        else:
            strategies.append("accurate_stt")

        # Каскадный LLM (запасной timeout)
        strategies.append("cascade_llm")

        # Streaming TTS (first chunk ASAP)
        strategies.append("streaming_tts")

        return {
            "strategies": strategies,
            "estimated_latency_ms": self._estimate_latency(strategies, audio),
        }

    def _estimate_latency(self, strategies: list[str], audio: bytes) -> int:
        latency = 0
        if "fast_stt" in strategies:
            latency += 150
        else:
            latency += 400
        latency += 200  # LLM
        if "streaming_tts" in strategies:
            latency += 50  # First chunk latency
        else:
            latency += 300
        return latency


# === Example: caching TTS ===
class TTSCache:
    """Кэш аудио-ответов."""

    def __init__(self, max_size_mb: int = 100):
        self.cache = {}
        self.max_size_bytes = max_size_mb * 1024 * 1024

    async def get_or_synthesize(self, text: str, voice: str, tts_fn) -> bytes:
        key = hashlib.md5(f"{text}:{voice}".encode()).hexdigest()
        if key in self.cache:
            log("TTS cache hit")
            return self.cache[key]
        audio = await tts_fn(text)
        if len(audio) < 50000:  # Не кэшируем длинные файлы
            self.cache[key] = audio
        return audio
```

---

## Резюме

```
Voice Pipeline:

  Microphone → VAD → STT → LLM → TTS → Speaker
       ↑                               |
       └────── Barge-in detector ──────┘

Ключевые метрики:
  — VAD latency: < 50ms
  — STT latency: 150-500ms (streaming)
  — LLM latency: 200-1000ms (cascade)
  — TTS latency: 75-500ms (streaming)
  — End-to-end target: < 1000ms, gold standard: < 300ms

Выбор провайдера:
  — Local Whisper: бесплатно, приватно, latency ~200ms
  — Deepgram: лучший WER, streaming
  — Cartesia Sonic: самая быстрая TTS (75ms)
  — ElevenLabs: лучшее качество + voice cloning
```

---

## Практическое задание

1. Собери голосовой пайплайн: VAD → Whisper → LLM → ElevenLabs TTS.

2. Реализуй barge-in: пользователь может прервать ответ агента.

3. Добавь speaker diarization для звонка между клиентом и саппортом.

4. Оптимизируй пайплайн для target latency < 500ms end-to-end.

---

## Проверь себя

1. Какие компоненты входят в real-time voice pipeline?
2. Чем отличается latency streaming vs batch STT?
3. Зачем нужен VAD, если STT сам определяет речь?
4. Что такое barge-in и как он реализован?  
5. Как speaker diarization помогает в multi-speaker сценариях?

---

## Ссылки

- [[01-economics-architecture]] — экономика модальностей
- [[02-vision-deep]] — предыдущий урок: vision deep dive
- [[04-video-deep]] — следующий урок: video agents
- [[../09-advanced-rag-agents/06-audio-agents]] — audio basics
