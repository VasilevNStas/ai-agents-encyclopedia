---
created: 2026-05-28
tags: [course/mcp-deep, mcp, ecosystem, a2a, protocols, comparison]
status: active
---

# Урок 18.5: MCP Ecosystem Map — протоколы, стандарты, интероперабельность

> [!quote] Ключевая идея
> MCP — не единственный протокол в экосистеме AI-агентов. A2A (Agent-to-Agent), Function Calling, Agent Protocol — каждый решает свою задачу. Архитектор должен понимать, где какой протокол применить и как их комбинировать.

---

## 1. Карта протоколов AI-агентов

```
                    ┌───────────────────────┐
                    │     LLM / Host         │
                    │  (OpenCode, Claude,    │
                    │   ChatGPT, custom)     │
                    └───────┬───────┬───────┘
                            │       │
                 ┌──────────┘       └──────────┐
                 ▼                              ▼
        ┌────────────────┐          ┌──────────────────┐
        │  MCP            │          │  Function Call    │
        │  (инструменты)  │          │  (нативные API)   │
        │  LLM → Tool     │          │  LLM → Provider   │
        └────────────────┘          └──────────────────┘
                 │
                 ▼
        ┌────────────────┐
        │  A2A            │
        │  (агент→агент)  │
        │  Agent → Agent  │
        └────────────────┘
                 │
                 ▼
        ┌────────────────┐
        │  Agent Protocol │
        │  (фреймворки)   │
        │  Task → Result  │
        └────────────────┘
```

---

## 2. MCP (Model Context Protocol)

**Назначение:** LLM → Внешние инструменты и данные.

```
LLM ── MCP ──► File System
           ──► Database
           ──► Web Search
           ──► Slack / Email
```

**Где применим:**
- Предоставление инструментов LLM
- Доступ к данным (файлы, БД, API)
- Выполнение действий от имени пользователя
- Интеграция с внешними сервисами

**Ключевая метафора:** "USB-C for AI" — стандартный разъём для подключения чего угодно к LLM.

**Кто использует:** OpenCode, Claude Code, Goose, Continue.dev, Cursor.

---

## 3. A2A (Agent-to-Agent)

**Назначение:** Агент ←→ Агент. Коммуникация между независимыми агентами.

```
[Customer Agent] ←── A2A ──► [Billing Agent]
       │                            │
       │ A2A                        │ A2A
       ▼                            ▼
[Technical Agent]           [Analytics Agent]
```

**Ключевые отличия от MCP:**

| Аспект | MCP | A2A |
|--------|-----|-----|
| Субъекты | LLM → Tool | Agent → Agent |
| Формат | JSON-RPC | JSON-RPC + Task-oriented |
| Операция | Вызов инструмента | Договор / делегирование |
| Состояние | Stateless | Stateful (долгие задачи) |
| Карточка агента | Tool schema | Agent Card (что умеет) |
| Аутентификация | Через транспорт | JWT, OAuth |

**A2A Agent Card:**

```json
{
  "agentCard": {
    "name": "BillingAgent",
    "description": "Handles billing and payment inquiries",
    "url": "https://billing.example.com/a2a",
    "version": "1.0.0",
    "capabilities": {
      "skills": [
        {
          "id": "process_refund",
          "name": "Process Refund",
          "description": "Process a refund for a customer order",
          "input": {
            "type": "object",
            "properties": {
              "order_id": {"type": "string"},
              "reason": {"type": "string"},
              "amount": {"type": "number"}
            }
          },
          "output": {
            "type": "object",
            "properties": {
              "status": {"type": "string"},
              "refund_id": {"type": "string"},
              "estimated_days": {"type": "integer"}
            }
          }
        }
      ]
    },
    "authentication": {
      "schemes": ["bearer"],
      "token_url": "https://auth.example.com/token"
    }
  }
}
```

**Где применим:**
- Мультиагентные системы с независимыми агентами
- B2B интеграция между AI-системами
- Делегирование подзадач специализированным агентам
- Рынок агентов (Agent Marketplace)

**Когда A2A, а когда MCP:**

```
Вам нужен поиск по документации?
→ MCP (LLM → search tool)

Вам нужно, чтобы агент-аналитик делегировал задачу агенту-дизайнеру?
→ A2A (Agent → Agent)

Вам нужно и то, и другое?
→ MCP + A2A в одном агенте
```

---

## 4. Function Calling (Provider-native)

