---
created: 2026-05-28
updated: 2026-05-28
tags: [course/ecosystem, langchain, crewai, autogen, frameworks]
status: active
---

# Урок 46: Agent Frameworks — LangGraph, CrewAI, AutoGen и другие

> [!quote] Ключевая идея
> Писать агента с нуля — как писать веб-сервер без фреймворка: можно, но дорого. LangGraph, CrewAI, AutoGen, Semantic Kernel — каждый решает свою задачу. LangGraph — для сложных stateful workflow, CrewAI — для role-based команд агентов, AutoGen — для conversational collaboration, Semantic Kernel — для enterprise на .NET. Выбор фреймворка — это архитектурное решение, не вопрос «что моднее».

> [!tip] Когда изучать этот урок
> Формально модуль 13 — заключительный. Но фреймворки можно и нужно изучать сразу после модуля 4 (мультиагентные системы). Это даст возможность экспериментировать с инструментами на протяжении всего курса, а не только в конце.

---

## Ландшафт фреймворков в 2026

```
┌────────────────────────────────────────────────────────┐
│  Agent Frameworks 2026                                  │
├───────────────────┬──────────────────┬─────────────────┤
│  LangGraph        │  CrewAI          │  MS Agent F/W   │
│  (LangChain Inc.) │  (CrewAI Inc.)   │  (Microsoft)     │
│                   │                  │                  │
│  Graph-based      │  Role-based      │  Conversational  │
│  State machine    │  Agent crews     │  + plugins       │
│                   │                  │                  │
│  16K+ stars       │  28K+ stars      │  GA April 2026  │
│  MIT license      │  MIT license     │  MIT license     │
├───────────────────┴──────────────────┴─────────────────┤
│  niche:                                                 │
│  LlamaIndex (RAG-first) · Pydantic AI (type-safe)      │
│  Claude Agent SDK (Anthropic-native) · Haystack (RAG)   │
└────────────────────────────────────────────────────────┘
```

---

## LangGraph — промышленный стандарт

LangGraph (от создателей LangChain) — де-факто стандарт для production agent-ов в 2026. Его ключевое отличие: **явный граф состояний**.

**Архитектура:** Агент — это граф, где узлы — шаги (think, call_tool, evaluate), а рёбра — переходы. Граф может быть цикличным (retry, escalation).

```python
from langgraph.graph import StateGraph, END
from typing import TypedDict, Literal


class AgentState(TypedDict):
    messages: list
    next_step: str
    retries: int


# Определяем узлы
def think(state: AgentState) -> AgentState:
    """Агент думает, что делать дальше."""
    response = llm.invoke(state["messages"])
    state["messages"].append(response)
    return state


def call_tool(state: AgentState) -> AgentState:
    """Вызывает инструмент."""
    tool_name = extract_tool_name(state["messages"][-1])
    result = tools[tool_name].run()
    state["messages"].append({"role": "tool", "content": result})
    return state


def should_continue(state: AgentState) -> Literal["tools", "end"]:
    """Определяет, продолжать или завершить."""
    last = state["messages"][-1]
    if "FINAL_ANSWER" in last.content:
        return "end"
    return "tools"


# Строим граф
graph = StateGraph(AgentState)

graph.add_node("think", think)
graph.add_node("call_tool", call_tool)

graph.set_entry_point("think")
graph.add_conditional_edges("think", should_continue, {
    "tools": "call_tool",
    "end": END,
})
graph.add_edge("call_tool", "think")

app = graph.compile()
```

**Что даёт граф:**
- **Checkpointing** — состояние сохраняется после каждого узла (SQLite, Postgres). Можно прервать, возобновить, отладить «путешествием во времени»
- **Human-in-the-loop** — interrupt перед опасным шагом, ждём approval
- **LangSmith observability** — полная трассировка каждого запуска

**Когда выбирать:**
- Сложные, stateful, ветвящиеся workflow
- Нужен HITL и checkpointing
- Production-grade observability

**Когда НЕ выбирать:**
- Простой агент «вопрос-ответ» (overkill)
- Нужно за 1 день (крутая кривая обучения)

