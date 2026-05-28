---
created: 2026-05-28
tags: [course/mcp-deep, mcp, composition, gateway, caching, patterns]
status: active
---

# Урок 18.3: MCP Composition Patterns — Gateway, Caching, Transformer, Router

> [!quote] Ключевая идея
> MCP-серверы редко живут в одиночку. Production-системы строят **сети MCP-серверов** — с gateway, кэшированием, трансформацией и роутингом. Этот уровень архитектуры превращает набор инструментов в платформу.

---

## 1. Зачем нужна композиция MCP

Один MCP-сервер = один источник данных/действий. Когда серверов становится 5, 10, 50 — возникает проблема:

```
Agent → search MCP → database MCP → slack MCP → analytics MCP → storage MCP → ...
```

- Каждый вызов — сетевая задержка
- Нет единого point of control (auth, rate limit)
- Агент должен знать адреса всех серверов
- Обновление сервера = изменение конфигурации агента

**Решение:** композиционные паттерны.

---

## 2. Gateway Pattern

Единая точка входа для всех MCP-запросов. Агент знает только один адрес — gateway.

```
                    ┌──────────────────┐
Agent ──► SSE ──►  │   MCP Gateway    │
                    │                  │
                    │  ┌────────────┐  │
                    │  │  Router    │  │
                    │  └─────┬──────┘  │
                    │        │         │
                    └────────┼─────────┘
                             │
            ┌────────────────┼────────────────┐
            ▼                ▼                ▼
     ┌──────────┐    ┌──────────┐    ┌──────────┐
     │ Search   │    │ Database │    │ Storage  │
     │ MCP      │    │ MCP      │    │ MCP      │
     └──────────┘    └──────────┘    └──────────┘
       (stdio)         (SSE)           (stdio)
```

### 2.1 Реализация Gateway

```python
import json
import asyncio
from typing import Any
from mcp import ClientSession, StdioServerParameters


class MCPGateway:
    """Gateway: единая точка входа к множеству MCP-серверов."""

    def __init__(self):
        self.servers: dict[str, MCPBackend] = {}
        self.tool_registry: dict[str, str] = {}  # tool_name → server_name

    def register_server(self, name: str, backend: "MCPBackend"):
        """Регистрирует backend-сервер."""
        self.servers[name] = backend

    async def initialize(self):
        """Инициализирует все backend-серверы и строит registry."""

        for name, backend in self.servers.items():
            tools = await backend.list_tools()
            for tool in tools:
                if tool.name in self.tool_registry:
                    print(f"[WARN] Tool conflict: {tool.name} in "
                          f"{self.tool_registry[tool.name]} and {name}")
                self.tool_registry[tool.name] = name

        print(f"[Gateway] Registered {len(self.tool_registry)} tools "
              f"from {len(self.servers)} servers")

    async def list_tools(self) -> list[dict]:
        """Возвращает объединённый список инструментов."""

        all_tools = []
        for name, backend in self.servers.items():
            tools = await backend.list_tools()
            for tool in tools:
                tool["server"] = name  # помечаем источник
            all_tools.extend(tools)
        return all_tools

    async def call_tool(self, name: str, arguments: dict) -> dict:
        """Маршрутизирует вызов к нужному backend-серверу."""

        server_name = self.tool_registry.get(name)
        if not server_name:
            return {
                "content": [{"type": "text", "text": f"Tool '{name}' not found"}],
                "isError": True,
            }

        backend = self.servers[server_name]
        return await backend.call_tool(name, arguments)


class MCPBackend:
    """Абстракция backend MCP-сервера."""

    def __init__(self, transport_type: str, params: dict):
        self.transport_type = transport_type
        self.params = params
        self.session: ClientSession | None = None

    async def list_tools(self) -> list[dict]:
        raise NotImplementedError

    async def call_tool(self, name: str, arguments: dict) -> dict:
        raise NotImplementedError


class StdioBackend(MCPBackend):
    """Backend через stdio транспорт."""

    async def connect(self):
        server_params = StdioServerParameters(
            command=self.params["command"],
            args=self.params.get("args", []),
            env=self.params.get("env"),
        )
        # Упрощённо: в реальности через mcp Python SDK
        self.session = await self._create_session(server_params)

    async def list_tools(self) -> list[dict]:
        if not self.session:
            await self.connect()
        result = await self.session.list_tools()
        return [t.model_dump() for t in result.tools]

    async def call_tool(self, name: str, arguments: dict) -> dict:
        if not self.session:
            await self.connect()
        result = await self.session.call_tool(name, arguments)
        return result.model_dump()


class SSEBackend(MCPBackend):
    """Backend через SSE транспорт."""

    async def connect(self):
        url = self.params["url"]
        # Упрощённо: через HTTP-клиент с SSE
        self.session_url = url
        self.session = await self._create_session(url)

    async def list_tools(self) -> list[dict]:
        # GET /tools/list через HTTP
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.session_url}/message",
                json={"method": "tools/list", "params": {}},
            )
            return resp.json().get("result", {}).get("tools", [])

    async def call_tool(self, name: str, arguments: dict) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.session_url}/message",
                json={
                    "method": "tools/call",
                    "params": {"name": name, "arguments": arguments},
                },
            )
            return resp.json().get("result", {})
```

