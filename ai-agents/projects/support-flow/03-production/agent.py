"""SupportFlow Stage 3: Production Agent — guardrails, budget, observability."""

import json
import os
import sys
import time
import re
from dataclasses import dataclass, field
from typing import Any
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "02-memory"))
from agent import MemoryAgent as BaseAgent
from agent import AgentConfig, ModelConfig, TOOL_SCHEMAS, TOOL_IMPL, execute_tool


# ============================================================
# Guardrails
# ============================================================


class InputGuardrail:
    DANGEROUS_PATTERNS = [
        "ignore all instructions",
        "ignore previous",
        "new system prompt",
        "forget everything",
        "override your",
        "you are now",
        "you are a",
        "system prompt:",
        "Ignore all",
    ]
    SENSITIVE_DATA = [
        r"sk-[a-zA-Z0-9]{20,}",
        r"ghp_[a-zA-Z0-9]{36}",
        r"-----BEGIN.*KEY-----",
        r"\b[\w\.-]+@[\w\.-]+\.\w{2,}\b",
        r"\b\d{16}\b",  # credit card
    ]

    def check_input(self, text: str) -> dict:
        for pattern in self.DANGEROUS_PATTERNS:
            if pattern.lower() in text.lower():
                return {
                    "action": "block",
                    "reason": f"Prompt injection attempt: '{pattern}'",
                }
        return {"action": "allow"}

    def check_output(self, text: str) -> dict:
        import re

        for pattern in self.SENSITIVE_DATA:
            if re.search(pattern, text):
                return {"action": "sanitize", "reason": "Sensitive data detected"}
        return {"action": "allow"}

    def sanitize(self, text: str) -> str:
        """Mask sensitive patterns in output."""
        import re

        for pattern in self.SENSITIVE_DATA:
            text = re.sub(pattern, "***", text)
        return text


class ToolGuardrail:
    DANGEROUS_TOOLS = {"delete", "drop", "truncate", "rm", "sudo", "shutdown"}
    HITL_TOOLS = {"send_email", "charge", "refund", "impersonate", "write_off"}

    def check_call(self, tool_name: str, args: dict) -> dict:
        tool_lower = tool_name.lower()
        for dangerous in self.DANGEROUS_TOOLS:
            if dangerous in tool_lower:
                return {"action": "block", "reason": f"Dangerous tool: {tool_name}"}
        for hitl in self.HITL_TOOLS:
            if hitl in tool_lower:
                return {
                    "action": "require_hitl",
                    "reason": f"Requires human approval: {tool_name}",
                }
        return {"action": "allow"}


# ============================================================
# Budget Controller
# ============================================================


class BudgetController:
    def __init__(self, max_cost: float = 0.50, max_calls: int = 20):
        self.max_cost = max_cost
        self.max_calls = max_calls
        self.spent = 0.0
        self.calls = 0

    def check(self, cost: float = 0.0) -> str:
        self.spent += cost
        self.calls += 1
        if self.spent >= self.max_cost:
            return "block"
        if self.calls >= self.max_calls:
            return "block"
        if self.spent >= self.max_cost * 0.8:
            return "warn"
        return "allow"

    def reset(self):
        self.spent = 0.0
        self.calls = 0


# ============================================================
# Metrics & Observability
# ============================================================


@dataclass
class StepMetrics:
    step: int
    tool_name: str | None = None
    latency_ms: float = 0.0
    cost: float = 0.0
    guardrail_action: str = "allow"
    error: str | None = None
    success: bool = True


