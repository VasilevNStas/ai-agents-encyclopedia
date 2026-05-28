---
created: 2026-05-28
tags: [course/memory-systems-deep, memory, episodic, semantic, procedural, architecture]
status: active
---

# Урок 24.1: Memory Architectures — Episodic, Semantic, Procedural

> [!quote] Ключевая идея
> Человеческая память имеет три типа: эпизодическая (что произошло), семантическая (факты), процедурная (как делать). Агент, спроектированный с этими типами, радикально превосходит агента с одним списком сообщений. Каждый тип требует своей архитектуры хранения и retrieval.

---

## 1. Три типа памяти агента

| Тип | Что хранит | Пример | Хранение | Retrieval |
|-----|-----------|--------|----------|-----------|
| **Episodic** | Конкретные события, диалоги, опыт | «Пользователь вчера спрашивал про баланс» | Векторная БД с timestamp | Semantic + temporal |
| **Semantic** | Факты, концепции, знания | «Баланс можно проверить через /account» | Графовая/векторная БД | Semantic search |
| **Procedural** | Навыки, последовательности действий | «Как сбросить пароль: 3 шага» | Правила/демонстрации | Pattern matching |

```python
class AgentMemory:
    """Трёхслойная память агента."""

    def __init__(self):
        self.episodic = EpisodicMemory()
        self.semantic = SemanticMemory()
        self.procedural = ProceduralMemory()

    async def remember(self, query: str, context: dict) -> dict:
        """Поиск по всем типам памяти."""
        return {
            "episodes": await self.episodic.search(query, context),
            "facts": await self.semantic.search(query),
            "procedures": await self.procedural.search(query),
        }

    async def store(self, experience: dict):
        """Сохраняет опыт во все типы памяти."""
        await self.episodic.store(experience)
        await self.semantic.extract_and_store(experience)
        await self.procedural.learn(experience)
```

---

## 2. Episodic Memory

```python
class EpisodicMemory:
    """Эпизодическая память: конкретные взаимодействия."""

    def __init__(self, max_episodes: int = 10000):
        self.episodes = []
        self.max_episodes = max_episodes
        self.encoder = SentenceTransformer("all-MiniLM-L6-v2")

    async def store(self, episode: dict):
        """Сохраняет эпизод с временной меткой."""

        episode["timestamp"] = datetime.now()
        episode["embedding"] = self.encoder.encode(episode.get("summary", episode["input"]))

        self.episodes.append(episode)

        # Eviction: удаляем старые
        if len(self.episodes) > self.max_episodes:
            self.episodes.sort(key=lambda e: e.get("importance", 0))
            self.episodes = self.episodes[-self.max_episodes:]

    async def search(self, query: str, context: dict, top_k: int = 5) -> list[dict]:
        """Semantic + temporal + importance поиск."""

        query_emb = self.encoder.encode(query)
        current_time = datetime.now()

        scored = []
        for ep in self.episodes:
            # Semantic score
            sem_score = self._cosine_similarity(query_emb, ep["embedding"])

            # Temporal recency
            hours_ago = (current_time - ep["timestamp"]).total_seconds() / 3600
            temp_score = 1.0 / (1.0 + hours_ago / 24)

            # Importance
            imp_score = ep.get("importance", 0.5)

            # Combined
            score = 0.5 * sem_score + 0.3 * temp_score + 0.2 * imp_score
            scored.append((score, ep))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [ep for _, ep in scored[:top_k]]

    async def consolidate(self):
        """Консолидация: похожие эпизоды → семантическая память."""
        # Cluster similar episodes → extract common patterns
        # Run nightly
        pass
```

---

## 3. Semantic Memory

