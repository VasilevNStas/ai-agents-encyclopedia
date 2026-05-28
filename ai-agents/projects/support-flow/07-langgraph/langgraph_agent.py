"""LangGraph migration of the SupportFlow ReAct agent.

This is a mock implementation that demonstrates the graph structure,
state transitions, and conditional routing — without requiring
the actual langgraph package to be installed.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable


# ── State Definition ────────────────────────────────────────────────


class AgentState(dict):
    """State passed between graph nodes.

    In real LangGraph this would be a TypedDict; here we use a dict
    subclass for convenience while keeping the same conceptual shape.
    """

    def __init__(
        self,
        messages: list[dict] | None = None,
        session_id: str | None = None,
        step_count: int = 0,
        total_cost: float = 0.0,
        **kwargs,
    ):
        super().__init__()
        self["messages"] = messages or []
        self["session_id"] = session_id or str(uuid.uuid4())[:8]
        self["step_count"] = step_count
        self["total_cost"] = total_cost
        self["classification"] = ""
        self["guardrail_result"] = "allow"
        self["rag_results"] = []
        self["llm_output"] = ""
        self["tool_result"] = ""
        self["escalation"] = ""
        self["final_response"] = ""
        self["error"] = None
        for k, v in kwargs.items():
            self[k] = v

    def __getattr__(self, name: str) -> Any:
        if name in self:
            return self[name]
        raise AttributeError(f"AgentState has no attribute {name!r}")

    def __setattr__(self, name: str, value: Any) -> None:
        self[name] = value


# ── Node Functions ──────────────────────────────────────────────────


def classify_node(state: AgentState) -> AgentState:
    """Classify the input into a ticket category."""
    last_msg = state.messages[-1]["content"] if state.messages else ""
    if any(w in last_msg.lower() for w in ["refund", "billing", "payment", "invoice"]):
        state.classification = "billing"
    elif any(w in last_msg.lower() for w in ["password", "login", "error", "bug"]):
        state.classification = "technical"
    elif any(w in last_msg.lower() for w in ["security", "hack", "breach"]):
        state.classification = "security"
    else:
        state.classification = "general"
    return state


def guardrail_node(state: AgentState) -> AgentState:
    """Input guardrail check — blocks dangerous patterns."""
    last_msg = state.messages[-1]["content"] if state.messages else ""
    dangerous = ["ignore all instructions", "override", "new system prompt"]
    for pattern in dangerous:
        if pattern in last_msg.lower():
            state.guardrail_result = "block"
            return state
    state.guardrail_result = "allow"
    return state


def rag_search_node(state: AgentState) -> AgentState:
    """Search the knowledge base for relevant context."""
    query = state.messages[-1]["content"] if state.messages else ""
    state.rag_results = [
        {"text": f"Mock result for: {query}", "score": 0.95, "source": "kb"},
        {"text": "Related FAQ entry", "score": 0.72, "source": "faq"},
    ]
    return state


def llm_call_node(state: AgentState) -> AgentState:
    """Call the LLM with context from RAG and conversation history."""
    state.llm_output = (
        f"LLM response based on classification={state.classification} "
        f"and {len(state.rag_results)} RAG results"
    )
    state.step_count += 1
    state.total_cost += 0.002
    return state


def tool_execute_node(state: AgentState) -> AgentState:
    """Execute a tool based on the LLM's decision."""
    state.tool_result = f"Tool executed successfully for {state.classification}"
    state.total_cost += 0.0005
    return state


def output_guardrail_node(state: AgentState) -> AgentState:
    """Check the LLM output for sensitive data."""
    sensitive = ["sk-", "ghp_"]
    for pattern in sensitive:
        if pattern in state.llm_output:
            state.final_response = "Response sanitized for sensitive data."
            return state
    state.final_response = state.llm_output
    return state


def escalate_node(state: AgentState) -> AgentState:
    """Escalate to a human agent with context."""
    state.escalation = (
        f"Escalated to human. "
        f"Classification: {state.classification}, "
        f"Steps: {state.step_count}"
    )
    state.final_response = state.escalation
    return state


def respond_node(state: AgentState) -> AgentState:
    """Build the final response."""
    if not state.final_response:
        state.final_response = state.tool_result or state.llm_output or "No response"
    return state


# ── Conditional Routing Logic ───────────────────────────────────────


