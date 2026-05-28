---
created: 2026-05-28
tags: [course/multi-modal-deep, rag, retrieval, embedding, cross-modal]
status: active
---

# Урок 19.5: Multi-modal RAG

> [!quote] Ключевая идея
> Multi-modal RAG — это не «поиск картинок по тексту». Это единое векторное пространство, где текст, изображение, аудио и видео лежат рядом. Вопрос пользователя может быть текстом, а ответ — изображением со схемой.

---

## 1. Cross-modal Embeddings (CLIP & Beyond)

```python
import torch
import numpy as np
from PIL import Image


class CrossModalEncoder:
    """Единый энкодер для текста и изображений (CLIP-based)."""

    def __init__(self, model_name: str = "openai/clip-vit-large-patch14"):
        import clip
        self.model, self.preprocess = clip.load(model_name, device=self._get_device())
        self.device = self._get_device()

    def _get_device(self) -> str:
        return "cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu"

    def encode_text(self, text: str) -> np.ndarray:
        """Текстовый эмбеддинг."""
        tokens = clip.tokenize([text]).to(self.device)
        with torch.no_grad():
            embedding = self.model.encode_text(tokens)
        return embedding.cpu().numpy().flatten().astype(np.float32)

    def encode_image(self, image: Image.Image | np.ndarray) -> np.ndarray:
        """Image embedding."""
        if isinstance(image, np.ndarray):
            image = Image.fromarray(image)
        processed = self.preprocess(image).unsqueeze(0).to(self.device)
        with torch.no_grad():
            embedding = self.model.encode_image(processed)
        return embedding.cpu().numpy().flatten().astype(np.float32)

    def similarity(self, text: str, image: Image.Image) -> float:
        """Cosine similarity между текстом и изображением."""
        text_emb = self.encode_text(text)
        image_emb = self.encode_image(image)
        return float(np.dot(text_emb, image_emb) / (np.linalg.norm(text_emb) * np.linalg.norm(image_emb)))

    def similarity_batch(self, text_emb: np.ndarray, image_embs: np.ndarray) -> np.ndarray:
        return np.dot(text_emb, image_embs.T) / (
            np.linalg.norm(text_emb) * np.linalg.norm(image_embs, axis=1)
        )


# === Audio Embeddings ===
class AudioEncoder:
    """Эмбеддинги аудио (CLAP — Contrastive Language-Audio Pretraining)."""

    def __init__(self, model_name: str = "laion/clap-htsat-fused"):
        import laion_clap
        self.model = laion_clap.CLAP_Module(enable_fusion=False)
        self.model.load_ckpt(model_name)

    def encode_audio(self, audio_path: str) -> np.ndarray:
        """Аудио-эмбеддинг из файла."""
        audio_data = self._load_audio(audio_path)
        embedding = self.model.get_audio_embedding_from_data(audio_data)
        return embedding.flatten().astype(np.float32)

    def encode_text(self, text: str) -> np.ndarray:
        """Текстовый эмбеддинг для поиска по описанию звука."""
        embedding = self.model.get_text_embedding([text])
        return embedding.flatten().astype(np.float32)
```

---

## 2. Multi-Vector Indexing

Каждый документ может иметь несколько эмбеддингов — по одному на модальность.

```python
class MultiVectorDocument:
    """Документ с эмбеддингами для каждой модальности."""

    def __init__(self, doc_id: str, content: dict):
        self.doc_id = doc_id
        self.content = content  # {"text": "...", "images": [...], "audio": [...]}

        # Embeddings per modality
        self.embeddings: dict[str, np.ndarray] = {}


class MultiVectorIndex:
    """Индекс с отдельными векторными пространствами под каждую модальность."""

    def __init__(self, text_encoder: CrossModalEncoder, audio_encoder: AudioEncoder | None = None):
        self.text_enc = text_encoder
        self.audio_enc = audio_encoder

        # Individual indices per modality
        self.indices: dict[str, "FaissIndex"] = {
            "text": FaissIndex(dim=768),
            "image": FaissIndex(dim=768),
        }
        if audio_encoder:
            self.indices["audio"] = FaissIndex(dim=512)

        self.documents: dict[str, MultiVectorDocument] = {}

    async def index_document(self, doc: MultiVectorDocument):
        """Индексирует документ по всем модальностям."""

        if "text" in doc.content:
            emb = self.text_enc.encode_text(doc.content["text"])
            doc.embeddings["text"] = emb
            self.indices["text"].add(emb, doc.doc_id)

        for img in doc.content.get("images", []):
            emb = self.text_enc.encode_image(img)
            doc.embeddings.setdefault("image", []).append(emb)
            self.indices["image"].add(emb, doc.doc_id)

        if "audio" in doc.content and self.audio_enc:
            emb = self.audio_enc.encode_audio(doc.content["audio"])
            doc.embeddings["audio"] = emb
            self.indices["audio"].add(emb, doc.doc_id)

        self.documents[doc.doc_id] = doc

    async def search(self, query: str, modalities: list[str] | None = None, top_k: int = 5) -> list[dict]:
        """Поиск по текстовому запросу во всех указанных модальностях."""

        if modalities is None:
            modalities = list(self.indices.keys())

        query_emb = self.text_enc.encode_text(query)
        results = []

        for modality in modalities:
            if modality not in self.indices:
                continue

            # Для image используем тот же текстовый query_emb (CLIP compatible)
            modality_results = self.indices[modality].search(query_emb, top_k)
            for doc_id, score in modality_results:
                results.append({
                    "doc_id": doc_id,
                    "modality": modality,
                    "score": float(score),
                    "content_snippet": self._get_snippet(doc_id, modality),
                })

        # Cross-modal re-ranking
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    def _get_snippet(self, doc_id: str, modality: str) -> str:
        doc = self.documents.get(doc_id)
        if not doc:
            return ""
        return doc.content.get(modality, doc.content.get("text", ""))[:200]
```

