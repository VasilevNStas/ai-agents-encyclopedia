---
created: 2026-05-08
updated: 2026-05-28
tags: [course/multi-agent, orchestration, architecture, topology]
status: active
---

# Урок 12: Мультиагентные системы — оркестрация

> [!quote] Ключевая идея
> Один агент — это солдат. Группа агентов — это армия. Но армией нужно управлять. **Оркестрация** — это то, как агенты распределяют задачи, обмениваются результатами и избегают хаоса. Выбор топологии оркестрации — первое и самое важное архитектурное решение в мультиагентной системе.

---

## Зачем нужны несколько агентов

Один агент умеет всё, но плохо. Специализированные агенты — каждый в своей области — работают лучше.

**Проблема универсального агента:**
- Пишет код — средне
- Ищет баги — средне
- Деплоит — страшно (может удалить продакшен)
- Пишет тесты — не хочет (лень)
- Отвечает за всё — ничего не успевает

**Решение: разделение труда + оркестрация**

```
Без оркестрации:
  Agent A: "я нашёл баг в auth.py"
  Agent B: "я переписал auth.py"  ← не знал, что A его чинит
  Agent A: "я удалил твои изменения" ← конфликт

С оркестрацией:
  Supervisor назначает задачу → Agent A ищет баг
  Supervisor: "Agent A нашёл баг, Agent B — чини"
  Agent B чинит, зная контекст от A
```

---

## Каталог топологий оркестрации

### Supervisor (иерархическая)

Центральный координатор принимает решения, распределяет задачи и проверяет результаты.

```
         ┌──────────────┐
         │  Supervisor  │  ← принимает решения, распределяет задачи
         └──────┬───────┘
     ┌──────────┼──────────┐
     ▼          ▼          ▼
 ┌──────┐  ┌──────┐  ┌──────┐
 │Agent1│  │Agent2│  │Agent3│  ← специализированные исполнители
 └──────┘  └──────┘  └──────┘
       ▲          ▲          ▲
       └──────────┴──────────┘
            feedback/results
```

**Когда:** нужен чёткий контроль и аудит (деплой, code review, финансы)

**Ограничения:** supervisor — single point of failure и bottleneck

### Peer-to-peer (децентрализованная)

Агенты равны и общаются напрямую. Решения принимаются коллегиально.

```
 ┌──────┐     ┌──────┐
 │Agent1│◄───►│Agent2│
 └──┬───┘     └──┬───┘
    │            │
 ┌──▼───┐     ┌──▼───┐
 │Agent3│◄───►│Agent4│
 └──────┘     └──────┘
```

**Когда:** исследовательские задачи, brainstorming, нет единой точки контроля

**Ограничения:** сложно отлаживать, нет гарантий порядка выполнения

### Pipeline (конвейер)

Каждый агент — шаг в последовательной обработке. Выход одного — вход другого.

```
 Документ → Summarizer → Analyser → Report Generator → Отчёт
              ↑              ↑              ↑
          Agent 1        Agent 2        Agent 3
```

**Когда:** обработка данных, ETL, code review pipeline (lint → test → build → deploy)

**Ограничения:**延迟 = сумма latency всех шагов, один упал — весь конвейер встал

### Broadcast (fan-out)

Одна задача отправляется всем агентам параллельно. Результаты агрегируются.

```
          ┌──────────────┐
          │  Dispatcher  │
          └──────┬───────┘
     ┌───────────┼───────────┐
     ▼           ▼           ▼
 ┌──────┐  ┌──────┐  ┌──────┐
 │Agent1│  │Agent2│  │Agent3│  ← все получают одну задачу
 └──┬───┘  └──┬───┘  └──┬───┘
    └─────────┼──────────┘
              ▼
       ┌──────────┐
       │ Aggregator│  ← собирает и сравнивает ответы
       └──────────┘
```

**Когда:** нужна redundancy (overlap), поиск багов (мнение 3), верификация результатов

**Ограничения:** дорого (N вызовов LLM), нужен агрегатор для разрешения конфликтов

### Swarm (лидер выбирается динамически)

Агенты самоорганизуются: выбирают лидера, который координирует, пока не перестанет справляться — тогда выбирается новый.

```
  Round 1: Agent2 — лидер (больше всего контекста по задаче)
  Round 2: Agent4 — лидер (Agent2 перегружен)
  Round 3: Agent1 — лидер (специалист по текущей подзадаче)
```

