---
created: 2026-05-28
tags: [course/memory-systems-deep, consolidation, compression, forgetting, archival]
status: active
---

# Урок 24.3: Memory Consolidation & Compression

> [!quote] Ключевая идея
> Память без консолидации — это свалка. Эпизоды нужно сжимать в факты, факты — связывать в знания, устаревшее — забывать. Агент без консолидации тонет в токенах.

---

## 1. Consolidation Pipeline

```python
class ConsolidationPipeline:
    """Ночная консолидация памяти."""

    async def run(self, memory: AgentMemory):
        log("Starting memory consolidation...")

        # 1. Compress: похожие эпизоды → summary
        compressed = await self._compress_episodes(memory.episodic)

        # 2. Extract: эпизоды → факты
        facts = await self._extract_facts(compressed)

        # 3. Link: факты → граф знаний
        await self._link_knowledge(memory.semantic, facts)

        # 4. Prune: удалить устаревшее
        await self._prune(memory)

        # 5. Rehearse: повторить важное
        await self._rehearse(memory)

        log("Consolidation complete")

    async def _compress_episodes(self, episodic: EpisodicMemory) -> list[dict]:
        """Группирует похожие эпизоды и сжимает их."""

        clusters = self._cluster(episodic.episodes, threshold=0.85)
        compressed = []

        for cluster in clusters:
            if len(cluster) == 1:
                compressed.append(cluster[0])
            else:
                summary = await self.llm.generate(
                    f"Summarize these similar interactions in 1-2 sentences:\n" +
                    "\n".join(e.get("summary", e["input"]) for e in cluster)
                )
                compressed.append({
                    "summary": summary,
                    "count": len(cluster),
                    "first": min(e["timestamp"] for e in cluster),
                    "last": max(e["timestamp"] for e in cluster),
                    "importance": max(e.get("importance", 0) for e in cluster),
                })

        return compressed
```

---

## 2. Importance Scoring

```python
class ImportanceScorer:
    """Оценка важности информации для памяти."""

    async def score(self, episode: dict) -> float:
        """0.0 (забыть) → 1.0 (никогда не забывать)."""

        score = 0.0

        # 1. User feedback
        if episode.get("feedback") == "positive":
            score += 0.3
        elif episode.get("feedback") == "negative":
            score += 0.2  # Важно помнить ошибки

        # 2. Novelty: новая информация важнее
        if episode.get("new_information", False):
            score += 0.2

        # 3. Recency: свежее важнее
        hours_ago = (datetime.now() - episode["timestamp"]).total_seconds() / 3600
        score += max(0, 0.1 * (1 - hours_ago / 168))  # Week decay

        # 4. Emotional valence: сильные реакции
        if episode.get("sentiment") in ["angry", "urgent", "grateful"]:
            score += 0.2

        # 5. Frequency: частые темы важнее
        score += min(0.2, episode.get("frequency", 0) * 0.05)

        return min(1.0, score)
```

---

## 3. Forgetting Curve

```python
class ForgettingCurve:
    """Ebbinghaus forgetting curve для агента."""

    def __init__(self):
        self.decay_factor = 0.5  # Как быстро забываем
        self.rehearsal_boost = 0.3  # Бонус от повторения

    def recall_probability(self, memory: dict) -> float:
        """Вероятность вспомнить информацию."""

        hours_since = (datetime.now() - memory["timestamp"]).total_seconds() / 3600
        rehearsals = memory.get("rehearsal_count", 0)

        # Ebbinghaus: P = e^(-t / S)
        # S = strength (растёт с повторениями)
        strength = 1.0 + rehearsals * self.rehearsal_boost
        probability = math.exp(-hours_since / (24 * strength))

        return probability

    def should_rehearse(self, memory: dict, threshold: float = 0.3) -> bool:
        """Нужно ли повторить для укрепления."""
        return self.recall_probability(memory) < threshold

    def optimal_review_schedule(self, initial_strength: float = 1.0) -> list[float]:
        """Оптимальные интервалы для повторения (Spaced Repetition)."""
        intervals = []
        strength = initial_strength
        for _ in range(10):
            # Next review when probability drops to 0.3
            interval = -math.log(0.3) * 24 * strength
            intervals.append(interval)
            strength += self.rehearsal_boost
        return intervals
```

---

## 4. Memory Compression Techniques

```python
class MemoryCompressor:
    """Сжатие памяти: уменьшение размера без потери смысла."""

    async def compress(self, memories: list[dict], target_tokens: int = 1000) -> list[dict]:
        """Сжимает набор воспоминаний до target_tokens."""

        # 1. Score by importance
        scored = [(await self.importance_scorer.score(m), m) for m in memories]
        scored.sort(key=lambda x: x[0], reverse=True)

        # 2. Keep important, compress/summarize the rest
        compressed = []
        tokens_used = 0

        for importance, memory in scored:
            memory_tokens = len(json.dumps(memory)) // 4

            if importance > 0.7:
                # Keep intact
                compressed.append(memory)
                tokens_used += memory_tokens
            elif tokens_used + memory_tokens <= target_tokens:
                # Summarize
                summary = await self._summarize_memory(memory)
                compressed.append(summary)
                tokens_used += len(summary) // 4
            else:
                break

        return compressed

    async def _summarize_memory(self, memory: dict) -> dict:
        prompt = f"Summarize in <50 chars: {memory.get('summary', memory.get('input', ''))}"
        summary = await self.llm.generate(prompt)
        return {"compressed": True, "summary": summary, "original_tokens": len(str(memory)) // 4}
```

---

## 5. Distributed Memory

```python
class DistributedMemory:
    """Распределённая память для multi-agent систем."""

    def __init__(self):
        self.local = AgentMemory()    # Local agent memory
        self.shared = SharedMemory()  # Shared across agents

    async def sync_to_shared(self):
        """Синхронизирует важные воспоминания в shared storage."""
        important = [m for m in self.local.episodic.episodes if m.get("importance", 0) > 0.7]
        await self.shared.batch_store(important)

    async def query_shared(self, query: str, agent_id: str = None) -> list[dict]:
        """Поиск по shared памяти (всех или конкретного агента)."""
        return await self.shared.search(query, agent_id=agent_id)
```

---

## Резюме

```
Consolidation Pipeline:

Episodes → Cluster → Compress → Extract Facts → Link → Prune → Rehearse

Ebbinghaus Curve: P(t) = e^(-t / S)
  t = время, S = сила (растёт с повторениями)

Важность: 0.0-1.0
  +0.3 user feedback
  +0.2 novelty
  +0.2 emotional
  +0.2 frequency

Forgetting:
  < 0.3 → rehearse (повторить)
  < 0.1 → archive (сжать)
  < 0.05 → forget (удалить)
```

---

## Практическое задание

1. Реализуй ConsolidationPipeline с компрессией эпизодов.

2. Добавь ImportanceScorer с 5 факторами.

3. Настрой ForgettingCurve с spaced repetition.

4. Реализуй MemoryCompressor с summarization.

---

## Проверь себя

1. Как работает консолидация памяти?

2. Какие факторы влияют на importance?

3. Что такое forgetting curve и как она работает?

4. Как spaced repetition применяется к памяти агента?

---

## Ссылки

- [[01-architectures]] — три типа памяти
- [[02-memgpt]] — MemGPT / Letta
- [[04-scale]] — следующий урок: distributed memory
