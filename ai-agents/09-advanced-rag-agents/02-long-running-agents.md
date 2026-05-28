---
created: 2026-05-28
tags: [course/advanced-rag, long-running, stateful, agents]
status: active
---

# Урок 34: Long-running & Stateful Agents

> [!quote] Ключевая идея
> Демо-агент живёт 30 секунд и умирает. Production-агент работает часы, дни, недели. Он должен помнить состояние, переживать перезагрузки и корректно завершаться.

---

## Проблема stateless-агентов

Типичный агент (ReAct, Plan-and-Solve) — stateless:

```python
# Stateless агент
def run_agent(task: str) -> str:
    context = [{"role": "system", "content": SYSTEM}]
    context.append({"role": "user", "content": task})

    for _ in range(20):
        response = llm.generate(context)
        context.append({"role": "assistant", "content": response})

        if response.contains_tool_call():
            result = execute(response.tool_call)
            context.append({"role": "user", "content": str(result)})
        else:
            return response.content

    return "Max steps"
```

**Что не так:**

| Проблема | Последствие |
|----------|-------------|
| **Нет сохранения** | Упал сервер — агент умер со всем прогрессом |
| **Нет контрольных точек** | Нельзя поставить на паузу и продолжить позже |
| **Нет мониторинга** | Не видно, на каком шаге агент |
| **Ограничен lifetime** | Контекст растёт → превышение лимита токенов |
| **Нет обработки ошибок** | Любой сбой — потеря всего прогресса |

**Long-running агент** решает все эти проблемы:

- Сохраняет состояние в persistent storage
- Позволяет ставить на паузу и возобновлять
- Переживает перезагрузки процесса
- Экспоненциально не растёт в стоимости

---

## State Persistence

### Хранение состояния агента

```python
import json
import sqlite3
from datetime import datetime
from typing import Any, Optional


class AgentState:
    """Состояние агента: история, прогресс, метаданные."""

    def __init__(
        self,
        agent_id: str,
        task: str,
        plan: list[str] | None = None,
        step: int = 0,
        context: list[dict] | None = None,
        metadata: dict | None = None,
    ):
        self.agent_id = agent_id
        self.task = task
        self.plan = plan or []
        self.step = step
        self.context = context or []
        self.metadata = metadata or {}
        self.status = "created"  # created | running | paused | done | failed
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        self.error: str | None = None

    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "task": self.task,
            "plan": self.plan,
            "step": self.step,
            "context": self.context,
            "metadata": self.metadata,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AgentState":
        state = cls(
            agent_id=data["agent_id"],
            task=data["task"],
            plan=data.get("plan"),
            step=data.get("step", 0),
            context=data.get("context"),
            metadata=data.get("metadata"),
        )
        state.status = data.get("status", "created")
        state.error = data.get("error")
        if "created_at" in data:
            state.created_at = datetime.fromisoformat(data["created_at"])
        if "updated_at" in data:
            state.updated_at = datetime.fromisoformat(data["updated_at"])
        return state
```

### Storage-бэкенды

| Бэкенд | Когда использовать | Pros | Cons |
|--------|-------------------|------|------|
| **JSON file** | Прототип, 1 агент | Простота | Нет конкурентности |
| **SQLite** | Локально, несколько агентов | ACID, встроенный | Нет сети |
| **Redis** | Высокая нагрузка, распределённо | Быстро, TTL | Не ACID |
| **PostgreSQL** | Production, много агентов | ACID, индексы | Тяжелее |

#### SQLite storage