---

## CrewAI — команды агентов

CrewAI моделирует агентов как **роли в команде**. Ты описываешь: «кто эти агенты, какие у них задачи, как они общаются» — фреймворк делает всё остальное.

```python
from crewai import Agent, Task, Crew

# Агент-исследователь
researcher = Agent(
    role="Senior Research Analyst",
    goal="Find the latest AI trends and breakthroughs",
    backstory="You're a curious researcher who loves technology",
    tools=[search_tool, web_scraper],
    verbose=True,
)

# Агент-писатель
writer = Agent(
    role="Technical Writer",
    goal="Create engaging blog posts from research",
    backstory="You transform complex topics into readable content",
    tools=[write_tool],
)

# Задачи для агентов
research_task = Task(
    description="Research the latest AI breakthroughs in 2026",
    expected_output="A comprehensive list of top 5 breakthroughs",
    agent=researcher,
)

write_task = Task(
    description="Write a blog post about the research findings",
    expected_output="A 1500-word blog post in markdown",
    agent=writer,
)

# Собираем команду
crew = Crew(
    agents=[researcher, writer],
    tasks=[research_task, write_task],
    process="sequential",  # или hierarchical, parallel
)

result = crew.kickoff()
```

**Когда выбирать:**
- Мультиагентные системы с чёткими ролями
- Быстрое прототипирование (2-3 дня до working prototype)
- Product-команда должна читать workflow

**Когда НЕ выбирать:**
- Одиночный агент
- Сложные stateful workflow (нет checkpointing)
- Нужна тонкая observability

---

## Microsoft Agent Framework (ex-AutoGen + Semantic Kernel)

В апреле 2026 Microsoft объединил AutoGen и Semantic Kernel в единый **Microsoft Agent Framework 1.0 GA**. Один SDK для .NET и Python.

**Два режима:**

1. **Conversational (ex-AutoGen):** Агенты общаются через GroupChat с speaker selection. Хорошо для исследовательских сценариев, где решение рождается в диалоге.

```python
from autogen_agentchat import Agent, GroupChat

class AnalystAgent(Agent):
    async def handle_message(self, msg, context):
        # Анализирует данные
        return {"analysis": "..."}

class CriticAgent(Agent):
    async def handle_message(self, msg, context):
        # Критикует анализ
        return {"critique": "..."}

chat = GroupChat(
    agents=[AnalystAgent(), CriticAgent()],
    max_rounds=10,
)
result = await chat.run("Analyze this dataset")
```

2. **Plugin-based (ex-Semantic Kernel):** Агент с planner, который цепляет плагины. Для enterprise / .NET команд.

```csharp
// Semantic Kernel — C# first
var builder = Kernel.CreateBuilder();
builder.AddOpenAIChatCompletion("gpt-5.4");
builder.Plugins.AddFromType<DatabasePlugin>();

var kernel = builder.Build();

var result = await kernel.InvokePromptAsync(
    "Find all users who signed up last month",
);
```

**Когда выбирать:**
- Уже на Microsoft / Azure инфраструктуре
- Нужна первая поддержка C# и Python
- Conversational multi-agent experiments

---

## Сравнительная таблица

| Характеристика | LangGraph | CrewAI | MS Agent F/W | LlamaIndex | Pydantic AI |
|---------------|:---------:|:------:|:------------:|:----------:|:-----------:|
| Языки | Python, JS | Python | C#, Python, Java | Python, TS | Python |
| Абстракция | Граф состояний | Роли + задачи | Чат + плагины | RAG-агенты | Type-safe |
| Multi-agent | Явный граф | Crew (roles) | GroupChat | Sub-questions | ❌ |
| State | Checkpointing | Task passing | History | Index-based | ❌ |
| Observability | LangSmith | Базовая | Azure Monitor | ❌ | ❌ |
| HITL | ✅ Встроенный | Через код | ✅ Встроенный | ❌ | ❌ |
| Production Score* | 8.9/10 | 8.5/10 | 7.8/10 | 7.0/10 | 6.5/10 |
| Когда брать | Stateful сложное | Быстрый multi-agent | .NET / Azure | RAG-first | Type-safe Python |

