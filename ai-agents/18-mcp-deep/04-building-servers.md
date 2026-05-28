---
created: 2026-05-28
tags: [course/mcp-deep, mcp, python-sdk, node-sdk, building, architect]
status: active
---

# Урок 18.4: Building MCP Servers — Python SDK, Node SDK, CI/CD

> [!quote] Ключевая идея
> MCP-серверы можно писать на любом языке, но официальные SDK (Python и TypeScript) дают правильные абстракции: server lifecycle, transport management, schema validation. Разберём оба SDK, сравним подходы, напишем production-сервер.

---

## 1. MCP Python SDK

### 1.1 Установка и базовый сервер

```bash
pip install mcp
```

Минимальный сервер:

```python
# server.py
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent


# 1. Создаём экземпляр сервера
server = Server("math-tools")


# 2. Регистрируем инструменты
@server.tool()
async def add(a: int, b: int) -> list[TextContent]:
    """Add two numbers together."""
    result = a + b
    return [TextContent(type="text", text=str(result))]


@server.tool()
async def multiply(a: int, b: int) -> list[TextContent]:
    """Multiply two numbers."""
    result = a * b
    return [TextContent(type="text", text=str(result))]


@server.tool()
async def calculator(expression: str) -> list[TextContent]:
    """Evaluate a mathematical expression. Use with caution."""
    try:
        import ast, operator

        allowed_ops = {
            ast.Add: operator.add, ast.Sub: operator.sub,
            ast.Mult: operator.mul, ast.Div: operator.truediv,
        }

        def eval_expr(node):
            if isinstance(node, ast.Constant):
                return node.value
            elif isinstance(node, ast.BinOp):
                return allowed_ops[type(node.op)](
                    eval_expr(node.left), eval_expr(node.right)
                )
            else:
                raise ValueError(f"Unsupported: {type(node).__name__}")

        result = eval_expr(ast.parse(expression, mode="eval").body)
        return [TextContent(type="text", text=str(result))]

    except Exception as e:
        return [TextContent(type="text", text=f"Error: {e}")]


# 3. Запуск
if __name__ == "__main__":
    import asyncio
    asyncio.run(stdio_server(server))
```

**Как это работает под капотом:**

```python
# Декоратор @server.tool() делает три вещи:
# 1. Регистрирует функцию в tool registry сервера
# 2. Генерирует JSON Schema из type hints (int → {"type": "integer"})
# 3. Добавляет docstring как description инструмента

# Это эквивалентно ручной регистрации:
server.set_tool(
    Tool(
        name="add",
        description="Add two numbers together.",
        inputSchema={
            "type": "object",
            "properties": {
                "a": {"type": "integer"},
                "b": {"type": "integer"},
            },
            "required": ["a", "b"],
        },
    ),
    handler=add,
)
```

### 1.2 Python SDK: Resources и Prompts

```python
from mcp.types import Resource, ResourceTemplate


# Resources — данные, которые LLM может читать
@server.resource("docs://{path}")
async def get_documentation(path: str) -> str:
    """Serve documentation files."""
    safe_path = path.replace("..", "").lstrip("/")
    try:
        content = await read_file(f"/docs/{safe_path}")
        return content
    except FileNotFoundError:
        return f"Documentation '{path}' not found."


# Resource templates — динамические URI
server.add_resource_template(
    ResourceTemplate(
        uriTemplate="data://reports/{year}/{month}",
        name="Monthly Reports",
        mimeType="text/markdown",
    )
)


# Prompts — шаблоны промтов
@server.prompt()
async def code_review_prompt(language: str, code: str) -> str:
    """Create a code review prompt."""
    return f"""Review this {language} code:

```{language}
{code}
```

Check for:
1. Security vulnerabilities
2. Performance issues
3. Code style
4. Error handling
"""
```

### 1.3 Python SDK: Lifecycle hooks

```python
from mcp.server.lifecycle import ServerLifecycle


class CustomLifecycle(ServerLifecycle):
    """Кастомный lifecycle с инициализацией и очисткой."""

    async def on_initialize(self, client_capabilities: dict) -> dict:
        """Вызывается при handshake с клиентом."""
        print(f"[Lifecycle] Client connected: {client_capabilities}")
        await self._connect_database()
        await self._load_models()
        return {
            "server_version": "2.0.0",
            "capabilities": {
                "tools": {},
                "resources": {},
                "logging": {},
            },
        }

    async def on_shutdown(self):
        """Вызывается при отключении клиента."""
        print("[Lifecycle] Client disconnected. Cleaning up...")
        await self._close_database()
        await self._save_cache()

    async def _connect_database(self):
        # Подключение к БД при старте
        pass

    async def _close_database(self):
        # Закрытие соединений
        pass


# Подключение кастомного lifecycle
server.lifecycle = CustomLifecycle()
```