```python
class SQLiteStorage:
    """Хранение состояний агентов в SQLite."""

    def __init__(self, db_path: str = "agents.db"):
        self.conn = sqlite3.connect(db_path)
        self._init_db()

    def _init_db(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS agent_states (
                agent_id TEXT PRIMARY KEY,
                state TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_agent_status
            ON agent_states(json_extract(state, '$.status'))
        """)
        self.conn.commit()

    def save(self, state: AgentState):
        self.conn.execute(
            "INSERT OR REPLACE INTO agent_states "
            "(agent_id, state, created_at, updated_at) "
            "VALUES (?, ?, ?, ?)",
            (
                state.agent_id,
                json.dumps(state.to_dict()),
                state.created_at.isoformat(),
                state.updated_at.isoformat(),
            ),
        )
        self.conn.commit()

    def load(self, agent_id: str) -> Optional[AgentState]:
        cursor = self.conn.execute(
            "SELECT state FROM agent_states WHERE agent_id = ?",
            (agent_id,),
        )
        row = cursor.fetchone()
        if row:
            return AgentState.from_dict(json.loads(row[0]))
        return None

    def list_by_status(self, status: str) -> list[AgentState]:
        cursor = self.conn.execute(
            "SELECT state FROM agent_states WHERE "
            "json_extract(state, '$.status') = ?",
            (status,),
        )
        return [
            AgentState.from_dict(json.loads(row[0]))
            for row in cursor.fetchall()
        ]

    def delete(self, agent_id: str):
        self.conn.execute(
            "DELETE FROM agent_states WHERE agent_id = ?",
            (agent_id,),
        )
        self.conn.commit()

    def close(self):
        self.conn.close()
```

> [!important] Выбор storage
> SQLite — отличный выбор для 90% случаев. Он быстрее JSON (индексы, ACID) и не требует отдельного сервера. Redis нужен, когда у тебя 1000+ одновременных агентов.

---

## Checkpointing

**Checkpoint** — снэпшот состояния агента в конкретный момент времени. Позволяет:

- Восстановиться после сбоя
- Откатиться к предыдущему шагу
- Анализировать принятые решения

```python
class CheckpointManager:
    """Управление чекпоинтами агента."""

    def __init__(self, storage: SQLiteStorage, max_history: int = 50):
        self.storage = storage
        self.max_history = max_history

    def save_checkpoint(self, state: AgentState, reason: str = ""):
        """Сохранение чекпоинта."""

        checkpoint = state.to_dict()
        checkpoint["checkpoint_reason"] = reason
        checkpoint["checkpoint_time"] = datetime.utcnow().isoformat()

        checkpoints = self._get_checkpoints(state.agent_id)
        checkpoints.append(checkpoint)

        # Ограничение истории (чтобы не раздувать БД)
        if len(checkpoints) > self.max_history:
            checkpoints = checkpoints[-self.max_history:]

        self._save_checkpoints(state.agent_id, checkpoints)

    def restore_checkpoint(
        self, agent_id: str, step: int | None = None
    ) -> Optional[AgentState]:
        """Восстановление из чекпоинта."""

        checkpoints = self._get_checkpoints(agent_id)
        if not checkpoints:
            return None

        if step is not None:
            # Восстановиться до конкретного шага
            for cp in reversed(checkpoints):
                if cp["step"] <= step:
                    return AgentState.from_dict(cp)

        # Последний чекпоинт
        return AgentState.from_dict(checkpoints[-1])

    def rollback(
        self, agent_id: str, steps_back: int = 1
    ) -> Optional[AgentState]:
        """Откат на N шагов назад."""

        checkpoints = self._get_checkpoints(agent_id)
        if len(checkpoints) <= steps_back:
            return None

        target = checkpoints[-(steps_back + 1)]
        return AgentState.from_dict(target)

    def _get_checkpoints(self, agent_id: str) -> list[dict]:
        cursor = self.storage.conn.execute(
            "SELECT state FROM agent_states WHERE agent_id = ?",
            (f"checkpoint:{agent_id}",),
        )
        row = cursor.fetchone()
        if row:
            return json.loads(row[0])
        return []

    def _save_checkpoints(self, agent_id: str, checkpoints: list[dict]):
        self.storage.conn.execute(
            "INSERT OR REPLACE INTO agent_states "
            "(agent_id, state, created_at, updated_at) "
            "VALUES (?, ?, ?, ?)",
            (
                f"checkpoint:{agent_id}",
                json.dumps(checkpoints),
                datetime.utcnow().isoformat(),
                datetime.utcnow().isoformat(),
            ),
        )
        self.storage.conn.commit()
```

