"""Tests for the core agent loop."""

import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_agent_processes_user_message(mock_llm, agent_config):
    """Agent should respond to a user message via LLM."""

    agent = Agent(config=agent_config, llm=mock_llm)
    response = await agent.process("Hello, what can you do?")

    assert response is not None
    assert len(response["content"]) > 0
    assert response["role"] == "assistant"


@pytest.mark.asyncio
async def test_agent_calls_tools_when_needed(mock_llm, agent_config):
    """Agent should invoke tools when the LLM requests it."""

    # Mock LLM to request a tool call first
    mock_llm.chat.completions.create.side_effect = [
        {
            "choices": [
                {
                    "message": {
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "call_1",
                                "function": {
                                    "name": "grep",
                                    "arguments": '{"pattern": "TODO", "path": "."}',
                                },
                            }
                        ],
                    },
                }
            ],
            "usage": {"total_tokens": 30},
        },
        {
            "choices": [{"message": {"content": "Found 5 TODOs", "role": "assistant"}}],
            "usage": {"total_tokens": 40},
        },
    ]

    agent = Agent(config=agent_config, llm=mock_llm)
    agent.tool_executor = AsyncMock()
    agent.tool_executor.execute.return_value = {
        "status": "ok",
        "matches": ["TODO fix bug"],
    }

    response = await agent.process("Find TODOs in the code")

    assert agent.tool_executor.execute.called
    assert "5 TODOs" in response["content"]


@pytest.mark.asyncio
async def test_agent_respects_max_turns(mock_llm, agent_config):
    """Agent should stop after max_turns limit."""

    agent_config["max_turns"] = 3
    agent = Agent(config=agent_config, llm=mock_llm)

    # Mock LLM to keep requesting tools
    async def never_ending(*args, **kwargs):
        return {
            "choices": [
                {
                    "message": {
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "call_x",
                                "function": {"name": "read", "arguments": "{}"},
                            }
                        ],
                    },
                }
            ],
            "usage": {"total_tokens": 10},
        }

    mock_llm.chat.completions.create.side_effect = never_ending
    agent.tool_executor = AsyncMock()
    agent.tool_executor.execute.return_value = {"status": "ok"}

    with pytest.raises(MaxTurnsExceeded):
        await agent.process("Keep going")


@pytest.mark.asyncio
async def test_agent_handles_empty_response(mock_llm, agent_config):
    """Agent should handle when LLM returns empty content."""

    mock_llm.chat.completions.create.return_value = {
        "choices": [{"message": {"content": "", "role": "assistant"}}],
        "usage": {"total_tokens": 5},
    }

    agent = Agent(config=agent_config, llm=mock_llm)
    response = await agent.process("Say nothing")

    assert response["content"] == ""  # valid but empty


@pytest.mark.asyncio
async def test_agent_accumulates_cost(mock_llm, agent_config):
    """Agent should track cost across multiple turns."""

    agent = Agent(config=agent_config, llm=mock_llm)

    # Create side_effect that returns unique cost each time
    costs = iter([0.002, 0.003, 0.001])

    async def cost_accumulator(*args, **kwargs):
        c = next(costs)
        return {
            "choices": [
                {"message": {"content": f"Response costing ${c}", "role": "assistant"}}
            ],
            "usage": {"total_tokens": int(c * 1000)},
        }

    mock_llm.chat.completions.create.side_effect = cost_accumulator

    await agent.process("Turn 1")
    await agent.process("Turn 2")
    await agent.process("Turn 3")

    assert pytest.approx(agent.total_cost, 0.001) == 0.006


@pytest.mark.asyncio
async def test_agent_cancels_on_high_cost(mock_llm, agent_config):
    """Agent should stop if daily budget is exceeded."""

    agent_config["budget"]["daily_usd"] = 0.01
    agent = Agent(config=agent_config, llm=mock_llm)

    async def expensive_call(*args, **kwargs):
        return {
            "choices": [{"message": {"content": "Expensive!", "role": "assistant"}}],
            "usage": {"total_tokens": 1000},
        }

    mock_llm.chat.completions.create.side_effect = expensive_call

    await agent.process("First call")

    with pytest.raises(BudgetExceeded):
        await agent.process("Second call that pushes over budget")
