---
created: 2026-05-28
tags: [course/mcp-deep, mcp, server, patterns, transport, architect]
status: active
---

# Урок 18.1: MCP Server Patterns — транспорт, жизненный цикл, архитектура

> [!quote] Ключевая идея
> MCP-сервер — это не просто «обёртка над API». От выбора транспорта, модели жизненного цикла и паттерна соединения зависит надёжность, безопасность и стоимость всей системы агента.

---

## 1. Зачем нужен глубокий разбор MCP

Первый модуль MCP ([[../../../07-skills/03-mcp-integration|Урок 27]] и [[../../../prompt-engineering/06-mcp/06-mcp|PE: Модуль 6]]) даёт базовое понимание. Но production-архитектору нужно знать:

- Какой транспорт когда выбирать
- Как сервер управляет соединениями
- Как масштабировать MCP-инфраструктуру
- Как тестировать и мониторить

Этот модуль закрывает эти вопросы.

---

## 2. Транспорт: глубокое сравнение

MCP определяет два транспорта: **stdio** и **SSE** (Server-Sent Events). Разница не только в том, локальный или удалённый сервер.

### 2.1 stdio — локальный процесс

```
[Host Process]
    |
    | spawn (fork/exec)
    |
[MCP Server Subprocess]
    stdin  → JSON-RPC requests
    stdout ← JSON-RPC responses + notifications
    stderr → логи (не участвует в протоколе)
```

**Как работает:**
```
Host → [init] → {"jsonrpc":"2.0","method":"initialize","params":{...,"protocolVersion":"2025-03-26"}}
Host → [tools/list]
Server → [tools/list] → {"jsonrpc":"2.0","id":2,"result":{"tools":[...]}}
Host → [tools/call] → {"jsonrpc":"2.0","method":"tools/call","params":{"name":"search","arguments":{...}}}
Server → [tools/call result] → {"jsonrpc":"2.0","id":3,"result":{"content":[...]}}
```

**Плюсы:**
- Максимальная безопасность (изоляция процесса, нет сети)
- Нет latency сети (IPC через pipe)
- Простая конфигурация (нет портов, TLS)
- Естественная изоляция ресурсов (каждый сервер — отдельный процесс с ulimit)

**Минусы:**
- Живёт только пока жив host (перезапуск агента = перезапуск сервера)
- Не масштабируется горизонтально
- Нет sharing между несколькими host-ами
- Потребление памяти: каждый сервер — отдельный процесс

**Когда выбирать:**
- Локальные агенты (CLI, IDE)
- Инструменты с доступом к локальной файловой системе
- Разработка и отладка MCP-серверов
- Single-tenant десктопные приложения

**Production warning:** stdio НЕ подходит для multi-tenant серверных архитектур. Каждый пользователь/сессия будет порождать свой процесс.

### 2.2 SSE — удалённый сервер

```
[Host Process]                     [MCP Server]
    |                                    |
    |── HTTP POST /session (connect) ──→ |
    |←─ SSE stream (events) ←────────────|
    |── HTTP POST /message (request) ──→ |
    |←─ SSE event (response) ←───────────|
```

**Как работает:**
```python
# 1. Host устанавливает SSE-соединение
POST /session HTTP/1.1
→ {"sessionId": "sess_abc123"}

# 2. Сервер отправляет события через SSE
GET /sessions/sess_abc123/messages HTTP/1.1
Accept: text/event-stream

→ event: message
  data: {"jsonrpc":"2.0","id":1,"result":{"tools":[...]}}

# 3. Host отправляет запросы через POST
POST /sessions/sess_abc123/message HTTP/1.1
Content-Type: application/json

→ {"jsonrpc":"2.0","method":"tools/call","id":2,"params":{...}}

# 4. Ответ приходит через SSE
→ event: message
  data: {"jsonrpc":"2.0","id":2,"result":{...}}
```

