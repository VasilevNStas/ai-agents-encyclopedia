---
created: 2026-05-28
tags: [course/data, communication, mcp, a2a, protocols]
status: active
---

# Урок 38: Agent Communication Protocols

> [!quote] Ключевая идея
> AI-агенты — не изолированные существа. Они общаются с другими агентами, инструментами и сервисами. Протокол коммуникации определяет, насколько система будет масштабируемой, отказоустойчивой и расширяемой.

---

## Проблема: агенты должны общаться

Одиночный агент решает ограниченный круг задач. Когда задач становится много — нужна команда агентов.

```
Без протокола:
  Agent_A: "Привет, сделай X"
  Agent_B: "Что такое X? Я жду Y"

С протоколом:
  Agent_A → Bus: {"type": "task", "action": "X", "id": "req-001"}
  Agent_B ← Bus: получает, выполняет, отвечает
  Agent_A ← Bus: {"type": "result", "id": "req-001", "status": "done"}
```

Три уровня коммуникации:

| Уровень | Протокол | Назначение |
|---|---|---|
| Агент → Инструмент | MCP | Вызов внешних инструментов |
| Агент → Агент | A2A | Координация между агентами |
| Агент → Система | Message Bus | Асинхронная очередь событий |

---

## MCP — Model Context Protocol

MCP (Model Context Protocol) — стандарт подключения инструментов к LLM-агентам через JSON-RPC.

### Сервер

```python
import json
import sys
from typing import Any

class MCPRequest:
    def __init__(self, data: dict):
        self.id = data.get("id")
        self.method = data.get("method")
        self.params = data.get("params", {})

    @classmethod
    def from_stdio(cls) -> "MCPRequest":
        line = sys.stdin.readline()
        if not line:
            raise EOFError("stdin closed")
        return cls(json.loads(line))


class MCPResponse:
    def __init__(self, request_id: Any, result: Any = None, error: Any = None):
        self.id = request_id
        self.result = result
        self.error = error

    def to_dict(self) -> dict:
        resp = {"jsonrpc": "2.0", "id": self.id}
        if self.error:
            resp["error"] = self.error
        else:
            resp["result"] = self.result
        return resp


class MCPServer:
    """
    Базовый MCP-сервер.
    Регистрируешь инструменты → сервер слушает stdin → вызывает по имени.
    """
    def __init__(self, name: str, version: str = "1.0.0"):
        self.name = name
        self.version = version
        self._tools: dict[str, callable] = {}

    def tool(self, name: str, description: str = ""):
        """Декоратор для регистрации инструмента."""
        def wrapper(func):
            self._tools[name] = {"fn": func, "desc": description}
            return func
        return wrapper

    def list_tools(self) -> list[dict]:
        return [
            {"name": name, "description": meta["desc"]}
            for name, meta in self._tools.items()
        ]

    def handle(self, req: MCPRequest) -> MCPResponse:
        if req.method == "list_tools":
            return MCPResponse(req.id, result=self.list_tools())

        if req.method == "call_tool":
            tool_name = req.params.get("name")
            tool_args = req.params.get("arguments", {})
            tool = self._tools.get(tool_name)
            if not tool:
                return MCPResponse(
                    req.id,
                    error={"code": -32601, "message": f"Unknown tool: {tool_name}"},
                )
            try:
                result = tool["fn"](**tool_args)
                return MCPResponse(req.id, result=result)
            except Exception as e:
                return MCPResponse(
                    req.id,
                    error={"code": -32000, "message": str(e)},
                )

        return MCPResponse(
            req.id, error={"code": -32601, "message": f"Unknown method: {req.method}"}
        )

    def serve_stdio(self):
        """Бесконечный цикл: читает JSON-RPC из stdin, пишет в stdout."""
        while True:
            try:
                req = MCPRequest.from_stdio()
                resp = self.handle(req)
                print(json.dumps(resp.to_dict()), flush=True)
            except EOFError:
                break
            except Exception as e:
                print(json.dumps({"jsonrpc": "2.0", "error": {"message": str(e)}}))


# Пример сервера с инструментом поиска
server = MCPServer("file-search", version="1.0.0")

@server.tool("search_files", "Поиск файлов по glob-паттерну")
def search_files(pattern: str) -> list[str]:
    import glob
    return glob.glob(pattern, recursive=True)

@server.tool("count_lines", "Подсчёт строк в файле")
def count_lines(path: str) -> int:
    with open(path) as f:
        return len(f.readlines())

# server.serve_stdio()  # раскомментировать для запуска
```