def route_after_classify(state: AgentState) -> str:
    """Route based on classification."""
    if state.classification == "security":
        return "escalate"
    return "guardrail"


def route_after_guardrail(state: AgentState) -> str:
    """Block or proceed."""
    if state.guardrail_result == "block":
        return "escalate"
    return "rag_search"


def route_after_llm(state: AgentState) -> str:
    """Route to tool execution or output guardrail."""
    if "tool" in state.llm_output:
        return "tool_execute"
    return "output_guardrail"


def route_after_rag(state: AgentState) -> str:
    """After RAG, always call LLM."""
    return "llm_call"


def route_after_tool(state: AgentState) -> str:
    """After tool, check output."""
    return "output_guardrail"


def route_after_output_guardrail(state: AgentState) -> str:
    """Escalate or respond."""
    if "sanitized" in state.final_response:
        return "escalate"
    return "respond"


# ── Graph Definition (mock) ─────────────────────────────────────────


@dataclass
class GraphNode:
    name: str
    func: Callable[[AgentState], AgentState]
    routes: dict[str, str] = field(default_factory=dict)


class StateGraph:
    """Minimal mock of LangGraph's StateGraph.

    Demonstrates the concept: a directed graph of nodes, each with
    conditional routing to the next node.
    """

    def __init__(self, state_schema: type):
        self.state_schema = state_schema
        self._nodes: dict[str, GraphNode] = {}
        self._conditional_edges: dict[str, Callable] = {}
        self._entry_point: str | None = None

    def add_node(self, name: str, func: Callable) -> None:
        self._nodes[name] = GraphNode(name=name, func=func)

    def set_entry_point(self, name: str) -> None:
        self._entry_point = name

    def add_conditional_edges(
        self,
        source: str,
        router: Callable,
        path_map: dict[str, str],
    ) -> None:
        self._conditional_edges[source] = router
        for condition, target in path_map.items():
            self._nodes[source].routes[condition] = target

    def add_edge(self, source: str, target: str) -> None:
        self._nodes[source].routes["_default"] = target

    def compile(self) -> "CompiledGraph":
        if not self._entry_point:
            raise ValueError("Entry point not set")
        return CompiledGraph(
            nodes=self._nodes,
            entry_point=self._entry_point,
            conditional_edges=self._conditional_edges,
        )


class CompiledGraph:
    """Compiled graph ready to run."""

    def __init__(
        self,
        nodes: dict[str, GraphNode],
        entry_point: str,
        conditional_edges: dict[str, Callable],
    ):
        self._nodes = nodes
        self._entry_point = entry_point
        self._conditional_edges = conditional_edges

    def invoke(self, state: AgentState) -> AgentState:
        """Run the graph to completion (synchronous)."""
        current = self._entry_point
        visited: list[str] = []
        max_steps = 20

        for _ in range(max_steps):
            if current not in self._nodes:
                break
            visited.append(current)
            node = self._nodes[current]

            # Execute node
            state = node.func(state)

            # Determine next node
            next_node = self._resolve_next(current, state)
            if next_node is None:
                break
            current = next_node

        return state

    def stream(self, state: AgentState) -> list[dict]:
        """Yield each node's output as an event (mock streaming)."""
        current = self._entry_point
        events: list[dict] = []
        max_steps = 20

        for _ in range(max_steps):
            if current not in self._nodes:
                break
            node = self._nodes[current]
            start = time.time()
            state = node.func(state)
            elapsed = int((time.time() - start) * 1000)

            events.append(
                {
                    "type": "node",
                    "node": current,
                    "latency_ms": elapsed,
                    "state_snapshot": {
                        "step_count": state.step_count,
                        "total_cost": round(state.total_cost, 4),
                        "classification": state.classification,
                        "guardrail_result": state.guardrail_result,
                    },
                }
            )

            next_node = self._resolve_next(current, state)
            if next_node is None:
                break
            current = next_node

        return events

    def _resolve_next(self, current: str, state: AgentState) -> str | None:
        if current in self._conditional_edges:
            router = self._conditional_edges[current]
            condition = router(state)
            node_routes = self._nodes[current].routes
            return node_routes.get(condition)
        node_routes = self._nodes[current].routes
        return node_routes.get("_default")


# ── Graph Builder ───────────────────────────────────────────────────