### 2.2 Gateway vs Direct Connection

| Критерий | Direct | Gateway |
|----------|--------|---------|
| Конфигурация агента | Знает все сервера | Знает один gateway |
| Добавление сервера | Менять конфиг агента | Менять конфиг gateway |
| Auth | На каждом сервере | Единая точка |
| Rate limiting | Распределённый | Централизованный |
| Latency | Минимальная | +1 hop |
| Single point of failure | Нет | Gateway |

**Золотое правило:** Gateway для >3 MCP-серверов или когда нужен централизованный контроль.

---

## 3. Router Pattern

Router направляет запросы к разным backend-серверам на основе логики.

### 3.1 Content-based Router

```python
class ContentBasedRouter(MCPGateway):
    """Router: направляет запросы на основе содержимого аргументов."""

    def __init__(self):
        super().__init__()
        self.routes: list[RouteRule] = []

    def add_route(self, rule: "RouteRule"):
        self.routes.append(rule)

    async def call_tool(self, name: str, arguments: dict) -> dict:
        # Проверяем правила маршрутизации
        for rule in self.routes:
            if rule.matches(name, arguments):
                backend = self.servers[rule.target_server]
                # Возможна трансформация аргументов
                transformed_args = rule.transform(arguments)
                return await backend.call_tool(rule.target_tool or name, transformed_args)

        # Default: прямой вызов
        return await super().call_tool(name, arguments)


@dataclass
class RouteRule:
    """Правило маршрутизации."""

    condition: Callable[[str, dict], bool]
    target_server: str
    target_tool: str | None = None
    transform_fn: Callable[[dict], dict] | None = None

    def matches(self, tool_name: str, arguments: dict) -> bool:
        return self.condition(tool_name, arguments)

    def transform(self, arguments: dict) -> dict:
        if self.transform_fn:
            return self.transform_fn(arguments)
        return arguments


# Пример: routing по языку запроса
router = ContentBasedRouter()

router.add_route(RouteRule(
    condition=lambda name, args: args.get("language") == "ru",
    target_server="search-ru",
    target_tool="search",
))

router.add_route(RouteRule(
    condition=lambda name, args: args.get("language") == "en",
    target_server="search-en",
    target_tool="search",
))
```

### 3.2 Model Router (cost optimization)

