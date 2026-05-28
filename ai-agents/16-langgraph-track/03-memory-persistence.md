---
created: 2026-05-28
tags: [course/langgraph, memory, persistence, checkpointing, architect]
status: active
---

# LangGraph L03: Memory & Persistence

> [!quote] Ключевая идея
> В уроке 7 мы обсуждали три слоя памяти. LangGraph даёт **персистентный слой "из коробки"**: checkpointing автоматически сохраняет состояние после каждого узла. Это меняет архитектуру: агент может упасть и продолжить с того же места, а разработчик — «перемотать» агента на любой шаг для отладки.

---

## Проблема: агент без памяти — одноразовый

Без persistence каждый запуск агента начинается с чистого листа:

```python
# Без persistence
response = graph.invoke({"messages": [user_input]})
# Если процесс упал на шаге 5 — всё потеряно
# Если нужно отладить — только по логам
```

С checkpointing агент сохраняет состояние **после каждого узла**:

```python
# С checkpointing
from langgraph.checkpoint.memory import MemorySaver

memory = MemorySaver()
graph = builder.compile(checkpointer=memory)

# thread_id = идентификатор сессии
config = {"configurable": {"thread_id": "session_42"}}

# Первый вызов
result1 = graph.invoke({"messages": [msg1]}, config)

# Второй вызов — агент «помнит» предыдущие шаги
result2 = graph.invoke({"messages": [msg2]}, config)

# Если процесс упал — продолжаем с последнего сохранённого узла
```

---

## Checkpointer: что сохраняется

Checkpointer фиксирует **всё состояние графа** после каждого узла:

```
После узла "think":
  State:
    messages: [user_msg, ai_response]
    next_step: "tools"
    retries: 0
    tool_calls_count: 1

После узла "tools":
  State:
    messages: [..., ai_response, tool_result]
    next_step: "think"
    retries: 0
    tool_calls_count: 1
```

**Доступные checkpointer-ы:**

| Хранилище | Когда использовать | Скорость | Production |
|-----------|-------------------|----------|------------|
| `MemorySaver` | Разработка, тесты | Мгновенно | Нет (в памяти) |
| `SqliteSaver` | Локальный прототип | Быстро | Да (single-node) |
| `PostgresSaver` | Production | Средне | Да (multi-node) |
| `MongoDBSaver` | Если уже есть MongoDB | Средне | Да |
| `RedisSaver` | High-throughput | Очень быстро | Да (in-memory) |

```python
# Sqlite — для разработки
from langgraph.checkpoint.sqlite import SqliteSaver

with SqliteSaver.from_conn_string("checkpoints.db") as saver:
    graph = builder.compile(checkpointer=saver)
    result = graph.invoke(inputs, config)


# Postgres — для production
from langgraph.checkpoint.postgres import PostgresSaver

conn_string = "postgresql://user:pass@host:5432/agents"
with PostgresSaver.from_conn_string(conn_string) as saver:
    graph = builder.compile(checkpointer=saver)
    # Автоматически создаёт таблицу checkpoint
    await saver.setup()
    result = await graph.ainvoke(inputs, config)
```

---

## Thread ID: изоляция сессий

`thread_id` — ключ, изолирующий одну сессию агента от другой:

```python
# Каждый пользователь — свой thread
def handle_user_request(user_id: str, message: str):
    config = {"configurable": {"thread_id": f"user_{user_id}"}}
    return graph.invoke({"messages": [{"role": "user", "content": message}]}, config)


# Один пользователь — много диалогов
config_dialog_1 = {"configurable": {"thread_id": "user_42_dialog_1"}}
config_dialog_2 = {"configurable": {"thread_id": "user_42_dialog_2"}}
```

**Важно:** thread_id НЕ хранит состояние между разными графами. При изменении структуры графа старые checkpoint-ы становятся невалидными — версионируй графы.

---

## State Recovery: переживаем падение

Реальный сценарий: LLM API вернул timeout, агент упал на середине.

```python
import time
from tenacity import retry, stop_after_attempt, wait_exponential


class ResilientAgent:
    def __init__(self, graph, checkpointer):
        self.graph = graph.compile(checkpointer=checkpointer)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def invoke_with_retry(self, inputs, config):
        return self.graph.invoke(inputs, config)

    def recover(self, thread_id: str):
        """Продолжить с последнего сохранённого состояния."""
        config = {"configurable": {"thread_id": thread_id}}
        state = self.graph.get_state(config)
        if state and state.next:
            print(f"Recovering from node: {state.next}")
            return self.graph.invoke(None, config)  # None = продолжить
        return None


# Использование
agent = ResilientAgent(builder, saver)
try:
    result = agent.invoke_with_retry(inputs, config)
except Exception:
    # Логируем, алертим — но данные не потеряны
    logger.error("Agent failed, state saved for recovery")
    # Позже можно восстановить
    recovered = agent.recover("thread_42")
```

