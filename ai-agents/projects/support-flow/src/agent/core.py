"""SupportFlow — production AI-agent core."""

import json
import time
import hashlib
from typing import Any, Optional
from dataclasses import dataclass, field

from .config import AgentConfig


@dataclass
class AgentStep:
    """Single step in agent's reasoning chain."""

    step_number: int
    thought: str
    action: Optional[str] = None
    action_args: Optional[dict] = None
    observation: Optional[str] = None
    token_cost: float = 0.0
    latency_ms: int = 0
    guardrail_action: str = "allow"


@dataclass
class AgentSession:
    """Complete session state for audit."""

    session_id: str
    user_id: str
    start_time: float
    steps: list[AgentStep] = field(default_factory=list)
    total_cost: float = 0.0
    status: str = "active"

    def add_step(self, step: AgentStep):
        self.steps.append(step)
        self.total_cost += step.token_cost

    def summary(self) -> dict:
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "duration_ms": (time.time() - self.start_time) * 1000,
            "steps": len(self.steps),
            "total_cost": round(self.total_cost, 4),
            "status": self.status,
            "tool_calls": [s.action for s in self.steps if s.action],
        }


class BudgetController:
    """Multi-layer budget control."""

    def __init__(self, config: AgentConfig):
        self.config = config.budget
        self.spent = 0.0
        self.call_count = 0
        self.tool_call_count = 0

    def check(self, step_cost: float = 0.0) -> str:
        self.spent += step_cost
        self.call_count += 1

        if self.spent >= self.config.max_cost_per_session:
            return "block"
        if self.call_count >= self.config.max_llm_calls_per_session:
            return "block"
        if self.spent >= self.config.alert_threshold:
            return "warn"
        return "allow"

    def record_tool_call(self):
        self.tool_call_count += 1
        if self.tool_call_count >= self.config.max_tool_calls_per_session:
            return "block"
        return "allow"


class AuditTrail:
    """Immutable audit trail for compliance."""

    def __init__(self):
        self.records: list[dict] = []

    def record(self, session: AgentSession):
        record = session.summary()
        record["hash"] = self._hash(record)
        self.records.append(record)
        return record

    def get_by_user(self, user_id: str) -> list[dict]:
        return [r for r in self.records if r["session_id"].startswith(user_id)]

    def _hash(self, record: dict) -> str:
        return hashlib.sha256(
            json.dumps(record, sort_keys=True, default=str).encode()
        ).hexdigest()[:16]


class Guardrail:
    """Multi-layer guardrail system."""

    DANGEROUS_PATTERNS = [
        "ignore all instructions",
        "ignore previous",
        "you are now",
        "new system prompt",
        "forget everything",
        "override",
    ]

    SENSITIVE_PATTERNS = [
        r"sk-[a-zA-Z0-9]{20,}",  # API keys
        r"ghp_[a-zA-Z0-9]{36}",  # GitHub tokens
        r"-----BEGIN.*KEY-----",  # Private keys
        r"\b[\w\.-]+@[\w\.-]+\.\w{2,}\b",  # Email
    ]

    DANGEROUS_TOOLS = ["delete", "drop", "truncate", "rm", "send_email"]

    def check_input(self, user_input: str) -> dict:
        for pattern in self.DANGEROUS_PATTERNS:
            if pattern in user_input.lower():
                return {"action": "block", "reason": f"Suspicious pattern: {pattern}"}
        return {"action": "allow"}

    def check_output(self, output: str) -> dict:
        import re

        for pattern in self.SENSITIVE_PATTERNS:
            if re.search(pattern, output):
                return {"action": "sanitize", "reason": "Sensitive data detected"}
        return {"action": "allow"}

    def check_tool_call(self, tool_name: str, args: dict) -> dict:
        for dangerous in self.DANGEROUS_TOOLS:
            if dangerous in tool_name.lower():
                return {
                    "action": "require_hitl",
                    "reason": f"Dangerous tool: {tool_name}",
                    "tool": tool_name,
                    "args": args,
                }
        return {"action": "allow"}