### Когда сохранять checkpoint

```python
checkpoint_manager = CheckpointManager(storage)

def run_with_checkpoints(state: AgentState):
    """Цикл агента с чекпоинтами."""

    for step in range(state.step, MAX_STEPS):
        # 1. Выполнить шаг
        result = execute_step(state, step)

        # 2. Сохранить состояние после каждого ЧЁТНОГО шага
        if step % 2 == 0:
            checkpoint_manager.save_checkpoint(
                state, reason=f"step_{step}_completed"
            )
            storage.save(state)

        # 3. Сохранять при важных событиях
        if result.is_milestone:
            checkpoint_manager.save_checkpoint(
                state, reason=f"milestone_{result.name}"
            )

        # 4. При ошибке — сохранить перед retry
        if result.is_error:
            checkpoint_manager.save_checkpoint(
                state, reason=f"error_{result.error}_before_retry"
            )
```

> [!tip] Стратегия чекпоинтов
> Не сохраняй после каждого шага — это дорого (I/O). Сохраняй:
> - После каждого N-го шага
> - После milestone (важное решение)
> - Перед потенциально опасным действием (write, delete, deploy)
> - При ошибке

---

## Async Agents & Background Tasks

Long-running агенты должны работать **асинхронно**: не блокировать пользователя, выполнять задачи в фоне, отправлять уведомления.

```python
import asyncio
from typing import Any, Callable


class AsyncAgent:
    """Агент, работающий в фоновом режиме."""

    def __init__(
        self,
        storage: SQLiteStorage,
        checkpoint_mgr: CheckpointManager,
        llm: Any,
        tools: list,
    ):
        self.storage = storage
        self.checkpoints = checkpoint_mgr
        self.llm = llm
        self.tools = {t.name: t for t in tools}
        self.tasks: dict[str, asyncio.Task] = {}

    async def start(self, agent_id: str, task: str) -> AgentState:
        """Запустить агента в фоне."""

        state = AgentState(
            agent_id=agent_id,
            task=task,
            status="running",
        )
        self.storage.save(state)

        task_obj = asyncio.create_task(
            self._run_loop(state),
            name=agent_id,
        )
        self.tasks[agent_id] = task_obj

        # Callback по завершению
        task_obj.add_done_callback(
            lambda t: self._on_complete(agent_id, t)
        )

        return state

    async def _run_loop(self, state: AgentState):
        """Основной цикл агента."""

        try:
            while state.status == "running":
                # Проверка: не отменили ли задачу
                if asyncio.current_task().cancelled():
                    state.status = "paused"
                    self.storage.save(state)
                    return

                # Выполнить шаг
                step_result = await self._execute_step(state)

                # Сохранить чекпоинт
                if state.step % 3 == 0:
                    self.checkpoints.save_checkpoint(
                        state, reason=f"step_{state.step}"
                    )
                    self.storage.save(state)

                state.step += 1

                # Проверка завершения
                if self._is_finished(step_result):
                    state.status = "done"
                    self.storage.save(state)
                    return

            state.status = "done"

        except Exception as e:
            state.status = "failed"
            state.error = str(e)
            self.storage.save(state)
            raise

        finally:
            self.storage.save(state)

    async def _execute_step(self, state: AgentState) -> dict:
        """Один шаг цикла агента (асинхронный)."""

        prompt = self._build_prompt(state)
        response = self.llm.generate(prompt)

        if response.tool_call:
            tool = self.tools[response.tool_call.name]
            # Асинхронный вызов инструмента
            result = await tool.arun(**response.tool_call.args)
            state.context.append({
                "role": "assistant",
                "content": f"Tool: {response.tool_call.name}\nResult: {result}",
            })
            return {"type": "tool", "name": response.tool_call.name}

        state.context.append({
            "role": "assistant",
            "content": response.content,
        })
        return {"type": "final", "content": response.content}

    def _build_prompt(self, state: AgentState) -> str:
        return f"Task: {state.task}\n\nStep: {state.step}\n\nPlan: {state.plan}\n\nContext: {state.context}"

    def _is_finished(self, result: dict) -> bool:
        if result["type"] == "final":
            return "FINAL" in result["content"]
        return False

    def _on_complete(self, agent_id: str, task: asyncio.Task):
        """Callback после завершения."""

        self.tasks.pop(agent_id, None)

        if task.exception():
            print(f"[{agent_id}] Failed: {task.exception()}")
            # Можно отправить webhook
            self._send_webhook(
                agent_id,
                "failed",
                str(task.exception()),
            )
        else:
            print(f"[{agent_id}] Completed")
            self._send_webhook(agent_id, "completed", "")

    def _send_webhook(self, agent_id: str, event: str, data: str):
        """Уведомление внешней системы."""

        pass  # POST на endpoint

    async def pause(self, agent_id: str) -> bool:
        """Поставить агента на паузу."""

        task = self.tasks.get(agent_id)
        if task and not task.done():
            task.cancel()
            return True
        return False

    async def resume(self, agent_id: str) -> Optional[AgentState]:
        """Возобновить агента из последнего чекпоинта."""

        state = self.checkpoints.restore_checkpoint(agent_id)
        if state:
            state.status = "running"
            self.storage.save(state)
            await self.start(agent_id, state.task)
            return state
        return None

    def get_status(self, agent_id: str) -> Optional[AgentState]:
        return self.storage.load(agent_id)
```

