---
created: 2026-05-28
tags: [course/advanced-rag, streaming, real-time, events, voice]
status: active
---

# Урок 36: Streaming и Real-Time агенты

> [!quote] Ключевая идея
> Весь предыдущий курс предполагал request-response: пользователь сказал — агент ответил. Но real-time агенты работают иначе: они слушают непрерывный поток событий и реагируют по мере поступления. **Это другая архитектура, другая модель памяти и другие требования к latency.**

---

## Request-Response vs Event-Driven

```python
# Request-Response (все уроки выше)
def agent_loop(user_input: str):
    response = llm.generate(user_input)
    while response.has_tool_call():
        result = execute(response.tool_call)
        response = llm.generate(result)
    return response

# Event-Driven (real-time)
async def agent_loop_stream(events: AsyncIterable[Event]):
    state = AgentState()
    async for event in events:
        match event.type:
            case "user_message":
                response = await llm.generate(state.context + event.text)
                await send_to_user(response)
            case "system_alert":
                state.alert(event.data)
            case "sensor_reading":
                state.update_reading(event.data)
                if state.should_alert():
                    await send_alert(state.alert_message())
            case "tool_result":
                state.memory.store(event.data)
```

Ключевые отличия:

| Аспект | Request-Response | Event-Driven |
|--------|-----------------|--------------|
| Управление | Пользователь | События |
| Состояние | Stateless (сессия) | Stateful (постоянно) |
| Latency | 1-10 сек (терпимо) | < 500ms (критично) |
| Память | Контекст окна | Буфер событий + summary |
| Масштабирование | По запросам | По событиям |

---

## Транспорты для real-time

### WebSocket

Двусторонний канал между агентом и клиентом:

```python
import asyncio
import json
import websockets

async def agent_ws(websocket):
    async for message in websocket:
        data = json.loads(message)
        response = await process_event(data)
        await websocket.send(json.dumps(response))

async def main():
    async with websockets.serve(agent_ws, "localhost", 8765):
        await asyncio.Future()  # run forever
```

**Когда использовать:** интерактивные агенты, live chat, collaborative editing.

### Server-Sent Events (SSE)

Однонаправленный поток от сервера клиенту:

```python
from sse_starlette.sse import EventSourceResponse

async def agent_sse(query: str):
    async def event_generator():
        # Эмуляция streaming-генерации
        async for chunk in llm.generate_stream(query):
            yield {
                "event": "token",
                "data": json.dumps({"text": chunk})
            }
        yield {"event": "done", "data": "complete"}

    return EventSourceResponse(event_generator())
```

**Когда использовать:** прогресс-бары, live-генерация, streaming ответов LLM.

### Message Queue (RabbitMQ, Kafka)

Асинхронная очередь для high-load систем:

```
                    ┌──────────┐
Sensor ──► Kafka ──►│  Agent   │──► Output Queue
Alert  ──► Kafka ──►│ Stream   │──► Database
Event  ──► Kafka ──►│ Processor│──► Dashboard
                    └──────────┘
```

**Когда использовать:** IoT, мониторинг, high-volume обработка событий.

---

## Voice-агенты (STT → LLM → TTS)

Voice-агент — частный случай streaming, но с тремя дополнительными этапами:

```
Microphone
    │
    ▼
Speech-to-Text (STT)  ──► Whisper, Deepgram, AssemblyAI
    │
    ▼
LLM Reasoning          ──► GPT-4o, Claude (multi-modal)
    │
    ▼
Text-to-Speech (TTS)   ──► ElevenLabs, Cartesia, OpenAI TTS
    │
    ▼
Speaker
```

### Архитектура voice-агента

```python
import asyncio

class VoiceAgent:
    def __init__(self):
        self.stt = STTClient(model="whisper-large-v3")
        self.llm = LLMClient(model="gpt-4o-audio-preview")
        self.tts = TTSClient(model="elevenlabs-turbo-v2.5")
        self.conversation_history = []

    async def process_audio_stream(self, audio_chunks: AsyncIterable[bytes]):
        # 1. STT: аудио → текст (streaming)
        async for text_chunk in self.stt.transcribe_stream(audio_chunks):
            self.conversation_history.append({"role": "user", "content": text_chunk})

            # 2. LLM: текст → ответ (возможно, с tool calls)
            response = await self.llm.generate(
                messages=self.conversation_history,
                tools=AGENT_TOOLS,
                stream=True
            )

            # 3. TTS: текст → аудио (streaming)
            async for audio_chunk in self.tts.synthesize_stream(response.text):
                yield audio_chunk  # в speaker пользователя

            # 4. Сохраняем историю
            self.conversation_history.append({
                "role": "assistant",
                "content": response.text
            })
```