```python
class ModelRouterMCP:
    """Router: выбирает модель LLM под задачу через MCP."""

    COMPLEXITY_PATTERNS = {
        "high": ["analyze", "compare", "optimize", "refactor", "design"],
        "medium": ["explain", "summarize", "translate", "format"],
        "low": ["search", "list", "get", "ping"],
    }

    MODELS = {
        "high": {"model": "claude-opus-4.7",     "cost_per_call": 0.05},
        "medium": {"model": "claude-sonnet-4.6", "cost_per_call": 0.01},
        "low": {"model": "claude-haiku-4.6",     "cost_per_call": 0.002},
    }

    async def route_call(self, tool_name: str, arguments: dict) -> dict:
        complexity = self._classify(arguments.get("prompt", ""))
        model = self.MODELS[complexity]

        # Вызываем LLM через выбранную модель
        return await self._call_llm(model["model"], arguments)

    def _classify(self, prompt: str) -> str:
        prompt_lower = prompt.lower()

        for pattern in self.COMPLEXITY_PATTERNS["high"]:
            if pattern in prompt_lower:
                return "high"

        for pattern in self.COMPLEXITY_PATTERNS["medium"]:
            if pattern in prompt_lower:
                return "medium"

        return "low"
```

---

## 4. Caching Pattern

Кэширование результатов дорогих инструментов.

```python
import hashlib
import json
import time
from functools import wraps


class MCPCache:
    """Кэш для результатов MCP-вызовов."""

    def __init__(self, backend: "CacheBackend", default_ttl: int = 300):
        self.backend = backend
        self.default_ttl = default_ttl

        # Какие инструменты кэшировать и на сколько
        self.cache_policy: dict[str, int] = {
            "search": 60,           # 60 секунд
            "get_document": 3600,   # 1 час
            "get_weather": 600,     # 10 минут
            "list_files": 30,       # 30 секунд
            "analyze_screenshot": 0, # не кэшировать
        }

    def should_cache(self, tool_name: str) -> bool:
        ttl = self.cache_policy.get(tool_name, -1)
        return ttl > 0

    def get_ttl(self, tool_name: str) -> int:
        return self.cache_policy.get(tool_name, self.default_ttl)

    def make_key(self, tool_name: str, arguments: dict) -> str:
        """Генерирует ключ кэша на основе инструмента и аргументов."""

        canonical = json.dumps(arguments, sort_keys=True)
        raw = f"{tool_name}:{canonical}"
        return hashlib.sha256(raw.encode()).hexdigest()[:32]

    async def get_or_call(self, tool_name: str, arguments: dict, call_fn) -> dict:
        """Возвращает результат из кэша или вызывает инструмент."""

        if not self.should_cache(tool_name):
            return await call_fn(tool_name, arguments)

        key = self.make_key(tool_name, arguments)
        cached = await self.backend.get(key)

        if cached is not None:
            return cached

        result = await call_fn(tool_name, arguments)
        ttl = self.get_ttl(tool_name)
        await self.backend.set(key, result, ttl)
        return result


class RedisCacheBackend:
    """Кэш на Redis."""

    def __init__(self, redis_client):
        self.redis = redis_client
        self.prefix = "mcp:cache:"

    async def get(self, key: str) -> dict | None:
        data = await self.redis.get(f"{self.prefix}{key}")
        if data:
            return json.loads(data)
        return None

    async def set(self, key: str, value: dict, ttl: int):
        await self.redis.setex(
            f"{self.prefix}{key}", ttl, json.dumps(value, default=str)
        )

    async def invalidate(self, pattern: str):
        """Инвалидация по паттерну (например, после записи)."""
        keys = await self.redis.keys(f"{self.prefix}{pattern}*")
        if keys:
            await self.redis.delete(*keys)
```

### Cache invalidation strategies

