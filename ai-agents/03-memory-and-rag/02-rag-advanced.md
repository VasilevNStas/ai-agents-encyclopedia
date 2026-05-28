---
created: 2026-05-08
tags: [course/memory, rag, advanced]
status: active
---

# Урок 8: RAG 2.0 — от Naive к Production

> [!quote] Ключевая идея
> Naive RAG (просто «нарежь текст → сделай embedding → найди похожее») работает только в демках. В production нужна цепочка: **retrieval → reranking → contextualization → generation**.

---

## Что такое RAG

**RAG (Retrieval-Augmented Generation)** — паттерн, в котором LLM перед ответом ищет релевантную информацию во внешнем источнике.

```
Запрос: "Какая столица Франции?"

Шаг 1: Поиск
  → ищем в базе знаний по запросу
  → находим: "Париж — столица Франции"

Шаг 2: Генерация
  → отправляем LLM: запрос + найденный контекст
  → LLM отвечает с опорой на контекст
```

**Зачем:** LLM не знает твои данные. RAG — способ «скормить» модели то, чего нет в её обучении.

---

## Naive RAG и его проблемы

Простейшая реализация:

```python
def naive_rag(query: str, docs: list[str]) -> str:
    # 1. Нарезать документы на куски
    chunks = chunk_docs(docs, chunk_size=500)
    
    # 2. Превратить всё в embeddings
    query_emb = embed(query)
    chunk_embs = [embed(c) for c in chunks]
    
    # 3. Найти top-k похожих
    top_k = cosine_similarity(query_emb, chunk_embs)[:3]
    
    # 4. Склеить контекст и отправить LLM
    context = "\n".join(top_k)
    return llm.generate(f"Контекст: {context}\nВопрос: {query}")
```

**Проблемы Naive RAG:**

| Проблема | Почему | Последствие |
|----------|--------|-------------|
| **Chunking** | Режем текст вслепую (500 токенов) | Разрываем мысль посередине |
| **Lost-in-middle** | Нашли 10 кусков, но LLM видит только 3 | Лучший ответ может быть в 4-м |
| **Semantic gap** | "столица Франции" ≠ embedding "Париж Елисейские поля" | Похоже по смыслу, а не по задаче |
| **Галлюцинации** | LLM может игнорировать контекст | Выдаёт свой ответ вместо факта |

---

## RAG 2.0 — production-пайплайн

```
Запрос
  │
  ▼
┌──────────────┐
│ Query        │  — переформулировка запроса
│ Rewriting    │    "столица Франции" → "какой город является столицей Франции"
└──────┬───────┘
       ▼
┌──────────────┐
│ Hybrid       │  — semantic (embedding) + keyword (BM25)
│ Search       │    вектора + точное совпадение терминов
└──────┬───────┘
       ▼
┌──────────────┐
│ Reranking    │  — LLM или cross-encoder пересортирует результаты
│              │    убирает нерелевантные, поднимает лучшие
└──────┬───────┘
       ▼
┌──────────────┐
│ Contextual   │  — добавляет метаданные: источник, дата,
│ Enrichment   │    окружающий контекст куска
└──────┬───────┘
       ▼
┌──────────────┐
│ Generation   │  — LLM отвечает с опорой на контекст
│              │    + цитирует источники
└──────────────┘
```

### Query Rewriting

Пользователь может спросить криво. Нужно переформулировать:

```python
def rewrite_query(chat_history: list, query: str) -> str:
    """Переформулирует запрос для поиска."""

    prompt = f"""
    История диалога: {chat_history}
    Последний запрос: {query}

    Переформулируй запрос так, чтобы поисковая система
    нашла наиболее релевантные документы.
    Ответь ТОЛЬКО переформулированным запросом.
    """
    return llm.generate(prompt, temperature=0)

# Пример:
# Было: "а как там с налогами?"
# Стало: "налоговое законодательство РФ 2026 год изменения ставок"
```

### Hybrid Search

```python
def hybrid_search(query: str, top_k: int = 10) -> list[Document]:
    """Semantic + keyword search с объединением результатов."""

    # Semantic (embedding-based)
    query_emb = embed(query)
    semantic_results = vector_db.search(query_emb, top_k=top_k)

    # Keyword (BM25 — точное совпадение)
    keyword_results = bm25_search(query, top_k=top_k)

    # Fusion: объединяем и сортируем (RRF — Reciprocal Rank Fusion)
    combined = rrf_merge(semantic_results, keyword_results)

    return combined[:top_k]
```