### Webhook-уведомления

```python
import httpx


class WebhookNotifier:
    """Уведомление внешних систем о событиях агента."""

    def __init__(self, webhook_url: str | None = None):
        self.webhook_url = webhook_url

    async def notify(self, agent_id: str, event: str, payload: dict):
        if not self.webhook_url:
            return

        async with httpx.AsyncClient() as client:
            try:
                await client.post(
                    self.webhook_url,
                    json={
                        "agent_id": agent_id,
                        "event": event,
                        "payload": payload,
                        "timestamp": datetime.utcnow().isoformat(),
                    },
                    timeout=10,
                )
            except httpx.RequestError as e:
                print(f"Webhook failed: {e}")

    async def on_step(self, agent_id: str, step: int, action: str):
        await self.notify(agent_id, "step", {"step": step, "action": action})

    async def on_complete(self, agent_id: str, result: str):
        await self.notify(agent_id, "complete", {"result": result})

    async def on_error(self, agent_id: str, error: str):
        await self.notify(agent_id, "error", {"error": error})
```

---

## Recovery: Graceful Degradation

Агент должен уметь восстанавливаться после сбоев без потери прогресса.

```python
class RecoveryManager:
    """Управление восстановлением агентов."""

    def __init__(
        self,
        storage: SQLiteStorage,
        checkpoint_mgr: CheckpointManager,
        async_agent: AsyncAgent,
        max_retries: int = 3,
    ):
        self.storage = storage
        self.checkpoints = checkpoint_mgr
        self.async_agent = async_agent
        self.max_retries = max_retries

    async def recover_all(self):
        """Восстановить всех агентов после рестарта системы."""

        agents = self.storage.list_by_status("running")

        for state in agents:
            print(f"Восстановление агента {state.agent_id}...")
            await self._recover_agent(state.agent_id)

        failed = self.storage.list_by_status("failed")
        for state in failed:
            if state.metadata.get("retries", 0) < self.max_retries:
                print(f"Перезапуск упавшего агента {state.agent_id}...")
                await self._recover_agent(state.agent_id)

    async def _recover_agent(self, agent_id: str) -> bool:
        """Восстановить одного агента."""

        state = self.checkpoints.restore_checkpoint(agent_id)
        if not state:
            print(f"Нет чекпоинта для {agent_id}, старт с начала")
            state = self.storage.load(agent_id)
            if not state:
                return False

        # Обновить метаданные
        retries = state.metadata.get("retries", 0) + 1
        state.metadata["retries"] = retries
        state.metadata["recovered_at"] = datetime.utcnow().isoformat()
        state.metadata["recovery_attempt"] = retries
        state.status = "running"
        state.error = None

        self.storage.save(state)

        # Перезапуск агента
        await self.async_agent.resume(agent_id)
        return True

    def graceful_shutdown(self):
        """Graceful shutdown: сохранить всех бегущих агентов."""

        agents = self.storage.list_by_status("running")
        for state in agents:
            self.checkpoints.save_checkpoint(
                state, reason="shutdown"
            )
            state.status = "paused"
            self.storage.save(state)
            print(f"Агент {state.agent_id} приостановлен")
```

