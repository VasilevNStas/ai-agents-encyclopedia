---
created: 2026-05-28
tags: [course/memory-systems-deep, memgpt, letta, os, virtual-context]
status: active
---

# Урок 24.2: Agentic Memory — MemGPT / Letta

> [!quote] Ключевая идея
> MemGPT (ныне Letta) перевернул парадигму: вместо «запихнуть историю в контекст» он ввёл операционную систему памяти. LLM — это CPU, память — иерархический storage, функции — syscalls. Агент сам решает, что хранить в рабочей памяти, а что выгрузить.

---

## 1. Letta Architecture

```python
class LettaAgent:
    """Letta (MemGPT): операционная система памяти для LLM."""

    def __init__(self, model, config: dict = None):
        self.model = model
        self.memory = MemoryHierarchy()
        self.context_window = ContextManager(max_tokens=128000)
        self.scheduler = MemoryScheduler()

    async def step(self, user_message: str) -> str:
        """Один шаг агента с управлением памятью."""

        # 1. Build context: рабочая память + релевантные воспоминания
        context = await self.context_window.build(self.memory, user_message)

        # 2. LLM generates response + memory operations
        response = await self.model.generate(
            context + f"\nUser: {user_message}\nAssistant:"
        )

        # 3. Parse memory operations from response
        memory_ops = self._parse_memory_ops(response)
        for op in memory_ops:
            await self._execute_memory_op(op)

        # 4. Memory maintenance
        await self.scheduler.maintenance(self.memory)

        return self._clean_response(response)

    async def _execute_memory_op(self, op: dict):
        """Исполняет операции с памятью, сгенерированные LLM."""

        if op["type"] == "store":
            await self.memory.store(op["key"], op["value"], op.get("importance", 0.5))

        elif op["type"] == "forget":
            await self.memory.forget(op["key"])

        elif op["type"] == "consolidate":
            await self.memory.consolidate(op.get("keys", []))

        elif op["type"] == "recall":
            return await self.memory.recall(op["query"])
```


---

## 2. Memory Hierarchy

```python
class MemoryHierarchy:
    """Иерархическая память Letta."""

    def __init__(self):
        # Working memory: всегда в контексте
        self.working_memory = {
            "persona": "You are a helpful assistant.",
            "current_user": None,
            "current_task": None,
        }

        # Archival memory: векторное хранилище (не в контексте)
        self.archival = ChromaCollection()

        # Recall memory: недавние взаимодействия (частично в контексте)
        self.recall = deque(maxlen=100)

        # Core memory: базовые знания (всегда в контексте)
        self.core = {
            "system_prompt": "",
            "tools": [],
        }

    async def build_context(self, user_message: str) -> str:
        """Строит контекст: core + working + recall + archival snippets."""

        context_parts = [
            f"<core>\n{json.dumps(self.core, indent=2)}\n</core>",
            f"<working>\n{json.dumps(self.working_memory, indent=2)}\n</working>",
            f"<archival>\n{await self._search_archival(user_message, k=3)}\n</archival>",
        ]

        # Добавляем recall только последние несколько
        recent_recall = list(self.recall)[-5:]
        if recent_recall:
            context_parts.append(
                f"<recall>\n{json.dumps(recent_recall, indent=2)}\n</recall>"
            )

        return "\n\n".join(context_parts)
```


---

## 3. Memory Operations (System Calls)

```python
class MemoryOperations:
    """Операции с памятью, доступные LLM как tools."""

    TOOLS = {
        "memory_store": {
            "description": "Store information in archival memory",
            "params": {"key": "str", "value": "str", "importance": "float"},
        },
        "memory_recall": {
            "description": "Search archival memory",
            "params": {"query": "str", "k": "int"},
        },
        "memory_forget": {
            "description": "Remove information from memory",
            "params": {"key": "str"},
        },
        "working_memory_update": {
            "description": "Update working memory (always in context)",
            "params": {"field": "str", "value": "str"},
        },
    }

    async def memory_store(self, key: str, value: str, importance: float = 0.5):
        """Сохраняет в archival memory."""
        embedding = self.encoder.encode(f"{key}: {value}")
        self.archival.add(
            embedding=embedding,
            metadata={"key": key, "value": value, "importance": importance, "timestamp": datetime.now()},
        )

    async def working_memory_update(self, field: str, value: str):
        """Обновляет working memory (всегда в контексте)."""
        if field in self.working_memory:
            self.working_memory[field] = value
            log(f"Working memory updated: {field} = {value}")
```


---

## 4. Context Budget Management

```python
class ContextManager:
    """Управление бюджетом контекстного окна."""

    def __init__(self, max_tokens: int = 128000):
        self.max_tokens = max_tokens
        self.allocations = {
            "core": 2000,        # System prompt + tools
            "working": 1000,     # Current state
            "recall": 5000,      # Recent interactions
            "archival": 10000,   # Retrieved snippets
            "user_input": 2000,  # Current user message
            "scratchpad": 5000,  # Agent reasoning
        }

    def get_available(self) -> int:
        """Сколько токенов доступно для archival retrieval."""
        used = sum(self.allocations.values())
        return self.max_tokens - used

    def dynamic_allocate(self, context: dict) -> dict:
        """Динамическое перераспределение бюджета."""
        # Если нужно больше места для archival → урезать recall
        if context.get("archival_needed", 0) > self.allocations["archival"]:
            self.allocations["recall"] = max(1000, self.allocations["recall"] - 2000)
            self.allocations["archival"] += 2000

        return self.allocations
```

---

## Резюме

```
Letta / MemGPT: OS for LLM Memory

| Component    | Human analog    | Size    | Always in context? |
|-------------|-----------------|---------|-------------------|
| Core        | BIOS            | 2K      | ✅                |
| Working     | RAM             | 1K      | ✅                |
| Recall      | Short-term      | 5K      | Partial           |
| Archival    | Long-term       | 10K+    | ❌ (retrieved)    |
| Scratchpad  | Working memory  | 5K      | ✅                |

Memory operations (tools for LLM):
  memory_store    — сохранить в архив
  memory_recall   — поиск по архиву
  memory_forget   — удалить
  working_update  — обновить рабочую память
  consolidate     — объединить похожие записи
```

---

## Практическое задание

1. Реализуй MemoryHierarchy с 4 уровнями (core, working, recall, archival).

2. Добавь MemoryOperations как tools для LLM.

3. Настрой ContextManager с динамическим бюджетом.

---

## Проверь себя

1. Чем Letta отличается от обычного RAG?

2. Какие 4 уровня памяти в Letta?

3. Как LLM управляет своей памятью через tools?

4. Как работает context budget management?

---

## Ссылки

- [[01-architectures]] — три типа памяти
- [[03-consolidation]] — следующий урок: memory consolidation
- [[../../../03-memory-and-rag/01-memory-types]] — memory basics