**Плюсы:**
- Удалённый доступ, централизованное управление
- Масштабирование (один сервер — много host-ов)
- Постоянная работа (не зависит от host-процесса)
- Можно обновлять без перезапуска агентов

**Минусы:**
- Сложнее в настройке (TLS, аутентификация)
- Сетевая latency (2-50ms в дата-центре, 50-300ms через интернет)
- SSE — односторонний протокол (сервер → клиент), для двусторонней связи нужен дополнительный HTTP POST

**Когда выбирать:**
- Multi-tenant production-системы
- Инструменты, разделяемые между командами
- Централизованные базы знаний и API
- Когда сервер должен жить независимо от агента

### 2.3 Практическое правило выбора

```python
def choose_transport(requirements: dict) -> str:
    """Выбор транспорта по требованиям."""
    
    if requirements.get("multi_tenant"):
        return "sse"  # иначе N процессов
    
    if requirements.get("network_access"):
        return "sse"  # stdio не поддерживает сеть
    
    if requirements.get("shared_state"):
        return "sse"  # иначе каждый host имеет свою копию состояния
    
    local_latency_ms = requirements.get("max_latency_ms", 100)
    if local_latency_ms < 10:
        return "stdio"  # SSE добавит минимум 1-5ms
    
    return "sse"  # универсальный выбор
```

---

## 3. Жизненный цикл MCP-сервера

```
ФАЗЫ ЖИЗНИ СЕРВЕРА:

[INIT] → initialization handshake
  │
  ▼
[READY] → обработка запросов
  │
  ├──→ [RECONNECTING] → при разрыве соединения
  │       │
  │       ▼
  │     [READY]
  │
  └──→ [SHUTDOWN] → graceful shutdown
```

### 3.1 Initialization Handshake

Каждое соединение начинается с handshake, где согласуются протокол, capabilities и версии:

```python
# INIT запрос
{
    "jsonrpc": "2.0",
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-03-26",
        "capabilities": {
            "roots": {"listChanged": True},
            "sampling": {}
        },
        "clientInfo": {
            "name": "opencode",
            "version": "1.0.0"
        }
    }
}

# INIT ответ
{
    "jsonrpc": "2.0",
    "result": {
        "protocolVersion": "2025-03-26",
        "capabilities": {
            "tools": {},        # сервер предоставляет инструменты
            "resources": {},    # сервер предоставляет ресурсы
            "prompts": {},      # сервер предоставляет промпты
            "logging": {}       # поддержка логирования
        },
        "serverInfo": {
            "name": "custom-search-server",
            "version": "0.2.0"
        }
    }
}
```

После INIT host отправляет `notifications/initialized` — и сервер переходит в READY.

### 3.2 Graceful Shutdown

```python
import signal
import asyncio
from mcp.server import Server


class GracefulMCPServer:
    """MCP-сервер с graceful shutdown."""

    def __init__(self, server: Server):
        self.server = server
        self._shutdown_requested = False
        self._active_requests: set[asyncio.Task] = set()

    def register_signal_handlers(self):
        signal.signal(signal.SIGTERM, self._handle_sigterm)
        signal.signal(signal.SIGINT, self._handle_sigterm)

    def _handle_sigterm(self, signum, frame):
        if not self._shutdown_requested:
            self._shutdown_requested = True
            asyncio.create_task(self._shutdown())

    async def _shutdown(self):
        """Graceful shutdown: завершаем активные запросы."""

        # 1. Отправляем notification клиентам
        await self.server.send_notification(
            "server/shutdown",
            {"reason": "maintenance", "grace_period_seconds": 10}
        )

        # 2. Ждём активные запросы (с таймаутом)
        if self._active_requests:
            timeout = 10.0  # 10 секунд на завершение
            done, pending = await asyncio.wait(
                self._active_requests,
                timeout=timeout,
            )
            for task in pending:
                task.cancel()

        # 3. Сохраняем состояние
        await self._persist_state()

        # 4. Закрываем соединения
        await self.server.close()

    async def execute_request(self, request):
        """Обёртка для отслеживания активных запросов."""
        task = asyncio.create_task(self._handle(request))
        self._active_requests.add(task)
        try:
            return await task
        finally:
            self._active_requests.discard(task)
```