### 1.4 Python SDK: Error handling

```python
from mcp.server.exceptions import (
    ToolError,
    ResourceError,
    InvalidParams,
)


@server.tool()
async def query_database(sql: str) -> list[TextContent]:
    """Execute a read-only SQL query."""

    # Валидация
    if not sql.strip().upper().startswith("SELECT"):
        raise InvalidParams("Only SELECT queries are allowed")

    try:
        result = await database.execute(sql)
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    except DatabaseConnectionError as e:
        # Специфичная ошибка
        raise ToolError(f"Database unavailable: {e}")

    except Exception as e:
        # Неожиданная ошибка — логируем и возвращаем безопасное сообщение
        log.error(f"Query failed: {e}", exc_info=True)
        raise ToolError("Query execution failed. Check logs.")
```

---

## 2. MCP TypeScript SDK

### 2.1 Установка и базовый сервер

```bash
npm install @modelcontextprotocol/sdk
```

Минимальный сервер:

```typescript
// server.ts
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
  Tool,
} from "@modelcontextprotocol/sdk/types.js";

// 1. Создаём сервер
const server = new Server(
  {
    name: "math-tools",
    version: "1.0.0",
  },
  {
    capabilities: { tools: {} },
  }
);

// 2. Регистрируем инструменты
server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [
    {
      name: "add",
      description: "Add two numbers",
      inputSchema: {
        type: "object",
        properties: {
          a: { type: "number" },
          b: { type: "number" },
        },
        required: ["a", "b"],
      },
    } as Tool,
  ],
}));

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  switch (name) {
    case "add": {
      const result = (args as { a: number; b: number }).a +
                      (args as { a: number; b: number }).b;
      return {
        content: [{ type: "text", text: String(result) }],
      };
    }

    default:
      throw new Error(`Unknown tool: ${name}`);
  }
});

// 3. Запуск
const transport = new StdioServerTransport();
await server.connect(transport);
```

### 2.2 TypeScript SDK: Streamable HTTP

TypeScript SDK поддерживает Streamable HTTP — улучшение над SSE:

```typescript
import { StreamableHTTPServerTransport } from
  "@modelcontextprotocol/sdk/server/streamableHttp.js";

// Streamable HTTP позволяет:
// - Отправлять частичные результаты по мере готовности
// - Отменять долгие запросы
// - Работать через стандартные HTTP load balancer

const transport = new StreamableHTTPServerTransport({
  endpoint: "/mcp",
  sessionTimeout: 300000,  // 5 минут
});

// Запуск через Express/Fastify
app.use("/mcp", transport.expressMiddleware());
```

### 2.3 Python vs TypeScript SDK: сравнение

| Критерий | Python SDK | TypeScript SDK |
|----------|------------|----------------|
| Декларативность | Декораторы (`@server.tool()`) | Ручные handlers (`setRequestHandler`) |
| Schema generation | Из type hints (авто) | Ручная (`inputSchema`) |
| Resources | `@server.resource()` | `ListResourcesRequestSchema` |
| Prompts | `@server.prompt()` | `ListPromptsRequestSchema` |
| Streaming | Через progressToken | Streamable HTTP (built-in) |
| Lifecycle | Lifecycle hooks | События (connect, close) |
| stdio | `stdio_server(server)` | `StdioServerTransport` |
| SSE | `sse_server()` | `SSEServerTransport` |

**Выбор:**
- Python — быстрый прототип, data science, ML-инструменты
- TypeScript — web-экосистема, streaming, serverless (Vercel, CloudFlare)

---

## 3. Testing MCP-серверов

### 3.1 Unit-тесты

```python
# test_math_server.py
import pytest
from mcp.testing import McpTestClient


@pytest.fixture
async def client():
    """Создаёт тестовый клиент для MCP-сервера."""
    from server import server
    async with McpTestClient(server) as test_client:
        yield test_client


@pytest.mark.asyncio
async def test_add(client):
    result = await client.call_tool("add", {"a": 2, "b": 3})
    assert result.content[0].text == "5"


@pytest.mark.asyncio
async def test_add_negative(client):
    result = await client.call_tool("add", {"a": -1, "b": 1})
    assert result.content[0].text == "0"


@pytest.mark.asyncio
async def test_add_large_numbers(client):
    result = await client.call_tool("add", {
        "a": 10**9, "b": 10**9
    })
    assert result.content[0].text == str(2 * 10**9)


@pytest.mark.asyncio
async def test_multiply(client):
    result = await client.call_tool("multiply", {"a": 4, "b": 5})
    assert result.content[0].text == "20"


@pytest.mark.asyncio
async def test_unknown_tool(client):
    with pytest.raises(Exception, match="not found"):
        await client.call_tool("unknown", {})
```