### Проблемы voice-агентов

1. **Latency** — каждый этап (< 300ms) для естественного диалога
2. **Turn detection** — когда пользователь закончил говорить? (VAD — Voice Activity Detection)
3. **Interruptions** — пользователь перебил агента — нужно остановить TTS
4. **Context window** — аудио-токены занимают больше места, чем текст
5. **Tool calls** — как делать function calling в real-time диалоге

### Готовая инфраструктура

- **LiveKit** — open-source платформа для voice-агентов
- **Pipecat** — фреймворк для real-time AI
- **Vocode** — голосовые агенты с абстракцией STT/LLM/TTS
- **Twilio Voice** — для телефонных voice-агентов

---

## State Management в streaming

Главная проблема event-driven агентов: как хранить состояние между событиями?

```python
class StreamingAgentState:
    def __init__(self):
        # Буфер последних событий (скользящее окно)
        self.event_buffer = deque(maxlen=100)

        # Сжатое состояние (LLM-generated summary)
        self.compressed_state: str = ""

        # Активные задачи
        self.active_tasks: dict[str, TaskState] = {}

        # Контекстные переменные
        self.context_vars: dict[str, Any] = {}

    async def on_event(self, event: Event):
        self.event_buffer.append(event)

        # Каждые N событий — сжатие состояния
        if len(self.event_buffer) >= 50:
            self.compressed_state = await self.summarize_state()

        # Обработка события
        await self.process(event)

    async def summarize_state(self) -> str:
        prompt = f"""Compress the following event sequence into a concise
        state summary. Keep: active tasks, important changes, pending decisions.

        Events: {[e.summary() for e in self.event_buffer]}"""
        return await fast_llm.generate(prompt)
```

---

## Real-time в production

### Мониторинг

```
Latency budget:
  Total:      < 2000ms (voice) / < 5000ms (chat)
    STT:      < 300ms
    LLM:      < 1000ms (streaming first token)
    TTS:      < 300ms
    Network:  < 400ms

Метрики:
  p50/p95/p99 latency по каждому этапу
  Events processed per second
  Active connections
  Error rate (STT failures, LLM timeouts, TTS glitches)
```

### Graceful degradation

Когда latency растёт — снижай качество постепенно:

```yaml
latency < 1000ms:
  model: gpt-4o (best quality)
  stt: whisper-large-v3
  tts: elevenlabs-pro

latency 1000-3000ms:
  model: gpt-4o-mini
  stt: whisper-medium
  tts: elevenlabs-turbo

latency > 3000ms:
  model: gemini-flash (fastest)
  stt: whisper-small
  tts: basic (espeak-ng)
```

---

## Резюме

```
Streaming Agent ≠ Request-Response Agent

Отличия:
  - Event-driven loop (не user→response)
  - Stateful (буфер событий + summary)
  - Жёсткие требования к latency (< 500ms)
  - Voice = STT + LLM + TTS pipeline
  - Graceful degradation при росте latency

Транспорты:
  WebSocket — двусторонняя связь
  SSE — однонаправленный поток
  Message Queue — high-load системы
```

---

## Практическое задание

Реализуй streaming-агента для обработки событий датчиков:

- Создай `SensorAgent`, который слушает поток событий через WebSocket (симулируй `async for event in events:`)
- Агент получает события типов: `temperature_reading`, `motion_detected`, `system_alert`
- Реализуй `StreamingAgentState`: буфер последних 20 событий + сжатое состояние через LLM-саммари каждые 10 событий
- Если `temperature_reading > 45` — агент отправляет alert немедленно
- Если в буфере больше 3 `motion_detected` подряд без `temperature` — отправить warning

Требования: event-driven loop, stateful обработка, хотя бы одно условное срабатывание на основе накопленного состояния.

---

## Проверь себя

1. Чем event-driven цикл отличается от request-response?
2. Какие три транспорта подходят для real-time агентов? Когда что использовать?
3. Из каких трёх этапов состоит voice-агент?
4. Как управлять состоянием в streaming-агенте (буфер + summary)?
5. Как работает graceful degradation при росте latency?

---

## Ссылки

- Дальше: [[10-data-communication/01-data-engineering]]
- Назад: [[09-advanced-rag-agents/03-multi-modal-agents]]
- Смежно: [[09-advanced-rag-agents/02-long-running-agents]]
