"""RAG pipeline: rewrite, hybrid search, rerank, format context."""

import re
import sys
from pathlib import Path
from typing import Optional

from ..agent.config import RAGConfig, AgentConfig

_memory_dir = Path(__file__).resolve().parent.parent.parent / "02-memory"
if _memory_dir.exists() and str(_memory_dir) not in sys.path:
    sys.path.insert(0, str(_memory_dir))

from vector_store import VectorStore  # noqa: E402


class QueryRewriter:
    """Rewrites user queries for better retrieval.

    Simulates query expansion and reformulation strategies.
    In production, this would use an LLM call or dedicated model.
    """

    def __init__(self):
        self._stopwords = {
            "a",
            "an",
            "the",
            "is",
            "are",
            "was",
            "were",
            "do",
            "does",
            "did",
            "has",
            "have",
            "had",
            "i",
            "you",
            "he",
            "she",
            "it",
            "we",
            "they",
            "my",
            "your",
            "his",
            "her",
            "its",
            "our",
            "their",
        }

    def rewrite(self, query: str) -> list[str]:
        """Expand query into multiple search variants.

        Args:
            query: Original user query.

        Returns:
            List of query variants for multi-faceted retrieval.
        """
        simple = query.strip().rstrip("?.")
        keywords = [w for w in simple.split() if w.lower() not in self._stopwords]
        expanded = " ".join(keywords) if len(keywords) > 1 else simple

        return [
            simple,
            expanded,
            f"{simple} guide tutorial",
            f"{simple} how to",
        ]

    def compress_history(self, query: str, history: list[str]) -> str:
        """Prepend recent conversation history to the query."""
        if not history:
            return query
        return f"{' '.join(history[-3:])} {query}"


class HybridRetriever:
    """Combines dense (vector) and sparse (keyword) search.

    Uses VectorStore for dense retrieval and a simple token-based
    BM25 approximation for sparse retrieval.
    """

    def __init__(self, vector_store: VectorStore):
        self.vector_store = vector_store

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        """Run hybrid search: fuse dense and sparse results."""
        dense_results = self.vector_store.search(query, top_k=top_k * 2)
        sparse_results = self._bm25_search(query, top_k=top_k * 2)
        return self._fuse(dense_results, sparse_results, top_k=top_k)

    def _bm25_search(self, query: str, top_k: int) -> list[dict]:
        """Simple term-frequency based sparse search (BM25 approximation)."""
        query_terms = set(re.findall(r"\w+", query.lower()))
        if not query_terms:
            return []

        scored = []
        for doc in self.vector_store._documents:
            doc_terms = re.findall(r"\w+", doc["text"].lower())
            doc_len = max(len(doc_terms), 1)
            term_counts = {}
            for t in doc_terms:
                term_counts[t] = term_counts.get(t, 0) + 1

            score = sum(term_counts.get(term, 0) / doc_len for term in query_terms)
            if score > 0:
                scored.append((score, doc))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            {
                "id": doc["id"],
                "text": doc["text"],
                "metadata": doc["metadata"],
                "score": score,
            }
            for score, doc in scored[:top_k]
        ]

    def _fuse(
        self,
        dense: list[dict],
        sparse: list[dict],
        top_k: int,
        alpha: float = 0.7,
    ) -> list[dict]:
        """Reciprocal rank fusion of dense and sparse results."""
        scores: dict[str, float] = {}
        docs: dict[str, dict] = {}

        for i, r in enumerate(dense):
            doc_id = r["id"]
            scores[doc_id] = scores.get(doc_id, 0) + alpha * (1.0 / (i + 1))
            docs[doc_id] = r

        for i, r in enumerate(sparse):
            doc_id = r["id"]
            scores[doc_id] = scores.get(doc_id, 0) + (1 - alpha) * (1.0 / (i + 1))
            docs[doc_id] = r

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return [
            {**docs[doc_id], "fusion_score": round(score, 4)}
            for doc_id, score in ranked[:top_k]
        ]


class Reranker:
    """Re-ranks search results using a simulated cross-encoder.

    In production, replace with Cohere or a cross-encoder model.
    """

    def rerank(self, query: str, results: list[dict], top_k: int = 3) -> list[dict]:
        """Re-rank results by simulated relevance to the query."""
        if not results:
            return []

        scored = [(self._simulate_relevance(query, r["text"]), r) for r in results]
        scored.sort(key=lambda x: x[0], reverse=True)

        return [{**r, "rerank_score": round(score, 4)} for score, r in scored[:top_k]]

    def _simulate_relevance(self, query: str, text: str) -> float:
        query_terms = set(re.findall(r"\w+", query.lower()))
        text_lower = text.lower()
        if not query_terms:
            return 0.0
        matches = sum(1 for t in query_terms if t in text_lower)
        return matches / len(query_terms)


class RAGPipeline:
    """Full RAG pipeline: rewrite, search, rerank, format context.

    Usage:
        pipeline = RAGPipeline()
        result = pipeline.run("How do I reset my password?")
        context = result["context"]  # formatted string for LLM prompt
    """

    def __init__(
        self,
        config: Optional[RAGConfig] = None,
        vector_store: Optional[VectorStore] = None,
    ):
        self.config = config or RAGConfig()
        self.vector_store = vector_store or VectorStore(config=self.config)
        self.rewriter = QueryRewriter()
        self.retriever = HybridRetriever(self.vector_store)
        self.reranker = Reranker()

    def run(
        self,
        query: str,
        top_k: Optional[int] = None,
        history: Optional[list[str]] = None,
    ) -> dict:
        """Execute the full RAG pipeline.

        Args:
            query: User's question.
            top_k: Number of final results. Defaults to config.rerank_top_k.
            history: Recent conversation history for context.

        Returns:
            Dict with keys: query, rewritten_queries, results,
            context (formatted string), result_count, error (if any).
        """
        try:
            rewritten = self.rewriter.rewrite(query)
            combined_query = rewritten[0]

            if history:
                combined_query = self.rewriter.compress_history(combined_query, history)

            search_results = self.retriever.search(
                combined_query, top_k=top_k or self.config.top_k
            )

            reranked = self.reranker.rerank(
                query,
                search_results,
                top_k=top_k or self.config.rerank_top_k,
            )

            context = self._format_context(reranked)

            return {
                "query": query,
                "rewritten_queries": rewritten,
                "results": reranked,
                "context": context,
                "result_count": len(reranked),
            }

        except Exception as e:
            return {
                "query": query,
                "error": str(e),
                "results": [],
                "context": "No relevant information found.",
                "result_count": 0,
            }

    def add_to_knowledge_base(
        self,
        texts: list[str],
        metadata_list: Optional[list[dict]] = None,
    ) -> None:
        """Add documents to the underlying vector store."""
        self.vector_store.add_documents(texts, metadata_list)

    def _format_context(self, results: list[dict]) -> str:
        """Format search results as a context block for the LLM prompt."""
        if not results:
            return "No relevant information found."

        lines = ["Relevant information from knowledge base:", ""]
        for i, r in enumerate(results, 1):
            source = r.get("metadata", {}).get("source", "knowledge base")
            lines.append(f"[{i}] Source: {source}")
            lines.append(f"    {r['text']}")
            lines.append("")

        return "\n".join(lines)