*Alice Labs Production Score на основе 18+ production деплоев.

---

## Decision Tree

```python
def choose_framework(
    is_multi_agent: bool,
    need_checkpointing: bool,
    need_hitl: bool,
    fast_prototype: bool,
    dotnet_team: bool,
    rag_first: bool,
) -> str:
    """Выбирает фреймворк по параметрам проекта."""

    if dotnet_team:
        return "Microsoft Agent Framework (.NET)"

    if rag_first and not is_multi_agent:
        return "LlamaIndex"

    if fast_prototype and is_multi_agent:
        return "CrewAI"                        # 2-3 дня до прототипа

    if need_checkpointing or need_hitl:
        return "LangGraph"                     # единственный с HITL

    if is_multi_agent:
        return "MS Agent Framework (Python)"   # conversational

    # Одиночный, без сложного state
    if not is_multi_agent:
        return "Pydantic AI"                   # type-safe, лёгкий

    return "LangGraph"                         # fallback — стандарт
```

---

## Одна задача, три фреймворка

Лучший способ понять разницу — реализовать одну задачу в каждом фреймворке. Возьмём **PR Review**: агент получает PR, проверяет код на баги и стиль, возвращает отчёт.

### LangGraph: граф состояний

```python
from langgraph.graph import StateGraph, END
from typing import TypedDict, Literal
import json


class ReviewState(TypedDict):
    pr_files: list[dict]
    issues: list[dict]
    review_report: str
    step: str


def fetch_pr(state: ReviewState) -> ReviewState:
    """Читает файлы из PR."""
    files = []
    for f in state["pr_files"]:
        content = read_file(f["path"])
        files.append({**f, "content": content})
    state["pr_files"] = files
    return state


def analyze_code(state: ReviewState) -> ReviewState:
    """Запускает статический анализ каждого файла."""
    issues = []
    for f in state["pr_files"]:
        analysis = llm.invoke(
            f"Review this {f['language']} code for bugs and style:\n"
            f"```{f['language']}\n{f['content']}\n```"
        )
        issues.append({
            "file": f["path"],
            "analysis": analysis.content,
        })
    state["issues"] = issues
    return state


def generate_report(state: ReviewState) -> ReviewState:
    """Агрегирует все замечания в единый отчёт."""
    report = llm.invoke(
        f"Aggregate these reviews into a structured report:\n"
        f"{json.dumps(state['issues'], indent=2)}"
    )
    state["review_report"] = report.content
    return state


def route(state: ReviewState) -> Literal["analyze", "report", "end"]:
    """Маршрутизация: от какого шага к какому."""
    if state["step"] == "fetch":
        return "analyze"
    elif state["step"] == "analyze":
        return "report"
    return "end"


# Сборка графа
builder = StateGraph(ReviewState)
builder.add_node("fetch", fetch_pr)
builder.add_node("analyze", analyze_code)
builder.add_node("report", generate_report)
builder.set_entry_point("fetch")
builder.add_conditional_edges("fetch", route)
builder.add_conditional_edges("analyze", route)
builder.add_edge("report", END)

app = builder.compile()

# Запуск
result = app.invoke({
    "pr_files": [
        {"path": "src/auth.py", "language": "python"},
        {"path": "src/api.ts", "language": "typescript"},
    ],
    "issues": [],
    "review_report": "",
    "step": "fetch",
})
```

**Что здесь происходит:** мы явно описываем граф (fetch → analyze → report), каждый шаг — чистая функция, состояние сохраняется и может быть прервано в любой точке (checkpointing). Если упал analyze — restart с analyze, не с fetch.

### CrewAI: роли и задачи

