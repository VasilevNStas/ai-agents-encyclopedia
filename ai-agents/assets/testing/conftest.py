"""Pytest fixtures and helpers for AI agent testing."""

import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture
def mock_llm():
    """Mock LLM client returning controlled responses."""
    client = MagicMock()
    client.chat.completions.create = AsyncMock()

    async def mock_response(*args, **kwargs):
        return {
            "choices": [{"message": {"content": "Mock response", "role": "assistant"}}],
            "usage": {"prompt_tokens": 50, "completion_tokens": 20, "total_tokens": 70},
        }

    client.chat.completions.create.side_effect = mock_response
    return client


@pytest.fixture
def mock_vector_db():
    """Mock vector database returning sample chunks."""
    db = MagicMock()
    db.search = AsyncMock()
    db.search.return_value = [
        {"id": "1", "text": "Sample context chunk 1", "score": 0.95},
        {"id": "2", "text": "Sample context chunk 2", "score": 0.87},
    ]
    return db


@pytest.fixture
def agent_config():
    """Default agent configuration for tests."""
    return {
        "name": "test-agent",
        "model": "gpt-4o",
        "max_tokens": 4096,
        "temperature": 0.0,
        "tools": ["read", "grep", "bash"],
        "guardrails": {
            "moderation": True,
            "pii_filter": True,
            "max_turns": 50,
        },
        "budget": {"daily_usd": 1.0, "cost_per_call": 0.01},
        "cache_ttl": 300,
    }


@pytest.fixture
def sample_docs():
    """Load sample documents for RAG testing."""
    import pathlib

    fixtures_dir = pathlib.Path(__file__).parent / "fixtures"
    docs = {}
    for f in fixtures_dir.glob("*.md"):
        docs[f.stem] = f.read_text()
    return docs


@pytest.fixture
def agent_context():
    """Minimal agent execution context."""
    return {
        "messages": [],
        "tool_calls": 0,
        "tokens_used": 0,
        "cost_accrued": 0.0,
        "start_time": None,
    }
