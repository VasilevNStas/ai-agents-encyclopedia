---
created: 2026-05-28
tags: [course/langgraph, tools, function-calling, architect]
status: active
---

# LangGraph L02: Tools & Function Calling в графах

> [!quote] Ключевая идея
> В уроке 6 (Tool Use & Function Calling) инструменты вызывались в цикле. LangGraph добавляет слой: **ToolNode** — стандартизированный узел для вызова инструментов с автоматической маршаллизацией аргументов, обработкой ошибок и параллельным выполнением.

---

## ToolNode — стандартный узел инструментов

Вместо ручного парсинга `tool_calls`:

```python
# Было (урок 6):
for tc in response.tool_calls:
    name = tc.function.name
    args = json.loads(tc.function.arguments)
    result = globals()[name](**args)
    messages.append({"role": "tool", "content": str(result)})
```

Используем `ToolNode`:

```python
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_core.tools import tool


# 1. Определяем инструменты как @tool
@tool
def search_knowledge_base(query: str) -> str:
    """Search the company knowledge base for relevant information."""
    return f"Results for: {query}"


@tool
def get_weather(city: str, units: str = "celsius") -> str:
    """Get current weather for a city."""
    return f"Weather in {city}: 22°{units[0].upper()}"


@tool
def calculate(expression: str) -> str:
    """Evaluate a mathematical expression."""
    return str(eval(expression))


# 2. Собираем в список
tools = [search_knowledge_base, get_weather, calculate]

# 3. ToolNode — автоматически:
#    - парсит tool_calls из последнего сообщения
#    - вызывает соответствующий @tool
#    - возвращает ToolMessage с результатом
tool_node = ToolNode(tools)
```

**Что делает ToolNode:**
- Читает `message.tool_calls` из последнего AI message
- Маппит имя функции на зарегистрированный инструмент
- Валидирует аргументы (Pydantic-схемы)
- Выполняет параллельно, если несколько tool_calls
- Возвращает `ToolMessage` для каждого вызова

---

## Маршрутизация: tools_condition

`tools_condition` — built-in conditional edge, заменяющий `should_continue`:

```python
from langgraph.prebuilt import tools_condition

builder.add_conditional_edges(
    "think",
    tools_condition,  # если есть tool_calls → "tools", иначе → END
)
```

**Что делает tools_condition:**
```python
def tools_condition(state: AgentState) -> Literal["tools", END]:
    messages = state["messages"]
    if messages and hasattr(messages[-1], "tool_calls") and messages[-1].tool_calls:
        return "tools"
    return END
```

---

## Параллельные вызовы инструментов

Современные модели (GPT-4, Claude Sonnet 4.6, DeepSeek) могут вызывать **несколько инструментов в одном ответе**. ToolNode выполняет их параллельно:

```python
# LLM возвращает:
# tool_calls = [
#   {"name": "search_kb", "args": {"query": "pricing"}},
#   {"name": "get_weather", "args": {"city": "Berlin"}},
#   {"name": "calculate", "args": {"expression": "1500 * 0.85"}}
# ]

# ToolNode.execute_parallel → все три одновременно
# Результаты приходят как 3 ToolMessage → в messages
```

```python
# Кастомный контроль параллелизма
from langgraph.prebuilt import ToolNode


class RateLimitedToolNode(ToolNode):
    """ToolNode с ограничением параллельных вызовов."""

    def __init__(self, tools, max_parallel: int = 2):
        super().__init__(tools)
        self.max_parallel = max_parallel

    async def ainvoke(self, state, config=None, **kwargs):
        messages = state["messages"]
        last = messages[-1]
        calls = last.tool_calls

        if len(calls) <= self.max_parallel:
            return await super().ainvoke(state, config, **kwargs)

        # Батчим по max_parallel
        results = []
        for i in range(0, len(calls), self.max_parallel):
            batch = calls[i:i + self.max_parallel]
            last.tool_calls = batch
            batch_result = await super().ainvoke(state, config, **kwargs)
            results.append(batch_result)

        return self._merge_results(results)
```

---

## Обработка ошибок в инструментах

В production инструменты падают. LangGraph позволяет добавить fallback-логику прямо в граф:

```python
from langgraph.graph import StateGraph, START, END


def safe_call_tool(state: AgentState) -> AgentState:
    """Вызов инструмента с обработкой ошибок."""
    try:
        result = tool_node.invoke(state)
        return result
    except Exception as e:
        # Инструмент упал — возвращаем сообщение об ошибке
        return {
            "messages": [
                ToolMessage(
                    content=f"ToolError: {str(e)}",
                    tool_call_id=state["messages"][-1].tool_calls[0].id,
                )
            ],
            "errors": [str(e)],
        }


def should_retry(state: AgentState) -> Literal["tools", "think", "end"]:
    """Решение: retry, переформулировать или ответить с ошибкой."""
    last = state["messages"][-1]
    if isinstance(last, ToolMessage) and "ToolError" in last.content:
        if state.get("retries", 0) < 3:
            return "tools"  # повторить
        else:
            return "think"  # сообщить пользователю
    return "end"
```

**Стратегии обработки ошибок:**

| Стратегия | Условие | Результат |
|-----------|---------|-----------|
| Retry | Временная ошибка (timeout) | Повторить тот же вызов |
| Reformulate | Ошибка аргументов | LLM переформулирует запрос |
| Skip | Опциональный инструмент | Пропустить и продолжить |
| Escalate | Критическая ошибка | Передать человеку |

---

## Практика: агент с 3 инструментами в LangGraph

Собери граф с:
1. Тремя инструментами (search, calculator, file_read)
2. ToolNode для автоматического выполнения
3. `tools_condition` для маршрутизации
4. Обработкой ошибок (retry 2 раза)
5. Ограничением: максимум 5 вызовов инструментов за сессию

```python
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_core.tools import tool
from typing import TypedDict, Annotated, Literal
import operator


@tool
def search(query: str) -> str:
    """Search internal documentation."""
    return f"Searching: {query}"


@tool
def calculator(expression: str) -> str:
    """Calculate math expression."""
    return str(eval(expression))


@tool
def read_file(path: str) -> str:
    """Read file contents."""
    with open(path) as f:
        return f.read()


tools = [search, calculator, read_file]
tool_node = ToolNode(tools)


class AgentState(TypedDict):
    messages: Annotated[list, operator.add]
    tool_calls_count: int
    errors: Annotated[list, operator.add]


def think(state: AgentState) -> AgentState:
    response = llm.invoke(state["messages"])
    return {"messages": [response]}


def should_continue(
    state: AgentState,
) -> Literal["tools", "think", "end"]:
    """Маршрутизация с лимитом на tool calls."""
    if state["tool_calls_count"] >= 5:
        return "end"  # превышен лимит

    route = tools_condition(state)
    if route == "tools":
        return "tools"
    return "end"


# Сборка графа
builder = StateGraph(AgentState)

builder.add_node("think", think)
builder.add_node("tools", tool_node)

builder.add_edge(START, "think")
builder.add_conditional_edges("think", should_continue, {
    "tools": "tools",
    "end": END,
})
builder.add_edge("tools", "think")

graph = builder.compile()
```

---

## Инструменты с конфигурацией

Для production инструментам нужен контекст: кто вызвал, какой tenant, какой budget:

```python
from langchain_core.tools import tool
from langgraph.prebuilt import InjectedToolArg
from typing import Annotated


@tool
def search_restricted(
    query: str,
    user_id: Annotated[str, InjectedToolArg],
    max_results: Annotated[int, InjectedToolArg] = 5,
) -> str:
    """Search documents, scoped to user's access level."""
    # user_id и max_results приходят из конфигурации, не от LLM
    access_level = get_user_access(user_id)
    results = vector_store.search(query, top_k=max_results)
    filtered = [r for r in results if r.access_level <= access_level]
    return str(filtered)


# При вызове агента:
config = {"configurable": {"user_id": "usr_42", "max_results": 3}}
graph.invoke({"messages": [user_msg]}, config)
```

---

## Резюме

```
ToolNode:
  - автоматический парсинг tool_calls
  - параллельное выполнение
  - Pydantic-валидация аргументов
  
tools_condition:
  - стандартный conditional edge
  - "tools" если есть tool_calls → END

Production:
  - RateLimitedToolNode для контроля параллелизма
  - safe_call_tool с retry/reformulate/escalate
  - InjectedToolArg для контекста
```

---

## Проверь себя

1. Чем ToolNode отличается от ручного вызова инструментов?
2. Как tools_condition определяет, вызывать инструмент или завершить?
3. Зачем нужен `InjectedToolArg`? Приведи пример.
4. Какие стратегии обработки ошибок инструментов ты знаешь?
5. Напиши ToolNode, который логирует каждый вызов инструмента в `state["trace"]`.

---

## Ссылки

- [[01-graph-basics]] — предыдущий урок: основы графов
- [[03-memory-persistence]] — следующий урок: память и checkpointing
- [[../../../06-prompt-engineering/03-structured-output]] — как LLM формирует tool_calls