```python
from crewai import Agent, Task, Crew


# Определяем агентов как роли
linter = Agent(
    role="Senior Code Linter",
    goal="Find all style violations, anti-patterns, and potential bugs",
    backstory="You have 15 years of experience reviewing code for quality",
    verbose=True,
)

security_auditor = Agent(
    role="Security Auditor",
    goal="Find security vulnerabilities including injection, XSS, auth bypass",
    backstory="You're a certified security engineer with OWASP expertise",
)

report_writer = Agent(
    role="Technical Report Writer",
    goal="Aggregate findings into a clear, actionable review report",
    backstory="You translate complex technical issues into readable reports",
)

# Задачи для каждого агента
lint_task = Task(
    description=(
        "Review the following files for code quality, style, and bugs:\n"
        "- src/auth.py (Python)\n"
        "- src/api.ts (TypeScript)\n\n"
        "Focus on: naming conventions, error handling, code duplication"
    ),
    expected_output="List of style violations and code quality issues with line numbers",
    agent=linter,
)

security_task = Task(
    description=(
        "Audit these files for security vulnerabilities:\n"
        "- src/auth.py\n- src/api.ts\n\n"
        "Focus on: SQL injection, XSS, authentication bypass, unsafe parsing"
    ),
    expected_output="List of security vulnerabilities with severity levels",
    agent=security_auditor,
)

report_task = Task(
    description=(
        "Combine the lint and security findings into a structured report.\n"
        "Group by severity: CRITICAL, HIGH, MEDIUM, LOW\n"
        "Include file paths and suggested fixes."
    ),
    expected_output="A formatted markdown report with all findings grouped by severity",
    agent=report_writer,
)

# Собираем crew
review_crew = Crew(
    agents=[linter, security_auditor, report_writer],
    tasks=[lint_task, security_task, report_task],
    process="sequential",  # lint → security → report
)

result = review_crew.kickoff()
```

**Что здесь происходит:** мы описываем «кто эти люди» (role, goal, backstory) и «что они делают» (tasks). CrewAI сам решает, как агенты общаются и передают результаты. Кода в 2 раза меньше, чем LangGraph, но контроль меньше.

### Microsoft Agent Framework: conversational

```python
from autogen_agentchat import Agent, GroupChat


class LintAgent(Agent):
    async def handle_message(self, msg, context):
        # Проверка стиля
        return {"type": "lint_result", "findings": [
            {"file": "src/auth.py", "line": 42, "issue": "Line too long"},
            {"file": "src/api.ts", "line": 15, "issue": "Missing return type"},
        ]}


class SecurityAgent(Agent):
    async def handle_message(self, msg, context):
        # Аудит безопасности
        return {"type": "security_result", "findings": [
            {"file": "src/auth.py", "line": 7, "issue": "Hardcoded secret",
             "severity": "CRITICAL"},
        ]}


class ReporterAgent(Agent):
    async def handle_message(self, msg, context):
        # Сборка отчёта
        findings = context.get("all_findings", [])
        return {"type": "report", "content": self._format_report(findings)}

    def _format_report(self, findings):
        lines = ["# PR Review Report\n"]
        for f in findings:
            lines.append(f"- **{f['severity']}** {f['file']}:{f['line']} — {f['issue']}")
        return "\n".join(lines)


# Групповой чат — агенты обсуждают PR и приходят к консенсусу
chat = GroupChat(
    agents=[LintAgent(), SecurityAgent(), ReporterAgent()],
    max_rounds=5,
)

result = await chat.run("Review PR #128: src/auth.py, src/api.ts")
```

**Что здесь происходит:** агенты общаются через GroupChat. Каждый получает сообщение, обрабатывает и передаёт дальше. Это не pipeline (как CrewAI), а именно диалог — агенты могут уточнять, спорить, соглашаться.

### Сравнение подходов

| Аспект | LangGraph | CrewAI | MS Agent F/W |
|--------|:---------:|:------:|:------------:|
| Строк кода | ~60 | ~35 | ~50 |
| Контроль потока | ★★★★★ | ★★★ | ★★★ |
| Простота чтения | ★★★ | ★★★★★ | ★★★ |
| Отладка | ★★★★★ (checkpoint) | ★★ | ★★★ |
| Гибкость | ★★★★★ | ★★★ | ★★★ |
| Когда переходить | Production | Prototype | .NET shop |

**Эмпирическое правило:** начни с CrewAI (3 дня до прототипа), затем мигрируй на LangGraph (production), если нужен контроль.

