---
created: 2026-05-28
tags: [course/mcp-deep, mcp, security, production, auth, architect]
status: active
---

# Урок 18.2: MCP Security & Production

> [!quote] Ключевая идея
> MCP-сервер — это удалённо исполняемый код. Каждый инструмент — это surface для атаки. Production-ready MCP означает: аутентификация, авторизация, sandboxing, rate limiting, мониторинг и аудит.

---

## 1. Модель угроз MCP

```
┌─────────────────────────────────────────────────────┐
│                    АТАКИ НА MCP                      │
├─────────────────────────────────────────────────────┤
│                                                      │
│  1. Неавторизованный доступ к серверу                │
│     → кто угодно может вызывать инструменты          │
│                                                      │
│  2. Prompt injection через аргументы                 │
│     → злоумышленник передаёт "ignore safety"         │
│                                                      │
│  3. Resource exhaustion (DoS)                        │
│     → 1000 вызовов search за секунду                 │
│                                                      │
│  4. Path traversal (stdio)                           │
│     → read_file("../../../etc/passwd")               │
│                                                      │
│  5. Supply chain атака                               │
│     → скомпрометированный MCP-пакет                  │
│                                                      │
│  6. Data exfiltration                                │
│     → tool возвращает чувствительные данные           │
│                                                      │
└─────────────────────────────────────────────────────┘
```

---

## 2. Аутентификация

MCP **не определяет** встроенную аутентификацию. Это responsibility транспорта.

### 2.1 stdio: аутентификация через окружение

Для stdio аутентификация — это окружение процесса:

```json
{
  "mcpServers": {
    "database": {
      "command": "python",
      "args": ["mcp_db_server.py"],
      "env": {
        "DB_API_KEY": "sk-...",
        "DB_CONNECTION_STRING": "postgresql://..."
      }
    }
  }
}
```

**Host передаёт credentials через переменные окружения.** Сервер читает их при старте. Это безопасно, потому что:
- Переменные окружения изолированы между процессами
- Не видны другим процессам в системе
- Автоматически очищаются при завершении процесса

### 2.2 SSE: API Key + Bearer Token

Для SSE аутентификация — через HTTP-заголовки:

```python
from fastapi import FastAPI, Header, HTTPException
from mcp.server.sse import SseServerTransport


class AuthenticatedMCPServer:
    """MCP-сервер с API Key аутентификацией."""

    def __init__(self):
        self.api_keys: dict[str, str] = {}  # key → tenant_id
        self._load_keys()

    def _load_keys(self):
        """Загружает ключи из защищённого хранилища."""
        # В реальности — Vault, AWS Secrets Manager, K8s Secrets
        self.api_keys = {
            os.environ["MCP_API_KEY"]: "tenant-alpha",
        }

    async def verify_auth(
        self,
        authorization: str = Header(None),
    ) -> str:
        """Проверяет Bearer token и возвращает tenant ID."""

        if not authorization:
            raise HTTPException(status_code=401, detail="Missing Authorization")

        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer":
            raise HTTPException(status_code=401, detail="Invalid scheme")

        tenant = self.api_keys.get(token)
        if not tenant:
            raise HTTPException(status_code=403, detail="Invalid API key")

        return tenant


# === Интеграция с SSE ===

class SecureSseServerTransport(SseServerTransport):
    """SSE transport с аутентификацией."""

    async def handle_session(self, scope, receive, send):
        # Проверка аутентификации при установке SSE
        headers = dict(scope.get("headers", []))
        auth_header = headers.get(b"authorization", b"").decode()

        if not auth_header.startswith("Bearer "):
            await send({
                "type": "http.response.start",
                "status": 401,
                "headers": [(b"content-type", b"application/json")],
            })
            await send({
                "type": "http.response.body",
                "body": b'{"error":"Unauthorized"}',
            })
            return

        await super().handle_session(scope, receive, send)
```

### 2.3 mTLS для production

Для production-систем — mutual TLS:

```python
import ssl


def create_mtls_context(
    cert_path: str,
    key_path: str,
    ca_cert_path: str,
) -> ssl.SSLContext:
    """Создаёт SSLContext с mutual TLS."""

    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.verify_mode = ssl.CERT_REQUIRED  # требует клиентский сертификат
    context.load_cert_chain(cert_path, key_path)
    context.load_verify_locations(ca_cert_path)

    return context


# Uvicorn с mTLS
# uvicorn.run(app, ssl=create_mtls_context(...), host="0.0.0.0", port=8443)
```

---

## 3. Авторизация: кто что может вызывать?

API key говорит **кто** ты. RBAC говорит **что** ты можешь делать.

```python
from enum import Enum


class Role(Enum):
    READER = "reader"       # только read-only инструменты
    OPERATOR = "operator"   # read-write, но без деструктивных
    ADMIN = "admin"         # полный доступ


class Permission(Enum):
    TOOL_CALL = "tool:call"
    RESOURCE_READ = "resource:read"
    RESOURCE_WRITE = "resource:write"
    ADMIN = "admin"


# Матрица доступа
ROLE_PERMISSIONS: dict[Role, set[Permission]] = {
    Role.READER: {Permission.TOOL_CALL, Permission.RESOURCE_READ},
    Role.OPERATOR: {
        Permission.TOOL_CALL,
        Permission.RESOURCE_READ,
        Permission.RESOURCE_WRITE,
    },
    Role.ADMIN: {
        Permission.TOOL_CALL,
        Permission.RESOURCE_READ,
        Permission.RESOURCE_WRITE,
        Permission.ADMIN,
    },
}

# Какие инструменты доступны какой роли
TOOL_ACCESS: dict[str, Role] = {
    "search": Role.READER,
    "get_document": Role.READER,
    "create_ticket": Role.OPERATOR,
    "delete_ticket": Role.ADMIN,
    "run_migration": Role.ADMIN,
}


class AuthorizedMCPServer:
    """MCP-сервер с RBAC."""

    def __init__(self):
        self.role_map: dict[str, Role] = {}  # tenant → role

    def authorize(self, tenant: str, tool_name: str) -> bool:
        """Проверяет, может ли tenant вызывать tool."""

        role = self.role_map.get(tenant)
        if not role:
            return False

        required_role = TOOL_ACCESS.get(tool_name)
        if not required_role:
            return False

        # Проверяем иерархию ролей
        role_level = list(Role).index(role)
        required_level = list(Role).index(required_role)
        return role_level >= required_level

    async def handle_tool_call(self, tenant: str, name: str, arguments: dict):
        if not self.authorize(tenant, name):
            return {
                "content": [{
                    "type": "text",
                    "text": f"Access denied: {name} requires {TOOL_ACCESS[name]} role",
                }],
                "isError": True,
            }

        return await self._execute_tool(name, arguments)
```

---

## 4. Sandboxing: изоляция MCP-сервера

Каждый MCP-сервер должен работать в изолированном окружении.

### 4.1 Subprocess sandbox (stdio)

```python
import subprocess
import resource


def launch_sandboxed_server(
    command: list[str],
    memory_limit_mb: int = 512,
    cpu_time_limit: int = 30,
    network_access: bool = False,
    allowed_paths: list[str] | None = None,
) -> subprocess.Popen:
    """Запускает MCP-сервер в sandbox."""

    def set_limits():
        # Ограничение памяти
        resource.setrlimit(
            resource.RLIMIT_AS,
            (memory_limit_mb * 1024 * 1024, memory_limit_mb * 1024 * 1024),
        )
        # Ограничение CPU времени
        resource.setrlimit(
            resource.RLIMIT_CPU,
            (cpu_time_limit, cpu_time_limit),
        )
        # Ограничение числа процессов
        resource.setrlimit(resource.RLIMIT_NPROC, (50, 50))

    env = os.environ.copy()
    if not network_access:
        env.pop("HTTP_PROXY", None)
        env.pop("HTTPS_PROXY", None)

    return subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        preexec_fn=set_limits,
        env=env,
    )
```

### 4.2 Docker sandbox (для SSE)

