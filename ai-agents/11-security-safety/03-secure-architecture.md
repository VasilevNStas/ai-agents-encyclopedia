---
created: 2026-05-28
tags: [course/security, architecture, sandboxing, secrets, permissions]
status: active
---

# Урок 42: Secure Agent Architecture

> [!quote] Ключевая идея
> Агент — это программа с теми же правами, что и пользователь. Если агент скомпрометирован, атакующий получает эти права. Secure architecture минимизирует ущерб: наименьшие привилегии, песочница, изоляция сети, безопасное хранение секретов.

---

## Принцип наименьших привилегий (Least Privilege)

Агент имеет доступ только к тому, что нужно **сейчас**, а не «в теории может понадобиться».

```python
from enum import Enum, auto


class Permission(Enum):
    NONE = auto()
    READ = auto()
    WRITE = auto()
    EXECUTE = auto()
    ADMIN = auto()


@dataclass
class ResourcePermission:
    resource_pattern: str   # glob: /tmp/agent/*, db://users/read
    permission: Permission
    reason: str             # почему эта привилегия нужна


class PermissionManager:
    """Выдаёт минимально необходимые права на каждый шаг."""

    def __init__(self):
        self._grants: list[ResourcePermission] = []

    def grant(self, permission: ResourcePermission) -> None:
        self._grants.append(permission)

    def revoke_all(self) -> None:
        self._grants.clear()

    def check_access(self, resource: str,
                     required: Permission) -> bool:
        for grant in self._grants:
            if self._match(grant.resource_pattern, resource):
                if grant.permission.value >= required.value:
                    return True
        return False

    def _match(self, pattern: str, resource: str) -> bool:
        import fnmatch
        return fnmatch.fnmatch(resource, pattern)

    def request_permission(self, resource: str,
                           required: Permission,
                           reason: str) -> bool:
        """Агент запрашивает временное расширение прав."""
        if self.check_access(resource, required):
            return True

        # В реальной системе — human-in-the-loop
        print(f"[PERMISSION] Request: {required.name} on {resource}")
        print(f"[PERMISSION] Reason: {reason}")

        # Временное расширение на одну операцию
        self.grant(ResourcePermission(
            resource_pattern=resource,
            permission=required,
            reason=reason,
        ))
        return True


# Пример
pm = PermissionManager()
pm.grant(ResourcePermission(
    resource_pattern="/tmp/agent/*",
    permission=Permission.READ,
    reason="чтение временных файлов",
))

assert pm.check_access("/tmp/agent/data.json", Permission.READ) is True
assert pm.check_access("/etc/passwd", Permission.READ) is False
assert pm.check_access("/tmp/agent/data.json", Permission.WRITE) is False
```

> [!important]
> Принцип наименьших привилегий требует **динамического** управления правами. Не выдавай все права при старте — выдавай по запросу и отзывай после использования. JIT (Just-In-Time) permissions.

---

## Sandboxing: изоляция кода

Агент может выполнять код — значит, этот код должен быть изолирован.

