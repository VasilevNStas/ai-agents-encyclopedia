---
created: 2026-05-09
tags: [course/skills, mcp, tools, ecosystem]
status: active
---

# Урок 27: MCP — Model Context Protocol

> [!quote] Ключевая идея
> MCP (Model Context Protocol) — это стандарт подключения внешних инструментов к LLM. Если skills — это инструкции для ассистента, то MCP — это **инструменты**, которые ассистент может вызывать. Вместе они образуют экосистему расширений.

---

## Что такое MCP

MCP (Model Context Protocol) — открытый протокол, который позволяет LLM вызывать внешние инструменты через единый интерфейс.

```
LLM (DeepSeek, Claude, GPT)
    │
    │ MCP Protocol (JSON-RPC over stdio/HTTP)
    │
    ▼
┌──────────────────────────────────────┐
│         MCP Server                    │
│  (предоставляет инструменты)          │
│                                       │
│  Инструменты:                         │
│  ├── search_files                     │
│  ├── read_database                    │
│  ├── send_slack_message               │
│  └── run_sql_query                    │
└──────────────────────────────────────┘
```

---

## MCP vs Skills

| Критерий | Skills | MCP |
|----------|--------|-----|
| Что это | Инструкции для ассистента | Инструменты для вызова |
| Формат | Markdown-файл | JSON-RPC сервер |
| Что делает | Меняет поведение LLM | Расширяет возможности LLM |
| Пример | `skill("brainstorming")` | `search_files("*.py")` |
| Зависит от | OpenCode | Любой MCP-клиент |

**Вместе:**
- Skills говорят **как** делать
- MCP инструменты говорят **чем** делать

---

## Типы MCP серверов

### File System
```json
{
  "tools": [
    {
      "name": "read_file",
      "description": "Читает файл по пути",
      "parameters": {
        "path": {"type": "string"}
      }
    },
    {
      "name": "write_file",
      "parameters": {
        "path": {"type": "string"},
        "content": {"type": "string"}
      }
    }
  ]
}
```

### Database
```json
{
  "tools": [
    {
      "name": "query_sql",
      "description": "Выполняет SQL запрос (только SELECT)",
      "parameters": {
        "query": {"type": "string"}
      }
    }
  ]
}
```

### Web / API
```json
{
  "tools": [
    {
      "name": "web_search",
      "description": "Поиск в интернете",
      "parameters": {
        "query": {"type": "string"}
      }
    },
    {
      "name": "web_fetch",
      "parameters": {"url": {"type": "string"}}
    }
  ]
}
```

### Communication
```json
{
  "tools": [
    {
      "name": "send_slack",
      "description": "Отправить сообщение в Slack",
      "parameters": {
        "channel": {"type": "string"},
        "message": {"type": "string"}
      }
    },
    {
      "name": "send_email",
      "parameters": {
        "to": {"type": "string"},
        "subject": {"type": "string"},
        "body": {"type": "string"}
      }
    }
  ]
}
```

---

## Как MCP меняет архитектуру агента

Без MCP:

```
Агент → hardcoded инструменты (только то, что в коде)
     или → bash (опасно, неструктурированно)
```

С MCP:

```
Агент → MCP Server (File System) → read/write файлы
     → MCP Server (Database)     → SQL запросы
     → MCP Server (Slack)        → отправка сообщений
     → MCP Server (Browser)      → веб-скрейпинг
```

Каждый MCP сервер — это **плагин**, который можно добавить или убрать без изменения кода агента.

---

## MCP + Skills = полная экосистема

```python
# 1. Загружаем skill для методологии
skill("systematic-debugging")

# 2. Skill говорит: используй эти инструменты
# 3. Инструменты предоставлены MCP серверами

def debug_bug(bug_report: str):
    # Шаг 1 (из skill): найти файлы
    files = mcp_call("filesystem", "search_files", {"pattern": "**/*.py"})

    # Шаг 2 (из skill): прочитать подозрительный файл
    content = mcp_call("filesystem", "read_file", {"path": files[0]})

    # Шаг 3 (из skill): поискать похожие баги
    similar = mcp_call("database", "query_sql", {
        "query": "SELECT * FROM bugs WHERE status = 'open'"
    })

    # Шаг 4 (из skill): отправить результат
    mcp_call("slack", "send_message", {
        "channel": "#bugs",
        "message": f"Found bug in {files[0]}"
    })
```

---

## Эcосистема расширений

```
OpenCode / Агент
    │
    ├── Skills (инструкции)
    │   ├── brainstorming
    │   ├── debugging
    │   ├── writing-plans
    │   └── кастомные (из проекта)
    │
    └── MCP (инструменты)
        ├── File System
        ├── Database
        ├── Web Search
        ├── Slack / Email
        ├── GitHub
        └── кастомные (напиши сам)
```

---

## Резюме

```
Skills = как делать (методология)
MCP    = чем делать (инструменты)

Вместе образуют экосистему расширений:
  - Skills меняют поведение LLM
  - MCP расширяют возможности LLM
  - И то, и другое — плагины (подключаются по необходимости)
```

---

## Практическое задание

1. Опиши JSON Schema для MCP-сервера, который предоставляет инструмент `search_code` с параметрами: `query` (string, required), `language` (string, optional), `max_results` (integer, optional, default=10).

2. Возьми любой MCP-сервер из урока (File System, Database, Web Search) и напиши Python-функцию, которая вызывает его через `mcp_call`. Добавь обработку ошибок и логирование вызова.

---

## Проверь себя

1. Чем MCP отличается от Skills?
2. Какие типы MCP серверов существуют?
3. Как MCP меняет архитектуру агента?
4. Что даёт комбинация Skills + MCP?

---

## Ссылки

- [MCP Specification](https://modelcontextprotocol.io)
- Назад: [[07-skills/01-opencode-skills]]
- [[../../../opencode-skills/index|opencode-skills — полный курс]]
- [[skills/prompt-engineer.skill.md]] — пример skill из проекта