@dataclass
class SessionMetrics:
    session_id: str
    start_time: float
    steps: list[StepMetrics] = field(default_factory=list)
    total_cost: float = 0.0
    guardrail_triggers: int = 0
    errors: int = 0

    def add_step(self, step: StepMetrics):
        self.steps.append(step)
        self.total_cost += step.cost
        if step.guardrail_action != "allow":
            self.guardrail_triggers += 1
        if step.error:
            self.errors += 1

    def summary(self) -> dict:
        return {
            "session_id": self.session_id,
            "duration_ms": (time.time() - self.start_time) * 1000,
            "steps": len(self.steps),
            "total_cost": round(self.total_cost, 4),
            "guardrail_triggers": self.guardrail_triggers,
            "errors": self.errors,
            "tool_calls": [s.tool_name for s in self.steps if s.tool_name],
        }


# ============================================================
# Production Agent
# ============================================================

PRODUCTION_SYSTEM_PROMPT = """You are SupportFlow, a production-grade support agent.

Available tools for safe operations:
- search_knowledge_base: find answers (always search first)
- save_to_memory: store important information
- read_from_memory: retrieve past information
- get_current_time: check date/time
- calculator: perform calculations

Safety rules:
- NEVER perform destructive operations (delete, remove, drop)
- If a user asks for something dangerous — politely refuse
- Always verify before sending emails or processing payments
- If the user is frustrated — stay calm and ask clarifying questions
- When unsure — admit it and offer escalation

Always respond in the user's language."""


class ProductionAgent:
    """Production-агент с guardrails, budget control и observability."""

    def __init__(self, config: AgentConfig | None = None):
        self.config = config or AgentConfig()

        # Core agent (from Stage 2, but we bypass its run method)
        self._base = BaseAgent(config)
        self.system_prompt = PRODUCTION_SYSTEM_PROMPT

        # Production layers
        self.input_guardrail = InputGuardrail()
        self.tool_guardrail = ToolGuardrail()
        self.budget = BudgetController()
        self.session = SessionMetrics(
            session_id=f"sess_{int(time.time())}",
            start_time=time.time(),
        )

    def run(self, user_input: str) -> dict:
        # 1. Input guardrail
        input_check = self.input_guardrail.check_input(user_input)
        if input_check["action"] == "block":
            self.session.add_step(
                StepMetrics(
                    step=0,
                    guardrail_action="block",
                    error=f"Input blocked: {input_check['reason']}",
                    success=False,
                )
            )
            return {
                "response": f"I can't process this request. {input_check['reason']}",
                "blocked": True,
                "guardrail": input_check,
            }

        # 2. Budget check
        budget_status = self.budget.check()
        if budget_status == "block":
            return {
                "response": "Session budget exceeded. Please start a new session.",
                "blocked": True,
            }

        # 3. Build messages with RAG context
        rag_context = ""
        if self._base.rag:
            rag_result = self._base.rag.retrieve(user_input)
            rag_context = self._base.rag.format_context(rag_result)

        system = self.system_prompt
        if rag_context:
            system = f"{system}\n\nRelevant documentation:\n{rag_context}"

        self._base.memory.add_message("user", user_input)
        messages: list[dict] = [{"role": "system", "content": system}]
        history = self._base.memory.get_conversation_context(limit=10)
        for msg in history:
            messages.append({"role": msg["role"], "content": msg["content"]})

        # 4. ReAct loop with guardrails + monitoring
        for iteration in range(1, self.config.max_iterations + 1):
            step_start = time.time()

            if self.config.verbose:
                print(f"\n─── Iteration {iteration} ───")

            try:
                response = self._base.llm.chat_completion(messages, TOOL_SCHEMAS)
            except Exception as e:
                self.session.add_step(
                    StepMetrics(
                        step=iteration,
                        error=str(e),
                        success=False,
                        latency_ms=(time.time() - step_start) * 1000,
                    )
                )
                return {"response": f"I encountered an error: {e}. Please try again."}

            content = response["content"] or ""
            tool_calls = response.get("tool_calls", [])

            if self.config.verbose and content:
                print(f"[Assistant]: {content[:200]}...")

            # Output guardrail
            output_check = self.input_guardrail.check_output(content)
            if output_check["action"] == "sanitize":
                content = self.input_guardrail.sanitize(content)

            if not tool_calls:
                self._base.memory.add_message("assistant", content)
                self.session.add_step(
                    StepMetrics(
                        step=iteration,
                        latency_ms=(time.time() - step_start) * 1000,
                        cost=0.001,
                        success=True,
                    )
                )
                return {
                    "response": content,
                    "iterations": iteration,
                    "cost": self.session.total_cost,
                    "metrics": self.session.summary(),
                }

            messages.append(
                {
                    "role": "assistant",
                    "content": content or "",
                    "tool_calls": [
                        {
                            "id": tc["id"],
                            "type": "function",
                            "function": {
                                "name": tc["function"]["name"],
                                "arguments": tc["function"]["arguments"],
                            },
                        }
                        for tc in tool_calls
                    ],
                }
            )

            for tc in tool_calls:
                name = tc["function"]["name"]
                args = json.loads(tc["function"]["arguments"])

                # Tool guardrail
                tool_check = self.tool_guardrail.check_call(name, args)
                if tool_check["action"] == "block":
                    result = f"Action blocked: {tool_check['reason']}"
                    self.session.add_step(
                        StepMetrics(
                            step=iteration,
                            tool_name=name,
                            guardrail_action="block",
                            success=False,
                            error=tool_check["reason"],
                        )
                    )
                elif tool_check["action"] == "require_hitl":
                    result = (
                        f"Action requires human approval: {name}({json.dumps(args)})"
                    )
                    self.session.add_step(
                        StepMetrics(
                            step=iteration,
                            tool_name=name,
                            guardrail_action="hitl",
                            success=False,
                        )
                    )
                else:
                    if self.config.verbose:
                        print(f"[Tool]: {name}({json.dumps(args)})")

                    result = execute_tool(name, args, memory=self._base.memory)
                    self.session.add_step(
                        StepMetrics(
                            step=iteration,
                            tool_name=name,
                            latency_ms=(time.time() - step_start) * 1000,
                            cost=0.002,
                            success=True,
                        )
                    )

                if self.config.verbose:
                    print(f"[Result]: {result[:200]}...")

                # Budget check per tool call
                budget_status = self.budget.check(cost=0.002)
                if budget_status == "block":
                    result += "\n[Budget limit reached. Ending session.]"

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": result,
                    }
                )

                if budget_status == "block":
                    break
            if budget_status == "block":
                break

        msg = "Max iterations or budget reached. Please start a new session."
        self._base.memory.add_message("assistant", msg)
        return {
            "response": msg,
            "error": "limit_reached",
            "metrics": self.session.summary(),
        }


