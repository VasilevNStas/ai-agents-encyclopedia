---
created: 2026-05-28
tags: [course/context-window-deep, optimization, sliding-window, summarization, chunking]
status: active
---

# Урок 21.2: Context Window Optimization

> [!quote] Ключевая идея
> Оптимизация контекстного окна — это не «впихнуть всё в 128K». Это стратегия: sliding window для real-time, hierarchical summarization для длинных документов, chunking с перекрытием для RAG, selective attention для кода. Каждая техника решает свою проблему.

---

## 1. Sliding Window

```python
class SlidingWindowOptimizer:
    """Оптимизация окна через скользящее окно."""

    def __init__(self, window_size: int = 32000, overlap: int = 4000):
        self.window_size = window_size
        self.overlap = overlap

    def process_long_text(self, text: str, model_fn: callable, task: str) -> list[str]:
        """Обработка текста через скользящее окно с перекрытием."""

        tokens = self._tokenize(text)
        results = []

        for i in range(0, len(tokens), self.window_size - self.overlap):
            window = tokens[i:i + self.window_size]
            window_text = self._detokenize(window)

            # Промпт с контекстом окна
            result = model_fn(
                f"[Window {i//len(window)}/{len(tokens)//self.window_size}]\n"
                f"Task: {task}\n"
                f"Content:\n{window_text}"
            )
            results.append({
                "window": i // (self.window_size - self.overlap),
                "start_token": i,
                "end_token": i + len(window),
                "result": result,
            })

        return self._merge_results(results, task)

    def _merge_results(self, results: list[dict], task: str) -> list[str]:
        """Слияние overlapping результатов."""

        if task == "summarize":
            # Промежуточные саммари → финальное саммари
            summaries = [r["result"] for r in results]
            if len(summaries) <= 3:
                return summaries
            # Hierarchical merge
            while len(summaries) > 3:
                paired = ["\n".join(summaries[i:i+3]) for i in range(0, len(summaries), 3)]
                summaries = [model_fn(f"Combine:\n{p}") for p in paired]
            return summaries

        elif task == "qa":
            # Каждый ответ с указанием источника
            return [f"[Section {r['window']}]: {r['result']}" for r in results]

        return [r["result"] for r in results]
```

---

## 2. Hierarchical Summarization

Для длинных документов, которые даже не влезают в 10M:

```python
class HierarchicalSummarizer:
    """Многоуровневая суммаризация длинных документов."""

    CHUNK_SIZE = 8000  # Токенов на чанк

    async def summarize(self, document: str, max_depth: int = 3) -> str:
        """Рекурсивная иерархическая суммаризация."""

        chunks = self._chunk_document(document)

        # Level 1: chunk summaries
        level = await self._summarize_chunks(chunks)
        depth = 1

        # Level 2+: combine chunk summaries
        while len(level) > 1 and depth < max_depth:
            level = await self._summarize_chunks(level)
            depth += 1

        return level[0] if level else ""

    async def _summarize_chunks(self, chunks: list[str]) -> list[str]:
        """Суммаризация списка чанков."""

        summaries = []
        for chunk in chunks:
            if self._count_tokens(chunk) > self.CHUNK_SIZE:
                # Рекурсивно делим большой чанк
                sub_chunks = self._chunk_document(chunk, self.CHUNK_SIZE)
                sub_summaries = await self._summarize_chunks(sub_chunks)
                chunk = "\n".join(sub_summaries)

            summary = await self.llm.generate(
                f"Summarize concisely (max 3 sentences):\n{chunk}"
            )
            summaries.append(summary)

        if len(summaries) > 5:
            # Batch combine
            batch_size = 5
            combined = []
            for i in range(0, len(summaries), batch_size):
                batch = summaries[i:i + batch_size]
                combined.append(await self.llm.generate(
                    f"Combine these summaries into one:\n" + "\n".join(batch)
                ))
            summaries = combined

        return summaries
```

---

## 3. Chunking Strategies for Long Context

