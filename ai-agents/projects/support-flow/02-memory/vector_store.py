"""Chroma-based vector store wrapper for SupportFlow."""

import uuid
from typing import Optional

from src.agent.config import RAGConfig


class MockEmbeddings:
    """Mock embedding model returning deterministic vectors for demo.

    In production, replace with OpenAI's text-embedding-3-small
    or Cohere embed via Chroma's native integration.
    """

    def __init__(self, model: str = "text-embedding-3-small"):
        self.model = model
        self.dimension = 384

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)

    def _embed(self, text: str) -> list[float]:
        seed = sum(ord(c) for c in text) % 1000
        return [(seed + i) / 1000.0 for i in range(self.dimension)]


class VectorStore:
    """Chroma-based vector store for document storage and retrieval.

    Uses mock embeddings for demo. In production, swap MockEmbeddings
    with Chroma's OpenAIEmbeddingFunction or similar.

    Attributes:
        config: RAG configuration with collection name and top_k settings.
    """

    def __init__(self, config: Optional[RAGConfig] = None):
        self.config = config or RAGConfig()
        self.embedding_fn = MockEmbeddings(model=self.config.embedding_model)
        self.collection_name = self.config.collection_name
        self._documents: list[dict] = []

    def add_documents(
        self, texts: list[str], metadata_list: Optional[list[dict]] = None
    ) -> None:
        """Add documents to the vector store.

        Args:
            texts: List of document texts.
            metadata_list: Optional list of metadata dicts (one per text).
                Defaults to empty dicts if not provided.

        Raises:
            ValueError: If texts and metadata_list lengths differ.
        """
        if not texts:
            return
        if metadata_list is None:
            metadata_list = [{} for _ in texts]
        if len(texts) != len(metadata_list):
            raise ValueError("texts and metadata_list must have the same length")

        embeddings = self.embedding_fn.embed_documents(texts)
        for text, meta, emb in zip(texts, metadata_list, embeddings):
            self._documents.append(
                {
                    "id": str(uuid.uuid4()),
                    "text": text,
                    "metadata": meta,
                    "embedding": emb,
                }
            )

    def search(self, query: str, top_k: Optional[int] = None) -> list[dict]:
        """Search for documents similar to the query.

        Args:
            query: Search query string.
            top_k: Number of results to return. Defaults to config.top_k.

        Returns:
            List of dicts with keys: id, text, metadata, score.
        """
        if not self._documents:
            return []
        top_k = top_k or self.config.top_k
        query_emb = self.embedding_fn.embed_query(query)

        scored = [
            (self._cosine_similarity(query_emb, doc["embedding"]), doc)
            for doc in self._documents
        ]
        scored.sort(key=lambda x: x[0], reverse=True)

        return [
            {
                "id": doc["id"],
                "text": doc["text"],
                "metadata": doc["metadata"],
                "score": round(score, 4),
            }
            for score, doc in scored[:top_k]
        ]

    def delete_collection(self) -> None:
        """Remove all documents from the store."""
        self._documents.clear()

    def _cosine_similarity(self, a: list[float], b: list[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5
        if not norm_a or not norm_b:
            return 0.0
        return dot / (norm_a * norm_b)

    @property
    def document_count(self) -> int:
        """Number of documents currently stored."""
        return len(self._documents)
