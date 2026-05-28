---
created: 2026-05-28
tags: [course/memory-rag, vector-db, qdrant, pinecone, weaviate, milvus]
status: active
---

# Урок 11: Vector Databases — как хранить и искать эмбеддинги

> [!quote] Ключевая идея
> Vector Database (векторная БД) — это база данных, которая умеет искать не по точному совпадению, а по **смыслу**. Она хранит эмбеддинги (векторы чисел) и находит ближайшие по косинусной близости. В 2026 это стандартная инфраструктура для RAG, semantic search и recommendation systems.

---

## Зачем нужна отдельная база для векторов?

Postgres с `pgvector` умеет хранить векторы. Зачем ещё одна база?

| Критерий | pgvector | Специализированная БД (Qdrant, Pinecone) |
|----------|:--------:|:----------------------------------------:|
| Скорость поиска на 10M векторов | ~200ms | ~5-20ms |
| Metadata filtering + vector search | Есть (WHERE) | Есть (индексированное) |
| Hybrid search (keyword + vector) | Через tsvector | Встроенный (BM25 + vector) |
| Quantization (сжатие для скорости) | halfvec (fp16) | Binary, Product, Scalar |
| Scale | ~10M на ноде | 100M+ на ноде, 10B+ распределённо |
| Managed cloud | Через Supabase/Neon | Нативный serverless |

**Когда хватит pgvector:** < 1M векторов, уже есть Postgres, не нужен hybrid search.
**Когда нужна специализированная:** > 5M векторов, нужна скорость < 50ms, сложная фильтрация.

---

## Главные игроки в 2026

| База | Язык | Лицензия | Hybrid search | Фильтрация | Scale | Цена (10M векторов/мес) |
|------|:----:|:--------:|:------------:|:----------:|:----:|:-----------------------:|
| **Qdrant** | Rust | Apache 2.0 | Сparse vectors | Лучшая в классе | ~100M/node | ~$95 |
| **Pinecone** | C++ | Proprietary | Sparse + dense | Server-side | 1B+ (serverless) | ~$70 |
| **Weaviate** | Go | BSD-3 | BM25 + vector | Inverted index | ~100M/node | ~$135 |
| **Milvus** | Go+C++ | Apache 2.0 | Sparse + dense | Scalar index | 10B+ (distributed) | ~$110 |
| **Chroma** | Python+Rust | Apache 2.0 | Нет | Базовая | ~10M | ~$80 |
| **pgvector** | C (ext) | PostgreSQL | tsvector + vector | WHERE | ~10M | $0 (ваш Postgres) |

```python
# Сравнение скорости: ANN search (Approximate Nearest Neighbor)
# на 10M векторов, 768 dimensions, recall@10 = 0.99
BENCHMARKS = {
    "qdrant":   {"p99_latency_ms": 12, "index_time_min": 45},
    "pinecone": {"p99_latency_ms": 18, "index_time_min": 30},
    "weaviate": {"p99_latency_ms": 25, "index_time_min": 60},
    "milvus":   {"p99_latency_ms": 15, "index_time_min": 40},
    "pgvector": {"p99_latency_ms": 200, "index_time_min": 120},
    "chroma":   {"p99_latency_ms": 50, "index_time_min": 10},
}
```

---

## Qdrant — Rust-first, производительность и фильтрация

Qdrant — лучший выбор для большинства production RAG-систем в 2026.

**Ключевое преимущество:** Фильтрация по произвольным JSON-полям без потери скорости. Это важно для RAG, где почти всегда фильтр по `user_id`, `tenant`, `date_range`.

```python
from qdrant_client import QdrantClient
from qdrant_client.models import (
    VectorParams, Distance, PointStruct, Filter, FieldCondition, Range,
)

client = QdrantClient(url="http://localhost:6333")

# Создаём коллекцию
client.create_collection(
    collection_name="documents",
    vectors_config=VectorParams(size=768, distance=Distance.COSINE),
)

# Вставляем векторы с payload (метаданными)
client.upsert(
    collection_name="documents",
    points=[
        PointStruct(
            id=1,
            vector=[0.1, 0.2, ...],  # эмбеддинг
            payload={
                "user_id": 42,
                "doc_type": "invoice",
                "created_at": "2026-05-01",
                "tags": ["finance", "urgent"],
            },
        ),
    ],
)

# Поиск с фильтрацией — без потери скорости
results = client.search(
    collection_name="documents",
    query_vector=[0.15, 0.25, ...],
    query_filter=Filter(
        must=[
            FieldCondition(key="user_id", match={"value": 42}),
            FieldCondition(key="created_at", range=Range(gte="2026-01-01")),
        ],
    ),
    limit=10,
)
```