```python
import subprocess
import resource
import tempfile
import os
from pathlib import Path


class SandboxedAgent:
    """Изолированное окружение для выполнения кода агента."""

    def __init__(self, sandbox_dir: str = "/tmp/agent-sandbox"):
        self.sandbox_dir = Path(sandbox_dir)
        self.sandbox_dir.mkdir(parents=True, exist_ok=True)

    def _set_limits(self) -> None:
        """Ограничение ресурсов."""
        resource.setrlimit(resource.RLIMIT_CPU, (5, 5))       # 5 секунд CPU
        resource.setrlimit(resource.RLIMIT_AS, (256 * 1024 * 1024,  # 256 MB RAM
                                                 256 * 1024 * 1024))
        resource.setrlimit(resource.RLIMIT_NOFILE, (50, 50))  # 50 открытых файлов
        resource.setrlimit(resource.RLIMIT_NPROC, (10, 10))   # 10 процессов

    def run_code(self, code: str, timeout: int = 10) -> dict:
        """Выполняет код в изолированном subprocess."""
        with tempfile.NamedTemporaryFile(
            dir=self.sandbox_dir, suffix=".py", delete=False,
            mode="w",
        ) as f:
            f.write(code)
            script_path = f.name

        try:
            result = subprocess.run(
                ["python3", "-c", code],
                cwd=self.sandbox_dir,
                capture_output=True,
                text=True,
                timeout=timeout,
                env={  # чистый env без секретов
                    "PATH": "/usr/bin:/bin",
                    "HOME": "/nonexistent",
                    "USER": "sandbox",
                },
            )

            return {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
                "sandboxed": True,
            }

        except subprocess.TimeoutExpired:
            return {"error": "timeout", "sandboxed": True}
        except Exception as e:
            return {"error": str(e), "sandboxed": True}
        finally:
            os.unlink(script_path)

    def validate_code(self, code: str) -> bool:
        """Статический анализ кода на опасные вызовы."""
        dangerous_imports = [
            "socket", "requests", "urllib",
            "subprocess", "os.system", "shutil",
            "ctypes", "pickle", "shelve",
            "sqlite3", "http.server",
        ]

        for imp in dangerous_imports:
            if f"import {imp}" in code or f"from {imp}" in code:
                return False

        return True
```

### Техники sandboxing

| Техника | Описание | Глубина защиты |
|---------|----------|----------------|
| **Subprocess jail** | Выполнение в отдельном процессе с ограничениями | Средняя |
| **Container (Docker)** | Каждый запуск в новом контейнере | Высокая |
| **gVisor / Firecracker** | Микровиртуализация | Очень высокая |
| **WebAssembly (Wasm)** | Изоляция на уровне инструкций | Высокая |
| **Deno / Bun permissions** | Встроенная система прав в рантайме | Средняя |

> [!warning]
> Sandboxing — не панацея. Container escapes существуют. На критических системах используй многослойную изоляцию: subprocess внутри контейнера внутри виртуальной машины.

---

## Tool Permissions

Каждый инструмент агента должен проверять права перед выполнением.

```python
from functools import wraps
from typing import Callable


class SecureToolWrapper:
    """Оборачивает инструмент проверкой прав."""

    def __init__(self, permission_manager: PermissionManager):
        self.pm = permission_manager
        self._tool_registry: dict[str, dict] = {}

    def register(self, name: str, required_perm: Permission,
                 resource_pattern: str,
                 fn: Callable) -> None:
        self._tool_registry[name] = {
            "fn": fn,
            "required_perm": required_perm,
            "resource_pattern": resource_pattern,
        }

    def execute(self, tool_name: str, args: dict,
                context: TenantContext) -> dict:
        tool = self._tool_registry.get(tool_name)
        if not tool:
            return {"error": f"unknown tool: {tool_name}"}

        resource = tool["resource_pattern"].format(**args)

        if not self.pm.check_access(resource, tool["required_perm"]):
            return {
                "error": "permission denied",
                "required": tool["required_perm"].name,
                "resource": resource,
                "action": "blocked",
            }

        # Rate limiting
        if not self._check_rate_limit(tool_name, context):
            return {
                "error": "rate limit exceeded",
                "action": "blocked",
            }

        return tool["fn"](**args)

    def _check_rate_limit(self, tool_name: str,
                          context: TenantContext) -> bool:
        """Проверка rate limit для инструмента."""
        # В реальной системе — token bucket или sliding window
        return True


# Пример регистрации
secure_tools = SecureToolWrapper(pm)

secure_tools.register(
    name="read_file",
    required_perm=Permission.READ,
    resource_pattern="{path}",
    fn=lambda path: open(path).read(),
)

secure_tools.register(
    name="delete_file",
    required_perm=Permission.ADMIN,
    resource_pattern="{path}",
    fn=lambda path: os.remove(path),
)
```

