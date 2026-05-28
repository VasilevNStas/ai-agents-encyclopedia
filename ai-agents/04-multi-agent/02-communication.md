---
created: 2026-05-08
tags: [course/multi-agent, communication, architecture]
status: active
---

# Урок 13: Коммуникация между агентами

> [!quote] Ключевая идея
> Агенты должны общаться. Но как? Через общий чат? Через файлы? Через API? Выбор протокола коммуникации определяет, насколько система будет масштабируемой и отказоустойчивой.

---

## Проблема: агенты не телепаты

Когда два агента работают над одной задачей, им нужно обмениваться данными. Если коммуникация не спроектирована — возникает хаос.

```
❌ Хаос без коммуникации:
Agent1: "я нашёл баг в auth.py"
Agent2: "я переписал auth.py"  ← не знал, что Agent1 его уже чинит
Agent1: "я удалил твои изменения"
```

---

## Протоколы коммуникации

### 1. Через Supervisor (централизованно)

```
Agent1 → Supervisor → Agent2
```

**Плюсы:** Supervisor контролирует всё, нет конфликтов  
**Минусы:** узкое горлышко, Supervisor — single point of failure

### 2. Через общее хранилище (файлы / БД)

```
Agent1 пишет в results/auth-bug.md
Agent2 читает results/auth-bug.md
```

**Плюсы:** независимость, можно перечитать позже  
**Минусы:** stale data (агент может прочитать устаревшее)

### 3. Через сообщения (message bus)

```
Agent1 отправляет: {"type": "bug_found", "file": "auth.py", "line": 42}
Agent2 получает и реагирует
```

**Плюсы:** асинхронно, масштабируемо  
**Минусы:** сложнее в реализации

---

## Пример: Message Bus

```python
from dataclasses import dataclass
from enum import Enum
from queue import Queue

class MessageType(Enum):
    BUG_FOUND = "bug_found"
    CODE_READY = "code_ready"
    REVIEW_NEEDED = "review_needed"
    DEPLOY_READY = "deploy_ready"

@dataclass
class Message:
    sender: str
    msg_type: MessageType
    payload: dict
    timestamp: float

class MessageBus:
    def __init__(self):
        self.queues: dict[str, Queue] = {}

    def subscribe(self, agent_name: str):
        self.queues[agent_name] = Queue()

    def publish(self, message: Message, to: str = None):
        """Отправить сообщение конкретному агенту или всем."""
        if to:
            self.queues[to].put(message)
        else:
            for q in self.queues.values():
                q.put(message)

    def poll(self, agent_name: str) -> list[Message]:
        """Забрать все сообщения для агента."""
        msgs = []
        q = self.queues.get(agent_name)
        while q and not q.empty():
            msgs.append(q.get())
        return msgs


# Использование
bus = MessageBus()
bus.subscribe("debug_agent")
bus.subscribe("code_agent")

bus.publish(Message(
    sender="user",
    msg_type=MessageType.BUG_FOUND,
    payload={"file": "auth.py", "line": 42}
), to="debug_agent")
```

---

## Формат сообщений

Агенты должны общаться в **едином формате**. Без этого — разнобой:

```
❌ Agent1 пишет: "баг в файле auth.py на 42 строке"
❌ Agent2 пишет: {"bug": "auth.py:42"}
❌ Agent3 пишет: [auth.py, 42]
```

Единый протокол:

```json
{
  "type": "bug_report",
  "agent": "debug_agent_v2",
  "timestamp": "2026-05-08T19:00:00Z",
  "payload": {
    "file": "auth.py",
    "line": 42,
    "severity": "high",
    "description": "token not validated before DB query",
    "suggested_fix": "add token check at line 40"
  }
}
```

**Правило:** каждый тип сообщения — JSON Schema. Агенты валидируют входящие сообщения по схеме.

---

## Синхронная vs Асинхронная коммуникация

| | Синхронная | Асинхронная |
|--|-----------|-------------|
| Агент A ждёт ответ B | ✅ Да | ❌ Нет |
| Скорость | Медленнее | Быстрее |
| Сложность | Проще | Сложнее |
| Отказоустойчивость | Низкая (B упал — A тоже) | Высокая (сообщение в очереди) |
| Пример | Supervisor → Agent → ответ | Message Bus |

---

## Anti-patterns

### 1. Агенты говорят напрямую
```python
# ❌ Agent1 вызывает Agent2 напрямую
agent2.run(task)  # что если agent2 занят или упал?
```

### 2. Неструктурированные сообщения
```python
# ❌ Агент пишет "как бог на душу положит"
results.append("нашёл баг, почини")
# ✅
results.append({"type": "bug", "file": "auth.py"})
```

### 3. Бесконечное ожидание
```python
# ❌ Ждём ответ вечно
result = agent2.run(task)
# agent2 упал — ждём вечность
# ✅
result = agent2.run(task, timeout=30)
if result is None:
    result = agent3.run(task)  # fallback
```

---

## Резюме

```
Агенты общаются через:
1. Supervisor (централизованно)
2. Общее хранилище (файлы)
3. Message Bus (асинхронные сообщения)

Правила:
  - Единый формат (JSON Schema)
  - Асинхронность где возможно
  - Timeout на каждый запрос
  - Никаких прямых вызовов между агентами
```

---

## Практическое задание

Реализуй коммуникацию двух агентов через Message Bus:

1. **CoderAgent** — получает описание задачи, пишет код (симулируй возвратом строки вида `"def {task}():\n    pass"`)
2. **ReviewerAgent** — получает код, проверяет его и возвращает `"approved"` или список замечаний
3. **MessageBus** — связывает их асинхронно через очереди
4. CoderAgent отправляет результат ReviewerAgent-у через bus, ReviewerAgent отвечает

Добавь:
- timeout на ожидание ответа (3 секунды)
- fallback: если ReviewerAgent не ответил — вывести `"Review timeout"`
- structured message format: `{type, sender, payload, timestamp}`

Запусти демо с 3 разными задачами.

---

## Проверь себя

1. Какие 3 протокола коммуникации между агентами существуют?
2. Почему асинхронная коммуникация надёжнее синхронной?
3. Зачем нужен единый формат сообщений?
4. Какой anti-pattern нарушает отказоустойчивость?

---

## Ссылки

- Дальше: [[04-multi-agent/03-anti-patterns]]
- Назад: [[04-multi-agent/01-orchestration]]