**Когда выбрать Qdrant:** Всегда, если не уверены. Rust-ядро, Apache 2.0, отличная фильтрация, $95/мес за 10M векторов.

---

## Pinecone — «просто работает»

Pinecone — это Heroku мира vector databases. Нулевая ops-нагрузка.

**Плюсы:** Serverless (не думаешь о capacity), автоматическое масштабирование, отличная документация.
**Минусы:** Проприетарная, дороже на scale (vendor lock-in), ограниченная кастомизация.

```python
import pinecone

pinecone.init(api_key="...")

# Serverless index — масштабируется автоматически
index = pinecone.Index("documents", metric="cosine")

index.upsert([
    ("id1", [0.1, 0.2, ...], {"user_id": 42, "text": "..."}),
])

results = index.query(
    vector=[0.15, 0.25, ...],
    filter={"user_id": 42},
    top_k=10,
)
```

**Когда выбрать Pinecone:** Команда без SRE / платформенного инженера. Нужен production за 1 день.

---

## Weaviate — hybrid search без компромиссов

Weaviate — единственная БД со встроенным BM25 (keyword search) + векторный поиск. Не нужен внешний reranker.

```python
import weaviate

client = weaviate.Client("http://localhost:8080")

# Векторный поиск
client.query.get("Document", ["title", "content"]) \
    .with_near_vector({"vector": [0.1, 0.2, ...]}) \
    .with_limit(10) \
    .do()

# Hybrid search (keyword + vector) — без reranker!
client.query.get("Document", ["title", "content"]) \
    .with_hybrid(query="accounting report", vector=[0.1, 0.2, ...]) \
    .with_limit(10) \
    .do()
```

**Когда выбрать Weaviate:** Нужен keyword search + vector search в одной БД. Приложения с сильной текстовой компонентой (юридические документы, поддержка с FAQ).

---

## Milvus — для миллиардов векторов

Milvus — единственная БД, которая держит 10B+ векторов. Disaggregated compute + storage. Kubernetes-native.

**Когда выбрать Milvus:** У вас >1B векторов и есть команда data engineering.

**Когда НЕ выбирать:** Для 10M векторов — overkill. Qdrant или Pinecone будут проще и дешевле.

---

## Chroma — для прототипов и embedded

Chroma — самая лёгкая: запускается в Python-процессе, не требует отдельного сервера.

```python
import chromadb

client = chromadb.Client()  # in-process, без сервера
collection = client.create_collection("docs")

collection.add(
    documents=["Текст документа 1", "Текст 2"],
    metadatas=[{"source": "pdf"}, {"source": "web"}],
    ids=["doc1", "doc2"],
)

results = collection.query(query_texts=["бухгалтерский отчёт"], n_results=5)
```

**Когда выбрать Chroma:** Прототип, локальная разработка, <1M векторов. Никогда для production.

---

## pgvector — когда уже есть Postgres

```sql
CREATE EXTENSION vector;

CREATE TABLE documents (
    id SERIAL PRIMARY KEY,
    content TEXT,
    embedding vector(768),
    user_id INTEGER,
    created_at TIMESTAMP
);

-- Создаём индекс для скорости
CREATE INDEX ON documents USING hnsw (embedding vector_cosine_ops);

-- Поиск
SELECT id, content, 1 - (embedding <=> '[0.1, 0.2, ...]') AS similarity
FROM documents
WHERE user_id = 42
ORDER BY embedding <=> '[0.1, 0.2, ...]'
LIMIT 10;
```

**Когда выбрать pgvector:** < 5M векторов, уже есть Postgres, не нужен hybrid search.

---

## Decision Tree