**Когда:** динамические задачи, где лидерство должно меняться по ходу

**Ограничения:** сложная реализация, overhead на election, редкая практика

### Mesh (полная связность)

Каждый агент может общаться с каждым. Нет центрального координатора.

```
 ┌──────┐ ─── ┌──────┐ ─── ┌──────┐
 │Agent1│ ◄──►│Agent2│ ◄──►│Agent3│
 └──┬───┘ ─── └──┬───┘ ─── └──┬───┘
    │   ◄──►     │   ◄──►     │
 ┌──▼───┐ ─── ┌──▼───┐ ─── ┌──▼───┐
 │Agent4│ ◄──►│Agent5│ ◄──►│Agent6│
 └──────┘ ─── └──────┘ ─── └──────┘
```

**Когда:** simulation, multi-player games, complex adaptive systems

**Ограничения:** O(n²) связей, хаос без протоколов, почти не используется в production

---

## Матрица выбора топологии

| Критерий | Supervisor | Peer-to-peer | Pipeline | Broadcast | Swarm | Mesh |
|----------|:----------:|:------------:|:--------:|:---------:|:-----:|:----:|
| Контроль | ★★★★★ | ★★ | ★★★ | ★★★ | ★★ | ★ |
| Отказоуст. | ★★ | ★★★★ | ★★ | ★★★★ | ★★★★ | ★★★★ |
| Масштабир. | ★★ | ★★★ | ★★★ | ★★★ | ★★★ | ★★ |
| Простота | ★★★★★ | ★★★ | ★★★★ | ★★★ | ★ | ★ |
| Cost-эффект. | ★★★★ | ★★★ | ★★★★★ | ★★ | ★★★ | ★★ |
| Отладка | ★★★★★ | ★★ | ★★★★ | ★★★ | ★ | ★ |
| Production use | 70% | 5% | 15% | 5% | 2% | 3% |

> **Эмпирическое правило:** 70% production-систем используют Supervisor. Начни с него. Переходи к другим только если Supervisor стал узким местом.

### Decision Tree

```
Задача:
  ├── Последовательные шаги (ETL, code review)?
  │   └── Pipeline
  ├── Нужен аудит и контроль?
  │   └── Supervisor
  ├── Исследование / brainstorming?
  │   └── Peer-to-peer
  ├── Нужна redundancy / верификация?
  │   └── Broadcast + Aggregator
  ├── Динамическая смена ролей?
  │   └── Swarm
  └── Simulation / complex system?
      └── Mesh
```

---

## Supervisor: production-реализация

### Базовая архитектура

```python
from dataclasses import dataclass
from enum import Enum, auto
from queue import PriorityQueue
import asyncio
import time


class Priority(Enum):
    CRITICAL = 0   # safety, security
    HIGH = 1       # blocking bugs
    NORMAL = 2     # features
    LOW = 3        # chores


@dataclass
class Task:
    id: str
    description: str
    priority: Priority
    context: dict
    deadline: float | None = None
    depends_on: list[str] | None = None


@dataclass
class AgentSpec:
    name: str
    capabilities: list[str]
    max_concurrent_tasks: int = 1
    timeout_seconds: int = 60


class Supervisor:
    """Универсальный supervisor для production-мультиагентных систем."""

    def __init__(self):
        self.agents: dict[str, AgentSpec] = {}
        self.task_queue: PriorityQueue = PriorityQueue()
        self.active_tasks: dict[str, Task] = {}
        self.results: dict[str, dict] = {}
        self.registry: dict[str, int] = {}  # task_id → agent

    def register_agent(self, agent: AgentSpec):
        self.agents[agent.name] = agent

    def submit_task(self, task: Task):
        """Добавляет задачу в очередь с приоритетом."""
        self.task_queue.put((task.priority.value, task))

    def _select_agent(self, task: Task) -> str | None:
        """Выбирает агента по capability и текущей загрузке."""
        candidates = []
        for name, spec in self.agents.items():
            if any(cap in task.description for cap in spec.capabilities):
                active = self.registry.get(name, 0)
                if active < spec.max_concurrent_tasks:
                    candidates.append((active, name))

        if not candidates:
            return None

        # Агент с наименьшей загрузкой
        candidates.sort()
        return candidates[0][1]

    async def run_cycle(self):
        """Основной цикл: берёт задачу → назначает → собирает результат."""
        while not self.task_queue.empty():
            _, task = self.task_queue.get()

            # Проверка зависимостей
            if task.depends_on:
                missing = [d for d in task.depends_on if d not in self.results]
                if missing:
                    # Возвращаем в очередь — зависимости ещё не выполнены
                    self.task_queue.put((task.priority.value, task))
                    continue

            agent = self._select_agent(task)
            if agent is None:
                # Нет свободных агентов — возвращаем в очередь
                self.task_queue.put((task.priority.value, task))
                continue

            # Назначаем задачу
            self.active_tasks[task.id] = task
            self.registry[agent] = self.registry.get(agent, 0) + 1

            try:
                result = await asyncio.wait_for(
                    self._execute(agent, task),
                    timeout=self.agents[agent].timeout_seconds,
                )
                self.results[task.id] = {"status": "done", "result": result}
            except asyncio.TimeoutError:
                self.results[task.id] = {"status": "timeout", "error": f"{agent} timed out"}
            except Exception as e:
                self.results[task.id] = {"status": "error", "error": str(e)}
            finally:
                self.registry[agent] -= 1
                self.active_tasks.pop(task.id, None)

    async def _execute(self, agent_name: str, task: Task) -> dict:
        """Выполняет задачу агентом. В реальности — A2A или MCP-вызов."""
        agent = self.agents[agent_name]
        return {
            "agent": agent_name,
            "task": task.id,
            "output": f"[{agent_name}] processed: {task.description}",
            "timestamp": time.time(),
        }
```

