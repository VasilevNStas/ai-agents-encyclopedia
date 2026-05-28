"""SupportFlow Stage 5: Cost Optimization — Model Router + Budget Tracking."""

import json
import os
import sys
import time
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "03-production"))
from agent import ProductionAgent, AgentConfig, ModelConfig

sys.path.insert(0, os.path.dirname(__file__))
from model_router import ModelRouter


class CostOptimizedAgent:
    """Агент с model routing и cost tracking."""

    MODEL_COST_MAP = {
        "claude-haiku-4.6": 0.002,
        "gpt-4o-mini": 0.002,
        "claude-sonnet-4.6": 0.01,
        "gpt-4o": 0.01,
        "claude-opus-4.7": 0.05,
        "gpt-4.5": 0.05,
        "deepseek-chat": 0.001,
    }

    def __init__(self, config: AgentConfig | None = None):
        self.config = config or AgentConfig()
        self.router = ModelRouter()
        self.total_cost = 0.0
        self.total_calls = 0
        self.model_usage: dict[str, int] = {}
        self.baseline_cost_total = 0.0

    def run(self, user_input: str) -> dict:
        start = time.time()

        # 1. Route to appropriate model
        chosen_model = self.router.route(user_input)
        cost_per_call = self.MODEL_COST_MAP.get(chosen_model, 0.005)
        baseline_cost = 0.01  # sonnet baseline

        self.total_calls += 1
        self.model_usage[chosen_model] = self.model_usage.get(chosen_model, 0) + 1
        self.total_cost += cost_per_call
        self.baseline_cost_total += baseline_cost

        if self.config.verbose:
            print(
                f"\n[Router] {user_input[:60]}... → {chosen_model} "
                f"(${cost_per_call:.3f}, saved ${baseline_cost - cost_per_call:.3f})"
            )

        # 2. Execute with chosen model
        custom_config = AgentConfig(
            model=ModelConfig(
                provider=self._get_provider(chosen_model),
                model=chosen_model,
            ),
            verbose=self.config.verbose,
        )
        agent = ProductionAgent(custom_config)
        result = agent.run(user_input)

        # 3. Annotate
        result["model_used"] = chosen_model
        result["cost"] = cost_per_call
        result["savings_vs_baseline"] = round(baseline_cost - cost_per_call, 4)
        result["total_session_cost"] = round(self.total_cost, 4)

        return result

    def _get_provider(self, model: str) -> str:
        if model.startswith("gpt"):
            return "openai"
        if model.startswith("claude"):
            return "anthropic"
        if model.startswith("deepseek"):
            return "deepseek"
        return self.config.model.provider

    def stats(self) -> dict:
        return {
            "total_calls": self.total_calls,
            "total_cost": round(self.total_cost, 4),
            "baseline_cost (sonnet)": round(self.baseline_cost_total, 4),
            "savings": round(self.baseline_cost_total - self.total_cost, 4),
            "models_used": dict(sorted(self.model_usage.items())),
        }


def main():
    import argparse

    parser = argparse.ArgumentParser(description="SupportFlow Cost-Optimized Agent")
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("query", nargs="*")
    args = parser.parse_args()

    config = AgentConfig(verbose=not args.quiet)
    agent = CostOptimizedAgent(config)

    query = " ".join(args.query)
    if query:
        result = agent.run(query)
        print(f"\n=== Response ===")
        print(result["response"])
        print(
            f"=== Model: {result.get('model_used', 'N/A')} | "
            f"Cost: ${result.get('cost', 0):.4f} | "
            f"Saved: ${result.get('savings_vs_baseline', 0):.4f} ==="
        )
    else:
        print(f"\nSupportFlow Cost-Optimized Agent (interactive)")
        while True:
            try:
                q = input("You: ")
                if q.lower() in ("exit", "quit"):
                    break
                result = agent.run(q)
                print(f"\nAgent: {result['response']}\n")
            except KeyboardInterrupt:
                break

    s = agent.stats()
    print(
        f"\nSession: {s['total_calls']} calls | "
        f"${s['total_cost']} spent | "
        f"saved ${s['savings']} ({s['models_used']})"
    )


if __name__ == "__main__":
    main()