---

## 3. Hybrid Retrieval

```python
class HybridMultiModalRetriever:
    """Гибридный поиск: текстовый BM25 + векторный + кросс-модальный."""

    def __init__(self, vector_index: MultiVectorIndex, bm25_index: Any = None):
        self.vector = vector_index
        self.bm25 = bm25_index  # BM25 index (текст)
        self.alpha = 0.7  # Вес векторного поиска vs BM25

    async def hybrid_search(self, query: str, top_k: int = 5) -> list[dict]:
        """Объединяет BM25 + векторный + кросс-модальный поиск."""

        results = {}

        # 1. BM25 search (текст)
        if self.bm25:
            bm25_results = self.bm25.search(query, top_k=top_k * 2)
            for doc_id, score in bm25_results:
                results[doc_id] = results.get(doc_id, 0) + (1 - self.alpha) * score

        # 2. Vector search (текст → текст + изображения)
        vector_results = await self.vector.search(query, top_k=top_k * 2)
        for r in vector_results:
            results[r["doc_id"]] = results.get(r["doc_id"], 0) + self.alpha * r["score"]

        # 3. Cross-modal search (если запрос содержит image)
        # Если пользователь приложил картинку, ищем похожие изображения

        # Sort by combined score
        sorted_results = sorted(results.items(), key=lambda x: x[1], reverse=True)
        return [
            {"doc_id": doc_id, "score": score, "source": "hybrid"}
            for doc_id, score in sorted_results[:top_k]
        ]

    async def search_with_image_query(self, query_image: Image.Image, text_query: str = "", top_k: int = 5) -> list[dict]:
        """Поиск по изображению + опциональному тексту."""

        query_emb = self.vector.text_enc.encode_image(query_image)
        text_emb = self.vector.text_enc.encode_text(text_query) if text_query else None

        # Fusion: усредняем эмбеддинги
        if text_emb is not None:
            query_emb = (query_emb + text_emb) / 2

        results = self.vector.indices["image"].search(query_emb, top_k)
        return [
            {"doc_id": doc_id, "score": float(score), "modality": "image"}
            for doc_id, score in results
        ]
```

---

## 4. Cross-modal Re-ranking

После гибридного поиска нужно переранжировать результаты, учитывая семантическую релевантность между модальностями.

```python
class CrossModalReRanker:
    """Re-ranking результатов поиска с учётом кросс-модальной релевантности."""

    def __init__(self, cross_encoder: Any = None):
        self.cross_encoder = cross_encoder  # Например, CLIP-based cross-encoder

    async def rerank(self, query: str, results: list[dict], top_k: int = 5) -> list[dict]:
        """Переранжирует результаты гибридного поиска."""

        # 1. Cross-encoder scoring
        scored = []
        for r in results:
            content = r.get("content_snippet", "")
            # Для изображений используем CLIP similarity
            if r["modality"] == "image":
                relevance = await self._image_text_relevance(query, r.get("image"))
            else:
                relevance = self._text_text_relevance(query, content)

            scored.append({**r, "relevance": relevance})

        # 2. Reciprocal Rank Fusion (RRF)
        scored = self._rrf_merge(
            results,           # original ranking
            scored,            # cross-encoder ranking
        )

        scored.sort(key=lambda x: x["combined_score"], reverse=True)
        return scored[:top_k]

    def _rrf_merge(self, list1: list[dict], list2: list[dict], k: int = 60) -> list[dict]:
        """Reciprocal Rank Fusion: объединение двух ранжированных списков."""

        scores = {}

        for rank, r in enumerate(list1):
            doc_id = r["doc_id"]
            scores[doc_id] = scores.get(doc_id, 0) + 1 / (k + rank + 1)

        for rank, r in enumerate(list2):
            doc_id = r["doc_id"]
            scores[doc_id] = scores.get(doc_id, 0) + 1 / (k + rank + 1)

        result = sorted(list1, key=lambda r: scores.get(r["doc_id"], 0), reverse=True)
        for r in result:
            r["combined_score"] = scores.get(r["doc_id"], 0)

        return result
```

---

## 5. Multi-modal Context Building

