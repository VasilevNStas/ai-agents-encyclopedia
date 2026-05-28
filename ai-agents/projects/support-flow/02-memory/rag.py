"""RAG pipeline: query rewrite → search → re-rank для SupportFlow."""

import json
import re
from dataclasses import dataclass, field
from typing import Any

from vector_store import VectorStore


@dataclass
class RAGConfig:
    top_k: int = 5
    rerank_top_k: int = 3
    chunk_size: int = 512
    chunk_overlap: int = 64


@dataclass
class RAGResult:
    chunks: list[dict]
    query: str
    original_query: str


# ============================================================
# Knowledge Base Documents
# ============================================================

SUPPORT_DOCUMENTS = [
    # Password & Account
    {
        "text": "Password reset: go to login page, click 'Forgot Password', enter email, check inbox for reset link. Link expires in 24 hours. If you don't receive the email, check spam folder or contact support.",
        "category": "account",
        "priority": 1,
    },
    {
        "text": "Account deletion: Settings → Danger Zone → Delete Account. This is irreversible. All data will be permanently removed within 30 days. You can export your data first via Settings → Export.",
        "category": "account",
        "priority": 1,
    },
    {
        "text": "Two-factor authentication: enable in Security settings. Supported methods: authenticator app (Google Authenticator, Authy), SMS backup codes. TOTP-based, rotates every 30 seconds.",
        "category": "security",
        "priority": 1,
    },
    # Billing
    {
        "text": "Billing cycle is monthly. Invoices are sent on the 1st of each month. Payment methods: credit card, PayPal, wire transfer (Enterprise). Late payment: 5-day grace period, then service suspension.",
        "category": "billing",
        "priority": 1,
    },
    {
        "text": "Plans: Basic $10/mo (1 user, 5GB storage, email support), Pro $25/mo (5 users, 50GB, priority support, API access), Enterprise custom pricing (unlimited users, custom SLAs, dedicated support).",
        "category": "billing",
        "priority": 1,
    },
    {
        "text": "Upgrade: instant. Downgrade: at end of billing cycle. Refunds: full refund within 14 days of purchase, pro-rated after 14 days. Enterprise per contract terms. Processing: 5-10 business days.",
        "category": "billing",
        "priority": 1,
    },
    {
        "text": "Discounts: annual billing gives 2 months free. Non-profit discount: 50%. Student discount: 30% (verify with .edu email). Referral program: 1 month free per referral.",
        "category": "billing",
        "priority": 2,
    },
    # Technical
    {
        "text": "API rate limits: 1000 requests/hour for Pro, 10000 for Enterprise. Endpoints: REST API at api.example.com/v1, GraphQL at api.example.com/graphql. Authentication via Bearer token.",
        "category": "tech",
        "priority": 1,
    },
    {
        "text": "Integration guides: Zapier trigger on new invoice, Slack notification on payment received, webhook events for subscription changes. See docs.example.com/integrations for full list.",
        "category": "tech",
        "priority": 2,
    },
    {
        "text": "Status page: status.example.com. Historical uptime: 99.9%. Scheduled maintenance: notified 72h in advance. Incidents posted within 5 minutes of detection.",
        "category": "tech",
        "priority": 2,
    },
    # Security & Compliance
    {
        "text": "Data encryption: AES-256 at rest, TLS 1.3 in transit. SOC 2 Type II certified. GDPR compliant. Data stored in EU (Frankfurt) or US (Virginia), configurable. Backups every 6 hours.",
        "category": "security",
        "priority": 1,
    },
    {
        "text": "API keys: generate in Developer Settings. Rotate every 90 days recommended. Never commit to version control. Use environment variables. If compromised, revoke immediately in settings.",
        "category": "security",
        "priority": 1,
    },
    {
        "text": "Privacy: we collect only essential data (email, name, usage stats). No selling of personal data. Full policy at example.com/privacy. Data Processing Agreement available for Enterprise.",
        "category": "legal",
        "priority": 1,
    },
    # Troubleshooting
    {
        "text": "Common errors: 401 Unauthorized (check API key), 429 Rate Limit (wait or upgrade), 503 Service Unavailable (check status page). For 4xx errors, fix the request. For 5xx, contact support.",
        "category": "tech",
        "priority": 1,
    },
    {
        "text": "Email not received: check spam folder, verify email in settings, whitelist our domain. If using Gmail, check Promotions tab. Still missing? Contact support with your email address.",
        "category": "account",
        "priority": 2,
    },
    {
        "text": "Slow performance: check internet connection, clear browser cache, try incognito mode. If using VPN, try disabling. Still slow? Check status page for ongoing incidents.",
        "category": "tech",
        "priority": 3,
    },
]


# ============================================================
# Query Rewriting
# ============================================================


