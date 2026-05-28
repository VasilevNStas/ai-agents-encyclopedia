> [!success] Status: Implemented
> RAG pipeline + трёхслойная память. Самостоятельные модули.

# SupportFlow — Этап 2: Память и RAG

> После [[../../../03-memory-and-rag/01-memory-types|Модуль 3 (Память и RAG)]]

## Что реализовано

- **Трёхслойная память**: short-term (буфер диалога 20 сообщений), working (KV для текущей задачи), long-term (Markdown-файлы)
- **RAG пайплайн**: query rewrite → vector search → re-rank (без внешних зависимостей)
- **15 документов** поддержки по 5 категориям (billing, account, security, tech, legal)
- **5 инструментов**: search_kb, save_to_memory, read_from_memory, time, calculator

## Файлы

| Файл | Описание |
|------|----------|
| `agent.py` | MemoryAgent с ReAct-циклом + память + RAG |
| `memory.py` | ShortTermMemory, WorkingMemory, LongTermMemory, AgentMemory |
| `rag.py` | RAGPipeline, QueryRewriter, ReRanker |
| `vector_store.py` | VectorStore с cosine similarity |
| `DIFF.md` | Что изменилось относительно Stage 1 |

## Ключевые концепты

- **Трёхслойная память**: STM (текущий диалог) → WM (текущая задача) → LTM (долгосрочное хранение)
- **RAG 2.0**: не просто search, а rewrite → retrieve → re-rank
- **Memory как инструмент**: агент сам решает, когда сохранить/прочитать
