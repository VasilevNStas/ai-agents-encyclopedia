# DIFF: Stage 2 — Memory & RAG

> Относительно: [[../../01-core/DIFF|Stage 1 — Core ReAct]]
> Модуль курса: [[../../../03-memory-and-rag/01-memory-types]]

## Что изменилось

### Добавлено

| Компонент | Файл | Описание |
|-----------|------|----------|
| `AgentMemory` | `memory.py` | Трёхслойная память: short-term (буфер диалога), working (ключ-значение), long-term (файлы Markdown) |
| `RAGPipeline` | `rag.py` | Пайплайн: query rewrite → vector search → re-rank + фильтрация |
| `QueryRewriter` | `rag.py` | Расширение запроса синонимами + выделение категорий |
| `ReRanker` | `rag.py` | Ранжирование: exact phrase boost, word overlap, short text boost, priority |
| `VectorStore` | `vector_store.py` | Chroma-совместимое хранилище с cosine similarity |
| `MemoryAgent` | `agent.py` | Новый класс агента, наследующий всё из Stage 1 + память + RAG |
| `SUPPORT_DOCUMENTS` | `rag.py` | 15 документов поддержки по 5 категориям |

### Изменено

| Аспект | Stage 1 | Stage 2 |
|--------|---------|---------|
| System prompt | Статичный | Динамический (RAG-контекст добавляется перед каждым вызовом) |
| Conversation | Только current messages | Short-term memory с историей до 20 сообщений |
| Knowledge base | Hardcoded dict | Векторный поиск + реранжирование |
| Инструменты | 3 (search_kb, time, calc) | 5 (добавлены save_to_memory, read_from_memory) |
| `execute_tool` | Прямой вызов | С передачей memory/rag контекста |
| `search_knowledge_base` | Точное совпадение | RAG-поиск с fallback на точное совпадение |

### Исправлено (memory.py)

- Убрана зависимость от `src.agent.config` — модуль теперь самодостаточен
- `MemoryConfig` dataclass вместо `AgentConfig`
- `LongTermMemory` использует `storage_dir` из конфига

## Архитектура

```
User Input
    │
    ▼
┌──────────────────────────────────┐
│  MemoryAgent.run()               │
│                                  │
│  1. Add to short-term memory     │
│  2. RAG retrieval                │
│  3. Build prompt with context    │
│  4. ReAct loop                   │
│  5. Add response to memory       │
└──────────────────────────────────┘
    │                    │
    ▼                    ▼
┌──────────┐    ┌────────────────┐
│  Memory  │    │  RAG Pipeline  │
│          │    │                │
│ STM: buf │    │ Rewrite→Search │
│ WM:  KV  │    │ →Re-rank→Fmt  │
│ LTM: md  │    └────────────────┘
└──────────┘
```

## Как запустить

```bash
# С RAG (по умолчанию)
export OPENAI_API_KEY="sk-..."
python agent.py --provider openai "как сбросить пароль?"

# Без RAG
python agent.py --provider openai --no-rag "сколько стоит Pro план?"

# С сохранением в память
python agent.py "запомни: мой аккаунт #12345"
# Затем: "что я просил запомнить?"
```

## Что дальше

Следующий этап: [[../../03-production/DIFF|Stage 3 — Production: guardrails, budget, observability]]