---

## Миграция между фреймворками

### CrewAI → LangGraph (prototype → production)

Переход происходит, когда:
- Прототип работает, но нужно checkpointing и HITL
- Агенты делают не то, что вы хотели (нужен явный граф)
- Выросла стоимость — нужно тонкое управление контекстом

```python
# Шаг 1: Выделяем чистую бизнес-логику из CrewAI
def analyze_file(file_path: str, language: str) -> list[dict]:
    """Чистая функция — тестируем без фреймворка."""
    content = read_file(file_path)
    response = llm.invoke(
        f"Review this {language} code:\n```{language}\n{content}\n```"
    )
    return parse_issues(response)

# Шаг 2: Оборачиваем в LangGraph для координации
class MigrationState(TypedDict):
    files: list[dict]
    results: dict
    report: str

def analyze_node(state: MigrationState) -> MigrationState:
    for f in state["files"]:
        key = f["path"]
        state["results"][key] = analyze_file(key, f["language"])
    return state
```

### LangGraph → CrewAI (overkill → simplicity)

Обратный переход — когда LangGraph избыточен:

```python
# Было: 10 узлов в графе для задачи «напиши письмо»
# Стало: 1 Crew с 2 агентами и sequential process

crew = Crew(
    agents=[writer, editor],
    tasks=[draft_task, polish_task],
    process="sequential",
)
```

**Правило:** если в графе меньше 4 узлов и нет циклов — фреймворк с графом избыточен.

### Microsoft Agent Framework → LangGraph (vendor → open)

Когда уходите с Azure или нужны возможности, которых нет в MS F/W:

```python
# Замена GroupChat на граф
# Вместо: агенты общаются через чат, порядок不确定
# Стало: явный граф с известными переходами
```

---

## Антипаттерны фреймворков (расширенно)

### 1. Фреймворк как единственный источник правды
```python
# ❌ Вся логика внутри LangGraph — невозможно отлаживать
app = graph.compile()

# ✅ Чистая бизнес-логика вне фреймворка
def business_logic(data):  # тестируем отдельно
    ...

# LangGraph только координирует вызовы
```

### 2. Слишком ранний выбор фреймворка
```python
# ❌ "Давайте сразу на LangGraph" — а нужно было просто два вызова LLM

# ✅ Сначала — чистые функции и LLM вызовы
# Потом — фреймворк, когда complexity требует
```

### 3. Игнорировать governance
Фреймворк не остановит опасный вызов инструмента. Всегда добавляй governance layer (guardrails, audit, approval) поверх фреймворка.

### 4. CrewAI без мониторинга
```python
# ❌ CrewAI запущен, агенты общаются — но никто не видит, что они делают
# Через час — $500 токенов, а результат непонятен

# ✅ Всегда LangSmith или логгирование каждого шага
```

### 5. LangGraph: over-engineering простых задач
```python
# ❌ Граф из 10 узлов для задачи «переведи текст с русского на английский»
class TranslationState(TypedDict):
    text: str
    detected_lang: str
    translated: str
    validated: str
    step: str

# 5 узлов, 4 conditional edges, checkpointing — для одного вызова LLM

# ✅ Простой вызов функции
def translate(text: str) -> str:
    return llm.invoke(f"Translate to English: {text}")
```

**Признак:** ты тратишь больше времени на описание графа, чем на бизнес-логику. **Лечение:** начни с функций, добавь граф когда появится ветвление.

### 6. CrewAI: magic-зависимости

CrewAI скрывает много деталей. Это удобно, пока не сломается:

```python
# ❌ Магия: непонятно, как агенты общаются, в каком порядке,
# передаётся ли контекст, сколько токенов потрачено
result = crew.kickoff()

# ✅ Требуй явности:
crew = Crew(
    agents=[...],
    tasks=[...],
    process="sequential",  # или hierarchical
    verbose=True,          # логировать каждый шаг
    memory=True,           # явно включать память
)
```

**Признак:** `crew.kickoff()` и молитва. **Лечение:** включи `verbose=True`, смотри логи, проверяй каждый шаг.

