"""SupportFlow Stage 7: LangGraph — State Graph, Streaming, Checkpointing.

Запускает SupportFlow как граф состояний вместо ReAct-цикла.
Каждый шаг — явный узел графа с типизированным состоянием.
"""

import json
import sys
import os
import time

sys.path.insert(0, os.path.dirname(__file__))
from langgraph_agent import SupportFlowGraph, compare_with_react


class LangGraphRunner:
    """Обёртка над LangGraph SupportFlow."""

    def __init__(self):
        self.graph = SupportFlowGraph()

    def run(self, user_input: str) -> dict:
        start = time.time()
        state = self.graph.run(user_input)
        duration_ms = (time.time() - start) * 1000

        trace = {
            "nodes_executed": [],
            "transitions": [],
        }

        # Build execution trace from state
        if hasattr(state, "step_count"):
            trace["nodes_executed"] = [
                "classify",
                "guardrail",
                "rag_search" if state.get("rag_results") else None,
                "llm_call",
                "tool_execute",
                "response",
            ]
            trace["nodes_executed"] = [n for n in trace["nodes_executed"] if n]

        return {
            "response": state.final_response or state.get("llm_output", ""),
            "classification": state.classification,
            "steps": state.step_count,
            "cost": state.total_cost,
            "duration_ms": round(duration_ms, 1),
            "session_id": state.session_id,
            "error": state.get("error"),
            "trace": trace,
        }

    def stream(self, user_input: str) -> list[dict]:
        """Пошаговое выполнение с промежуточными результатами."""
        events = []
        state = None

        for event in self.graph.stream(user_input):
            events.append(event)
            state = event.get("state")

        return events


def main():
    import argparse

    parser = argparse.ArgumentParser(description="SupportFlow LangGraph Agent")
    parser.add_argument(
        "--stream", action="store_true", help="Show step-by-step execution"
    )
    parser.add_argument(
        "--compare", action="store_true", help="Show ReAct vs LangGraph comparison"
    )
    parser.add_argument("query", nargs="*")
    args = parser.parse_args()

    if args.compare:
        print(compare_with_react())
        return

    agent = LangGraphRunner()
    query = " ".join(args.query)

    if query:
        if args.stream:
            print(f"\nUser: {query}\n")
            events = agent.stream(query)
            for event in events:
                node = event.get("node", "?")
                latency = event.get("latency_ms", 0)
                print(f"  [{node}] {latency}ms")
                if event.get("state"):
                    s = event["state"]
                    if s.get("llm_output"):
                        print(f"    LLM: {s['llm_output'][:100]}...")
                    if s.get("tool_result"):
                        print(f"    Tool: {s['tool_result'][:100]}...")
                    if s.get("final_response"):
                        print(f"    Final: {s['final_response'][:100]}...")
            print()
        else:
            result = agent.run(query)
            print(f"\n=== Response ===")
            print(result["response"])
            print(
                f"=== Classification: {result['classification']} | "
                f"Steps: {result['steps']} | "
                f"Cost: ${result['cost']:.4f} | "
                f"Duration: {result['duration_ms']}ms ==="
            )
    else:
        print("\nSupportFlow LangGraph Agent (interactive)")
        print("Commands: 'exit' to quit, '/stream' for step-by-step\n")
        while True:
            try:
                q = input("You: ")
                if q.lower() in ("exit", "quit"):
                    break
                if q == "/stream":
                    args.stream = True
                    print("[Stream mode on]")
                    continue
                if args.stream:
                    events = agent.stream(q)
                    for e in events:
                        node = e.get("node", "?")
                        print(f"  [{node}] {e.get('latency_ms', 0)}ms")
                result = agent.run(q)
                print(f"\nAgent: {result['response']}\n")
            except KeyboardInterrupt:
                break


if __name__ == "__main__":
    main()
