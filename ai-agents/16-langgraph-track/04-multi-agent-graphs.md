---
created: 2026-05-28
tags: [course/langgraph, multi-agent, supervisor, orchestration, architect]
status: active
---

# LangGraph L04: Multi-Agent Graphs

> [!quote] Ключевая идея
> В уроке 12 (Оркестрация) мы обсуждали 6 топологий мультиагентных систем. LangGraph реализует их как **композицию графов**: каждый агент — свой граф, Supervisor — граф, который вызывает другие графы. Это даёт изоляцию, переиспользование и тестируемость на каждом уровне.

---

## Supervisor — граф, управляющий графами

Supervisor — это граф, который решает, какому агенту делегировать задачу:

```python
from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.prebuilt import ToolNode


# === Sub-agent: Code Reviewer ===
# Каждый агент — самостоятельный граф
code_review_builder = StateGraph(MessagesState)
code_review_builder.add_node("think", code_review_think)
code_review_builder.add_node("tools", ToolNode(code_review_tools))
code_review_builder.add_edge(START, "think")
code_review_builder.add_conditional_edges("think", tools_condition, {
    "tools": "tools",
    END: END,
})
code_review_builder.add_edge("tools", "think")
code_review_graph = code_review_builder.compile()


# === Supervisor: Agent Router ===
class SupervisorState(TypedDict):
    messages: Annotated[list, operator.add]
    active_agent: str
    task: str


def supervisor_router(state: SupervisorState) -> AgentState:
    """Выбирает агента на основе задачи."""
    task = state["task"]
    prompt = f"""You are a supervisor. Route this task to the right agent.
Available agents:
- code_review: analyze code, find bugs, suggest fixes
- security_audit: check for vulnerabilities, injections
- research: search docs, find information

Task: {task}

Respond with the agent name ONLY."""

    response = llm.invoke(prompt)
    agent_name = response.content.strip().lower()
    return {"active_agent": agent_name}
```

---

## Agent Teams: параллельная работа

Сценарий: код-ревью требует одновременно проверить качество кода, безопасность и стиль:

```python
from langgraph.types import Send


class ReviewState(TypedDict):
    pr_description: str
    code_diff: str
    reviews: Annotated[list, operator.add]
    final_report: str


def distribute_review(state: ReviewState):
    """Запускает трёх агентов параллельно."""
    return [
        Send("code_review",  # узел графа
             {"task": state["pr_description"],
              "code": state["code_diff"],
              "focus": "quality"}),
        Send("security_scan",
             {"task": state["pr_description"],
              "code": state["code_diff"],
              "focus": "security"}),
        Send("style_check",
             {"task": state["pr_description"],
              "code": state["code_diff"],
              "focus": "style"}),
    ]


# Сборка
builder = StateGraph(ReviewState)
builder.add_node("code_review", code_review_node)
builder.add_node("security_scan", security_node)
builder.add_node("style_check", style_node)
builder.add_node("aggregator", aggregator_node)

# Fan-out: после дистрибутора все три агента запускаются параллельно
builder.add_conditional_edges(START, distribute_review, [
    "code_review", "security_scan", "style_check"
])

# Fan-in: после завершения всех трёх → aggregator
builder.add_edge(["code_review", "security_scan", "style_check"], "aggregator")
builder.add_edge("aggregator", END)
```

**Send** — ключевой механизм LangGraph для параллельного запуска. Создаёт N экземпляров узла, каждый со своим state.

---

## Handoff: передача задачи между агентами

Когда агент A понимает, что задача требует экспертизы агента B:

```python
@tool
def handoff_to_specialist(agent_name: str, task: str) -> str:
    """Transfer task to a specialist agent.
    
    Args:
        agent_name: one of [security_expert, data_analyst, legal_review]
        task: clear description of what needs to be done
    """
    # Эта функция — не обычный инструмент, а триггер перехода
    # LangGraph intercepts этот вызов и перенаправляет граф
    return f"Handing off to {agent_name}: {task}"


class HandoffState(TypedDict):
    messages: Annotated[list, operator.add]
    current_agent: str
    handoff_queue: Annotated[list, operator.add]


def route_handoff(state: HandoffState) -> str:
    """Маршрутизация на основе handoff."""
    last = state["messages"][-1]
    if hasattr(last, "tool_calls"):
        for tc in last.tool_calls:
            if tc.function.name == "handoff_to_specialist":
                args = json.loads(tc.function.arguments)
                state["handoff_queue"].append(args)
                return args["agent_name"]
    return "respond"


builder = StateGraph(HandoffState)
builder.add_node("general_agent", general_handler)
builder.add_node("security_expert", security_handler)
builder.add_node("data_analyst", data_handler)
builder.add_node("legal_review", legal_handler)
builder.add_node("respond", final_response)

builder.add_edge(START, "general_agent")
builder.add_conditional_edges("general_agent", route_handoff, {
    "security_expert": "security_expert",
    "data_analyst": "data_analyst",
    "legal_review": "legal_review",
    "respond": "respond",
})
# Каждый специалист возвращает управление
for specialist in ["security_expert", "data_analyst", "legal_review"]:
    builder.add_edge(specialist, "general_agent")
builder.add_edge("respond", END)
```