```python
class MultiModalContextBuilder:
    """Сборка контекста из разных модальностей для LLM."""

    def __init__(self, max_tokens: int = 8000):
        self.max_tokens = max_tokens
        self.content: list[dict] = []

    async def build_context(self, query: str, retrieved: list[dict]) -> list[dict]:
        """Собирает мультимодальный контекст для передачи в LLM."""

        context = []
        tokens_used = 0

        for r in retrieved:
            doc_id = r["doc_id"]
            modality = r.get("modality", "text")
            doc = self._get_full_doc(doc_id)

            if modality == "text" and doc.get("text"):
                snippet = doc["text"][:2000]
                context.append({"type": "text", "text": f"[Source {doc_id}]: {snippet}"})
                tokens_used += len(snippet) // 4

            elif modality == "image" and doc.get("image"):
                # Изображение может стоить 1000+ токенов — считаем
                image_tokens = self._estimate_image_tokens(doc["image"])
                if tokens_used + image_tokens <= self.max_tokens:
                    context.append({"type": "image", "image": doc["image"]})
                    tokens_used += image_tokens

            elif modality == "audio" and doc.get("transcript"):
                snippet = doc["transcript"][:1000]
                context.append({"type": "text", "text": f"[Audio Transcript {doc_id}]: {snippet}"})
                tokens_used += len(snippet) // 4

            if tokens_used >= self.max_tokens:
                break

        # Query goes first
        context.insert(0, {"type": "text", "text": query})
        return context

    def _estimate_image_tokens(self, image: Image.Image) -> int:
        """Приблизительный подсчёт токенов для изображения (GPT-4o pricing)."""
        w, h = image.size
        tiles = ((w + 155) // 156) * ((h + 155) // 156)
        return 85 + 170 * tiles  # base + tiles cost
```

---

## 6. Multi-modal RAG Pipeline (Complete)

```python
class MultiModalRAGPipeline:
    """Полный пайплайн мультимодального RAG."""

    def __init__(self, encoder: CrossModalEncoder, llm: Any, vector_store: Any):
        self.encoder = encoder
        self.llm = llm
        self.index = MultiVectorIndex(encoder)
        self.retriever = HybridMultiModalRetriever(self.index)
        self.reranker = CrossModalReRanker()
        self.context_builder = MultiModalContextBuilder()

    async def answer(self, query: str, query_image: Image.Image | None = None) -> dict:
        """Полный цикл RAG: retrieve → rerank → build → generate."""

        # 1. Retrieve
        if query_image:
            retrieved = await self.retriever.search_with_image_query(query_image, query)
        else:
            retrieved = await self.retriever.hybrid_search(query)

        # 2. Rerank
        reranked = await self.reranker.rerank(query, retrieved)

        # 3. Build context
        context = await self.context_builder.build_context(query, reranked)

        # 4. Generate
        response = await self.llm.generate(
            messages=[
                {"role": "system", "content": "Answer the query using the provided context."},
                {"role": "user", "content": context},
            ]
        )

        return {
            "query": query,
            "has_image": query_image is not None,
            "retrieved": len(retrieved),
            "reranked": len(reranked),
            "context_modalities": [c["type"] for c in context],
            "response": response,
        }
```

---

## Резюме

```
Multi-modal RAG Pipeline:

Query (text ± image)
       │
       ▼
┌────────────────┐
│ 1. Retrieve    │ ← BM25 + Vector + Cross-modal
│ 2. Re-rank     │ ← Cross-encoder + RRF
│ 3. Build       │ ← Multi-modal context (text+images+transcripts)
│ 4. Generate    │ ← LLM with multi-modal context
└────────────────┘
       │
       ▼
Response (text + optional images)

Ключевые компоненты:
  — CLIP encoder: единое пространство текст↔изображение
  — CLAP encoder: текст↔аудио
  — Multi-vector index: отдельный FAISS под модальность
  — Hybrid retriever: BM25 + vector search
  — Cross-modal reranker: RRF + CLIP similarity
```

---

## Практическое задание

1. Реализуй CrossModalEncoder на основе CLIP для поиска изображений по тексту.

2. Собери MultiVectorIndex с отдельными индексами для текста и изображений.

3. Добавь HybridMultiModalRetriever с BM25 + векторным поиском.

4. Реализуй MultiModalRAGPipeline end-to-end: query → ответ с картинками.

---

## Проверь себя

1. Чем CLIP отличается от обычного text encoder?
2. Зачем нужны отдельные векторные индексы под каждую модальность?
3. Как работает гибридный поиск (BM25 + vector + cross-modal)?
4. Зачем нужен re-ranker, если уже есть vector search?
5. Как строится multi-modal контекст для LLM?

---

## Ссылки

- [[01-economics-architecture]] — экономика модальностей
- [[02-vision-deep]] — vision deep dive
- [[04-video-deep]] — video agents
- [[06-production]] — следующий урок: production multi-modal
- [[../09-advanced-rag-agents/01-agentic-rag]] — advanced RAG basics
