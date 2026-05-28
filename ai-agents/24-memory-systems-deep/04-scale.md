---
created: 2026-05-28
tags: [course/memory-systems-deep, distributed, scale, persistence, multi-agent]
status: active
---

# Урок 24.4: Memory at Scale — Distributed & Persistent

> [!quote] Ключевая идея
> Один агент — одна память. Десять агентов — распределённая база. Тысячи — шардирование, репликация, consistency. Production memory для multi-agent — это infrastructure challenge, не ML.

---

## 1. Shared Memory Architecture

```python
class SharedMemoryService:
    """Централизованная shared memory для multi-agent."""

    def __init__(self, storage: str = "postgres"):
        self.db = AsyncPostgreSQL() if storage == "postgres" else RedisMemory()
        self.cache = RedisCache(ttl=300)

    async def store(self, agent_id: str, memory: dict, scope: str = "private"):
        """Сохраняет в shared memory."""

        memory_entry = {
            "agent_id": agent_id,
            "scope": scope,      # "private" | "team" | "global"
            "content": memory,
            "embedding": await self._compute_embedding(memory),
            "timestamp": datetime.now(),
            "ttl": memory.get("ttl", None),
        }

        await self.db.execute("""
            INSERT INTO shared_memory (agent_id, scope, content, embedding, timestamp, ttl)
            VALUES ($1, $2, $3, $4, $5, $6)
        """, memory_entry.values())

        # Invalid cache
        await self.cache.delete(f"mem:{agent_id}:{scope}")

    async def search(self, query: str, scope: str = "team", agent_id: str = None, top_k: int = 10) -> list[dict]:
        """Поиск по shared памяти."""

        query_emb = await self._compute_embedding(query)

        rows = await self.db.query("""
            SELECT * FROM shared_memory
            WHERE scope = $1
              AND ($2 IS NULL OR agent_id = $2)
              AND (ttl IS NULL OR ttl > NOW())
            ORDER BY embedding <-> $3
            LIMIT $4
        """, scope, agent_id, query_emb, top_k)

        return rows
```

---

## 2. Sharding Strategies

```python
class MemoryShardManager:
    """Шардирование памяти по агентам и топикам."""

    def __init__(self, num_shards: int = 4):
        self.shards = [Shard(i) for i in range(num_shards)]

    def get_shard(self, agent_id: str, topic: str = None) -> Shard:
        """Определяет шард для хранения."""

        if topic:
            # Topic-based: все данные по теме в одном шарде
            shard_id = hash(topic) % len(self.shards)
        else:
            # Agent-based: все данные агента в одном шарде
            shard_id = hash(agent_id) % len(self.shards)

        return self.shards[shard_id]

    async def rebalance(self):
        """Ребалансировка шардов при добавлении/удалении."""

        # Проверяем нагрузку на шарды
        loads = [await shard.size() for shard in self.shards]
        avg_load = sum(loads) / len(loads)

        for i, load in enumerate(loads):
            if load > avg_load * 1.2:  # >20% выше среднего
                await self._migrate(i, loads.index(min(loads)))


class Shard:
    """Один шард памяти."""

    def __init__(self, shard_id: int):
        self.id = shard_id
        self.store = ChromaCollection(persist_directory=f"/data/memory/shard_{shard_id}")
```

---

## 3. Consistency & Conflict Resolution

```python
class MemoryConsistency:
    """Обеспечение consistency при параллельных записях."""

    async def write_with_lock(self, agent_id: str, memory: dict):
        """Optimistic locking для памяти."""

        async with self.lock(agent_id):
            version = await self.db.query(
                "SELECT version FROM memory_versions WHERE agent_id = $1", agent_id
            )
            await self.db.execute("""
                INSERT INTO shared_memory (agent_id, content, version, timestamp)
                VALUES ($1, $2, $3, $4)
            """, agent_id, memory, version + 1, datetime.now())

            await self.db.execute(
                "UPDATE memory_versions SET version = $1 WHERE agent_id = $2",
                version + 1, agent_id
            )

    async def resolve_conflict(self, conflicting_memories: list[dict]) -> dict:
        """Разрешение конфликтов при merge."""

        prompt = f"""Resolve conflict between these memories:
{json.dumps(conflicting_memories, indent=2)}

Rules:
1. Keep the most specific information
2. Prefer recent over old
3. If contradictory, trust the one with higher importance
4. Merge compatible information

Return resolved memory as JSON."""

        return await self.llm.generate(prompt)
```

---

## 4. Agent-specific Memory Store

```python
class AgentMemoryStore:
    """Memory store для конкретного агента с гигиеной данных."""

    def __init__(self, agent_id: str, backend: SharedMemoryService):
        self.agent_id = agent_id
        self.backend = backend

    async def remember_relevant(self, query: str, k: int = 5) -> list[dict]:
        """Вспоминает релевантное из своей памяти."""

        results = await self.backend.search(
            query=query,
            scope="private",
            agent_id=self.agent_id,
            top_k=k,
        )

        # Повышаем rehearsal count для найденных
        for r in results:
            await self._increment_rehearsal(r["id"])

        return results

    async def cleanup_stale(self, max_age_days: int = 90):
        """Очистка устаревшей памяти."""

        deleted = await self.backend.db.execute("""
            DELETE FROM shared_memory
            WHERE agent_id = $1
              AND timestamp < NOW() - INTERVAL '$2 days'
              AND importance < 0.3
        """, self.agent_id, max_age_days)

        log(f"Cleaned {deleted} stale memories for agent {self.agent_id}")
```

---

## Резюме

```
Memory at Scale — ключевые решения:

Хранение:
  Postgres: структурированные данные, версионирование
  Vector DB: semantic search
  Redis: кэш горячих воспоминаний

Шардирование:
  По агенту: просто, но неравномерно
  По топику: равномерно, но сложнее
  Hybrid: topic + agent

Consistency:
  Optimistic locking (версии)
  Last-write-wins (просто)
  LLM merge (умно)

Очистка:
  TTL-based: автоматическое удаление
  Importance-based: сохраняем важное
  Age-based: >90 дней → удалить
```

---

## Практическое задание

1. Реализуй SharedMemoryService с PostgreSQL backend.

2. Добавь MemoryShardManager с topic-based шардированием.

3. Настрой optimistic locking для записи.

4. Реализуй cleanup stale памяти по расписанию.

---

## Проверь себя

1. Как организована shared memory для multi-agent?

2. Какие стратегии шардирования существуют?

3. Как обеспечивается consistency?

4. Как работает очистка устаревшей памяти?

---

## Ссылки

- [[03-consolidation]] — consolidation
- [[../../../04-multi-agent/01-orchestration]] — multi-agent orchestration
- [[../../../05-production/04-resilience]] — resilience patterns
