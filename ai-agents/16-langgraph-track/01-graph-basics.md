---
created: 2026-05-28
tags: [course/langgraph, langgraph, graph, state, architect]
status: active
---

# LangGraph L01: Graph Architecture & State Management

> [!quote] Ключевая идея
> LangGraph — это не «ещё один фреймворк для агентов». Это **графовая машина состояний**, где каждый узел — шаг логики, а каждое ребро — явное условие перехода. В отличие от циклов с `while True`, граф даёт предсказуемость, тестируемость и наблюдаемость.

---

## Проблема: почему `while True` — не архитектура

В уроках 1-3 мы строили ReAct-цикл как `while True: think → act → observe`. Это работает для прототипа, но в production:

```python
# Антипаттерн: неявный цикл
def react_loop(task: str):
    context = [{"role": "user", "content": task}]
    while True:
        response = llm.invoke(context)
        if response.tool_calls:
            for tc in response.tool_calls:
                result = execute_tool(tc)
                context.append({"role": "tool", "content": result})
        else:
            return response.content
```

Проблемы:
- **Где мы в цикле?** Неизвестно — нет явного состояния
- **Что может пойти не так?** Никаких guardrails между шагами
- **Как отладить шаг 5?** Только логи — нет снэпшотов состояния
- **Как вставить human-in-the-loop?** Нужно переписывать цикл

LangGraph решает это: **граф — это явная спецификация всех возможных путей агента.**

---

## Графовая модель агента

Каждый агент — это **ориентированный граф**:

```
[Вход] → [Узел: think] → [Узел: call_tool] → [Узел: evaluate] → [Выход]
                │                                      │
                └──── conditional_edge("нужен ли ещё    │
                         вызов инструмента?") ←─────────┘
```

Три элемента:
| Элемент | Описание |
|---------|----------|
| **State** | TypedDict — всё состояние агента на текущий момент |
| **Node** | Функция: принимает state, возвращает обновлённый state |
| **Edge** | Связь между узлами. Conditional edge = if-логика |

---

## Первый граф: ReAct в LangGraph

```python
from langgraph.graph import StateGraph, START, END
from typing import TypedDict, Literal, Annotated, Sequence
import operator


# === State ===
class AgentState(TypedDict):
    messages: Annotated[Sequence[dict], operator.add]
    next_step: str
    retries: int
    tool_results: Annotated[Sequence[str], operator.add]


# === Nodes ===
def think(state: AgentState) -> AgentState:
    """Агент решает, что делать дальше."""
    response = llm.invoke(state["messages"])
    return {"messages": [response]}


def call_tool(state: AgentState) -> AgentState:
    """Выполняет вызов инструмента."""
    last_msg = state["messages"][-1]
    tool_name = last_msg.tool_calls[0].function.name
    tool_args = last_msg.tool_calls[0].function.arguments
    result = tools[tool_name].invoke(tool_args)
    return {"tool_results": [f"{tool_name}: {result}"]}


# === Conditional Edge ===
def should_continue(state: AgentState) -> Literal["tools", "end"]:
    """Определяет маршрут: ещё инструмент или ответ."""
    last = state["messages"][-1]
    if hasattr(last, "tool_calls") and last.tool_calls:
        return "tools"
    return "end"


# === Graph ===
builder = StateGraph(AgentState)

builder.add_node("think", think)
builder.add_node("tools", call_tool)

builder.add_edge(START, "think")
builder.add_conditional_edges(
    "think",
    should_continue,
    {"tools": "tools", "end": END}
)
builder.add_edge("tools", "think")

graph = builder.compile()
```

> [!note] Что здесь происходит
> 1. `AgentState` — явная схема: что агент хранит между шагами
> 2. `think` — узел рассуждения (вызов LLM)
> 3. `call_tool` — узел выполнения инструмента
> 4. `should_continue` — conditional edge: если есть tool_calls → на узел tools, иначе → END
> 5. START и END — константы графа