```python
class ChunkingOptimizer:
    """Стратегии разбиения текста для оптимального использования контекста."""

    STRATEGIES = {
        "fixed": "Фиксированный размер токенов",
        "sentence": "По границам предложений",
        "paragraph": "По параграфам",
        "semantic": "По семантическим границам (embedding similarity)",
        "recursive": "Рекурсивно от крупного к мелкому",
        "document": "По структуре документа (главы, секции)",
    }

    def __init__(self, strategy: str = "semantic", chunk_size: int = 2000, overlap: int = 200):
        self.strategy = strategy
        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk(self, text: str) -> list[dict]:
        """Разбивает текст на чанки по выбранной стратегии."""

        if self.strategy == "fixed":
            return self._fixed_chunk(text)
        elif self.strategy == "sentence":
            return self._sentence_chunk(text)
        elif self.strategy == "paragraph":
            return self._paragraph_chunk(text)
        elif self.strategy == "semantic":
            return self._semantic_chunk(text)
        elif self.strategy == "recursive":
            return self._recursive_chunk(text)
        elif self.strategy == "document":
            return self._document_chunk(text)

    def _semantic_chunk(self, text: str) -> list[dict]:
        """Семантическое разбиение: по резким изменениям эмбеддингов."""

        sentences = self._split_sentences(text)
        chunks = []
        current_chunk = []
        current_emb = None
        chunk_start = 0

        for i, sentence in enumerate(sentences):
            emb = self.embed(sentence)
            current_chunk.append(sentence)

            if current_emb is not None:
                similarity = cosine_similarity(emb, current_emb)
                if similarity < 0.7 and len(current_chunk) > 3:
                    chunk_text = " ".join(current_chunk)
                    chunks.append({
                        "text": chunk_text,
                        "tokens": self.count_tokens(chunk_text),
                        "start_sentence": chunk_start,
                        "end_sentence": i,
                    })
                    # Overlap: последние 2 предложения
                    current_chunk = current_chunk[-2:]
                    chunk_start = i - 2

            current_emb = emb

        if current_chunk:
            chunk_text = " ".join(current_chunk)
            chunks.append({
                "text": chunk_text,
                "tokens": self.count_tokens(chunk_text),
                "start_sentence": chunk_start,
                "end_sentence": len(sentences),
            })

        return chunks

    def _recursive_chunk(self, text: str, separators: list[str] = None) -> list[dict]:
        """Recursive chunking: от крупных разделителей к мелким."""
        separators = separators or ["\n\n", "\n", ". ", " "]
        chunks = [text]

        for sep in separators:
            new_chunks = []
            for chunk in chunks:
                if self.count_tokens(chunk) > self.chunk_size:
                    parts = chunk.split(sep)
                    # Добавляем разделитель обратно (кроме последнего)
                    for i, part in enumerate(parts):
                        if i < len(parts) - 1:
                            part += sep
                        new_chunks.append(part)
                else:
                    new_chunks.append(chunk)

            chunks = self._merge_small_chunks(new_chunks, sep)
            if all(self.count_tokens(c) <= self.chunk_size for c in chunks):
                break

        return [{"text": c, "tokens": self.count_tokens(c)} for c in chunks]
```

---

## 4. Selective Attention for Code