```python
import docker


class DockerSandbox:
    """Запуск MCP-сервера в Docker контейнере."""

    def __init__(self):
        self.client = docker.from_env()

    def start_server(self, image: str, env: dict, port: int) -> str:
        """Запускает MCP-сервер в изолированном контейнере."""

        container = self.client.containers.run(
            image=image,
            environment=env,
            ports={f"{port}/tcp": port},
            network="mcp_sandbox_net",  # изолированная сеть
            mem_limit="512m",
            pids_limit=50,
            read_only=True,             # read-only файловая система
            tmpfs={"/tmp": "size=64M"},  # только /tmp для записи
            security_opt=["no-new-privileges:true"],
            cap_drop=["ALL"],            # никаких capabilities
            detach=True,
        )
        return container.id

    def stop_server(self, container_id: str):
        try:
            self.client.containers.get(container_id).stop(timeout=10)
        except docker.errors.NotFound:
            pass
```

### 4.3 Path traversal protection

Стандартная атака на File System MCP-серверы:

```python
import os
from pathlib import Path


class PathSandbox:
    """Защита от path traversal в MCP-инструментах."""

    def __init__(self, allowed_roots: list[Path]):
        self.allowed_roots = [root.resolve() for root in allowed_roots]

    def resolve_path(self, user_path: str) -> Path:
        """Проверяет, что path не выходит за пределы разрешённых корней."""

        resolved = Path(user_path).resolve()

        # Проверка на symlink-атаку
        if resolved.is_symlink():
            resolved = resolved.readlink()
            if not resolved.is_absolute():
                resolved = Path(user_path).parent / resolved
            resolved = resolved.resolve()

        # Проверка, что path внутри разрешённого корня
        for root in self.allowed_roots:
            try:
                resolved.relative_to(root)
                return resolved
            except ValueError:
                continue

        raise PermissionError(
            f"Path {user_path} is outside allowed directories: "
            f"{[str(r) for r in self.allowed_roots]}"
        )

    def sanitize_path(self, path: str) -> str:
        """Удаляет path traversal попытки."""

        # Убираем ../ и ..\
        sanitized = os.path.normpath(path)
        # Убираем null bytes
        sanitized = sanitized.replace("\0", "")
        return sanitized


# Использование в инструменте
sandbox = PathSandbox(allowed_roots=[Path("/data/projects")])


async def read_file_tool(path: str):
    """MCP tool: безопасное чтение файла."""
    safe_path = sandbox.resolve_path(path)

    if not safe_path.exists():
        return {"error": "File not found", "isError": True}

    if not safe_path.is_file():
        return {"error": "Not a file", "isError": True}

    content = safe_path.read_text(encoding="utf-8")
    return {"content": [{"type": "text", "text": content}]}
```

---

## 5. Rate Limiting

### 5.1 Token Bucket

```python
import time
import asyncio


class TokenBucket:
    """Token bucket rate limiter для MCP-запросов."""

    def __init__(self, rate: float, burst: int):
        self.rate = rate          # запросов в секунду
        self.burst = burst        # максимальный burst
        self.tokens = burst
        self.last_refill = time.monotonic()

    async def acquire(self) -> bool:
        """Пытается получить токен. Ждёт, если нужно."""

        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(
            self.burst,
            self.tokens + elapsed * self.rate,
        )
        self.last_refill = now

        if self.tokens >= 1:
            self.tokens -= 1
            return True

        # Нужно подождать
        wait_time = 1.0 / self.rate
        await asyncio.sleep(wait_time)
        self.tokens -= 1
        return True


class RateLimitedMCPServer:
    """MCP-сервер с rate limiting по tenant."""

    def __init__(self):
        self.limiters: dict[str, TokenBucket] = {}

        # Разные лимиты для разных уровней
        self.limiters["free"] = TokenBucket(rate=1, burst=5)     # 1 rps
        self.limiters["pro"] = TokenBucket(rate=10, burst=50)    # 10 rps
        self.limiters["enterprise"] = TokenBucket(rate=100, burst=500)

    async def check_rate_limit(self, tenant: str) -> bool:
        tier = self._get_tenant_tier(tenant)
        limiter = self.limiters.get(tier, self.limiters["free"])
        return await limiter.acquire()

    def _get_tenant_tier(self, tenant: str) -> str:
        # В реальности — из БД или кэша
        return "pro"
```