### 3.2 Integration-тесты

```python
# test_integration.py
import subprocess
import json
import time
import httpx


class MCPProcessManager:
    """Управление MCP-сервером как процессом для тестов."""

    def __init__(self, command: list[str]):
        self.command = command
        self.process = None

    def start(self):
        self.process = subprocess.Popen(
            self.command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        time.sleep(0.5)  # ждём инициализацию

    def stop(self):
        if self.process:
            self.process.terminate()
            self.process.wait(timeout=5)

    def send_request(self, method: str, params: dict) -> dict:
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params,
        }
        self.process.stdin.write(
            json.dumps(request).encode() + b"\n"
        )
        self.process.stdin.flush()
        response = self.process.stdout.readline()
        return json.loads(response)


def test_server_via_stdio():
    """Integration test через stdio."""
    manager = MCPProcessManager(["python", "server.py"])
    manager.start()

    try:
        # Initialize
        result = manager.send_request("initialize", {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "test", "version": "1.0"},
        })
        assert "result" in result

        # List tools
        result = manager.send_request("tools/list", {})
        tools = result["result"]["tools"]
        assert any(t["name"] == "add" for t in tools)

        # Call tool
        result = manager.send_request("tools/call", {
            "name": "add",
            "arguments": {"a": 2, "b": 3},
        })
        assert result["result"]["content"][0]["text"] == "5"

    finally:
        manager.stop()


@pytest.mark.asyncio
async def test_server_via_sse():
    """Integration test через SSE."""
    # Запускаем SSE-сервер
    proc = await asyncio.create_subprocess_exec(
        "python", "sse_server.py",
        stdout=asyncio.subprocess.PIPE,
    )
    await asyncio.sleep(1)

    try:
        async with httpx.AsyncClient() as client:
            # Connect SSE session
            sess_resp = await client.post("http://localhost:8000/session")
            session_id = sess_resp.json()["sessionId"]

            # Call tool
            resp = await client.post(
                f"http://localhost:8000/sessions/{session_id}/message",
                json={
                    "method": "tools/call",
                    "params": {"name": "add", "arguments": {"a": 2, "b": 3}},
                },
            )
            data = resp.json()
            assert data["result"]["content"][0]["text"] == "5"

    finally:
        proc.terminate()
```

### 3.3 Load testing

```python
# load_test.py
import asyncio
import time
from statistics import mean, median, pstdev


class MCPLoadTester:
    """Load test для MCP-сервера."""

    def __init__(self, tool_name: str, args_fn, concurrency: int = 10):
        self.tool = tool_name
        self.args_fn = args_fn
        self.concurrency = concurrency
        self.latencies: list[float] = []
        self.errors: int = 0

    async def run(self, iterations: int = 100):
        semaphore = asyncio.Semaphore(self.concurrency)

        async def single_request():
            async with semaphore:
                start = time.monotonic()
                try:
                    await client.call_tool(self.tool, self.args_fn())
                    latency = (time.monotonic() - start) * 1000
                    self.latencies.append(latency)
                except Exception:
                    self.errors += 1

        tasks = [single_request() for _ in range(iterations)]
        await asyncio.gather(*tasks)

    def report(self):
        n = len(self.latencies)
        return {
            "total_requests": len(self.latencies) + self.errors,
            "success": len(self.latencies),
            "errors": self.errors,
            "latency_ms": {
                "mean": round(mean(self.latencies), 2),
                "median": round(median(self.latencies), 2),
                "p95": round(sorted(self.latencies)[int(n * 0.95)], 2),
                "p99": round(sorted(self.latencies)[int(n * 0.99)], 2),
                "stddev": round(pstdev(self.latencies), 2),
            },
        }


# Запуск
tester = MCPLoadTester(
    tool_name="search",
    args_fn=lambda: {"query": "test query"},
    concurrency=20,
)
# asyncio.run(tester.run(iterations=500))
# print(tester.report())
```

---

## 4. CI/CD для MCP-серверов

### 4.1 GitHub Actions