**Назначение:** LLM → Функции, определённые в API провайдера.

```python
# OpenAI-style Function Calling
response = client.chat.completions.create(
    model="gpt-4o",
    tools=[{
        "type": "function",
        "function": {
            "name": "get_weather",
            "parameters": {"type": "object", "properties": {...}},
        }
    }]
)
```

**Сравнение с MCP:**

| Критерий | Function Calling | MCP |
|----------|-----------------|-----|
| Стандарт | Проприетарный (каждый провайдер свой) | Открытый (спецификация) |
| Переносимость | Только для одного провайдера | Любой MCP-клиент |
| Инструменты | Определены в коде агента | Внешние серверы |
| Сложность | Просто (всё в одном месте) | Сложнее (отдельные процессы) |
| Безопасность | В контексте агента | Sandbox (отдельный процесс) |
| Масштабирование | Через код агента | Горизонтальное (серверы) |

**Когда что:**

```
Прототип / MVP:
  Function Calling — быстро, не нужно поднимать серверы

Production / Multi-tenant:
  MCP — безопаснее, масштабируется, не зависит от провайдера

Гибрид:
  Function Calling для базовых операций
  MCP для сложных внешних интеграций
```

---

## 5. Agent Protocol (AutoGen / CrewAI)

**Назначение:** Унификация взаимодействия агентов внутри фреймворка.

```python
# AutoGen Agent Protocol
class MyAgent(ConversableAgent):
    """Agent, совместимый с Agent Protocol."""

    async def receive(self, message: dict, sender: "Agent") -> dict:
        """Принять сообщение от другого агента."""
        task = message.get("task")
        result = await self.process_task(task)
        return {"status": "completed", "result": result}


# Agent Protocol Task:
{
    "task_id": "task_123",
    "type": "code_review",
    "input": {
        "code": "def foo(): pass",
        "language": "python",
    },
    "metadata": {
        "priority": "high",
        "deadline": "2026-06-01T00:00:00Z",
    },
}

# Agent Protocol Result:
{
    "task_id": "task_123",
    "status": "completed",
    "output": {
        "issues": [
            {"line": 1, "severity": "warning", "message": "Missing docstring"},
        ],
        "score": 0.85,
    },
    "metrics": {
        "duration_ms": 1234,
        "model": "claude-sonnet-4.6",
        "cost": 0.002,
    },
}
```

| Критерий | Agent Protocol | MCP | A2A |
|----------|---------------|-----|-----|
| Уровень | Фреймворк | Транспорт | Коммуникация |
| Зависимость | AutoGen, CrewAI | Любой клиент | Любой агент |
| Формат | Task → Result | tool call | Делегирование |
| Orchestration | Встроена | Нет | Опционально |

---

## 6. Decision Matrix: какой протокол выбрать

```python
def choose_protocol(requirements: dict) -> list[str]:
    """Выбирает протоколы под требования."""

    protocols = []

    # 1. Нужны ли внешние инструменты?
    if requirements.get("external_tools"):
        if requirements.get("production") or requirements.get("multi_tenant"):
            protocols.append("MCP")
        else:
            protocols.append("function_calling")

    # 2. Нужна ли коммуникация между агентами?
    if requirements.get("agent_to_agent"):
        if requirements.get("independent_agents"):
            protocols.append("A2A")
        if requirements.get("framework_locked"):
            protocols.append("agent_protocol")

    # 3. Нужен ли рынок агентов?
    if requirements.get("agent_marketplace"):
        protocols.append("A2A")

    return protocols or ["function_calling"]  # fallback


# Примеры:

# Простой чат-бот с поиском погоды
choose_protocol({"external_tools": True})
# → ["function_calling"]

# Production support система
choose_protocol({
    "external_tools": True,
    "production": True,
    "multi_tenant": True,
})
# → ["MCP"]

# Мультиагентная система с независимыми сервисами
choose_protocol({
    "external_tools": True,
    "agent_to_agent": True,
    "independent_agents": True,
    "production": True,
})
# → ["MCP", "A2A"]
```

---

## 7. Комбинированная архитектура: MCP + A2A

В production-системах протоколы комбинируются:

```
                    ┌──────────────────────┐
                    │   Orchestrator Agent │
                    │    (Supervisor)      │
                    └────┬─────────────┬───┘
                         │             │
                    A2A  │             │ A2A
                         ▼             ▼
              ┌──────────────┐  ┌──────────────┐
              │ Billing      │  │ Technical    │
              │ Agent        │  │ Agent        │
              │              │  │              │
              │ MCP:         │  │ MCP:         │
              │  • query_db  │  │  • search    │
              │  • send_inv  │  │  • read_file │
              │  • calc_tax  │  │  • git_ops   │
              └──────────────┘  └──────────────┘
                         │             │
                         │    MCP      │
                         ▼             ▼
              ┌──────────────┐  ┌──────────────┐
              │ Stripe API   │  │ GitHub API   │
              │ (MCP server) │  │ (MCP server) │
              └──────────────┘  └──────────────┘
```

```python
class HybridAgent:
    """Агент, использующий MCP + A2A."""

    def __init__(self, mcp_tools: list, a2a_peers: dict):
        self.mcp = MCPClient(mcp_tools)
        self.a2a = A2AClient(a2a_peers)

    async def handle_task(self, task: dict) -> dict:
        task_type = task["type"]

        if task_type == "billing_question":
            # Используем MCP для инструментов
            invoice = await self.mcp.call("query_db", {
                "query": f"SELECT * FROM invoices WHERE id = {task['invoice_id']}"
            })
            return {"answer": self._format_invoice(invoice)}

        elif task_type == "technical_issue":
            # Делигируем техническому агенту через A2A
            result = await self.a2a.delegate(
                agent="technical",
                task={
                    "type": "debug",
                    "repo": task["repo"],
                    "issue": task["description"],
                },
            )
            return result

        elif task_type == "complex_escalation":
            # Комбинируем: MCP для данных + A2A для анализа
            logs = await self.mcp.call("search", {
                "query": f"error: {task['error']}"
            })
            result = await self.a2a.delegate(
                agent="senior-engineer",
                task={"type": "analyze", "logs": logs},
            )
            return result
```

---

## 8. Будущее протоколов (2026+)

### Тренды:

1. **MCP станет стандартным transport layer** — как HTTP для web. Большинство SaaS будут предоставлять MCP-эндпоинты наравне с REST API.

2. **A2A для агентских сетей** — рынок агентов (приложение A заказывает задачу агенту B). Пример: Agent-to-Agent protocol от Google.

3. **Унификация:** протоколы не конкурируют, а дополняют друг друга:
   - MCP: инструменты для LLM
   - A2A: коммуникация между агентами
   - Agent Protocol: внутренняя оркестрация в фреймворках

4. **Discovery + Registry:** MCP-серверы и A2A-агенты будут регистрироваться в реестрах с автоматическим discovery.

```
2024: Function Calling (каждый сам за себя)
2025: MCP + A2A (первые стандарты)
2026: MCP как HTTP для AI (стандарт де-факто)
2027: Agent Fabric (протоколы сращиваются)
```

---

## Резюме

```
MCP:     LLM → инструменты (JSON-RPC, stateless)
A2A:     Agent → Agent (task-oriented, stateful)
FuncCall: LLM → функция (проприетарный)
AgentP:  Agent → Task → Result (фреймворк)

Правило выбора:
  1. Нужен инструмент → MCP или Function Calling
  2. Нужно двум агентам поговорить → A2A
  3. Нужно и то, и другое → MCP + A2A
  4. Прототип → Function Calling, Production → MCP
```

---

## Практическое задание

1. Спроектируй архитектуру для multi-agent support системы:
   - Orchestrator-агент
   - Billing-агент (работает с БД)
   - Technical-агент (работает с кодом/Git)
   - Какие протоколы между ними? Почему?

2. Перепиши MCP-сервер из предыдущих уроков так, чтобы он мог коммуницировать с другим агентом через A2A.

3. Составь decision tree для выбора протокола в новой системе.

---

## Проверь себя

1. Чем A2A отличается от MCP по назначению?
2. Когда Function Calling предпочтительнее MCP?
3. Что такое Agent Card в A2A?
4. Как комбинировать MCP и A2A в одной системе?
5. Какой протокол выбрать для агентского маркетплейса?
6. Какой тренд в эволюции протоколов на 2026-2027?

---

## Ссылки

- [[01-server-patterns]] — транспорт MCP
- [[02-security-production]] — безопасность
- [[03-composition-patterns]] — композиция
- [[04-building-servers]] — создание серверов
- [[../../../04-multi-agent/04-a2a-protocol]] — A2A Protocol
- [Google A2A Specification](https://github.com/google/A2A)
- [MCP Specification](https://spec.modelcontextprotocol.io)