### Graceful degradation стратегия

```
Нормальная работа
    │
    ▼
┌───────────────────┐
│ Полный функционал │  ← LLM + все инструменты
└───────────────────┘
    │
    ▼  (LLM API упал)
┌───────────────────┐
│ Fallback: cache   │  ← Отвечать из кэша, если вопрос повторяется
└───────────────────┘
    │
    ▼  (Инструмент недоступен)
┌───────────────────┐
│ Fallback:         │  ← Пропустить шаг, ответить с пометкой
│ partial answer    │    "инструмент X недоступен"
└───────────────────┘
    │
    ▼  (Всё упало)
┌───────────────────┐
│ Сохранить         │  ← Checkpoint + status = paused
│ checkpoint        │
└───────────────────┘
```

```python
class GracefulAgent(AsyncAgent):
    """Агент с graceful degradation."""

    async def _execute_step(self, state: AgentState) -> dict:
        try:
            return await super()._execute_step(state)

        except httpx.RequestError:
            # LLM API недоступен — пробуем кэш
            cached = self._check_cache(state.task, state.step)
            if cached:
                return {"type": "cached", "content": cached}

            # Включаем режим пониженной функциональности
            return self._fallback_response(state)

        except ToolExecutionError as e:
            if e.tool_required:
                # Критичный инструмент — останавливаемся
                raise

            # Некритичный — пропускаем
            state.context.append({
                "role": "system",
                "content": f"Tool {e.tool_name} unavailable, skipping step",
            })
            return {"type": "skip", "reason": str(e)}

    def _fallback_response(self, state: AgentState) -> dict:
        """Ответ без LLM (fallback-режим)."""

        return {
            "type": "fallback",
            "content": (
                "Агент временно недоступен. "
                f"Прогресс сохранён (шаг {state.step}). "
                "Попробуйте позже."
            ),
        }

    def _check_cache(self, task: str, step: int) -> str | None:
        """Проверить кэш."""
        return None
```

---

## Production-сценарий: агент анализа кода

Сборка всех компонентов в реальном сценарии:

```python
async def main():
    # Инициализация
    storage = SQLiteStorage("production_agents.db")
    checkpoints = CheckpointManager(storage)
    agent = GracefulAgent(
        storage=storage,
        checkpoint_mgr=checkpoints,
        llm=llm,
        tools=[CodeAnalyzer(), GitTool(), FileReader()],
    )
    recovery = RecoveryManager(storage, checkpoints, agent)
    webhook = WebhookNotifier("https://hooks.example.com/agents")

    # Восстановление после возможного сбоя
    await recovery.recover_all()

    # Запуск нового агента
    state = await agent.start(
        agent_id="code-review-001",
        task="Проанализировать код в PR #142: "
             "найти потенциальные баги, проверить стиль, "
             "оценить тестовое покрытие",
    )

    # Мониторинг
    while True:
        status = agent.get_status("code-review-001")
        print(f"[{status.agent_id}] Status: {status.status}, "
              f"Step: {status.step}")

        if status.status in ("done", "failed"):
            await webhook.on_complete(
                status.agent_id,
                status.status,
            )
            break

        await asyncio.sleep(5)

    # Graceful shutdown при exit
    try:
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        recovery.graceful_shutdown()
```

