---
created: 2026-05-28
tags: [course/advanced-rag, multimodal, audio, architect]
status: active
---

# Урок 35c: Audio Agents — голос, речь, аудио

> [!quote] Ключевая идея
> Голосовые AI-агенты — один из самых быстрорастущих сценариев 2025-2026. Архитектура voice-агента отличается от текстового: real-time транскрипция, VAD (Voice Activity Detection), управление паузами, эмоциональный тон.

---

## 1. Архитектура voice-агента

```
[Микрофон] → VAD → [STT] → [LLM] → [TTS] → [Динамик]
                ↓                                    ↑
           [Buffer] → [Agent loop] → [Stream buffer] →
```

Компоненты:
| Компонент | Технология 2026 | Латенси |
|-----------|----------------|---------|
| **VAD** (детекция речи) | Silero VAD, WebRTC VAD | 10-50ms |
| **STT** (речь → текст) | Whisper v3, Deepgram, AssemblyAI | 200-500ms |
| **LLM** (обработка) | Claude/GPT-4o mini | 500-2000ms |
| **TTS** (текст → речь) | ElevenLabs, OpenAI TTS, Cartesia | 200-800ms |

---

## 2. Real-time транскрипция

```python
import asyncio
import websockets
from deepgram import DeepgramClient, LiveTranscriptionEvents


class VoiceTranscriber:
    """Real-time транскрипция аудио."""

    def __init__(self, api_key: str):
        self.client = DeepgramClient(api_key)
        self.buffer = ""

    async def transcribe_stream(self, audio_stream):
        """Транскрибирует аудио-поток в реальном времени."""
        dg_connection = self.client.listen.websocket.v("1")

        async def on_message(self, result, **kwargs):
            transcript = result.channel.alternatives[0].transcript
            if transcript.strip():
                self.buffer += transcript + " "
                # Передаём агенту по мере поступления
                await self.agent.process_partial(transcript)

        dg_connection.on(LiveTranscriptionEvents.Transcript, on_message)
        dg_connection.start()

        async for chunk in audio_stream:
            dg_connection.send(chunk)

        dg_connection.finish()
```

---

## 3. Voice Activity Detection

```python
class VAD:
    """Определяет, когда человек говорит / молчит."""

    def __init__(self, threshold: float = 0.5, min_speech_ms: int = 200):
        self.threshold = threshold
        self.min_speech = min_speech_ms
        self.speaking = False
        self.silence_start = None

    def process_audio(self, audio_chunk: bytes) -> str:
        """Возвращает 'speech', 'silence', 'continue'."""
        probability = self.detect_speech(audio_chunk)

        if probability > self.threshold and not self.speaking:
            self.speaking = True
            return "speech_start"

        if probability < self.threshold and self.speaking:
            if self.silence_start is None:
                self.silence_start = time.time()
            elif time.time() - self.silence_start > 0.5:  # 500ms silence
                self.speaking = False
                self.silence_start = None
                return "silence_timeout"  # пользователь закончил

        return "continue"
```

---

## 4. Voice Agent Loop

```python
class VoiceAgent:
    """Голосовой AI-агент."""

    def __init__(self, stt, llm, tts, vad):
        self.stt = stt         # Speech-to-Text
        self.llm = llm         # LLM
        self.tts = tts         # Text-to-Speech
        self.vad = vad         # Voice Activity Detection
        self.conversation = []

    async def handle_audio(self, audio_chunk: bytes):
        """Обрабатывает аудио-чunk от микрофона."""
        vad_state = self.vad.process_audio(audio_chunk)

        if vad_state == "speech_start":
            await self.start_listening()

        elif vad_state == "silence_timeout":
            # Пользователь закончил говорить — отвечаем
            full_text = self.stt.finalize()
            self.conversation.append({"role": "user", "content": full_text})

            # LLM
            response = await self.llm.generate(self.conversation)
            self.conversation.append({"role": "assistant", "content": response})

            # TTS
            await self.tts.speak(response)

        else:
            # Продолжаем слушать
            self.stt.feed_audio(audio_chunk)
```

---

## 5. Практика

Напиши голосового ассистента, который:
1. Слушает микрофон
2. Транскрибирует через Whisper/Deepgram
3. Отвечает через TTS
4. Поддерживает interrupt (пользователь перебивает агента)

---

## Ссылки

- [[05-vision-agents]] — vision-агенты
- [[../../../16-langgraph-track/05-production-streaming]] — streaming для low-latency