### 7. MS Agent Framework: vendor lock-in неявно

```python
# ❌ Используем специфичные для .NET фичи (C# first)
var planner = new SequentialPlanner(kernel);
var context = await planner.CreatePlanAsync(goal);

# Через год: хотим уйти с Azure — нужно переписывать всё
```

**Признак:** использование Azure-specific фич (Azure AI Search, Cosmos DB, Azure Monitor) напрямую, без абстракции. **Лечение:** оборачивай инфраструктуру в интерфейсы, чтобы можно было заменить.

### 8. Нет границы между framework и приложением

```python
# ❌ Как тестировать? Непонятно.
app = graph.compile()
result = app.invoke(input_data)

# ✅ Чёткая граница: бизнес-логика отдельно, фреймворк — обёртка
def business_rule(data):  # тестируется без LangGraph
    ...

nodes = {"process": lambda s: business_rule(s)}
```

**Признак:** unit-тесты требуют компиляции графа. **Лечение:** бизнес-логика — чистые функции, граф — только координация.

---

## Практическое задание

Реализуй задачу «проверка орфографии и грамматики текста» в двух фреймворках:

**CrewAI:**
- Создай двух агентов: `SpellChecker` (проверяет орфографию) и `GrammarChecker` (проверяет грамматику)
- Каждый возвращает список ошибок с исправлениями
- `ReportCompiler` собирает единый отчёт

**LangGraph:**
- Реализуй ту же задачу как граф состояний: check_spelling → check_grammar → compile_report
- Добавь checkpointing после каждого шага

Требования: оба решения должны принимать один и тот же входной текст и возвращать отчёт в одинаковом формате. Сравни количество строк кода и сложность отладки.

---

## Проверь себя

1. Какие три основных фреймворка для agent-ов в 2026?
2. Чем LangGraph отличается от CrewAI по подходу?
3. Что даёт checkpointing в LangGraph?
4. Когда выбирать Microsoft Agent Framework?
5. Почему не стоит сразу выбирать фреймворк?
6. Какой антипаттерн самый дорогой при использовании CrewAI?
7. В чём разница в реализации одной и той же задачи (PR review) в LangGraph vs CrewAI vs MS Agent Framework?
8. Когда нужно мигрировать с CrewAI на LangGraph?
9. Какой признак того, что LangGraph избыточен для задачи?
10. Как отделить бизнес-логику от фреймворка — и зачем?

---

## Резюме

```
Выбор фреймворка = задача × команда × production requirements

Сложный stateful workflow → LangGraph (checkpointing, HITL)
Быстрый multi-agent team  → CrewAI (роли, 2 дня до прототипа)
Conversational / .NET     → Microsoft Agent Framework
RAG-first                 → LlamaIndex
Type-safe простой агент   → Pydantic AI

Миграция:
  CrewAI → LangGraph (prototype → production)
  LangGraph → CrewAI (overkill → simplicity)
  MS F/W → LangGraph (vendor → open)

Антипаттерны:
  ❌ Фреймворк как единственный источник правды
  ❌ Слишком ранний выбор фреймворка
  ❌ LangGraph over-engineering
  ❌ CrewAI magic (kickoff and pray)
  ❌ MS vendor lock-in
  ❌ Нет границы между framework и бизнес-логикой
  ❌ Нет наблюдаемости

Правило: сначала чистые функции, потом фреймворк.
         Governance поверх фреймворка — обязательно.
         Наблюдаемость (LangSmith) — с первого дня.
         Мигрируй когда нужно, а не потому что «модно».
```

---

## Ссылки

- [[04-multi-agent/01-orchestration]] — оркестрация мультиагентных систем
- [[04-multi-agent/02-communication]] — коммуникация между агентами
- [Agent Frameworks Comparison 2026](https://alicelabs.ai/en/insights/open-source-ai-agent-frameworks-comparison-2026)
- [LangGraph vs CrewAI vs AutoGen 2026](https://turion.ai/blog/langgraph-vs-crewai-vs-autogen-comparison-2026/)
