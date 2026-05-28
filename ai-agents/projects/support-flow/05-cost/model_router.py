"""Intelligent model router — selects cost-appropriate model per query."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


MODEL_COSTS: dict[str, dict[str, float]] = {
    "claude-haiku-4.6": {"input": 0.25, "output": 1.25},
    "claude-sonnet-4.6": {"input": 3.00, "output": 15.00},
    "claude-opus-4.7": {"input": 15.00, "output": 75.00},
}

BASELINE_MODEL = "claude-sonnet-4.6"


@dataclass
class RoutingStats:
    """Aggregated routing statistics."""

    total_queries: int = 0
    haiku_count: int = 0
    sonnet_count: int = 0
    opus_count: int = 0
    estimated_cost: float = 0.0
    baseline_cost: float = 0.0

    @property
    def savings(self) -> float:
        return round(self.baseline_cost - self.estimated_cost, 4)

    @property
    def savings_pct(self) -> float:
        if self.baseline_cost == 0:
            return 0.0
        return round((self.savings / self.baseline_cost) * 100, 1)


class ModelRouter:
    """Routes queries to a cost-appropriate model based on complexity and context.

    Tiers:
        - Haiku  -> simple queries (FAQs, greetings)
        - Sonnet -> complex queries (multi-step reasoning, RAG)
        - Opus   -> escalated queries (high priority, sensitive)
    """

    SIMPLE_PATTERNS: list[str] = [
        r"\b(hi|hello|hey|greetings|good morning|good evening)\b",
        r"\b(thanks|thank you|thx|appreciate it)\b",
        r"\b(bye|goodbye|see you|later)\b",
        r"^(what is|who is|when is|where is)\s+\w+",
        r"\b(faq|help|guide|manual)\b",
        r"\b(yes|no|ok|okay|sure|fine|alright)\b",
        r"(how are|how do) you",
        r"what (can|do) you do",
        r"\b(password reset|login|logout|sign in)\b",
    ]

    COMPLEX_PATTERNS: list[str] = [
        r"\b(because|reason|explain|why|how come)\b",
        r"\b(compare|contrast|difference|similarities)\b",
        r"\b(analyze|analysis|evaluate|assessment)\b",
        r"\b(summarize|summary|synopsis|overview)\b",
        r"\b(steps|procedure|process|workflow|pipeline)\b",
        r"\b(troubleshoot|debug|diagnose|fix|error|issue|bug)\b",
        r"\b(investigate|research|find|search|locate)\b",
        r"\b(multiple|several|various|combination)\b",
        r"\b(document|report|write|draft|compose|generate)\b",
        r"\b(integrate|deploy|migrate|configure|implement)\b",
        r"\b(architecture|design|pattern|strategy|approach)\b",
    ]

    def __init__(self, avg_input_tokens: int = 500, avg_output_tokens: int = 300):
        self.stats = RoutingStats()
        self.avg_input_tokens = avg_input_tokens
        self.avg_output_tokens = avg_output_tokens

    def is_simple_query(self, query: str) -> bool:
        q = query.lower().strip()
        if len(q) < 15:
            return True
        if any(re.search(p, q) for p in self.SIMPLE_PATTERNS):
            return True
        return False

    def is_complex_query(self, query: str) -> bool:
        q = query.lower().strip()
        if len(q) > 250:
            return True
        matches = sum(1 for p in self.COMPLEX_PATTERNS if re.search(p, q))
        return matches >= 2

    def is_escalated(self, context: dict) -> bool:
        return (
            context.get("escalated", False)
            or context.get("priority") in ("high", "critical")
            or context.get("sentiment") == "angry"
        )

    def route(self, query: str, context: Optional[dict] = None) -> str:
        context = context or {}

        if self.is_escalated(context):
            model = "claude-opus-4.7"
        elif self.is_complex_query(query):
            model = "claude-sonnet-4.6"
        elif self.is_simple_query(query):
            model = "claude-haiku-4.6"
        else:
            model = "claude-sonnet-4.6"

        self._track(model)
        return model

    def _track(self, model: str) -> None:
        self.stats.total_queries += 1
        self.stats.estimated_cost += self._estimate_call_cost(model)
        self.stats.baseline_cost += self._estimate_call_cost(BASELINE_MODEL)

        if model == "claude-haiku-4.6":
            self.stats.haiku_count += 1
        elif model == "claude-sonnet-4.6":
            self.stats.sonnet_count += 1
        elif model == "claude-opus-4.7":
            self.stats.opus_count += 1

    def _estimate_call_cost(self, model: str) -> float:
        rates = MODEL_COSTS.get(model, MODEL_COSTS[BASELINE_MODEL])
        input_cost = (self.avg_input_tokens / 1_000_000) * rates["input"]
        output_cost = (self.avg_output_tokens / 1_000_000) * rates["output"]
        return round(input_cost + output_cost, 6)

    def estimate_cost(self, query: str, context: Optional[dict] = None) -> float:
        model = self.route(query, context)
        return self._estimate_call_cost(model)

    def stats_dict(self) -> dict:
        return {
            "total_queries": self.stats.total_queries,
            "haiku": self.stats.haiku_count,
            "sonnet": self.stats.sonnet_count,
            "opus": self.stats.opus_count,
            "estimated_cost": round(self.stats.estimated_cost, 4),
            "baseline_cost": round(self.stats.baseline_cost, 4),
            "savings": self.stats.savings,
            "savings_pct": self.stats.savings_pct,
        }