**Зачем:** embeddings хороши для смысла, BM25 — для точных терминов (имена, коды, даты). Вместе — лучший результат.

### Reranking

```python
def rerank(query: str, candidates: list[Document]) -> list[Document]:
    """LLM или cross-encoder пересортирует кандидаты."""

    # Cross-encoder (точнее, но медленнее)
    pairs = [(query, doc.text) for doc in candidates]
    scores = cross_encoder.score(pairs)
    
    # Сортируем по убыванию релевантности
    ranked = sorted(zip(candidates, scores), key=lambda x: -x[1])
    return [doc for doc, _ in ranked]
```

**Зачем:** embedding поиск находит «похожее», но не всегда «релевантное задаче». Reranking исправляет это.

### Contextual Enrichment

```python
def enrich_chunk(chunk: str, doc_meta: dict) -> str:
    """Добавляет контекст вокруг куска текста."""

    return f"""
[ИСТОЧНИК]: {doc_meta['filename']}
[ДАТА]: {doc_meta['date']}
[РАЗДЕЛ]: {doc_meta['section']}

{chunk}
"""
```

**Зачем:** кусок текста вне контекста документа может быть непонятен. Метаданные помогают LLM интерпретировать.

---

## GraphRAG

GraphRAG (Microsoft, 2024) — расширение RAG, где документы превращаются в **граф знаний**:

```
Текст: "DeepSeek выпустила модель R1 в 2025 году.
Она использует архитектуру MoE."

Граф:
  [DeepSeek] ──выпустила──> [R1]
       │                      │
       │                   использует
       │                      │
       ▼                      ▼
   [компания]            [MoE архитектура]

Вопрос: "Какую архитектуру использует DeepSeek R1?"
→ LLM идёт по графу: DeepSeek → R1 → MoE
→ Ответ: MoE
```

GraphRAG лучше обычного RAG для вопросов, которые требуют **связывания фактов из разных документов**.

---

## Когда RAG не нужен

RAG — не серебряная пуля. Иногда он не нужен:

| Сценарий | Что делать вместо RAG |
|----------|----------------------|
| Вопрос входит в контекстное окно (128k) | Просто вставь весь документ в промпт |
| Нужен точный ответ по одной строке | grep / SQL / API |
| Вопрос про архитектуру кода | Прочитай файлы напрямую инструментами |
| Творческая задача | Не нужны факты, нужен LLM "как есть" |

> [!important] Принцип
> RAG — это **мост** между LLM и данными, которые не влезают в контекст. Если данные влезают — RAG избыточен.

---

## Anti-patterns RAG

### 1. RAG как единственный источник
```python
# ❌ Верить только RAG
context = rag_search(query)
return llm.generate(f"Ответь строго по контексту: {context}")
# LLM может ошибиться — нужна валидация
```

### 2. Chunking без overlap
```python
# ❌ Куски без перекрытия
chunks = text.split(500)  # последнее предложение первого куска
                           # может не иметь начала во втором
# ✅ С перекрытием
chunks = split_with_overlap(text, chunk_size=500, overlap=50)
```

### 3. Слишком много контекста
```python
# ❌ Все 10 найденных кусков в промпт
context = "\n".join(top_10_chunks)
# LLM закопается в шуме, lost-in-the-middle
# ✅ Только top-3 после reranking
context = "\n".join(rerank(query, top_10_chunks)[:3])
```

---

## Резюме

```
Naive RAG:  chunks → embed → search → LLM
RAG 2.0:    rewrite → hybrid search → rerank → enrich → LLM

Naive RAG — для прототипа
RAG 2.0   — для продакшена
GraphRAG  — когда нужно связывать факты между документами

Главное правило: RAG — это пайплайн, а не один шаг.
```

---

## Практическое задание

Открой любой проект и попробуй спроектировать для него RAG-пайплайн:

1. Какие данные ты будешь индексировать?
2. Какой размер чанка выберешь?
3. Нужен ли тебе GraphRAG или хватит обычного поиска?
4. Как будешь валидировать ответы?

---

## Проверь себя

1. Чем RAG 2.0 отличается от Naive RAG?
2. Зачем нужен reranking, если embedding search уже нашёл релевантное?
3. В чём преимущество hybrid search (semantic + BM25)?
4. Когда RAG вообще не нужен?

---

## Ссылки

- GraphRAG: [Microsoft Research 2024](https://www.microsoft.com/en-us/research/project/graphrag/)
- [[03-memory-and-rag/01-memory-types]] — три слоя памяти
- [[03-memory-and-rag/03-llm-wiki]] — LLM Wiki: альтернатива RAG по Карпати