### Клиент

```python
import subprocess
import json

class MCPClient:
    """
    MCP-клиент, который общается с сервером через subprocess (stdio).
    """
    def __init__(self, server_command: list[str]):
        self.proc = subprocess.Popen(
            server_command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
        )
        self._req_id = 0

    def _request(self, method: str, params: dict = None) -> dict:
        self._req_id += 1
        req = {
            "jsonrpc": "2.0",
            "id": self._req_id,
            "method": method,
            "params": params or {},
        }
        line = json.dumps(req) + "\n"
        self.proc.stdin.write(line)
        self.proc.stdin.flush()

        resp_line = self.proc.stdout.readline()
        return json.loads(resp_line)

    def list_tools(self) -> list[dict]:
        resp = self._request("list_tools")
        return resp.get("result", [])

    def call_tool(self, name: str, arguments: dict = None) -> Any:
        resp = self._request("call_tool", {
            "name": name,
            "arguments": arguments or {},
        })
        if "error" in resp:
            raise RuntimeError(f"MCP error: {resp['error']}")
        return resp.get("result")

    def close(self):
        self.proc.terminate()


# Пример использования клиента (сервер должен быть запущен)
# client = MCPClient(["python", "server.py"])
# tools = client.list_tools()
# files = client.call_tool("search_files", {"pattern": "**/*.py"})
# print(files)
# client.close()
```

> [!important]
> MCP — это не библиотека, а **протокол**. Ты можешь реализовать сервер на Python, TypeScript, Go или любом другом языке. Главное — соблюдать JSON-RPC 2.0 и контракт list_tools / call_tool.

---

## A2A — Agent-to-Agent Protocol

A2A (Agent-to-Agent) — протокол Google (2025) для прямой координации между агентами.

```python
from dataclasses import dataclass
from enum import Enum
import uuid
from datetime import datetime

class A2ACardType(Enum):
    TEXT = "text"
    CODE = "code"
    FILE = "file"
    TASK = "task"
    DECISION = "decision"

@dataclass
class A2ACard:
    """Единица информации, которой обмениваются агенты."""
    card_id: str
    sender: str
    recipient: str
    card_type: A2ACardType
    content: str
    parent_id: str = ""
    metadata: dict = None

    def to_dict(self) -> dict:
        return {
            "card_id": self.card_id,
            "sender": self.sender,
            "recipient": self.recipient,
            "card_type": self.card_type.value,
            "content": self.content,
            "parent_id": self.parent_id,
            "metadata": self.metadata or {},
        }


class A2ABroker:
    """
    Брокер A2A-карточек.
    Агенты отправляют карточки брокеру, брокер доставляет их получателям.
    """
    def __init__(self):
        self.agents: dict[str, "A2AAgent"] = {}
        self.history: list[A2ACard] = []

    def register(self, agent: "A2AAgent") -> None:
        self.agents[agent.name] = agent
        agent.broker = self

    def send(self, card: A2ACard) -> None:
        self.history.append(card)
        recipient = self.agents.get(card.recipient)
        if recipient:
            recipient.inbox.append(card)

    def reply(self, original: A2ACard, content: str, card_type: A2ACardType) -> A2ACard:
        reply = A2ACard(
            card_id=str(uuid.uuid4()),
            sender=original.recipient,
            recipient=original.sender,
            card_type=card_type,
            content=content,
            parent_id=original.card_id,
        )
        self.send(reply)
        return reply


class A2AAgent:
    def __init__(self, name: str):
        self.name = name
        self.broker: A2ABroker = None
        self.inbox: list[A2ACard] = []

    def send(self, recipient: str, content: str, card_type: A2ACardType = A2ACardType.TEXT):
        card = A2ACard(
            card_id=str(uuid.uuid4()),
            sender=self.name,
            recipient=recipient,
            card_type=card_type,
            content=content,
        )
        self.broker.send(card)

    def process_inbox(self):
        for card in self.inbox:
            response = self.handle_card(card)
            if response:
                self.broker.reply(card, response, A2ACardType.TEXT)
        self.inbox.clear()

    def handle_card(self, card: A2ACard) -> str:
        raise NotImplementedError


# Пример: два агента обмениваются задачами
class DevAgent(A2AAgent):
    def handle_card(self, card: A2ACard) -> str:
        if card.card_type == A2ACardType.TASK:
            return f"Сделано: {card.content}"
        return f"Получено: {card.content[:50]}..."

class ReviewAgent(A2AAgent):
    def handle_card(self, card: A2ACard) -> str:
        return f"Проверено: {card.content} OK"


broker = A2ABroker()
dev = DevAgent("dev")
review = ReviewAgent("review")
broker.register(dev)
broker.register(review)

dev.send("review", "Проверь этот код", A2ACardType.TASK)
review.process_inbox()  # ответит "Проверено: Проверь этот код OK"
```