```yaml
# .github/workflows/mcp-server.yml
name: MCP Server CI/CD

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.13"

      - name: Install dependencies
        run: |
          pip install mcp httpx pytest-asyncio
          pip install -r requirements.txt

      - name: Run unit tests
        run: pytest tests/unit -v --timeout=30

      - name: Run integration tests
        run: pytest tests/integration -v --timeout=60

      - name: Run schema validation
        run: python tests/validate_schema.py

      - name: Run load tests (smoke)
        run: python tests/load_test.py --iterations 50 --concurrency 5

  security-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Dependency scan
        run: pip-audit

      - name: SAST scan
        uses: github/codeql-action/analyze@v3

  build-and-push:
    needs: [test, security-scan]
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v4

      - name: Build Docker image
        run: |
          docker build -t mcp-server:${{ github.sha }} .
          docker tag mcp-server:${{ github.sha }} \
            registry.example.com/mcp-server:latest
          docker tag mcp-server:${{ github.sha }} \
            registry.example.com/mcp-server:${{ github.sha }}

      - name: Push to registry
        run: |
          docker push registry.example.com/mcp-server:latest
          docker push registry.example.com/mcp-server:${{ github.sha }}

  deploy-canary:
    needs: [build-and-push]
    runs-on: ubuntu-latest
    environment: production
    steps:
      - name: Deploy canary (10% traffic)
        run: |
          kubectl set image deployment/mcp-server-canary \
            mcp-server=registry.example.com/mcp-server:${{ github.sha }}
          kubectl rollout status deployment/mcp-server-canary

      - name: Smoke test canary
        run: |
          python tests/smoke_test.py \
            --url https://mcp-canary.example.com

      - name: Promote to stable
        if: success()
        run: |
          kubectl set image deployment/mcp-server \
            mcp-server=registry.example.com/mcp-server:${{ github.sha }}
```

### 4.2 Dockerfile для MCP-сервера

```dockerfile
# Dockerfile
FROM python:3.13-slim AS builder

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ---
FROM python:3.13-slim AS runtime

# Безопасность
RUN adduser --disabled-password --gecos '' mcp
USER mcp

WORKDIR /app
COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY server.py .
COPY tools/ ./tools/

# Health check
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "from mcp.client import ping; ping('stdio')"

# Метаданные для MCP
LABEL mcp.server.version="1.0.0"
LABEL mcp.server.tools="add,multiply,calculator,search"

ENTRYPOINT ["python", "server.py"]
```

### 4.3 Versioning стратегия

```python
# version.py
MCP_SERVER_VERSION = "2.1.0"

# Семантическое версионирование для MCP-серверов:
# MAJOR — ломающие изменения в tool schemas
# MINOR — новые инструменты, не ломающие старые
# PATCH — bugfixes, производительность

# При изменении инструмента:
# 1. Добавление — MINOR
# 2. Удаление — MAJOR
# 3. Изменение параметров — MAJOR
# 4. Расширение параметров (опциональные) — MINOR


def check_client_compatibility(
    server_version: str,
    client_protocol: str,
) -> bool:
    """Проверяет совместимость версий."""

    from packaging.version import Version

    sv = Version(server_version)
    required = Version("2025-03-26")

    if Version(client_protocol) < required:
        return False

    return True
```

---

## 5. Production checklist

Перед деплоем MCP-сервера:

```
[ ] Сервер проходит unit + integration тесты
[ ] Schema validation всех инструментов
[ ] Load test: p95 latency < 1s
[ ] Error handling для всех инструментов
[ ] Graceful shutdown (SIGTERM → drain → exit)
[ ] Health check endpoint
[ ] Rate limiting настроен
[ ] Аутентификация (API Key / mTLS)
[ ] Audit logging
[ ] Dockerfile (non-root, минимальный образ)
[ ] CI/CD пайплайн
[ ] Версионирование
[ ] Документация инструментов
```

---

## Практическое задание

1. Напиши MCP-сервер на Python SDK с 3 инструментами: `search_files(pattern)`, `read_file(path)`, `file_stats(path)`. Используй type hints и docstrings.

2. Напиши unit-тесты для каждого инструмента с помощью `McpTestClient`.

3. Добавь Dockerfile и проверь, что сервер работает в контейнере.

4. Напиши load test для сервера: 100 запросов, concurrency 10. Какая p95 latency?

---

## Проверь себя

1. Чем Python SDK отличается от TypeScript SDK?
2. Как тестировать MCP-сервер без запуска LLM?
3. Как выглядит CI/CD пайплайн для MCP-сервера?
4. Почему Dockerfile должен использовать non-root пользователя?
5. Что проверять в integration тестах MCP-сервера?
6. Как версионировать MCP-сервер?

---

## Ссылки

- [[01-server-patterns]] — транспорт
- [[02-security-production]] — безопасность
- [[03-composition-patterns]] — композиция
- [[05-ecosystem-map]] — следующий урок: карта экосистемы
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [MCP TypeScript SDK](https://github.com/modelcontextprotocol/typescript-sdk)