# ============================================================
# CLI
# ============================================================


def main():
    import argparse

    parser = argparse.ArgumentParser(description="SupportFlow Production Agent")
    parser.add_argument(
        "--provider", default="openai", choices=["openai", "anthropic", "deepseek"]
    )
    parser.add_argument("--model", default="")
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("query", nargs="*")
    args = parser.parse_args()

    if not args.model:
        model_map = {
            "openai": "gpt-4o-mini",
            "anthropic": "claude-sonnet-4-20250514",
            "deepseek": "deepseek-chat",
        }
        args.model = model_map[args.provider]

    config = AgentConfig(
        model=ModelConfig(provider=args.provider, model=args.model),
        verbose=not args.quiet,
    )
    agent = ProductionAgent(config)

    query = " ".join(args.query)
    if query:
        print(f"\nUser: {query}")
        result = agent.run(query)
        print(f"\n=== Response ===")
        print(result["response"])
        print(f"=== Cost: ${result.get('cost', 0):.4f} ===")
    else:
        print(f"\nSupportFlow Production Agent (interactive)")
        print(f"Provider: {args.provider}")
        while True:
            try:
                q = input("You: ")
                if q.lower() in ("exit", "quit"):
                    break
                result = agent.run(q)
                print(f"\nAgent: {result['response']}\n")
            except KeyboardInterrupt:
                break


if __name__ == "__main__":
    main()