> [!important]
> Каждый инструмент должен иметь `required_perm` и `resource_pattern`. Даже read-only инструменты должны проверять права — не все файлы можно читать.

---

## API Key & Secrets Management

### Как НЕ надо

```python
# ❌ Hardcoded secrets
OPENAI_API_KEY = "sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

# ❌ Secrets в коде
config = {
    "db_password": "super_secret_123",
    "aws_secret_key": "AKIAIOSFODNN7EXAMPLE",
}

# ❌ Secrets в env без префикса
os.environ["SECRET"] = "xxx"
```

### Как надо

```python
import os
import base64
from cryptography.fernet import Fernet
from dataclasses import dataclass


@dataclass
class Secret:
    key: str
    value: bytes
    rotation_date: str
    source: str   # env, vault, file


class SecretsManager:
    """Безопасное хранение и ротация секретов."""

    def __init__(self, master_key: bytes | None = None):
        self._master_key = master_key or Fernet.generate_key()
        self._cipher = Fernet(self._master_key)
        self._cache: dict[str, Secret] = {}

    def load_from_env(self, prefix: str = "AGENT_") -> None:
        """Загружает секреты из env с префиксом."""
        for key, value in os.environ.items():
            if key.startswith(prefix):
                secret_name = key[len(prefix):].lower()
                encrypted = self._cipher.encrypt(value.encode())
                self._cache[secret_name] = Secret(
                    key=secret_name,
                    value=encrypted,
                    rotation_date="2026-06-01",
                    source="env",
                )

    def get(self, name: str) -> str | None:
        secret = self._cache.get(name)
        if secret:
            return self._cipher.decrypt(secret.value).decode()
        return None

    def rotate(self, name: str, new_value: str) -> None:
        encrypted = self._cipher.encrypt(new_value.encode())
        self._cache[name] = Secret(
            key=name,
            value=encrypted,
            rotation_date=datetime.date.today().isoformat(),
            source="manual_rotation",
        )

    def revoke(self, name: str) -> None:
        self._cache.pop(name, None)


# Использование
secrets = SecretsManager()
secrets.load_from_env("AGENT_")

api_key = secrets.get("openai_api_key")  # из AGENT_OPENAI_API_KEY
db_password = secrets.get("db_password") # из AGENT_DB_PASSWORD
```

### Vault-интеграция

```python
class VaultBackend:
    """Интеграция с HashiCorp Vault через API."""

    def __init__(self, vault_addr: str, vault_token: str):
        self.addr = vault_addr
        self.token = vault_token

    def read_secret(self, path: str, key: str) -> str | None:
        """Читает секрет из Vault KV store."""
        # В реальности: requests.get(f"{self.addr}/v1/{path}")
        # с заголовком X-Vault-Token
        return None
```

---

## Network Isolation

Агент не должен иметь доступ к внутренним системам без явной необходимости.

```python
from dataclasses import dataclass


@dataclass
class NetworkPolicy:
    allowed_domains: list[str]    # ["api.openai.com", "github.com"]
    allowed_ports: list[int]      # [443]
    blocked_cidrs: list[str]      # ["10.0.0.0/8", "172.16.0.0/12"]
    allow_localhost: bool = False


class NetworkIsolation:
    """Проверяет сетевые запросы на соответствие политике."""

    def __init__(self, policy: NetworkPolicy):
        self.policy = policy

    def check_url(self, url: str) -> bool:
        from urllib.parse import urlparse
        parsed = urlparse(url)

        # Блокировка внутренних IP
        if self._is_private(parsed.hostname):
            return self.policy.allow_localhost

        # Проверка домена
        for allowed in self.policy.allowed_domains:
            if parsed.hostname.endswith(allowed):
                return True

        return False

    def _is_private(self, hostname: str) -> bool:
        """Проверяет, является ли адрес внутренним."""
        import ipaddress
        try:
            ip = ipaddress.ip_address(hostname)
            return ip.is_private
        except ValueError:
            # Не IP, а домен — пропускаем
            return False


# Пример
policy = NetworkPolicy(
    allowed_domains=["api.openai.com", "api.github.com"],
    allowed_ports=[443],
    blocked_cidrs=["10.0.0.0/8"],
    allow_localhost=False,
)

isolator = NetworkIsolation(policy)
assert isolator.check_url("https://api.openai.com/v1/chat") is True
assert isolator.check_url("https://10.0.0.1/admin") is False
assert isolator.check_url("https://internal.corp.com") is False
```