```python
class CacheAwareGateway(MCPGateway):
    """Gateway с кэшированием и инвалидацией."""

    def __init__(self, cache: MCPCache):
        super().__init__()
        self.cache = cache

        # Инструменты, которые пишут данные
        self.write_tools = {"create", "update", "delete", "upload", "send"}

    async def call_tool(self, name: str, arguments: dict) -> dict:
        # Если это write-инструмент — инвалидируем связанные кэши
        if self._is_write_tool(name):
            result = await super().call_tool(name, arguments)
            await self._invalidate_related(name, arguments)
            return result

        # Для read-инструментов — через кэш
        return await self.cache.get_or_call(
            name, arguments,
            lambda n, a: super().call_tool(n, a),
        )

    def _is_write_tool(self, tool_name: str) -> bool:
        return any(w in tool_name.lower() for w in self.write_tools)

    async def _invalidate_related(self, tool_name: str, arguments: dict):
        """Инвалидирует кэши, связанные с записанными данными."""

        # Например: после update_user → инвалидируем get_user
        if "user" in tool_name:
            await self.cache.backend.invalidate("get_user")
        if "document" in tool_name:
            await self.cache.backend.invalidate("search")
            await self.cache.backend.invalidate("get_document")
```

---

## 5. Transformer Pattern

Сервер, который трансформирует данные между форматами.

```python
class TransformerMCP:
    """Transformer: конвертирует данные между форматами."""

    TOOLS = {
        "markdown_to_html": {
            "description": "Convert Markdown to HTML",
            "input": "text/markdown",
            "output": "text/html",
        },
        "json_to_yaml": {
            "description": "Convert JSON to YAML",
            "input": "application/json",
            "output": "text/yaml",
        },
        "csv_to_json": {
            "description": "Convert CSV to JSON array",
            "input": "text/csv",
            "output": "application/json",
        },
        "translate_text": {
            "description": "Translate text between languages",
            "input": "text/plain",
            "output": "text/plain",
        },
    }

    async def call_tool(self, name: str, arguments: dict) -> dict:
        if name == "markdown_to_html":
            return self._md_to_html(arguments["content"])

        elif name == "json_to_yaml":
            return self._json_to_yaml(arguments["content"])

        elif name == "csv_to_json":
            return self._csv_to_json(arguments["content"])

        elif name == "translate_text":
            return await self._translate(
                arguments["content"],
                arguments.get("source_lang", "auto"),
                arguments["target_lang"],
            )

        return {"error": f"Unknown transformer: {name}"}

    def _md_to_html(self, content: str) -> dict:
        import markdown
        html = markdown.markdown(content, extensions=["fenced_code", "tables"])
        return {"content": [{"type": "text", "text": html}]}

    def _csv_to_json(self, content: str) -> dict:
        import csv, io, json
        reader = csv.DictReader(io.StringIO(content))
        data = list(reader)
        return {"content": [{"type": "text", "text": json.dumps(data, indent=2)}]}

    async def _translate(self, text: str, source: str, target: str) -> dict:
        # Вызов LLM для перевода
        translated = await self.llm.translate(text, source, target)
        return {"content": [{"type": "text", "text": translated}]}
```

### Composition: цепочка трансформеров

```python
class TransformerChain:
    """Цепочка трансформаций: output одного → input другого."""

    def __init__(self, steps: list[dict]):
        self.steps = steps
        # steps = [
        #   {"tool": "csv_to_json", "output_var": "parsed"},
        #   {"tool": "translate_text", "input_var": "parsed", "args": {"target_lang": "en"}},
        # ]

    async def execute(self, initial_input: str) -> dict:
        context = {"input": initial_input}

        for step in self.steps:
            input_value = context.get(step.get("input_var", "input"), initial_input)
            args = {**step.get("args", {}), "content": input_value}

            result = await self._call_mcp(step["tool"], args)
            context[step["output_var"]] = result

        return context
```

---

## 6. Fan-Out Pattern

Один запрос → несколько MCP-серверов параллельно → агрегация.