### 5.2 Per-tool лимиты

Разные инструменты имеют разную стоимость:

```python
TOOL_COST: dict[str, float] = {
    "search": 1.0,          # 1 единица
    "get_document": 0.5,    # 0.5 единицы
    "analyze_large_dataset": 50.0,  # 50 единиц
    "export_all": 100.0,    # 100 единиц
}


class CostBasedRateLimiter:
    """Rate limiter с учётом стоимости инструмента."""

    def __init__(self, budget_per_minute: float = 100.0):
        self.budget = budget_per_minute
        self.spent_this_minute = 0.0
        self.minute_start = time.monotonic()

    async def check_tool_call(self, tool_name: str, tenant: str) -> bool:
        cost = TOOL_COST.get(tool_name, 1.0)

        # Сброс каждую минуту
        if time.monotonic() - self.minute_start > 60:
            self.spent_this_minute = 0.0
            self.minute_start = time.monotonic()

        if self.spent_this_minute + cost > self.budget:
            return False

        self.spent_this_minute += cost
        return True
```

---

## 6. Мониторинг и observability

### 6.1 Метрики для MCP

```python
from prometheus_client import Counter, Histogram, Gauge


# Счётчики
mcp_requests_total = Counter(
    "mcp_requests_total",
    "Total MCP requests by method and status",
    ["method", "status", "server"],
)

mcp_errors_total = Counter(
    "mcp_errors_total",
    "MCP errors by type",
    ["error_type", "server"],
)

# Гистограммы
mcp_request_duration = Histogram(
    "mcp_request_duration_seconds",
    "MCP request latency",
    ["method", "server"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

mcp_tool_duration = Histogram(
    "mcp_tool_duration_seconds",
    "MCP tool execution latency",
    ["tool", "server"],
    buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0),
)

# Gauges
mcp_active_connections = Gauge(
    "mcp_active_connections",
    "Active MCP connections",
    ["server"],
)

mcp_tool_budget = Gauge(
    "mcp_tool_budget_remaining",
    "Remaining budget for tenant",
    ["tenant"],
)


class MonitoredMCPServer:
    """MCP-сервер с Prometheus метриками."""

    async def handle_request(self, method: str, params: dict, server_name: str):
        with mcp_request_duration.labels(method, server_name).time():
            try:
                result = await self._process(method, params)
                mcp_requests_total.labels(method, "ok", server_name).inc()
                return result

            except Exception as e:
                mcp_requests_total.labels(method, "error", server_name).inc()
                mcp_errors_total.labels(type(e).__name__, server_name).inc()
                raise
```

### 6.2 Health Check endpoint

```python
@dataclass
class HealthStatus:
    status: str  # "healthy" | "degraded" | "unhealthy"
    uptime: float
    connections: int
    tool_latency_ms: float
    last_error: str | None = None


class MCPHealthChecker:
    """Health check для MCP-сервера."""

    def __init__(self, server):
        self.server = server
        self.start_time = time.monotonic()
        self.last_tool_latency: list[float] = []

    async def health(self) -> HealthStatus:
        latency = await self._measure_tool_latency()

        if latency > 5000:  # >5s → unhealthy
            return HealthStatus(
                status="unhealthy",
                uptime=time.monotonic() - self.start_time,
                connections=self.server.active_connections,
                tool_latency_ms=latency,
                last_error="Tool latency exceeded 5s threshold",
            )

        if latency > 1000:
            return HealthStatus(
                status="degraded",
                uptime=time.monotonic() - self.start_time,
                connections=self.server.active_connections,
                tool_latency_ms=latency,
            )

        return HealthStatus(
            status="healthy",
            uptime=time.monotonic() - self.start_time,
            connections=self.server.active_connections,
            tool_latency_ms=latency,
        )

    async def _measure_tool_latency(self) -> float:
        """Измеряет latency через вызов самого дешёвого инструмента."""
        start = time.monotonic()
        try:
            # Вызываем самый лёгкий инструмент (если есть ping-подобный)
            await self.server.handle_request("tools/call", {
                "name": "ping",
                "arguments": {},
            })
        except Exception:
            pass
        return (time.monotonic() - start) * 1000
```