---

## Function Calling как протокол

OpenAI/Anthropic function calling — это тоже протокол, только между LLM и кодом:

```python
from typing import get_type_hints

class FunctionRegistry:
    """
    Реестр функций, которые LLM может вызывать.
    Конвертирует Python-функции в OpenAI tool schema.
    """
    def __init__(self):
        self._functions: dict[str, callable] = {}

    def register(self, func: callable):
        sig = get_type_hints(func)
        self._functions[func.__name__] = {
            "fn": func,
            "schema": {
                "type": "function",
                "function": {
                    "name": func.__name__,
                    "description": func.__doc__ or "",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            k: {"type": self._py_to_json(v)}
                            for k, v in sig.items() if k != "return"
                        },
                        "required": [
                            k for k, v in sig.items()
                            if k != "return" and self._is_optional(v) is False
                        ],
                    },
                },
            },
        }

    def _py_to_json(self, typ) -> str:
        mapping = {str: "string", int: "integer", float: "number", bool: "boolean", list: "array", dict: "object"}
        origin = getattr(typ, "__origin__", None)
        if origin is not None:
            return "array" if origin is list else "object"
        return mapping.get(typ, "string")

    def _is_optional(self, typ) -> bool:
        origin = getattr(typ, "__origin__", None)
        return origin is type(None) or (origin is not None and type(None) in typ.__args__)

    def get_tools(self) -> list[dict]:
        return [v["schema"] for v in self._functions.values()]

    def call(self, name: str, arguments: dict) -> Any:
        func = self._functions.get(name)
        if not func:
            raise KeyError(f"Function {name} not found")
        return func["fn"](**arguments)


# Регистрируем функции
registry = FunctionRegistry()

def search_docs(query: str, max_results: int = 5) -> list[str]:
    """Поиск по документации."""
    return [f"doc_{i}.md" for i in range(max_results)]

def send_email(to: str, subject: str, body: str) -> bool:
    """Отправка email."""
    print(f"Sending email to {to}: {subject}")
    return True

registry.register(search_docs)
registry.register(send_email)

# Передаём schema LLM
tools_schema = registry.get_tools()
# LLM возвращает: {"function": "search_docs", "arguments": {"query": "MCP protocol", "max_results": 3}}
# Вызываем:
# result = registry.call("search_docs", {"query": "MCP protocol", "max_results": 3})
```

---

## Message Bus для агентов

Для production-систем нужен не in-memory брокер, а настоящая очередь: RabbitMQ, Kafka, Redis Streams.

```python
import asyncio
import json
import uuid
from datetime import datetime

class AgentMessage:
    def __init__(
        self,
        sender: str,
        receiver: str,
        msg_type: str,
        payload: dict,
        ttl_seconds: int = 60,
    ):
        self.id = str(uuid.uuid4())
        self.sender = sender
        self.receiver = receiver
        self.type = msg_type
        self.payload = payload
        self.timestamp = datetime.utcnow().isoformat()
        self.ttl = ttl_seconds

    def is_expired(self) -> bool:
        created = datetime.fromisoformat(self.timestamp)
        elapsed = (datetime.utcnow() - created).total_seconds()
        return elapsed > self.ttl

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "sender": self.sender,
            "receiver": self.receiver,
            "type": self.type,
            "payload": self.payload,
            "timestamp": self.timestamp,
            "ttl": self.ttl,
        }


class MessageBusAgent:
    """
    Агент, подключённый к message bus.
    В production вместо asyncio.Queue используй aiokafka, aio-pika, redis.
    """
    def __init__(self, name: str):
        self.name = name
        self._queue: asyncio.Queue = asyncio.Queue()

    async def send(self, bus: "MessageBus", receiver: str, msg_type: str, payload: dict):
        msg = AgentMessage(
            sender=self.name,
            receiver=receiver,
            msg_type=msg_type,
            payload=payload,
        )
        await bus.publish(msg)

    async def receive(self) -> AgentMessage:
        msg = await self._queue.get()
        if msg.is_expired():
            return None  # TTL истекло — игнорируем
        return msg

    async def process_loop(self, bus: "MessageBus"):
        while True:
            msg = await self.receive()
            if msg is None:
                continue
            print(f"[{self.name}] Received {msg.type} from {msg.sender}: {msg.payload}")
            await self.on_message(msg)

    async def on_message(self, msg: AgentMessage):
        """Переопредели в наследнике."""
        pass


class MessageBus:
    """
    Асинхронная шина сообщений.
    Каждый агент имеет свою очередь. Сообщение попадает в очередь получателя.
    """
    def __init__(self):
        self._agents: dict[str, asyncio.Queue] = {}

    def register(self, agent: MessageBusAgent):
        self._agents[agent.name] = agent._queue

    async def publish(self, msg: AgentMessage):
        queue = self._agents.get(msg.receiver)
        if queue:
            await queue.put(msg)
        else:
            print(f"[Bus] Unknown receiver: {msg.receiver} (msg dropped)")


# Пример
async def demo():
    bus = MessageBus()

    agent_a = MessageBusAgent("logger")
    agent_b = MessageBusAgent("processor")

    bus.register(agent_a)
    bus.register(agent_b)

    # Отправляем сообщение
    await agent_a.send(bus, "processor", "process_task", {"task": "analyze_logs"})

    # Получаем (в реальности — в process_loop)
    msg = await agent_b.receive()
    if msg:
        print(f"Got: {msg.type} → {msg.payload}")
    # Got: process_task → {'task': 'analyze_logs'}

# asyncio.run(demo())
```