class QueryRewriter:
    """Rewrite user query for better retrieval."""

    EXPANSIONS = {
        "сбросить пароль": "password reset forgot",
        "изменить email": "change email address update",
        "удалить аккаунт": "delete account removal cancel",
        "стоимость": "pricing cost price plan",
        "возврат": "refund money back cancel",
        "безопасность": "security encryption auth",
        "интеграция": "integration api webhook zapier",
        "ошибка": "error bug issue troubleshooting",
    }

    def rewrite(self, query: str) -> str:
        """Expand query with synonyms for better retrieval."""

        query_lower = query.lower()
        for keyword, expansion in self.EXPANSIONS.items():
            if keyword in query_lower:
                return f"{query} {expansion}"

        # Add common support terms
        support_terms = ["help", "support", "guide", "how to"]
        if not any(term in query_lower for term in support_terms):
            query = f"{query} support guide"

        return query

    def extract_filters(self, query: str) -> dict:
        """Extract category filters from query."""

        query_lower = query.lower()
        category_map = {
            "billing": [
                "billing",
                "payment",
                "invoice",
                "plan",
                "price",
                "cost",
                "subscription",
                "upgrade",
                "downgrade",
                "refund",
            ],
            "account": [
                "account",
                "password",
                "login",
                "email",
                "profile",
                "delete",
                "settings",
            ],
            "security": [
                "security",
                "encryption",
                "auth",
                "api key",
                "privacy",
                "compliance",
                "gdpr",
                "soc",
            ],
            "tech": [
                "api",
                "integration",
                "error",
                "performance",
                "status",
                "rate limit",
                "webhook",
            ],
        }

        for category, keywords in category_map.items():
            if any(k in query_lower for k in keywords):
                return {"category": category}
        return {}


# ============================================================
# Re-ranker
# ============================================================


class ReRanker:
    """Re-rank search results by relevance."""

    def rerank(self, query: str, results: list[dict]) -> list[dict]:
        """Score and re-rank results by multiple signals."""

        query_words = set(query.lower().split())

        for result in results:
            score = result.get("score", 0.0)

            # Boost: exact phrase match
            text_lower = result["text"].lower()
            if query.lower() in text_lower:
                score *= 1.5

            # Boost: word overlap
            text_words = set(text_lower.split())
            overlap = len(query_words & text_words)
            score += overlap * 0.05

            # Boost: short and direct answers
            if len(result["text"]) < 300:
                score *= 1.2

            # Boost: priority field
            priority = result.get("metadata", {}).get("priority", 3)
            score += (4 - priority) * 0.1

            result["score"] = round(score, 4)

        results.sort(key=lambda r: r["score"], reverse=True)
        return results


# ============================================================
# RAG Pipeline
# ============================================================


class RAGPipeline:
    """Полный RAG пайплайн: index → rewrite → search → re-rank."""

    def __init__(self, config: RAGConfig | None = None):
        self.config = config or RAGConfig()
        self.vector_store = VectorStore()
        self.rewriter = QueryRewriter()
        self.reranker = ReRanker()
        self._indexed = False

    def index_documents(self, documents: list[dict] | None = None):
        """Index support documents into vector store."""

        docs = documents or SUPPORT_DOCUMENTS
        texts = []
        metadata_list = []

        for doc in docs:
            # Chunk long documents
            chunks = self._chunk_text(doc["text"])
            for chunk in chunks:
                texts.append(chunk)
                metadata_list.append(
                    {
                        "category": doc.get("category", "general"),
                        "priority": doc.get("priority", 3),
                    }
                )

        self.vector_store.add_documents(texts, metadata_list)
        self._indexed = True
        print(f"[RAG] Indexed {len(texts)} chunks from {len(docs)} documents")

    def retrieve(self, query: str, top_k: int | None = None) -> RAGResult:
        """Полный retrieval: rewrite → search → re-rank."""

        if not self._indexed:
            self.index_documents()

        # 1. Query rewriting
        rewritten = self.rewriter.rewrite(query)
        filters = self.rewriter.extract_filters(query)

        # 2. Vector search
        results = self.vector_store.search(rewritten, top_k=top_k or self.config.top_k)

        # 3. Apply filters
        if filters:
            results = [
                r
                for r in results
                if r.get("metadata", {}).get("category") == filters.get("category")
            ]

        # 4. Re-rank
        results = self.reranker.rerank(query, results)

        # 5. Trim to final count
        results = results[: self.config.rerank_top_k]

        return RAGResult(
            chunks=results,
            query=rewritten,
            original_query=query,
        )

    def format_context(self, result: RAGResult) -> str:
        """Format RAG results as context for LLM prompt."""

        if not result.chunks:
            return ""

        parts = ["Relevant documentation:"]
        for i, chunk in enumerate(result.chunks, 1):
            parts.append(f"\n[{i}] {chunk['text']}")

        return "\n".join(parts)

    def _chunk_text(self, text: str) -> list[str]:
        """Split text into chunks of chunk_size with overlap."""

        if len(text) <= self.config.chunk_size:
            return [text]

        chunks = []
        start = 0
        while start < len(text):
            end = start + self.config.chunk_size
            if end < len(text):
                # Try to break at sentence boundary
                boundary = text.rfind(". ", start, end)
                if boundary > start:
                    end = boundary + 1
            chunks.append(text[start:end].strip())
            start = end - self.config.chunk_overlap

        return chunks


# ============================================================
# Quick test
# ============================================================

if __name__ == "__main__":
    rag = RAGPipeline()
    result = rag.retrieve("how to reset my password?")
    print(f"Query: {result.original_query}")
    print(f"Rewritten: {result.query}")
    print(f"Results: {len(result.chunks)}")
    for i, c in enumerate(result.chunks, 1):
        print(f"\n[{i}] (score={c['score']}) {c['text'][:120]}...")