### 6.3 Audit Logging

```python
import json
import logging
from datetime import datetime, timezone


class MCPAuditLogger:
    """Аудит всех вызовов MCP-инструментов."""

    def __init__(self):
        self.logger = logging.getLogger("mcp.audit")
        self._setup_handler()

    def _setup_handler(self):
        handler = logging.FileHandler("mcp_audit.log")
        handler.setFormatter(logging.Formatter(
            "%(asctime)s | %(message)s"
        ))
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)

    def log_call(
        self,
        tenant: str,
        tool: str,
        arguments: dict,
        result_size: int,
        latency_ms: int,
        error: str | None = None,
    ):
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tenant": tenant,
            "tool": tool,
            "arguments_sanitized": self._sanitize(arguments),
            "result_size_bytes": result_size,
            "latency_ms": latency_ms,
            "error": error,
        }
        self.logger.info(json.dumps(record, default=str))

    def _sanitize(self, data: dict) -> dict:
        """Маскирует чувствительные данные в логах."""
        sensitive_keys = {"password", "token", "secret", "api_key", "key"}
        sanitized = {}
        for k, v in data.items():
            if k.lower() in sensitive_keys:
                sanitized[k] = "***"
            else:
                sanitized[k] = v
        return sanitized
```

---

## 7. Error Budget для MCP

```python
class MCPErrorBudget:
    """SLO-based error budget для MCP-сервера."""

    def __init__(self, slo: float = 0.999, window_hours: int = 24):
        self.slo = slo                          # 99.9%
        self.window_hours = window_hours
        self.total_requests: int = 0
        self.failed_requests: int = 0
        self.window_start = time.monotonic()

    @property
    def error_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return self.failed_requests / self.total_requests

    @property
    def budget_remaining(self) -> float:
        """Сколько ошибок ещё можно сделать до нарушения SLO."""

        max_errors = self.total_requests * (1 - self.slo)
        budget = max_errors - self.failed_requests
        return max(0, budget)

    def record_request(self, success: bool):
        """Записывает результат запроса."""

        self._check_window()
        self.total_requests += 1
        if not success:
            self.failed_requests += 1

    def should_reject(self) -> bool:
        """Если budget исчерпан — отклоняем некритичные запросы."""

        return self.budget_remaining <= 0

    def _check_window(self):
        if time.monotonic() - self.window_start > self.window_hours * 3600:
            self.total_requests = 0
            self.failed_requests = 0
            self.window_start = time.monotonic()
```

---

## Резюме

```
Security layer для MCP (снизу вверх):

  6. Audit Logging     — кто, когда, что вызвал
  5. Error Budget      — SLO контроль
  4. Monitoring        — Prometheus метрики + health check
  3. Rate Limiting     — token bucket + per-tool cost
  2. Sandboxing        — Docker / ulimit / path protection
  1. AuthN + AuthZ     — API Key / mTLS + RBAC
```

---

## Практическое задание

1. Возьми MCP-сервер на stdio из предыдущего урока и добавь:
   - API Key аутентификацию через переменную окружения
   - Rate limiter (10 requests/sec)
   - Audit logging в файл

2. Реализуй PathSandbox для файлового MCP-сервера. Проверь:
   - `../../../etc/passwd` → блокируется
   - `/data/projects/main.py` → разрешается
   - symlink в разрешённую директорию → разрешается?

3. Напиши Docker Compose для MCP-сервера с ограничением памяти 256MB.

---

## Проверь себя

1. Почему MCP не определяет встроенную аутентификацию?
2. Чем отличается API Key от mTLS? Когда что выбирать?
3. Какие 5 слоёв безопасности нужно реализовать для MCP?
4. Как работает token bucket rate limiter?
5. Что такое error budget и зачем он нужен?
6. Почему path traversal — самая частая атака на MCP-серверы?

---

## Ссылки

- [[01-server-patterns]] — транспорт и жизненный цикл
- [[03-composition-patterns]] — следующий урок: композиция
- [[../../../11-security-safety/01-prompt-injection]] — защита от injection
- [OWASP API Security](https://owasp.org/www-project-api-security/)
