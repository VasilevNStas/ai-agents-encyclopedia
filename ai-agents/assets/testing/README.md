# Test suite for AI agents

```
testing/
├── conftest.py               # Pytest fixtures
├── test_agent_loop.py        # Core agent loop tests
├── test_guardrails.py        # Guardrails (moderation, PII, rate limit)
├── test_rag.py               # RAG pipeline tests
├── test_tools.py             # Tool execution tests
├── test_telemetry.py         # Observability tests
├── test_budget.py            # Budget and cost tracking
├── test_prompts.py           # Prompt rendering tests
└── fixtures/
    ├── sample_docs.md         # Test documents for RAG
    └── mock_responses.py      # Mock LLM responses
```