---

## Структура сообщения — стандарт

Любое сообщение между агентами должно содержать:

```json
{
  "id": "msg-001-abc123",
  "sender": "agent-code-reviewer-v2",
  "receiver": "agent-deployer-v1",
  "type": "review_complete",
  "version": "1.0",
  "payload": {
    "task_id": "t-42",
    "status": "approved",
    "findings": []
  },
  "timestamp": "2026-05-28T09:00:00Z",
  "ttl": 300,
  "correlation_id": "session-alpha-7"
}
```

| Поле | Обязательно | Описание |
|---|---|---|
| `id` | Да | Уникальный ID сообщения |
| `sender` | Да | Полное имя агента-отправителя |
| `receiver` | Да | Полное имя агента-получателя |
| `type` | Да | Тип сообщения (перечисление) |
| `version` | Да | Версия схемы сообщения |
| `payload` | Да | Тело сообщения |
| `timestamp` | Да | ISO 8601 |
| `ttl` | Нет | Время жизни в секундах |
| `correlation_id` | Нет | Для трассировки цепочек вызовов |

---

## Anti-patterns

### 1. Синхронное ожидание

```python
# ❌ Блокирующий вызов — агент зависает
result = agent_b.run(task)  # agent_b может упасть или зависнуть

# ✅ Асинхронно с timeout
try:
    result = await asyncio.wait_for(
        agent_b.run(task), timeout=30.0
    )
except asyncio.TimeoutError:
    result = await agent_c.run(task)  # fallback
```

### 2. Потеря сообщений

```python
# ❌ Если получатель offline — сообщение потеряно
bus.send(msg)

# ✅ Подтверждение доставки
class ReliableBus(MessageBus):
    async def publish(self, msg: AgentMessage) -> bool:
        queue = self._agents.get(msg.receiver)
        if queue:
            await queue.put(msg)
            return True
        return False  # caller решает: retry, dead letter, alert
```

### 3. Слишком болтливые агенты

```python
# ❌ Каждое действие → сообщение (шум)
await bus.send("processor", "step_1_start", {})
await bus.send("processor", "step_1_progress_10%", {})
await bus.send("processor", "step_1_progress_20%", {})

# ✅ Агрегированные статусы
await bus.send("processor", "step_complete", {
    "step": 1,
    "duration_ms": 450,
    "result": "ok"
})
```

---

## API Contract Management

MCP, A2A, Message Bus — все протоколы требуют управления контрактами. Без дисциплины контракты ломаются, агенты перестают понимать друг друга.

### Принципы контрактов

1. **Явность** — контракт описан в коде или схеме, а не в головах
2. **Обратная совместимость** — новая версия не ломает старых клиентов
3. **Версионирование** — breaking change = новая мажорная версия
4. **Документация** — каждый метод/сообщение имеет описание и пример

```json
// ❌ Неявный контракт
{"data": [1, 2, 3]}       // что это? ID? координаты? цены?

// ✅ Явный контракт
{
  "type": "user_ids",
  "version": "1.0",
  "data": [1, 2, 3],
  "description": "Список ID пользователей для уведомления"
}
```