```python
class FanOutMCP:
    """Fan-out: параллельный вызов нескольких MCP-серверов."""

    async def fan_out_and_aggregate(
        self,
        tool_calls: list[dict],
        timeout: float = 10.0,
    ) -> list[dict]:
        """Вызывает несколько инструментов параллельно и собирает результаты."""

        async def safe_call(call: dict) -> dict:
            try:
                result = await asyncio.wait_for(
                    self.call_tool(call["name"], call.get("arguments", {})),
                    timeout=timeout,
                )
                return {"call": call, "result": result, "error": None}

            except asyncio.TimeoutError:
                return {"call": call, "result": None, "error": "timeout"}

            except Exception as e:
                return {"call": call, "result": None, "error": str(e)}

        tasks = [safe_call(call) for call in tool_calls]
        return await asyncio.gather(*tasks)

    async def research_query(self, query: str) -> dict:
        """Пример: исследование через множественные источники."""

        results = await self.fan_out_and_aggregate([
            {"name": "web_search", "arguments": {"query": query}},
            {"name": "search_docs", "arguments": {"query": query}},
            {"name": "search_code", "arguments": {"query": query}},
        ])

        # Агрегация
        combined = {
            "web": results[0]["result"],
            "docs": results[1]["result"],
            "code": results[2]["result"],
        }

        # Синтез через LLM
        synthesis = await self.llm.generate(
            f"Синтезируй ответ из источников: {json.dumps(combined, indent=2)}"
        )

        return {"sources": combined, "synthesis": synthesis}
```

---

## 7. Anti-Patterns композиции

### 7.1 Cascading Gateway (gateway → gateway)

```
Agent → Gateway A → Gateway B → Server
```

Каждый лишний hop добавляет latency. Если gateway неизбежен — убедись, что он не вызывает другой gateway.

### 7.2 Слепое кэширование

```python
# ❌ Кэшировать всё подряд
cache_policy = {"*": 3600}

# ✅ Только идемпотентные read-инструменты
cache_policy = {
    "search": 60,
    "get_document": 3600,
    # write-инструменты — никогда
    "send_email": 0,
}
```

### 7.3 Synchronous fan-out

```python
# ❌ Последовательные вызовы
r1 = await mcp.call("search", {"q": "a"})
r2 = await mcp.call("search", {"q": "b"})
r3 = await mcp.call("search", {"q": "c"})

# ✅ Параллельные
r1, r2, r3 = await asyncio.gather(
    mcp.call("search", {"q": "a"}),
    mcp.call("search", {"q": "b"}),
    mcp.call("search", {"q": "c"}),
)
```

---

## Резюме

```
Паттерны композиции MCP:

Gateway     — единая точка входа, объединённый tool registry
Router      — маршрутизация по контенту / стоимости / модели
Cache       — кэш результатов (Redis), инвалидация по записи
Transformer — конвертация форматов, цепочки трансформаций
Fan-out     — параллельные вызовы, агрегация результатов

Правила:
  1. Gateway для >3 серверов
  2. Кэшировать только read-инструменты
  3. Fan-out через asyncio.gather
  4. Transformer в цепочках через артефакты
```

---

## Практическое задание

1. Реализуй Gateway для трёх MCP-серверов: search (stdio), database (SSE), storage (stdio).

2. Добавь Content-based Router: запросы на русском → search-ru, на английском → search-en.

3. Реализуй Redis-кэш для search-инструмента с TTL 60 секунд и инвалидацией при вызове update.

4. Напиши Fan-out для параллельного поиска по трём источникам с агрегацией через LLM.

---

## Проверь себя

1. В чём разница между Gateway и Router?
2. Когда Gateway становится single point of failure?
3. Почему нельзя кэшировать write-инструменты?
4. Какой паттерн использовать для параллельного вызова 5 MCP-серверов?
5. Что такое Transformer Chain и зачем он нужен?
6. Какой anti-pattern композиции самый опасный?

---

## Ссылки

- [[01-server-patterns]] — транспорт и жизненный цикл
- [[02-security-production]] — безопасность
- [[04-building-servers]] — следующий урок: создание MCP-серверов
- [[../../../04-multi-agent/01-orchestration]] — параллельные паттерны в мультиагентных системах
