#!/usr/bin/env python3
"""
LangSmith integration for agent tracing and evaluation.
"""

from langsmith import Client
from langsmith.run_trees import RunTree
import json
import time


LANGSMITH_CLIENT = None


def init_langsmith(api_key: str = None, project: str = "ai-agent"):
    """Initialize LangSmith client."""

    global LANGSMITH_CLIENT
    LANGSMITH_CLIENT = Client(api_key=api_key)
    LANGSMITH_CLIENT.create_project(project_name=project)
    return LANGSMITH_CLIENT


def trace_agent_run(
    inputs: dict,
    outputs: dict,
    steps: list[dict],
    total_cost: float,
    total_tokens: int,
    metadata: dict = None,
):
    """Create a trace for a complete agent run."""

    run = RunTree(
        name="agent-run",
        run_type="chain",
        inputs=inputs,
        outputs=outputs,
        extra={
            "metadata": metadata or {},
            "cost_usd": total_cost,
            "total_tokens": total_tokens,
        },
    )

    for i, step in enumerate(steps):
        child = run.create_child(
            name=f"step-{i}",
            run_type="llm" if step["type"] == "llm" else "tool",
            inputs=step.get("inputs", {}),
            outputs=step.get("outputs", {}),
        )
        child.end()
        child.post()

    run.end()
    if LANGSMITH_CLIENT:
        run.post()


def evaluate_agent_run(run_id: str, criteria: dict) -> dict:
    """Evaluate an agent run against criteria using LLM-as-Judge."""

    if not LANGSMITH_CLIENT:
        raise RuntimeError("LangSmith not initialized")

    results = {}
    for criterion, prompt in criteria.items():
        feedback = LANGSMITH_CLIENT.evaluate_run(
            run_id=run_id,
            evaluator=lambda run: {
                "key": criterion,
                "score": _llm_judge(run, prompt),
            },
        )
        results[criterion] = feedback

    return results


def _llm_judge(run, prompt: str) -> float:
    """Simple LLM-as-Judge scoring. Replace with actual LLM call."""
    # In production: call GPT-4 or Claude to score
    return 1.0
