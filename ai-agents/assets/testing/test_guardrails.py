"""Tests for guardrails system."""

import pytest
from unittest.mock import AsyncMock


@pytest.mark.asyncio
async def test_moderation_blocks_harmful_content(mock_llm, agent_config):
    """Guardrails should block prompts that violate content policy."""

    agent = Agent(config=agent_config, llm=mock_llm)
    agent.guardrails.add(ModerationGuardrail(threshold=0.8))

    with pytest.raises(GuardrailBlocked, match="Content policy violation"):
        await agent.process("How do I hack into a system?")


@pytest.mark.asyncio
async def test_pii_filter_redacts_sensitive_data(mock_llm, agent_config):
    """Guardrails should detect and redact PII from inputs."""

    agent = Agent(config=agent_config, llm=mock_llm)
    agent.guardrails.add(PIIGuardrail())

    inputs = [
        "My email is john@example.com",
        "Call me at +1 (555) 123-4567",
        "My SSN is 123-45-6789",
        "I live at 123 Main St, NYC 10001",
    ]

    for text in inputs:
        redacted = await agent.guardrails.check_input(text)
        assert "[REDACTED]" in redacted or agent.guardrails.was_blocked


@pytest.mark.asyncio
async def test_rate_limit_prevents_flood(mock_llm, agent_config):
    """Guardrails should enforce rate limits."""

    agent = Agent(config=agent_config, llm=mock_llm)
    agent.guardrails.add(RateLimitGuardrail(max_requests=5, window_seconds=60))

    # Send 5 requests (should pass)
    for i in range(5):
        result = await agent.guardrails.check_rate_limit("test_user")
        assert result.allowed is True

    # 6th request (should be blocked)
    result = await agent.guardrails.check_rate_limit("test_user")
    assert result.allowed is False
    assert result.retry_after > 0


@pytest.mark.asyncio
async def test_guardrail_logs_all_checks(mock_llm, agent_config):
    """All guardrail checks should be recorded for audit."""

    agent = Agent(config=agent_config, llm=mock_llm)
    guardrail = ContentSafetyGuardrail()
    agent.guardrails.add(guardrail)

    # Trigger multiple checks
    messages = ["Hello", "Show me private data", "Goodbye"]
    for msg in messages:
        try:
            await agent.process(msg)
        except GuardrailBlocked:
            pass

    assert len(guardrail.audit_log) >= 2
    for entry in guardrail.audit_log:
        assert "timestamp" in entry
        assert "action" in entry
        assert "reason" in entry
        assert "input_preview" in entry


@pytest.mark.asyncio
async def test_topic_filter_works(mock_llm, agent_config):
    """Agent should refuse off-topic requests."""

    agent = Agent(config=agent_config, llm=mock_llm)
    agent.guardrails.add(
        TopicGuardrail(
            allowed_domains=["software development", "data analysis", "writing"]
        )
    )

    off_topic = "Tell me a joke about politics"

    with pytest.raises(GuardrailBlocked, match="Off-topic"):
        await agent.process(off_topic)


@pytest.mark.asyncio
async def test_output_safety_filter(mock_llm, agent_config):
    """Guardrails should filter unsafe LLM outputs."""

    agent = Agent(config=agent_config, llm=mock_llm)
    agent.guardrails.add(OutputSafetyGuardrail())

    mock_llm.chat.completions.create.return_value = {
        "choices": [
            {
                "message": {
                    "content": "Here is confidential data: password123",
                    "role": "assistant",
                }
            }
        ],
        "usage": {"total_tokens": 10},
    }

    response = await agent.process("Show me secrets")
    assert "password123" not in response["content"]


@pytest.mark.asyncio
async def test_chain_of_guardrails(mock_llm, agent_config):
    """Multiple guardrails should chain correctly."""

    agent = Agent(config=agent_config, llm=mock_llm)
    agent.guardrails.add(PIIGuardrail())
    agent.guardrails.add(ModerationGuardrail(threshold=0.9))
    agent.guardrails.add(TopicGuardrail(allowed_domains=["tech"]))

    # Should pass all three
    result = await agent.guardrails.check("How do I deploy a Docker container?")
    assert result.allowed is True