---

## 4. Stateless vs Stateful MCP-серверы

Критический architectural decision, который влияет на масштабирование, надёжность и сложность.

### 4.1 Stateless

Сервер не хранит состояние между запросами. Каждый вызов самодостаточен:

```python
class StatelessSearchServer:
    """Stateless: нет состояния между вызовами."""

    async def handle_tool_call(self, name: str, arguments: dict) -> list:
        if name == "search":
            return await self._search(arguments["query"])
        elif name == "get_document":
            return await self._get_document(arguments["id"])
        # Нет зависимости от предыдущих вызовов

    async def _search(self, query: str) -> list:
        # Каждый вызов —独立的 запрос к ES
        return await self.elasticsearch.search(query)
```

**Плюсы:**
- Горизонтальное масштабирование (любой экземпляр обработает любой запрос)
- Простая балансировка (round-robin)
- Простое восстановление после сбоя (новый экземпляр = то же поведение)
- Идеально для serverless (AWS Lambda, GCP Cloud Functions)

**Минусы:**
- Каждый запрос платит за «разогрев» (подключение к БД, авторизация)
- Невозможно организовать long-running операции

### 4.2 Stateful

Сервер хранит контекст между вызовами:

```python
class StatefulSessionServer:
    """Stateful: поддерживает сессии пользователей."""

    def __init__(self):
        self.sessions: dict[str, SessionState] = {}

    async def handle_tool_call(self, name: str, arguments: dict, session_id: str):
        if name == "init_search":
            # Создаёт сессию поиска
            self.sessions[session_id] = SearchSession(
                query=arguments["query"],
                filters=arguments.get("filters", {}),
                page=0,
                results=[],
            )
            return {"session_id": session_id}

        elif name == "next_page":
            # Продолжает существующую сессию
            session = self.sessions.get(session_id)
            if not session:
                return {"error": "session_not_found"}
            session.page += 1
            return await self._fetch_page(session)

        elif name == "refine_query":
            session = self.sessions.get(session_id)
            session.filters.update(arguments.get("filters", {}))
            session.page = 0
            return await self._fetch_page(session)
```

**Плюсы:**
- Поддержка multi-step workflow
- Экономия на повторных вычислениях
- Возможность отменять/продолжать операции

**Минусы:**
- Сложное масштабирование (sticky sessions или distributed cache)
- Более сложное восстановление после сбоя
- Потребление памяти

### 4.3 Decision Matrix

| Критерий | Stateless | Stateful |
|----------|-----------|----------|
| Масштабирование | Простое (K8s HPA) | Сложное (sticky + distributed cache) |
| Serverless | ✅ Идеально | ❌ Сложно |
| Multi-step workflow | ❌ Через host | ✅ Есть |
| Память | Минимум | O(сессии) |
| Отказоустойчивость | Высокая (reset = ок) | Средняя (потеря сессии) |
| Примеры | search, calculator, translation | code review, data analysis, RAG |

---

## 5. Reconnection Strategies

SSE-соединения могут обрываться. Клиент должен уметь переподключаться.

### 5.1 Exponential Backoff

```python
import asyncio
import random


class MCPReconnector:
    """Переподключение с exponential backoff + jitter."""

    def __init__(self, base_delay: float = 1.0, max_delay: float = 60.0):
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.attempt = 0

    async def connect_with_retry(self, connect_fn, is_connected_fn):
        """Подключается с retry при обрыве."""

        while True:
            try:
                await connect_fn()
                self.attempt = 0  # сброс после успеха

                # Ждём обрыва
                while is_connected_fn():
                    await asyncio.sleep(0.1)

            except (ConnectionError, TimeoutError) as e:
                delay = self._next_delay()
                print(f"[MCP] Connection lost: {e}. Reconnecting in {delay:.1f}s...")
                await asyncio.sleep(delay)

    def _next_delay(self) -> float:
        self.attempt += 1
        delay = min(self.base_delay * (2 ** (self.attempt - 1)), self.max_delay)
        # jitter: ±25%
        jitter = random.uniform(0.75, 1.25)
        return delay * jitter
```