### Преимущества перед циклом

| Аспект | `while True` | LangGraph |
|--------|-------------|-----------|
| Состояние | Неявное (переменная context) | Явное (TypedDict) |
| Поток управления | Скрыт в коде | Визуальный граф |
| Тестирование | Интеграционное (весь цикл) | Поузловое (каждый node) |
| Human-in-loop | Переписывать цикл | Interrupt-точки на узлах |
| Мониторинг | Логи | Снэпшоты состояния на каждом шаге |

---

## State Reducers: как обновлять состояние

State в LangGraph иммутабелен. Каждый узел возвращает **изменения**, которые применяются через **reducers**.

```python
from typing import Annotated
import operator


class AgentState(TypedDict):
    # default: replace (перезаписать)
    next_step: str

    # operator.add: добавить в список
    messages: Annotated[list, operator.add]
    trace: Annotated[list, operator.add]

    # Кастомный reducer
    retries: Annotated[int, lambda current, update: current + update]
```

**Паттерны reducers:**

| Reducer | Поведение | Когда использовать |
|---------|-----------|-------------------|
| `operator.add` | Сложение (для int) / конкатенация (для list) | Счётчики, история сообщений |
| `operator.set` | Замена (по умолчанию) | Текущий шаг, флаги |
| `mesage_add` | Добавление сообщения с проверкой дубликатов | Список сообщений |
| Кастомная функция | Любая логика | Валидация при обновлении |

```python
def retry_reducer(current: int, update: int) -> int:
    """Не даёт retries уйти в отрицательные значения."""
    return max(0, current + update)


class SafeState(TypedDict):
    retries: Annotated[int, retry_reducer]
```

---

## Практика: конвертируй существующий ReAct-агент

Возьми код ReAct-цикла из урока 3 ([[../../../03-react-pattern|Урок 3: ReAct]]). Перепиши его как граф LangGraph:

1. Определи `AgentState` — какие поля нужны
2. Разбей цикл на узлы: `think`, `act`, `observe`
3. Добавь conditional edge для маршрутизации
4. Добавь guardrails как отдельный узел между `think` и `act`

**Критерии:**
- Граф должен компилироваться (`builder.compile()`)
- После каждого шага состояние должно быть наблюдаемо
- Добавь узел `validate` перед END, который проверяет ответ

---

## Когда граф — это overkill

LangGraph не всегда нужен:

```
Простой LLM-call (без цикла)    → не нужен граф
Одношаговый агент с 1 тулом      → можно обычный код
3-шаговый ReAct                  → граф полезен
10-шаговый мультиагент           → граф необходим
Production с HITL и canary       → граф обязателен
```

> [!tip] Правило архитектора
> Если агент делает больше 3 шагов или вызывает больше 2 инструментов — используй граф. Если меньше — обычный код даст ту же предсказуемость с меньшими затратами.

---

## Резюме

```
LangGraph:
  StateGraph(StateSchema) → builder.add_node() → add_edge() → compile()
  
  State = TypedDict с reducers
  Node = функция (state → partial state update)
  Edge = связь; conditional = функция-маршрутизатор
  
  START → [...] → END — все пути графа явные
```

---

## Проверь себя

1. Чем StateGraph отличается от простого `while True`?
2. Зачем нужны reducers? Что будет, если не указать reducer для списка?
3. Как conditional edge решает проблему «куда идти дальше»?
4. Когда граф — overkill?
5. Перепиши conditional edge `should_continue` так, чтобы он ограничивал max 5 шагов.

---

## Ссылки

- [[02-tools-calling]] — следующий урок: инструменты и Function Calling в LangGraph
- [[../../../03-react-pattern|Урок 3: ReAct паттерн]] — оригинальный ReAct для сравнения
- [LangGraph Documentation: State](https://langchain-ai.github.io/langgraph/concepts/high_level/)