```python
def choose_vector_db(
    max_vectors: int,
    need_hybrid_search: bool,
    need_metadata_filter: bool,
    ops_budget: str,
    existing_postgres: bool,
) -> str:
    """Выбирает векторную БД по параметрам проекта."""

    # Прототип
    if max_vectors < 100_000:
        return "chroma"

    # Маленький проект, уже есть Postgres
    if max_vectors < 5_000_000 and existing_postgres:
        return "pgvector"

    # Production < 100M
    if max_vectors < 100_000_000:
        if ops_budget == "minimal":
            return "pinecone"      # serverless, zero ops
        if need_hybrid_search:
            return "weaviate"      # BM25 + vector
        return "qdrant"            # лучшая фильтрация, скорость

    # Billion-scale
    if max_vectors < 1_000_000_000:
        return "qdrant"            # кластеризация

    # Enterprise scale
    return "milvus"                # 10B+
```

---

## Антипаттерны

**1. Embedding на лету при каждом поиске**
```python
# ❌ Генерировать эмбеддинг каждый раз
query_vec = embed_model.encode(user_query)
results = db.search(query_vec)

# ✅ Кэшировать частые запросы
cache_key = hash(user_query)
if cache_key in embedding_cache:
    query_vec = embedding_cache[cache_key]
else:
    query_vec = embed_model.encode(user_query)
    embedding_cache[cache_key] = query_vec
```

**2. Слишком большой batch для upsert**
```python
# ❌ 1M векторов за раз
db.upsert(points=[PointStruct(...) for _ in range(1_000_000)])

# ✅ Батчами по 1000
for batch in chunks(vectors, 1000):
    db.upsert(points=batch)
```

**3. Игнорировать фильтрацию**
```python
# ❌ Загрузить все, фильтровать в коде
all_docs = db.search(query_vec, limit=1000)
filtered = [d for d in all_docs if d.user_id == 42]

# ✅ Фильтр на стороне БД (в 10-100x быстрее)
filtered = db.search(query_vec, filter={"user_id": 42})
```

---

## Практическое задание

Разверни Qdrant (через Docker) и реализуй поиск документов:

1. Запусти Qdrant: `docker run -p 6333:6333 qdrant/qdrant`
2. Создай коллекцию `documents` с размером вектора 384 (all-MiniLM-L6-v2) и distance COSINE
3. Индексируй 10 документов (можно взять свою документацию или статьи) — для каждого сгенерируй эмбеддинг через `sentence-transformers`
4. Реализуй поиск с фильтрацией по полю `category` (например: "manual", "faq", "api")
5. Напиши функцию `hybrid_search(query, category, top_k=5)`, которая комбинирует векторный поиск и keyword filter

Требования: рабочий Qdrant client, 10+ документов в коллекции, 3 тестовых запроса с разными фильтрами, сравнение результатов поиска с фильтром и без.

---

## Проверь себя

1. Чем vector database отличается от обычной БД?
2. Когда хватит pgvector, а когда нужна специализированная БД?
3. Какое главное преимущество Qdrant перед Pinecone?
4. Что такое hybrid search и какая БД его поддерживает нативно?
5. Почему Chroma не для production?
6. Какой антипаттерн самый дорогой при работе с векторными БД?

---

## Резюме

```
Выбор векторной БД = масштаб × фильтрация × ops-бюджет

< 1M векторов → pgvector (уже есть Postgres) или Chroma (прототип)
< 100M       → Qdrant (по умолчанию) или Pinecone (zero ops)
< 1B         → Qdrant cluster
> 1B         → Milvus

Hybrid search → Weaviate
Лучшая фильтрация → Qdrant
Zero ops → Pinecone
Бесплатно → pgvector

Правило: выбирай БД по наихудшему сценарию,
         а не по демо-версии.
         Фильтрация на стороне БД — всегда.
         Embedding cache — если есть повторяющиеся запросы.
```

---

## Ссылки

- [[03-memory-and-rag/02-rag-advanced]] — RAG 2.0 пайплайн
- [[03-memory-and-rag/04-grace]] — GRACE для multi-hop RAG
- [Qdrant docs](https://qdrant.tech/documentation/)
- [Vector DB Comparison 2026](https://www.kargin-utkin.com/vector-database-comparison-2026-benchmarks)