def create_agent_graph() -> CompiledGraph:
    """Build the SupportFlow LangGraph and return a compiled instance."""
    builder = StateGraph(AgentState)

    builder.add_node("classify", classify_node)
    builder.add_node("guardrail", guardrail_node)
    builder.add_node("rag_search", rag_search_node)
    builder.add_node("llm_call", llm_call_node)
    builder.add_node("tool_execute", tool_execute_node)
    builder.add_node("output_guardrail", output_guardrail_node)
    builder.add_node("escalate", escalate_node)
    builder.add_node("respond", respond_node)

    builder.set_entry_point("classify")

    builder.add_conditional_edges(
        "classify",
        route_after_classify,
        {"escalate": "escalate", "guardrail": "guardrail"},
    )
    builder.add_conditional_edges(
        "guardrail",
        route_after_guardrail,
        {"escalate": "escalate", "rag_search": "rag_search"},
    )
    builder.add_conditional_edges(
        "rag_search",
        route_after_rag,
        {"llm_call": "llm_call"},
    )
    builder.add_conditional_edges(
        "llm_call",
        route_after_llm,
        {"tool_execute": "tool_execute", "output_guardrail": "output_guardrail"},
    )
    builder.add_conditional_edges(
        "tool_execute",
        route_after_tool,
        {"output_guardrail": "output_guardrail"},
    )
    builder.add_conditional_edges(
        "output_guardrail",
        route_after_output_guardrail,
        {"escalate": "escalate", "respond": "respond"},
    )

    return builder.compile()


# ── Wrapper Class ───────────────────────────────────────────────────


class SupportFlowGraph:
    """High-level wrapper around the compiled LangGraph.

    Provides a simple run/stream API that mirrors the original
    ReActAgent interface.
    """

    def __init__(self):
        self.graph = create_agent_graph()

    def run(self, user_input: str, session_id: str | None = None) -> AgentState:
        state = AgentState(
            messages=[{"role": "user", "content": user_input}],
            session_id=session_id or str(uuid.uuid4())[:8],
        )
        return self.graph.invoke(state)

    def stream(self, user_input: str) -> list[dict]:
        state = AgentState(messages=[{"role": "user", "content": user_input}])
        return self.graph.stream(state)


# ── Comparison: ReAct vs LangGraph ──────────────────────────────────


def compare_with_react() -> str:
    """Show the conceptual differences between ReAct loop and LangGraph."""
    return """=== ReAct Loop (Before) ===

while True:
    response = llm(messages)
    if FINAL_ANSWER in response:
        return extract_answer(response)
    if ACTION in response:
        result = execute_tool(response)
        messages.append(tool_result)

- State: implicit in local variables
- Flow: hardcoded if/else
- Testing: full integration only
- Streaming: manual yield

=== LangGraph (After) ===

graph = StateGraph(AgentState)
graph.add_node("classify", classify_node)
graph.add_node("guardrail", guardrail_node)
graph.add_node("rag_search", rag_search_node)
graph.add_node("llm_call", llm_call_node)
graph.add_node("tool_execute", tool_execute_node)
graph.add_node("output_guardrail", output_guardrail_node)
graph.add_node("respond", respond_node)

graph.add_conditional_edges(
    "classify", route_after_classify,
    {"escalate": "escalate", "guardrail": "guardrail"},
)
# ... more explicit edges ...

- State: explicit TypedDict
- Flow: directed graph with named edges
- Testing: per-node unit tests
- Streaming: built-in stream_mode
- HITL: interrupt() primitive
- Persistence: pluggable checkpointer

=== What Changes ===

1. Reasoning loop → explicit graph structure
2. Implicit state → typed schema
3. if/else branching → conditional edges
4. Manual tool dispatch → tool nodes with routing
5. No persistence → checkpoint/save/restore
6. No streaming → native event streaming
"""


# ── Example ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    agent = SupportFlowGraph()

    print("=== Invoke ===")
    result = agent.run("I need a refund for my last invoice")
    print(f"Classification: {result.classification}")
    print(f"Response: {result.final_response}")
    print(f"Steps: {result.step_count}")
    print(f"Cost: ${result.total_cost:.4f}")

    print("\n=== Stream ===")
    events = agent.stream("My password is not working")
    for event in events:
        print(f"  [{event['node']}] {event['latency_ms']}ms")

    print("\n=== Comparison ===")
    print(compare_with_react())