```python
class CodeContextOptimizer:
    """Оптимизация контекста для кода: selective attention."""

    def build_context(self, codebase: dict, query: str) -> str:
        """Строит оптимальный контекст из кодовой базы."""

        # 1. Selective attention: только релевантные файлы
        relevant_files = self._retrieve_relevant_files(codebase, query, top_k=10)

        # 2. Signature только для импортов и интерфейсов
        context = []
        for file_path, content in relevant_files:
            if len(content) > 1000:
                skeleton = self._extract_skeleton(content)
                context.append(f"# {file_path}\n{skeleton}")
            else:
                context.append(f"# {file_path}\n{content}")

        return "\n\n".join(context)

    def _extract_skeleton(self, code: str) -> str:
        """Извлекает скелет кода: классы, функции, их сигнатуры."""
        import ast

        try:
            tree = ast.parse(code)
        except SyntaxError:
            return code[:500]

        lines = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Сигнатура + docstring
                args = ast.dump(node.args)
                lines.append(f"def {node.name}({self._format_args(node.args)}):")
                doc = ast.get_docstring(node)
                if doc:
                    lines.append(f'    """{doc[:200]}"""')
                lines.append("    ...")

            elif isinstance(node, ast.ClassDef):
                bases = ", ".join(self._name(b) for b in node.bases)
                lines.append(f"class {node.name}({bases}):")
                lines.append("    ...")

        return "\n".join(lines[:100])  # Max 100 lines skeleton

    def _format_args(self, args) -> str:
        params = []
        for arg in args.args:
            annotation = ast.unparse(arg.annotation) if arg.annotation else ""
            params.append(f"{arg.arg}: {annotation}" if annotation else arg.arg)
        return ", ".join(params)
```

---

## 5. Dynamic Token Budget

```python
class DynamicTokenBudget:
    """Динамическое распределение токенов между компонентами."""

    def __init__(self, max_tokens: int = 128000):
        self.max_tokens = max_tokens
        self.allocations = {}

    def allocate(self, components: dict[str, int]) -> dict[str, int]:
        """Распределяет бюджет с учётом приоритетов.

        components: {"system_prompt": 500, "user_query": 200, 
                     "retrieved_docs": 5000, "conversation_history": 10000}
        """
        total_requested = sum(components.values())
        if total_requested <= self.max_tokens:
            return components  # Everything fits

        # Priority allocation
        priorities = {
            "system_prompt": 1,     # Highest — always fits
            "user_query": 2,        # Always fits
            "retrieved_docs": 3,    # Important — trim if needed
            "conversation_history": 4,  # Lowest — compress first
            "tool_results": 5,      # Optional — last
        }

        sorted_components = sorted(
            components.items(),
            key=lambda x: priorities.get(x[0], 99)
        )

        allocated = {}
        remaining = self.max_tokens

        for name, size in sorted_components:
            if remaining <= 0:
                break
            cap = 0
            if name == "conversation_history":
                cap = min(size, remaining)
                # Summarization или trimming
            elif name == "retrieved_docs":
                cap = min(size, remaining)
                # Можно дополнительно отфильтровать
            elif name == "system_prompt":
                cap = min(size, remaining)
            elif name == "user_query":
                cap = min(size, remaining)
            else:
                cap = min(size, remaining)

            allocated[name] = cap
            remaining -= cap

        log(f"Dynamic budget: allocated {sum(allocated.values())}/{self.max_tokens} tokens")
        return allocated
```

---

## Резюме

```
Оптимизация контекстного окна — 5 техник:

1. Sliding Window
   — Для real-time: последние N токенов
   — Overlap 10-20% для связности

2. Hierarchical Summarization
   — Для документов: чанки → саммари → комбинация
   — O(log n) глубина

3. Semantic Chunking
   — По границам семантических единиц
   — Лучше, чем fixed-size

4. Selective Attention (Code)
   — Только сигнатуры и интерфейсы
   — AST-parsing для извлечения скелета

5. Dynamic Token Budget
   — По приоритетам: system prompt > query > docs > history
   - Conversation отрезается первым
```

---

## Практическое задание

1. Реализуй HierarchicalSummarizer для документа >100K токенов.

2. Напиши SemanticChunker с разбиением по cosine similarity.

3. Добавь DynamicTokenBudget для агента с распределением по приоритетам.

---

## Проверь себя

1. Чем sliding window отличается от hierarchical summarization?

2. Почему semantic chunking лучше, чем fixed-size?

3. Как selective attention экономит контекст для кода?

4. Что отрезается первым при нехватке токенов?

---

## Ссылки

- [[01-landscape]] — контекстные окна 2026
- [[03-pricing-caching]] — pricing & caching
- [[../../../opencode-skills/09-performance/01-context-window-impact]] — влияние skills на контекст
