---
created: 2026-05-28
tags: [course/multi-agent, a2a, protocol, communication]
status: active
---

# Урок 15: A2A — Agent-to-Agent Protocol

> [!quote] Ключевая идея
> MCP даёт агенту инструменты. A2A даёт агентам язык для общения друг с другом. **MCP = инструменты, A2A = коммуникация.** Вместе они покрывают все сценарии взаимодействия в мультиагентной системе.

---

## Что такое A2A

**Agent-to-Agent (A2A)** — протокол от Google (2025), определяющий, как AI-агенты общаются, делегируют задачи и обмениваются результатами.

```
┌───────────┐         A2A          ┌───────────┐
│  Agent A  │ ◄──────────────────► │  Agent B  │
│  (client) │    discovery + task  │  (server) │
└───────────┘                      └───────────┘
```

A2A решает проблему: "Как агенты находят друг друга и договариваются о работе?" Без A2A каждый мультиагентный фреймворк изобретает свой велосипед.

### A2A vs MCP

| Характеристика | MCP | A2A |
|---------------|-----|-----|
| Что соединяет | Агент ↔ Инструмент | Агент ↔ Агент |
| Формат | Функции (call/return) | Задачи (assign/complete) |
| Состояние | Stateless | Stateful (долгие задачи) |
| Обнаружение | Нужна конфигурация | Agent Card (авто) |
| Уведомления | Нет | Push-уведомления |
| Безопасность | OAuth, API keys | OAuth 2.0 + взаимная аутентификация |

**Когда что использовать:**

```
MCP: "агенту нужен доступ к базе данных"  → MCP-сервер БД
A2A: "агенту нужно делегировать задачу    → A2A-сервер другого агента
      другому агенту"

Реальный сценарий:
  Supervisor Agent (A2A client)
    ├── Code Agent (A2A server + MCP client для git)
    ├── Test Agent (A2A server + MCP client для pytest)
    └── Deploy Agent (A2A server + MCP client для k8s)

  Supervisor общается с агентами через A2A.
  Каждый агент использует MCP для своих инструментов.
```

---

## Три примитива A2A

### Agent Card

Агент публикует карточку с описанием своих возможностей:

```json
{
  "agentCard": {
    "name": "code-reviewer",
    "description": "Reviews pull requests for security and quality",
    "url": "https://agents.mycompany.com/code-review",
    "capabilities": {
      "skills": ["security-audit", "code-quality", "style-check"],
      "languages": ["python", "typescript", "go"]
    },
    "authentication": {
      "schemes": [
        {"scheme": "bearer", "format": "jwt"},
        {"scheme": "oauth2", "scopes": ["agent:execute"]}
      ]
    }
  }
}
```

Agent Card публикуется в реестре агентов (например, внутренний DNS + .well-known/agent.json).

### Task

Основная единица работы. Агент A создаёт задачу, агент B выполняет:

```json
{
  "task": {
    "id": "task-42",
    "type": "code-review",
    "input": {
      "repo": "myorg/service-x",
      "pr_number": 128,
      "files": ["src/api/handler.py", "src/api/validator.py"]
    },
    "requirements": {
      "quality": "high",
      "security_scan": true
    },
    "status": "submitted"
  }
}
```

Жизненный цикл задачи:

```
submitted → working → reviewing → completed
                              → failed
                              → needs_input (ждёт ответа от A)
```

### Artifact

Результат работы агента:

```json
{
  "artifact": {
    "id": "artifact-7",
    "task_id": "task-42",
    "parts": [
      {
        "type": "text",
        "content": "Found 3 security issues..."
      },
      {
        "type": "file",
        "mime_type": "application/json",
        "url": "https://storage/scan-results.json"
      }
    ]
  }
}
```

---

## Discovery — как агенты находят друг друга

A2A использует многоуровневое обнаружение:

```
Уровень 1: Локальный реестр
  .agents/registry.json   — список агентов в проекте

Уровень 2: DNS-based
  _agents._tcp.mycompany.com  — SRV-записи с Agent Card URL

Уровень 3: Реестр агентов
  https://agents-hub.mycompany.com   — централизованный каталог
```

Пример локального реестра:

```json
{
  "agents": [
    {
      "name": "code-reviewer",
      "card_url": "https://agents.mycompany.com/code-review/agent-card.json",
      "local": true
    },
    {
      "name": "triage-bot",
      "card_url": "https://github.com/org/triage-bot/agent-card.json",
      "local": false
    }
  ]
}
```