```python
class SemanticMemory:
    """Семантическая память: факты и знания."""

    def __init__(self):
        self.knowledge_graph = nx.DiGraph()
        self.vector_store = ChromaCollection()

    async def extract_and_store(self, experience: dict):
        """Извлекает факты из опыта и сохраняет."""

        facts = await self._extract_facts(experience)
        for fact in facts:
            await self.store_fact(fact)

    async def _extract_facts(self, experience: dict) -> list[dict]:
        prompt = f"""Extract factual statements from this interaction:
Input: {experience.get('input', '')}
Output: {experience.get('output', '')}
Return as JSON list of {{"subject": str, "predicate": str, "object": str}}"""

        response = await self.llm.generate(prompt)
        return json.loads(self._extract_json(response))

    async def store_fact(self, fact: dict):
        """Сохраняет факт в граф и векторное хранилище."""

        # Graph: subject → predicate → object
        self.knowledge_graph.add_edge(
            fact["subject"], fact["object"],
            predicate=fact["predicate"],
            timestamp=datetime.now(),
        )

        # Vector: complete sentence
        text = f"{fact['subject']} {fact['predicate']} {fact['object']}"
        embedding = self.encoder.encode(text)
        self.vector_store.add(embedding, text)

    async def query(self, question: str) -> list[str]:
        """Поиск фактов по вопросу."""
        results = self.vector_store.search(question, k=5)
        return [r["text"] for r in results]
```

---

## 4. Procedural Memory

```python
class ProceduralMemory:
    """Процедурная память: навыки и последовательности."""

    def __init__(self):
        self.skills = {}  # {skill_name: [steps]}

    async def learn(self, experience: dict):
        """Извлекает процедурные знания из опыта."""

        procedure = await self._extract_procedure(experience)
        if procedure:
            skill_name = procedure["name"]
            if skill_name not in self.skills:
                self.skills[skill_name] = []
            self.skills[skill_name].append({
                "steps": procedure["steps"],
                "success": experience.get("success", True),
                "timestamp": datetime.now(),
            })

    async def retrieve(self, task: str) -> list[str] | None:
        """Находит подходящую процедуру."""

        # Pattern matching: находим похожие задачи
        for skill_name, demonstrations in self.skills.items():
            if self._task_matches(task, skill_name):
                # Берём самую успешную демонстрацию
                best = max(
                    [d for d in demonstrations if d["success"]],
                    key=lambda d: d["timestamp"],
                    default=None,
                )
                if best:
                    return best["steps"]
        return None

    async def chain_skills(self, task: str, subskills: list[str]) -> list[str]:
        """Составляет цепочку навыков для сложной задачи."""
        chain = []
        for skill in subskills:
            steps = await self.retrieve(skill)
            if steps:
                chain.extend(steps)
            else:
                chain.append(f"[Missing skill: {skill}]")
        return chain
```

---

## 5. Memory Consolidation Pipeline

```python
class MemoryConsolidation:
    """Консолидация: episodic → semantic, повторение важных эпизодов."""

    async def consolidate(self, agent_memory: AgentMemory):
        """Ночная консолидация памяти."""

        # 1. Cluster similar episodes
        clusters = self._cluster_episodes(agent_memory.episodic.episodes)

        # 2. Extract common patterns → semantic facts
        for cluster in clusters:
            if len(cluster) > 3:
                summary = await self._summarize_cluster(cluster)
                await agent_memory.semantic.store_fact(summary)

        # 3. Rehearse important episodes (replay for reinforcement)
        important = [
            ep for ep in agent_memory.episodic.episodes
            if ep.get("importance", 0) > 0.8
        ]
        for ep in important[:10]:
            ep["rehearsal_count"] = ep.get("rehearsal_count", 0) + 1
```

---

## Резюме

```
Three Memory Types:

Episodic:     что произошло + когда + важно ли
Semantic:     факты и связи (граф + вектор)
Procedural:   как делать (последовательности шагов)

Episodic → Semantic:  consolidation (nightly)
                  cluster similar → extract facts

Procedural:          learning from successful traces
```

---

## Практическое задание

1. Реализуй EpisodicMemory с semantic + temporal retrieval.

2. Добавь SemanticMemory с графом фактов.

3. Создай ProceduralMemory с извлечением навыков из трасс.

4. Настрой MemoryConsolidation pipeline.

---

## Проверь себя

1. Какие 3 типа памяти и чем отличаются?

2. Как эпизодическая память превращается в семантическую?

3. Чем процедурная память отличается от семантической?

4. Как работает consolidation?

---

## Ссылки

- [[02-memgpt]] — следующий урок: MemGPT/Letta
- [[../../../03-memory-and-rag/01-memory-types]] — memory types basics
- [[../../../03-memory-and-rag/02-rag-advanced]] — RAG advanced
