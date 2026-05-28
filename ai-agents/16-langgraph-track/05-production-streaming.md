---
created: 2026-05-28
tags: [course/langgraph, production, streaming, hitl, performance, architect]
status: active
---

# LangGraph L05: Production Patterns — Streaming, HITL, Performance

> [!quote] Ключевая идея
> В уроках 16-20 мы строили production-агента. LangGraph добавляет три кита production-архитектуры: **streaming** (токены в реальном времени), **human-in-the-loop** (пауза на утверждение) и **персистентность** (устойчивость к падениям). Без них агент — игрушка.

---

## Streaming: от request-response к real-time

Пользователь не должен ждать 10 секунд в тишине. Stream токенов — обязательный UX:

```python
from langgraph.graph import StateGraph, START, END


graph = builder.compile()

# Stream событий: каждый шаг графа
config = {"configurable": {"thread_id": "stream_demo"}}
for event in graph.stream(
    {"messages": [{"role": "user", "content": "Analyze this code"}]},
    config,
    stream_mode="updates",  # события: каждый узел по завершению
):
    for node_name, update in event.items():
        print(f"[{node_name}] {update}")


# Stream токенов: LLM output word-by-word
for event in graph.stream(
    inputs,
    config,
    stream_mode="messages",  # токены LLM
):
    if hasattr(event, "content"):
        print(event.content, end="", flush=True)
```

### Stream modes

| Mode | Что стримит | Когда использовать |
|------|------------|-------------------|
| `"values"` | Всё состояние после каждого узла | Отладка, логирование |
| `"updates"` | Только изменения от узла | UI-обновления |
| `"messages"` | Токены LLM в реальном времени | UX: печатающийся текст |
| `"custom"` | Кастомные события | Прогресс-бары, метрики |

```python
# WebSocket-endpoint для streaming
from fastapi import FastAPI, WebSocket
from langgraph.graph import StateGraph

app = FastAPI()
graph = builder.compile()


@app.websocket("/agent/{thread_id}")
async def agent_stream(websocket: WebSocket, thread_id: str):
    await websocket.accept()
    config = {"configurable": {"thread_id": thread_id}}

    async for message in websocket.iter_json():
        async for event in graph.astream(
            {"messages": [message]},
            config,
            stream_mode="messages",
        ):
            if hasattr(event, "content") and event.content:
                await websocket.send_text(event.content)

        await websocket.send_json({"type": "done"})
```

---

## Human-in-the-Loop: пауза для утверждения

HITL — агент доходит до точки принятия решения и **ждёт**:

```python
from langgraph.graph import StateGraph, START, END, interrupt


def execute_dangerous_action(state: AgentState) -> AgentState:
    """Узел с HITL: пауза перед опасным действием."""

    action = state["pending_action"]

    # interrupt() — останавливает граф, ждёт ввод
    # Значение передаётся пользователю как запрос на утверждение
    confirmation = interrupt({
        "type": "confirmation",
        "action": action["name"],
        "args": action["args"],
        "risk_level": action.get("risk", "medium"),
        "estimated_cost": action.get("cost", 0),
    })

    if confirmation.get("approved"):
        result = execute_tool(action["name"], action["args"])
        return {"tool_results": [result]}
    else:
        return {"tool_results": ["Action rejected by user"]}


# === Client-side: как обработать interrupt ===
config = {"configurable": {"thread_id": "hitl_demo"}}

for event in graph.stream(inputs, config, stream_mode="updates"):
    # Проверяем, не остановился ли граф на interrupt
    state = graph.get_state(config)
    if state and state.tasks:
        for task in state.tasks:
            if task.interrupts:
                # Показываем пользователю
                print(f"Interrupt: {task.interrupts[0].value}")

                # После ответа пользователя — продолжаем
                graph.update_state(
                    config,
                    {"values": {"approved": user_says_yes}},
                    as_node="execute_action",
                )
```

**Сценарии HITL:**

| Сценарий | Interrupt точка | Resumption |
|----------|----------------|------------|
| Подтверждение опасного действия | Перед `rm -rf`, `DELETE FROM` | Продолжить с новым state |
| Уточнение неоднозначного запроса | После think, перед action | LLM переформулирует |
| Проверка финального ответа | Перед END | Редактировать или подтвердить |
| Бюджетный лимит | При превышении $treshold | Утвердить или изменить план |

---

## Конфигурация узлов: разные параметры для разных шагов

Каждый узел может иметь свою модель, temperature, бюджет:

```python
from langgraph.graph import StateGraph, START, END


class AgentConfig(TypedDict):
    model: str
    temperature: float
    max_tokens: int
    budget: float


def think(state: AgentState, config: RunnableConfig) -> AgentState:
    """Использует модель из конфигурации."""
    cfg = config["configurable"]

    llm = get_model(cfg.get("model", "claude-sonnet-4.6"))
    llm = llm.with_config({
        "temperature": cfg.get("temperature", 0.3),
        "max_tokens": cfg.get("max_tokens", 4096),
    })

    response = llm.invoke(state["messages"])
    return {"messages": [response]}


# Разные конфигурации для разных узлов
graph = builder.compile()

# Supervisor → дешёвая модель, быстрая
# Code agent → дорогая модель, точная
configs = {
    "supervisor": {"model": "claude-haiku-4.6", "temperature": 0.1},
    "code_agent": {"model": "claude-sonnet-4.6", "temperature": 0.3},
}
```

---

## Performance: когда граф тормозит

**Проблема:** LangGraph-граф может быть медленнее ручного цикла из-за оверхэда сохранения состояния.

```python
import time
from langgraph.checkpoint.memory import MemorySaver


# Замер: граф без чекпоинтинга vs с чекпоинтингом
def benchmark():
    # Without checkpointer
    fast_graph = builder.compile()  # MemorySaver не подключён
    start = time.time()
    for _ in range(100):
        fast_graph.invoke(inputs)
    print(f"Without: {time.time() - start:.2f}s")

    # With checkpointer
    slow_graph = builder.compile(checkpointer=MemorySaver())
    start = time.time()
    for _ in range(100):
        slow_graph.invoke(inputs, {"configurable": {"thread_id": f"t{_}"}})
    print(f"With: {time.time() - start:.2f}s")
```

**Оптимизации:**

| Приём | Выигрыш | Цена |
|-------|---------|------|
| Выключить checkpointer для readonly-запросов | 10-30% | Нет history |
| Stream mode "messages" вместо "values" | Меньше данных | Меньше информации |
| Pydantic v2 для state schema | 20-40% | Совместимость |
| Batch tool calls | latency / N | Чуть сложнее |
| Кешировать LLM response (semantic cache) | 50-80% на повторах | RAM/Redis |

```python
# Production-оптимизация: отключаем checkpointing для неважных запросов
class OptimisedGraph:
    def __init__(self, builder):
        self.graph = builder.compile(checkpointer=PostgresSaver(...))

    def invoke_important(self, inputs, thread_id):
        """Полный граф с persistence."""
        return self.graph.invoke(
            inputs, {"configurable": {"thread_id": thread_id}}
        )

    def invoke_quick(self, inputs):
        """Быстрый режим: без сохранения."""
        # Создаём временный граф без чекпойнтера
        fast = builder.compile()
        return fast.invoke(inputs)
```

---

## Production checklist для LangGraph

```python
# config.yaml — production-конфигурация графа
production:
  checkpointer:
    backend: postgres
    connection_string: ${CHECKPOINTER_DB}
    auto_setup: true

  streaming:
    mode: messages  # токены для UX
    timeout: 30  # секунд без ответа → interrupt

  hitl:
    enabled: true
    interrupt_on:
      - action_risk: high
      - cost_exceeds: 0.50  # $
      - tool: [delete_file, send_email, execute_shell]

  limits:
    max_retries: 3
    max_handoffs: 5
    max_tool_calls: 20
    timeout_per_node: 10  # seconds

  logging:
    level: info
    trace_all_states: false  # только ошибки
    sample_rate: 0.1  # 10% запросов с полным трейсом

  alerts:
    - metric: latency_p99
      threshold: 10s
    - metric: error_rate
      threshold: 0.05
    - metric: cost_per_session
      threshold: 2.00
```

---

## Практика: streaming-агент с HITL

Собери агента который:
1. Stream-ит токены пользователю через WebSocket
2. Останавливается на подтверждение перед опасным действием
3. Использует PostgresSaver для persistence
4. Имеет budget control (останавливается при превышении $0.50)

```python
# TODO: Собери production-граф
# - think node с streaming
# - tool node с HITL для опасных инструментов
# - checkpointer для recovery
# - budget check после каждого tool call
```

---

## Резюме

```
Production LangGraph:

Streaming:
  - stream_mode="messages" → токены в реальном времени
  - stream_mode="updates" → события узлов
  - WebSocket endpoint для UX

HITL:
  - interrupt() → пауза графа
  - update_state() → resumption
  - Сценарии: approval, clarification, review

Performance:
  - Checkpointer overhead: 10-30%
  - Semantic cache: 50-80% на повторах
  - Buffer tool calls: latency / N
```

---

## Проверь себя

1. Чем `stream_mode="updates"` отличается от `stream_mode="values"`?
2. Как interrupt() останавливает граф? Как его возобновить?
3. Когда стоит выключать checkpointer для повышения скорости?
4. Спроектируй interrupt для сценария «агент хочет отправить email».
5. Какие метрики нужно мониторить в production LangGraph-агента?

---

## Ссылки

- [[04-multi-agent-graphs]] — предыдущий урок: мультиагентность
- [[../../../05-production/02-observability]] — observability (урок 17)
- [[../../../05-production/04-resilience]] — resilience (урок 19)
- [[../../../13-ecosystem-operations/03-production-operations]] — production ops (урок 48)