### 5.2 State Recovery

После переподключения stateful-сервер должен восстановить сессии:

```python
class StatefulMCPWithRecovery(StatefulSessionServer):
    """Восстановление состояния после reconnect."""

    def __init__(self, redis_client):
        super().__init__()
        self.redis = redis_client
        self._recovery_in_progress = False

    async def handle_reconnect(self, client_id: str):
        """Восстановление сессий после переподключения."""

        if self._recovery_in_progress:
            return {"status": "recovery_in_progress"}

        self._recovery_in_progress = True
        try:
            # 1. Загружаем сессии из Redis
            saved_sessions = await self.redis.hgetall(f"sessions:{client_id}")

            # 2. Восстанавливаем в памяти
            for session_id, serialized in saved_sessions.items():
                self.sessions[session_id] = SessionState.deserialize(serialized)

            # 3. Уведомляем host о состоянии
            return {
                "status": "recovered",
                "session_count": len(saved_sessions),
                "sessions": list(saved_sessions.keys()),
            }

        finally:
            self._recovery_in_progress = False

    async def persist_periodically(self, interval: int = 30):
        """Периодическое сохранение состояния в Redis."""

        while True:
            await asyncio.sleep(interval)
            for client_id, sessions in self._group_by_client().items():
                pipe = self.redis.pipeline()
                for session_id, state in sessions.items():
                    pipe.hset(
                        f"sessions:{client_id}",
                        session_id,
                        state.serialize(),
                    )
                await pipe.execute()
```

---

## 6. Connection Pooling для SSE

Когда один host использует несколько MCP-серверов, наивное управление соединениями приводит к проблемам.

```python
class MCPConnectionPool:
    """Пул соединений к MCP-серверам."""

    def __init__(self, max_connections_per_server: int = 4):
        self.pools: dict[str, asyncio.Queue] = {}
        self.max_per_server = max_connections_per_server

    async def get_connection(self, server_url: str) -> "MCPConnection":
        """Получить соединение из пула (или создать новое)."""

        if server_url not in self.pools:
            self.pools[server_url] = asyncio.Queue()

        pool = self.pools[server_url]

        if not pool.empty():
            return await pool.get()

        if self._active_count(server_url) < self.max_per_server:
            conn = await self._create_connection(server_url)
            return conn

        # Все соединения заняты — ждём
        return await pool.get()

    async def release_connection(self, server_url: str, conn: "MCPConnection"):
        """Вернуть соединение в пул."""

        if conn.is_healthy():
            await self.pools[server_url].put(conn)
        else:
            await conn.close()

    async def health_check_loop(self, interval: int = 30):
        """Периодическая проверка здоровья соединений."""

        while True:
            await asyncio.sleep(interval)
            for server_url, pool in self.pools.items():
                healthy = []
                while not pool.empty():
                    conn = await pool.get()
                    if conn.is_healthy():
                        healthy.append(conn)
                    else:
                        await conn.close()
                for conn in healthy:
                    await pool.put(conn)

    def _active_count(self, server_url: str) -> int:
        return self.pools[server_url].qsize()
```

---

## 7. JSON-RPC over MCP: подводные камни

MCP использует JSON-RPC 2.0, но с важными нюансами:

### Batch Requests не поддерживаются

```python
# ❌ JSON-RPC batch — НЕ работает в MCP
[
    {"jsonrpc":"2.0","method":"tools/call","id":1,"params":{...}},
    {"jsonrpc":"2.0","method":"tools/call","id":2,"params":{...}}
]

# ✅ Только последовательные запросы
{"jsonrpc":"2.0","method":"tools/call","id":1,"params":{...}}
# ждём ответ
{"jsonrpc":"2.0","method":"tools/call","id":2,"params":{...}}
```