**Антипаттерн:** бесконечная передача между агентами. Всегда добавляй лимит handoff-ов:

```python
def route_with_limit(state: HandoffState) -> str:
    if len(state["handoff_queue"]) >= 5:
        return "respond"
    return route_handoff(state)
```

---

## Shared State: общее состояние команды

В мультиагентной системе агенты должны видеть результат работы друг друга:

```python
class TeamState(TypedDict):
    # Общее для всех
    task: str
    findings: Annotated[list, operator.add]  # все агенты добавляют
    messages: Annotated[list, operator.add]

    # Приватное для каждого (неймспейс по агенту)
    agent_states: dict[str, dict]


def research_agent(state: TeamState) -> TeamState:
    """Агент видит findings других, добавляет свои."""
    context = "\n".join(state.get("findings", []))
    result = llm.invoke(f"Task: {state['task']}\nContext: {context}\nResearch:")
    return {
        "findings": [f"[research] {result.content}"],
        "agent_states": {"research": {"status": "done"}},
    }
```

**Правило:** агенты читают shared state, пишут в свои ключи. Конфликтов нет, потому что каждый ключ — отдельный reducer.

---

## Supervisor с динамическим составом

Архитектура: Supervisor выбирает не только агента, но и **создаёт** его:

```python
class DynamicTeamState(TypedDict):
    task: str
    team: dict[str, callable]  # имя агента → его граф
    results: Annotated[dict, operator.add]


def assemble_team(state: DynamicTeamState) -> DynamicTeamState:
    """Supervisor динамически собирает команду под задачу."""
    prompt = f"""Assemble a team for this task: {state['task']}
Available specialists: code_review, security, research, data_analyst, legal
Choose 1-3 agents. Return as JSON list."""

    response = llm.invoke(prompt)
    selected = json.loads(response.content)
    team = {name: agent_registry[name] for name in selected}
    return {"team": team}


def dispatch(state: DynamicTeamState):
    """Send task to all selected agents in parallel."""
    return [Send(name, {"task": state["task"], "results": {}})
            for name in state["team"]]
```

---

## Supervisor против Peer-to-Peer

| Аспект | Supervisor | Peer-to-Peer |
|--------|-----------|--------------|
| Сложность | Централизованная логика | Децентрализованная |
| Масштабирование | Supervisor может стать bottleneck | Линейное |
| Отладка | Вся маршрутизация в одном месте | Нужно трассировать все пары |
| Гибкость | Предсказуемое поведение | Адаптивное, но хаотичное |
| Когда использовать | Enterprise, compliance | Research, exploration |

**Выбор архитектора:** 80% production-систем используют Supervisor. Peer-to-Peer — для research-агентов и simulation.

---

## Практика: multi-review система

Собери мультиагентную систему для code review:
1. **Supervisor** — получает PR и распределяет по агентам
2. **Code Quality Agent** — проверяет логику, дублирование, тесты
3. **Security Agent** — ищет injection, утечки, уязвимости
4. **Style Agent** — проверяет форматирование, именование
5. **Aggregator** — собирает все отзывы в итоговый отчёт

```python
# Шаблон для практики
builder = StateGraph(ReviewState)

# TODO: добавить узлы
# builder.add_node("supervisor", ...)
# builder.add_node("quality", ...)
# builder.add_node("security", ...)
# builder.add_node("style", ...)
# builder.add_node("aggregator", ...)

# TODO: добавить fan-out через Send
# builder.add_conditional_edges(...)

# TODO: добавить fan-in
# builder.add_edge(...)

graph = builder.compile()
```

---

## Резюме

```
Multi-agent в LangGraph:

Supervisor = граф, который вызывает графы
Send = параллельный fan-out (N копий одного узла)
Handoff = передача задачи между агентами через инструмент
Fan-in = сбор результатов от N узлов в один
Shared state = общее состояние + приватные неймспейсы

Антипаттерны:
- Бесконечный handoff (всегда ставь лимит)
- Supervisor без fallback (всегда default route)
- Слепая вера в ответы агентов (нужна верификация)
```

---

## Проверь себя

1. Как Send реализует parallel fan-out?
2. Чем Supervisor отличается от Peer-to-Peer топологии?
3. Когда handoff через инструмент лучше, чем conditional edge?
4. Как избежать бесконечного цикла handoff-ов?
5. Спроектируй граф для системы из 4 агентов: исследователь → аналитик → писатель → редактор.

---

## Ссылки

- [[03-memory-persistence]] — предыдущий урок: память
- [[05-production-streaming]] — следующий урок: streaming, production
- [[../../../04-multi-agent/01-orchestration]] — теория оркестрации (урок 12)