---

## State History: отладка и аудит

Checkpointer хранит **всю историю состояний** — это built-in observability:

```python
# Получить всю историю состояний
config = {"configurable": {"thread_id": "session_42"}}
history = list(graph.get_state_history(config))

for i, state in enumerate(history):
    print(f"Step {i}: node={state.next}, "
          f"messages={len(state.values['messages'])}, "
          f"cost={state.values.get('total_cost', 0):.4f}")

# "Перемотать" на определённый шаг
checkpoint_id = "1ef3b6d0-1c5f-6c4e-8f2a-3b1c7d8e9f0a"
rollback_config = {
    "configurable": {
        "thread_id": "session_42",
        "checkpoint_id": checkpoint_id,  # ← откат к этому чекпоинту
    }
}
state_at_point = graph.get_state(rollback_config)
```

**Применения:**
- **Debugging**: посмотреть состояние на шаге N
- **Audit**: доказать, что агент не видел определённые данные
- **Rollback**: откатить агента до безопасного состояния
- **Replay**: прогнать тот же input с другой моделью

---

## Long-term Memory: за пределами сессии

Checkpoints хранят **состояние сессии**. Для跨-сессионной памяти (агент помнит пользователя днями) — используй отдельное хранилище:

```python
class LongTermMemory:
    """Память, переживающая сессии агента."""

    def __init__(self, pg_connection):
        self.db = pg_connection

    async def save_fact(self, user_id: str, fact: dict):
        """Сохранить факт о пользователе."""
        await self.db.execute(
            "INSERT INTO user_memory (user_id, key, value, updated_at) "
            "VALUES ($1, $2, $3, NOW()) "
            "ON CONFLICT (user_id, key) DO UPDATE SET value=$3, updated_at=NOW()",
            user_id, fact["key"], fact["value"]
        )

    async def get_context(self, user_id: str) -> str:
        """Собрать всё, что агент знает о пользователе."""
        rows = await self.db.fetch(
            "SELECT key, value FROM user_memory WHERE user_id=$1",
            user_id
        )
        if not rows:
            return ""
        return "\n".join(f"- {r['key']}: {r['value']}" for r in rows)


# В графе: узел, загружающий long-term память перед think
async def load_memory(state: AgentState, config: dict) -> AgentState:
    user_id = config["configurable"]["user_id"]
    context = await long_term_memory.get_context(user_id)
    if context:
        system_msg = {
            "role": "system",
            "content": f"Facts about user:\n{context}"
        }
        return {"messages": [system_msg]}
    return {}
```

---

## Практика: агент с persistence

1. Создай граф из урока L02 (агент с 3 инструментами)
2. Добавь `SqliteSaver` как checkpointer
3. Запусти агента с thread_id, сделай 2 вызова
4. Проверь `get_state_history` — увидишь все шаги
5. Убей процесс на середине, восстанови через `recover`

```python
# Проверка persistence
import tempfile
from langgraph.checkpoint.sqlite import SqliteSaver

with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
    with SqliteSaver.from_conn_string(tmp.name) as saver:
        graph = builder.compile(checkpointer=saver)
        config = {"configurable": {"thread_id": "test_01"}}

        # Шаг 1
        result = graph.invoke(
            {"messages": [{"role": "user", "content": "What's 15% of 200?"}]},
            config,
        )

        # История
        for s in graph.get_state_history(config):
            print(f"Node: {s.next}, Messages: {len(s.values.get('messages', []))}")
```

---

## Резюме

```
Persistence = checkpointer + thread_id

Checkpointer: MemorySaver → SqliteSaver → PostgresSaver
  - Сохраняет state после каждого узла
  - Позволяет recovery и отладку

Thread ID: изоляция сессий пользователей

State History: debugging, audit, rollback, replay

Long-term memory: отдельное хранилище вне checkpoint-ов
```

---

## Проверь себя

1. Что делает checkpointer? Какие данные он сохраняет?
2. Чем `thread_id` отличается от `user_id`?
3. Как восстановить агента после падения на шаге 4?
4. Зачем нужна `get_state_history`? Приведи 3 применения.
5. Почему нельзя хранить cross-session память в checkpoint-ах?

---

## Ссылки

- [[02-tools-calling]] — предыдущий урок: инструменты
- [[04-multi-agent-graphs]] — следующий урок: мультиагентные графы
- [[../../../03-memory-and-rag/01-memory-types]] — три слоя памяти (теория)