---

## Security Checklist для архитектора

```
[ ] Наименьшие привилегии: агент не имеет доступа к тому,
    что не нужно для текущей задачи

[ ] Sandboxing: код агента выполняется в изолированном окружении
    с ограничением ресурсов (CPU, RAM, FS, network)

[ ] Tool permissions: каждый инструмент проверяет права
    перед выполнением

[ ] Secrets management: секреты в encrypted storage,
    а не в коде или env без префикса

[ ] Network isolation: белый список доменов, блокировка
    внутренних сетей

[ ] Rate limiting: ограничение вызова инструментов
    (100 запросов/минуту, не 1000)

[ ] Audit / logging: все действия логируются без PII

[ ] Input validation: санитайзинг пользовательского ввода

[ ] Human-in-the-loop: опасные операции требуют подтверждения

[ ] Regular rotation: ключи и секреты ротируются по расписанию

[ ] Dependency scan: библиотеки агента проверяются на уязвимости
```

---

## Anti-patterns

| Anti-pattern | Почему опасно |
|---|---|
| **Hardcoded secrets** | Попадают в git — утекают навсегда |
| **Overly permissive tools** | `execute(command)` — всё, агент — это RCE |
| **Отсутствие rate limiting** | Один пользователь может сжечь весь бюджет |
| **Агент в той же сети, что и БД** | Injection -> прямой доступ к данным |
| **Нет изоляции между tenant-ами** | Утечка данных между пользователями |
| **Секреты в логах** | Логи часто имеют более широкий доступ |
| **Static permissions** | Права выданы при старте и не отзываются |
| **Self-modifying code** | Агент, который меняет свой код — угроза безопасности |

---

## Проверь себя

1. В чём суть принципа наименьших привилегий и как он применяется к агентам?
2. Какие 5 техник sandboxing перечислены в уроке?
3. Зачем нужен `SecureToolWrapper` и что он проверяет?
4. Как правильно хранить API-ключи агента? (3 метода)
5. Что должно быть в security checklist архитектора?

---

## Практическое задание

1. Реализуй `TokenBucketRateLimiter` и встрой его в `SecureToolWrapper`.
2. Напиши Docker-образ для sandboxed-агента: Alpine Python, без сети, с ограничением памяти.
3. Создай `SecretsRotator`, который автоматически ротирует ключи каждые N дней и уведомляет администратора.

---

## Резюме

```
Least privilege:  минимально необходимые права на каждый шаг
Sandboxing:       subprocess jail, контейнер, Wasm, gVisor
Tool permissions: каждый инструмент проверяет права и rate limit
Secrets:          encrypted storage + vault + ротация
Network:          белый список доменов, блокировка internal CIDR

Агент — программа с правами пользователя.
Secure architecture — это не опция, а требование.
```

---

## Ссылки

- [[06-prompt-engineering/01-system-prompts]] — проектирование промпта
- [[05-production/01-guardrails]] — защитные рельсы
- [[05-production/04-resilience]] — устойчивость
- [[05-production/05-agent-testing]] — тестирование безопасности
- [OWASP LLM Security](https://genai.owasp.org/)
- [Least Privilege — NIST](https://csrc.nist.gov/glossary/term/least_privilege)
- [HashiCorp Vault](https://www.vaultproject.io/)
