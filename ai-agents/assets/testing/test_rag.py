"""Tests for RAG (Retrieval-Augmented Generation) pipeline."""

import pytest
from unittest.mock import AsyncMock


@pytest.mark.asyncio
async def test_rag_retrieves_relevant_chunks(mock_llm, mock_vector_db, agent_config):
    """RAG should retrieve relevant context chunks for a query."""

    agent = Agent(config=agent_config, llm=mock_llm)
    agent.rag = RAGPipeline(vector_db=mock_vector_db)

    chunks = await agent.rag.retrieve("What is test-driven development?")

    assert len(chunks) == 2
    assert all("text" in c for c in chunks)
    assert chunks[0]["score"] >= chunks[1]["score"]  # sorted by relevance


@pytest.mark.asyncio
async def test_rag_injects_context_into_prompt(mock_llm, agent_config):
    """RAG should inject retrieved context into the LLM prompt."""

    agent = Agent(config=agent_config, llm=mock_llm)
    agent.rag = RAGPipeline(mock_vector_db)
    agent.rag.retrieve = AsyncMock()
    agent.rag.retrieve.return_value = [
        {"text": "TDD stands for Test-Driven Development", "score": 0.95},
    ]

    prompt = await agent.rag.build_prompt(
        query="What is TDD?",
        system_instruction="Answer based on context.",
    )

    assert "TDD stands for Test-Driven Development" in prompt
    assert "What is TDD?" in prompt


@pytest.mark.asyncio
async def test_rag_handles_empty_results(mock_llm, agent_config):
    """RAG should handle empty retrieval gracefully."""

    agent = Agent(config=agent_config, llm=mock_llm)
    mock_db = MagicMock()
    mock_db.search = AsyncMock(return_value=[])
    agent.rag = RAGPipeline(vector_db=mock_db)

    prompt = await agent.rag.build_prompt(
        query="Something obscure",
        system_instruction="Say if you don't know.",
    )

    assert prompt is not None
    assert "Something obscure" in prompt


@pytest.mark.asyncio
async def test_rag_reranks_by_score(mock_llm, agent_config):
    """RAG should rerank chunks by relevance score."""

    rag = RAGPipeline(vector_db=None)

    chunks = [
        {"text": "C", "score": 0.5},
        {"text": "A", "score": 0.95},
        {"text": "B", "score": 0.75},
    ]

    reranked = rag.rerank(chunks, top_k=2)
    assert len(reranked) == 2
    assert reranked[0]["text"] == "A"
    assert reranked[1]["text"] == "B"


@pytest.mark.asyncio
async def test_rag_respects_max_context_length(mock_llm, agent_config):
    """RAG should respect the max context window."""

    rag = RAGPipeline(vector_db=None, max_context_chars=50)

    chunks = [
        {
            "text": "This is a very long chunk that should be truncated at some point maybe",
            "score": 0.9,
        },
        {"text": "Short", "score": 0.8},
    ]

    context = rag.format_context(chunks)
    assert len(context) <= 50  # within limit


@pytest.mark.asyncio
async def test_rag_caches_queries(mock_llm, agent_config):
    """RAG should cache frequent queries to reduce latency."""

    mock_db = MagicMock()
    mock_db.search = AsyncMock()
    mock_db.search.return_value = [{"text": "Cached result", "score": 0.99}]

    rag = RAGPipeline(vector_db=mock_db, cache_ttl=300)
    q = "What is RAG?"

    result1 = await rag.retrieve(q)
    result2 = await rag.retrieve(q)  # should use cache

    assert mock_db.search.call_count == 1  # only called once
    assert result1 == result2