### Escalation pipeline

Когда агент не справляется — задача эскалируется более сильному агенту.

```python
class EscalationSupervisor(Supervisor):
    """Supervisor с эскалацией: junior → senior → human."""

    TIERS = ["junior", "senior", "lead", "human"]

    def __init__(self):
        super().__init__()
        self.agents_by_tier = {
            "junior": ["coder-bot", "test-bot"],
            "senior": ["senior-coder", "senior-reviewer"],
            "lead": ["lead-architect"],
            "human": ["human-approver"],
        }

    async def execute_with_escalation(self, task: Task) -> dict:
        """Пытается выполнить задачу на каждом уровне эскалации."""
        errors = []

        for tier in self.TIERS:
            for agent_name in self.agents_by_tier.get(tier, []):
                try:
                    result = await asyncio.wait_for(
                        self._execute(agent_name, task),
                        timeout=30,
                    )
                    result["escalation_tier"] = tier
                    return result
                except Exception as e:
                    errors.append(f"{agent_name}: {e}")
                    continue

        return {
            "status": "escalated_to_human",
            "task": task.id,
            "errors": errors,
        }
```

### Consensus pattern

Несколько агентов решают одну задачу — результат определяется голосованием.

```python
class ConsensusSupervisor(Supervisor):
    """Три агента решают задачу. Результат — majority vote."""

    MIN_VOTES = 2  # сколько совпадений нужно для консенсуса
    MIN_AGENTS = 3

    async def run_with_consensus(self, task: Task) -> dict:
        """Запускает N агентов на одной задаче и собирает консенсус."""
        agents = list(self.agents.keys())
        if len(agents) < self.MIN_AGENTS:
            raise ValueError(f"Нужно минимум {self.MIN_AGENTS} агента, есть {len(agents)}")

        # Все агенты получают одну задачу
        tasks = [self._execute(agent, task) for agent in agents[:self.MIN_AGENTS]]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Анализ результатов
        votes = {}
        for r in results:
            if isinstance(r, Exception):
                continue
            # Упрощённый fingerprint результата
            fingerprint = str(r)[:100]  # первые 100 символов
            votes[fingerprint] = votes.get(fingerprint, 0) + 1

        # Majority vote
        winner = max(votes, key=votes.get)
        if votes[winner] >= self.MIN_VOTES:
            return {"status": "consensus", "result": winner, "votes": votes}
        else:
            return {"status": "no_consensus", "votes": votes}
```

---

## Production-соображения

### State persistence

```python
class PersistentSupervisor(Supervisor):
    """Supervisor с сохранением состояния между запусками."""

    def __init__(self, db_path: str = "supervisor_state.json"):
        super().__init__()
        self.db_path = db_path
        self._load_state()

    def _load_state(self):
        try:
            import json
            with open(self.db_path) as f:
                data = json.load(f)
                self.results = data.get("results", {})
                self.registry = data.get("registry", {})
        except FileNotFoundError:
            pass

    def _save_state(self):
        import json
        with open(self.db_path, "w") as f:
            json.dump({
                "results": self.results,
                "registry": self.registry,
            }, f, indent=2)

    async def run_cycle(self):
        await super().run_cycle()
        self._save_state()
```