### Notifications (id == null)

Уведомления не требуют ответа — host отправляет их без ID:

```python
# Notification: без id, без ответа
{
    "jsonrpc": "2.0",
    "method": "notifications/initialized",
    "params": {}
}

# Сервер также может отправлять уведомления:
{
    "jsonrpc": "2.0",
    "method": "notifications/tools/list_changed",
    "params": {}
}
```

### Progress tracking

Для долгих операций MCP поддерживает прогресс через `progressToken`:

```python
# Запрос с прогрессом
{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "id": 5,
    "params": {
        "name": "analyze_large_dataset",
        "arguments": {"dataset": "sales_2025.csv"},
        "meta": {
            "progressToken": 42  # host хочет получать прогресс
        }
    }
}

# Сервер отправляет прогресс
{
    "jsonrpc": "2.0",
    "method": "notifications/progress",
    "params": {
        "progressToken": 42,
        "progress": 0.3,         # 30%
        "message": "Processing 3000/10000 rows"
    }
}

# Финальный ответ
{
    "jsonrpc": "2.0",
    "id": 5,
    "result": {
        "content": [...],
        "meta": {
            "duration_ms": 12345,
            "rows_processed": 10000
        }
    }
}
```

### Timeout tracking

MCP не определяет timeout на уровне протокола — это ответственность host-а:

```python
class MCPRequestWithTimeout:
    """Запрос к MCP-серверу с таймаутом."""

    DEFAULT_TIMEOUTS = {
        "initialize": 10.0,
        "tools/list": 5.0,
        "resources/list": 5.0,
        "tools/call": 30.0,    # вызов инструмента — до 30s
        "resources/read": 30.0,
    }

    async def call_with_timeout(
        self, method: str, params: dict, timeout: float | None = None
    ) -> dict:
        timeout = timeout or self.DEFAULT_TIMEOUTS.get(method, 30.0)

        try:
            result = await asyncio.wait_for(
                self._send_request(method, params),
                timeout=timeout,
            )
            return result

        except asyncio.TimeoutError:
            # Логируем и пробрасываем
            raise MCPTimeoutError(
                f"MCP request {method} timed out after {timeout}s"
            )
```

---

## Резюме

```
Транспорт:
  stdio — локально, безопасно, но не масштабируется
  SSE   — удалённо, масштабируется, но сложнее

Жизненный цикл:
  INIT → READY → ... → SHUTDOWN (graceful)

Stateless vs Stateful:
  stateless — масштабируется, serverless-ready, но без контекста
  stateful  — контекст есть, но сложнее infra

Reconnection:
  exponential backoff + jitter + state recovery

Connection Pooling:
  пул соединений на сервер, health check, reuse
```

---

## Практическое задание

1. Напиши MCP-сервер на stdio транспорте с двумя инструментами: `add(a, b)` и `multiply(a, b)`. Запусти и проверь через любой MCP-клиент.

2. Перепиши тот же сервер на SSE транспорт. В чём разница в запуске?

3. Добавь graceful shutdown: сервер должен завершать активные запросы перед выходом.

4. Реализуй reconnection strategy для SSE-клиента с exponential backoff.

---

## Проверь себя

1. Чем отличается stdio транспорт от SSE? Когда что выбирать?
2. Какие фазы проходит MCP-сервер за время жизни?
3. Почему stateless сервер проще масштабировать?
4. Что такое progressToken и зачем он нужен?
5. Как работает reconnection в SSE? Что такое jitter?
6. Почему JSON-RPC batch не поддерживается в MCP?

---

## Ссылки

- [[../../../07-skills/03-mcp-integration]] — основы MCP
- [[../../../prompt-engineering/06-mcp/06-mcp]] — MCP в курсе PE
- [[02-security-production]] — следующий урок: безопасность
- [MCP Specification — Transport](https://spec.modelcontextprotocol.io)