---

## Anti-patterns Long-running агентов

### 1. Игнорирование лимита контекста

```python
# ❌ Контекст растёт бесконтрольно
state.context.append(long_result)  # каждый шаг → больше токенов

# ✅ Суммаризация или окно
def trim_context(context: list, max_tokens: int = 32000):
    """Суммаризировать старые шаги."""
    total = count_tokens(context)
    while total > max_tokens:
        # Суммаризируем первые N сообщений
        old = context.pop(0)
        summary = llm.generate(f"Summarize: {old}")
        context.insert(0, {"role": "summary", "content": summary})
        total = count_tokens(context)
```

### 2. Слишком частые checkpoint

```python
# ❌ I/O на каждом шаге
for step in range(1000):
    result = execute(step)
    checkpoints.save(state)  # 1000 write операций
    storage.save(state)      # ещё 1000

# ✅ Баatched / interval
for step in range(1000):
    result = execute(step)
    if step % 10 == 0:
        checkpoints.save(state)
        storage.save(state)
```

### 3. Отсутствие timeout

```python
# ❌ Бесконечное ожидание
result = await tool.arun()  # может зависнуть навсегда

# ✅ С таймаутом
try:
    result = await asyncio.wait_for(
        tool.arun(), timeout=30
    )
except asyncio.TimeoutError:
    result = "TIMEOUT"
```

### 4. Необработанные исключения в async

```python
# ❌ Исключение убьёт задачу без сохранения
asyncio.create_task(run_loop())

# ✅ Сохранение ошибки
async def safe_run_loop(state):
    try:
        await run_loop(state)
    except Exception as e:
        state.status = "failed"
        state.error = str(e)
        checkpoints.save(state)
        storage.save(state)
```

> [!warning] Асинхронность ≠ параллелизм
> `asyncio` даёт кооперативную многозадачность, не настоящий параллелизм. Если нужно выполнять CPU-bound задачи параллельно — используй `concurrent.futures.ProcessPoolExecutor`.

---

## Практическое задание

Реализуй long-running агента для своего проекта:

1. Добавь `SQLiteStorage` для сохранения состояния
2. Реализуй `CheckpointManager` с сохранением каждые 5 шагов
3. Реализуй `AsyncAgent` с `pause()` / `resume()`
4. Добавь обработку ошибок: если LLM API недоступен — агент переходит в режим fallback
5. Напиши тест: запусти агента → убей процесс → восстанови из checkpoint

---

## Проверь себя

1. В чём отличие stateless-агента от stateful?
2. Какие три storage-бэкенда можно использовать для хранения состояния? Когда какой выбирать?
3. Зачем нужны checkpoint, а не просто сохранение текущего состояния?
4. Что такое graceful degradation и как она реализуется?
5. Почему нельзя сохранять состояние после каждого шага?

---

## Резюме

```
Stateful Agent = Agent + persistent storage + checkpoints + recovery

Storage:      JSON (прототип) → SQLite (default) → Redis (high-load)
Checkpoints:  снэпшоты состояния для восстановления
Async:        asyncio.create_task + webhooks
Recovery:     restore_checkpoint → resume → continue
Degradation:  full → cached → skip partial → checkpoint

Золотое правило: агент должен переживать перезагрузку сервера.
```

---

## Ссылки

- [[03-memory-and-rag/01-memory-types]] — три слоя памяти агента
- [[01-fundamentals/03-react-pattern]] — ReAct: база циклов
- [[04-multi-agent/01-orchestration]] — оркестрация долгих задач
- [[05-production/04-resilience]] — resilience и отказоустойчивость
- [[05-production/02-observability]] — мониторинг агентов
- [[09-advanced-rag-agents/01-agentic-rag]] — Agentic RAG как типичный long-running сценарий