### Graceful degradation

```python
class DegradableSupervisor(Supervisor):
    """Supervisor, который не падает, а деградирует при отказе агентов."""

    async def run_cycle(self):
        alive_agents = {}

        for name, spec in self.agents.items():
            if await self._health_check(name):
                alive_agents[name] = spec
            else:
                print(f"[WARN] Agent {name} is down — excluding from pool")

        if not alive_agents:
            # Даже если все агенты упали — не падаем, а ждём
            print("[WARN] All agents down — waiting for recovery")
            await asyncio.sleep(30)
            return

        self.agents = alive_agents
        await super().run_cycle()

    async def _health_check(self, agent_name: str) -> bool:
        """Проверяет, отвечает ли агент."""
        try:
            # ping-запрос к агенту
            await asyncio.wait_for(self._ping(agent_name), timeout=5)
            return True
        except Exception:
            return False

    async def _ping(self, agent_name: str) -> str:
        """Заглушка для ping. В реальности — A2A health check."""
        return f"{agent_name}: ok"
```

### Resource management

```python
@dataclass
class ResourceBudget:
    """Бюджет ресурсов на одну сессию."""
    max_tokens: int = 100_000
    max_cost_usd: float = 1.00
    max_steps: int = 50
    max_duration_seconds: int = 300


class BudgetedSupervisor(Supervisor):
    """Supervisor с контролем бюджета на задачу."""

    def __init__(self, budget: ResourceBudget):
        super().__init__()
        self.budget = budget
        self.tokens_used = 0
        self.cost_usd = 0.0
        self.steps_taken = 0
        self.start_time: float | None = None

    async def run_cycle(self):
        self.start_time = time.time()
        while not self.task_queue.empty():
            if not self._within_budget():
                self._log_budget_exceeded()
                break
            await super().run_cycle()

    def _within_budget(self) -> bool:
        if self.tokens_used >= self.budget.max_tokens:
            return False
        if self.cost_usd >= self.budget.max_cost_usd:
            return False
        if self.steps_taken >= self.budget.max_steps:
            return False

        elapsed = time.time() - self.start_time
        if elapsed >= self.budget.max_duration_seconds:
            return False

        return True

    def _log_budget_exceeded(self):
        print(f"""
[BUDGET_EXCEEDED]
  tokens:   {self.tokens_used}/{self.budget.max_tokens}
  cost:     ${self.cost_usd:.2f}/${self.budget.max_cost_usd:.2f}
  steps:    {self.steps_taken}/{self.budget.max_steps}
  duration: {time.time() - self.start_time:.0f}s/{self.budget.max_duration_seconds}s
""")
```

---

## Антипаттерны оркестрации

### 1. Supervisor-микроменеджер

```python
# ❌ Supervisor решает КАЖДЫЙ чих агента
class BadSupervisor:
    def run(self, task):
        while True:
            action = self.agents["code"].decide_next_action()
            if self._approve(action):  # микроменеджмент
                self.agents["code"].execute(action)

# ✅ Supervisor контролирует результат, а не процесс
class GoodSupervisor:
    async def run(self, task):
        result = await self.agents["code"].execute(task)
        return self._review_result(result)
```

### 2. Все агенты имеют доступ ко всему

```python
# ❌ Каждый агент может сделать всё что угодно
AGENT_PERMISSIONS = {
    "code_agent":  ["read", "write", "deploy", "delete", "admin"],
    "debug_agent": ["read", "write", "deploy", "delete", "admin"],
    "test_agent":  ["read", "write", "deploy", "delete", "admin"],
}

# ✅ Принцип минимальных привилегий
AGENT_PERMISSIONS = {
    "code_agent":  ["read", "write", "git_commit"],
    "debug_agent": ["read", "grep", "run_tests"],
    "deploy_agent": ["deploy", "restart", "rollback"],
    "test_agent":  ["read", "run_tests", "write_test_files"],
}
```

### 3. Слишком много агентов