---

## A2A в мультиагентной архитектуре

### Паттерн: Supervisor + Specialists

```
Supervisor Agent
  │
  ├── A2A ──► Code Reviewer Agent    (проверить код)
  ├── A2A ──► Documentation Agent    (написать документацию)
  └── A2A ──► Security Scanner       (проверить уязвимости)
          │
          └── MCP ──► Snyk API       (инструмент сканера)
```

Supervisor получает задачу, создаёт подзадачи для специалистов, ожидает артефакты и агрегирует результат.

### Паттерн: Peer-to-Peer

```
Agent A ──A2A──► Agent B ──A2A──► Agent C
   ▲                                    │
   └──────────────A2A────────────────────┘
```

Агенты сами решают, кому делегировать подзадачи. Гибко, но сложно отлаживать.

### Паттерн: Pipeline

```
Agent A (data fetch) ──A2A──► Agent B (analyze) ──A2A──► Agent C (report)
```

Каждый агент выполняет один этап и передаёт результат следующему.

---

## A2A на практике

### Пример: ревью PR

```python
class SupervisorAgent:
    def handle_pr_review(self, pr_url: str):
        # 1. Найти доступных агентов
        agents = self.discover_agents(capability="code-review")

        # 2. Выбрать подходящего
        reviewer = self.select_best(agents, criteria={
            "language": "python",
            "security_scan": True
        })

        # 3. Создать задачу (A2A)
        task = self.a2a.create_task(
            agent_url=reviewer.url,
            task_type="code-review",
            input={"pr_url": pr_url}
        )

        # 4. Ждать результат
        artifact = self.a2a.wait_for_completion(task.id)

        # 5. Агрегировать
        return self.format_review(artifact)
```

### Production-соображения

1. **Таймауты** — задачи должны иметь deadline. Если агент не ответил за N секунд — fallback.
2. **Idempotency** — повторная отправка задачи не создаёт дубликат (по task.id).
3. **Retry** — при временных ошибках (500, timeout) — повтор с экспоненциальной задержкой.
4. **Circuit Breaker** — если агент стабильно падает — перестать отправлять ему задачи.
5. **Audit log** — каждая задача логируется: кто создал, кто выполнил, сколько времени заняло.

---

## Резюме

```
A2A:
  discovery → Agent Card (кто что умеет)
  communication → Task (что нужно сделать)
  result → Artifact (что получилось)
  lifecycle → submitted → working → completed/failed

MCP — это руки агента (инструменты).
A2A — это голос агента (коммуникация).
Вместе — полноценная мультиагентная система.
```

---

## Практическое задание

Реализуй коммуникацию двух агентов через A2A-протокол:

1. **TranslateAgent** — публикует Agent Card с capability: `translation` для языков `[en, ru, de, fr]`
2. **FormatAgent** — публикует Agent Card с capability: `formatting` (markdown, uppercase, lowercase)
3. Создай локальный реестр агентов (`registry.json`) с Agent Card каждого агента
4. Напиши `SupervisorAgent`, который:
   - Находит агента по capability через реестр
   - Создаёт A2A Task с типом `translation` или `formatting`
   - Получает Artifact и возвращает результат

Формат Task: `{id, type, input, status}`
Формат Artifact: `{id, task_id, parts: [{type, content}]}`

Требования: discovery через реестр, stateful Task lifecycle (submitted → working → completed), минимум 2 сценария (перевод + форматирование).

---

## Проверь себя

1. Чем A2A отличается от MCP? Когда какой использовать?
2. Какие три примитива A2A? Зачем нужен каждый?
3. Что такое Agent Card и где она публикуется?
4. Как Supervisor Agent использует A2A для координации?
5. Какие production-соображения важны для A2A (таймауты, retry, idempotency)?

---

## Ссылки

- Дальше: [[13-ecosystem-operations/01-agent-frameworks]] — сразу к фреймворкам
- После фреймворков: [[05-production/01-guardrails]] — продолжение модулей 5-12
- Назад: [[04-multi-agent/03-anti-patterns]]
- Смежно: [[07-skills/03-mcp-integration]] — MCP в сравнении с A2A

> [!tip] Что дальше?
> После мультиагентных систем (модуль 4) **рекомендуется сразу перейти к уроку 46: [[13-ecosystem-operations/01-agent-frameworks|Agent Frameworks]]** — LangGraph, CrewAI, MS Agent Framework. Это даст практические инструменты для всех последующих модулей. Не ждите модуля 13.