### Semantic versioning для контрактов

| Версия | Когда менять | Пример |
|--------|-------------|--------|
| MAJOR | Поля удалены или изменён тип | `user_id: int` → `user_id: string` |
| MINOR | Добавлены новые поля (опциональные) | + `timezone` с default `"UTC"` |
| PATCH | Исправлена документация/описание | Уточнено описание поля |

### Backward compatibility checklist

При изменении контракта:

- [ ] Новые поля опциональны (с default)
- [ ] Старые поля сохранили тип и семантику
- [ ] Версия контракта обновлена
- [ ] Старые клиенты продолжают работать
- [ ] Breaking change документирован в changelog
- [ ] Обновлены тесты на контракт (contract tests)

```python
class ContractValidator:
    """
    Проверяет совместимость новой версии контракта со старой.
    """
    def __init__(self, old_schema: dict, new_schema: dict):
        self.old = old_schema
        self.new = new_schema

    def check_backward_compatibility(self) -> list[str]:
        violations = []
        old_fields = self.old.get("properties", {})
        new_fields = self.new.get("properties", {})

        for field, old_def in old_fields.items():
            if field not in new_fields:
                violations.append(f"FIELD_REMOVED: {field}")
                continue
            new_def = new_fields[field]
            if old_def.get("type") != new_def.get("type"):
                violations.append(f"TYPE_CHANGED: {field} {old_def['type']} → {new_def['type']}")

        return violations

    def report(self) -> str:
        issues = self.check_backward_compatibility()
        if not issues:
            return "✅ Контракт совместим"
        return "❌ Breaking changes:\n" + "\n".join(f"  - {i}" for i in issues)


# Пример
old = {
    "name": "search_request",
    "version": "1.0.0",
    "properties": {
        "query": {"type": "string"},
        "limit": {"type": "integer"},
    }
}
new = {
    "name": "search_request",
    "version": "2.0.0",
    "properties": {
        "query": {"type": "string"},
        "limit": {"type": "integer"},
        "sort_by": {"type": "string"},   # новое поле — OK (MINOR)
    }
}

validator = ContractValidator(old, new)
print(validator.report())
```

---

## Проверь себя

1. Какие три уровня коммуникации агентов выделены в уроке? Чем они отличаются?
2. Как MCP-сервер регистрирует инструменты? Как клиент их вызывает?
3. Чем A2A-протокол отличается от MCP? В каких сценариях нужен каждый?
4. Зачем в структуре сообщения поля `ttl` и `correlation_id`?
5. Какие anti-patterns приводят к потере сообщений?
6. Какие 4 принципа управления контрактами? Что проверяет backward compatibility checklist?

---

## Практическое задание

Реализуй двухагентную систему через Message Bus:

- **Agent-Translator** — получает текст и язык, возвращает перевод (симулируй словарём)
- **Agent-Formatter** — получает переведённый текст, форматирует его (Markdown, uppercase, lowercase по выбору)
- **MessageBus** — связывает их асинхронно
- Пользователь отправляет задание Translator-у, тот передаёт результат Formatter-у, Formatter возвращает финальный ответ

Требования: timeout 5 секунд, structured message, обработка ошибок.

---

## Резюме

```
Протоколы коммуникации для AI-агентов:
- MCP: агент → инструмент (JSON-RPC, stdio/HTTP)
- A2A: агент → агент (карточки Google, брокер)
- Function Calling: LLM → код (OpenAI tool schema)
- Message Bus: асинхронная очередь (Kafka, RabbitMQ, Redis)

Структура сообщения:
  id, sender, receiver, type, version, payload, timestamp, ttl

Управление контрактами:
  - Явность: контракт описан в схеме
  - Обратная совместимость: новые поля опциональны
  - Версионирование: MAJOR (breaking) / MINOR (новое) / PATCH (docs)
  - ContractValidator: автоматическая проверка совместимости

Правила:
  - Асинхронность + timeout
  - Подтверждение доставки (ack)
  - TTL для предотвращения stale messages
  - correlation_id для трассировки
  - Не спамить сообщениями
  - Breaking change = MAJOR релиз
```

---

## Ссылки

- [[07-skills/03-mcp-integration]] — MCP как инструмент расширения
- [[04-multi-agent/02-communication]] — базовая коммуникация агентов
- [[10-data-communication/01-data-engineering]] — данные для тестирования
- [[10-data-communication/03-human-in-the-loop]] — когда агент передаёт управление человеку
- [[05-production/01-guardrails]] — защита от нарушения контрактов