```python
# ❌ 20 агентов для «напиши hello world»
agents = [CodeAgent(), TestAgent(), ReviewAgent(), LintAgent(),
          DocAgent(), DeployAgent(), MonitorAgent(), ...]

# ✅ Добавляй агента ТОЛЬКО когда есть причина
1 агент  → не справляется? → 2 агента (разделение)
2 агента → путаются?       → Supervisor
Supervisor → тормозит?      → асинхронная коммуникация
```

### 4. Агент-дублёр

Task registry предотвращает дублирование задач:

```python
task_registry = {}

def assign_task(task_id: str, agent_name: str):
    if task_id in task_registry:
        raise ValueError(f"Задача {task_id} уже выполняется {task_registry[task_id]}")
    task_registry[task_id] = agent_name
```

### 5. Deadlock (циклическое ожидание)

```
Agent1: ждёт Agent2 → Agent2: ждёт Agent3 → Agent3: ждёт Agent1
```

Решение: граф зависимостей + timeout + детекция циклов (DFS).

### 6. Потеря контекста при handoff

```python
# ❌ Контекст потерян
Agent1 → Agent2: "почини баг"

# ✅ Структурированный handoff
handoff = {
    "task": "fix bug in auth.py:42",
    "context": {
        "what_is_broken": "token validation skipped before DB query",
        "already_tried": ["checked line 40-45", "confirmed bug exists"],
        "relevant_files": ["auth.py:42", "db.py:15"],
        "suggested_fix": "add `if not token: return 401` at line 40"
    },
    "constraints": {
        "must_pass_tests": True,
        "no_new_dependencies": True,
    }
}
```

### 7. Нет наблюдаемости

```python
# ❌ Чёрный ящик
while True:
    agent.run(task)

# ✅ Каждый шаг логируется
async def run_with_observability(agent, task):
    step = 0
    while True:
        log(f"Step {step}: executing {task}")
        result = await agent.run(task)
        log(f"Step {step}: result = {result[:100]}...")
        log(f"Step {step}: cost = ${calculate_cost(result)}")
        step += 1
```

---

## Резюме

```
Топологии оркестрации (по частоте в production):
  Supervisor (70%)  — контроль и аудит
  Pipeline (15%)    — последовательные шаги
  Peer-to-peer (5%) — исследовательские задачи
  Broadcast (5%)    — redundancy / верификация
  Swarm (2%)        — динамическая смена лидера
  Mesh (3%)         — simulation

Production Supervisor:
  - Приоритетная очередь задач
  - Выбор агента по capability + загрузке
  - Эскалация: junior → senior → human
  - Консенсус: majority vote для верификации
  - State persistence (переживает рестарт)
  - Graceful degradation (не падает при отказе)
  - Resource budget (лимиты на токены, cost, duration)

Правило архитектора:
  1. Начни с одного агента
  2. Добавь Supervisor когда агентов > 2
  3. Контролируй результат, а не процесс
  4. Каждый агент — минимальные привилегии
  5. Handoff — только структурированный (не теряй контекст)
  6. Наблюдаемость — с первого дня
  7. Бюджет — всегда (токены, cost, время)
```

---

## Практическое задание

1. Возьми свою текущую задачу с 2+ агентами
2. Пройди по decision tree из 12.3 — какая топология подходит?
3. Реализуй Supervisor с приоритетной очередью
4. Добавь эскалацию: если агент не справился за 30s — передай другому
5. Добавь budget control: останавливай цикл при превышении лимита cost

---

## Проверь себя

1. Какие 6 топологий оркестрации существуют? Какая самая частая в production?
2. Что делает Supervisor с задачей, от которой зависят другие?
3. Зачем нужен приоритет в очереди задач? Приведи пример.
4. Как работает escalation pipeline? Почему он важен?
5. В чём разница между микроменеджментом и контролем результата?
6. Как Consensus Supervisor отличается от обычного?
7. Что должно произойти при превышении resource budget?
8. Как PersistentSupervisor восстанавливает состояние после рестарта?

---

## Ссылки

- Дальше: [[04-multi-agent/02-communication]] — протоколы общения между агентами
- Дальше: [[13-ecosystem-operations/01-agent-frameworks]] — фреймворки (LangGraph, CrewAI)
- Назад: [[03-memory-and-rag/05-vector-databases]]
- [[04-multi-agent/04-a2a-protocol]] — A2A протокол для меж-агентского общения
- [[05-production/02-observability]] — наблюдаемость мультиагентных систем
