"""SupportFlow-specific guardrails extending base Guardrail."""

from __future__ import annotations

import time
import re
from dataclasses import dataclass, field
from typing import Any

from src.agent.core import Guardrail, BudgetController


TICKET_CATEGORIES: dict[str, dict[str, Any]] = {
    "billing": {
        "allowed_actions": {
            "lookup_invoice",
            "process_payment",
            "view_plan",
            "apply_credit",
        },
        "requires_authorization": {"refund", "waive_fee", "write_off"},
    },
    "technical": {
        "allowed_actions": {
            "diagnose",
            "reset_password",
            "check_status",
            "run_diagnostics",
        },
        "requires_authorization": {
            "deploy_hotfix",
            "modify_infrastructure",
            "access_logs",
        },
    },
    "account": {
        "allowed_actions": {"view_profile", "update_email", "change_preferences"},
        "requires_authorization": {
            "delete_account",
            "transfer_ownership",
            "impersonate",
            "export_data",
        },
    },
    "security": {
        "allowed_actions": {"scan", "verify_mfa", "check_permissions"},
        "requires_authorization": {
            "revoke_access",
            "reset_all_sessions",
            "disable_account",
        },
    },
    "general": {
        "allowed_actions": {"search_kb", "send_message", "greet"},
        "requires_authorization": set(),
    },
}

ESCALATION_RULES: dict[str, dict[str, str]] = {
    "refund_request": {
        "target_tier": "senior",
        "reason": "Financial impact — requires authorization",
    },
    "security_incident": {
        "target_tier": "security",
        "reason": "Possible security breach",
    },
    "data_deletion": {
        "target_tier": "lead",
        "reason": "Data compliance (GDPR/CCPA) required",
    },
    "pii_exposure": {"target_tier": "security", "reason": "PII leaked in conversation"},
    "legal_threat": {"target_tier": "lead", "reason": "Legal exposure detected"},
    "service_outage": {
        "target_tier": "senior",
        "reason": "Widespread service disruption",
    },
}

REFUND_PATTERNS: list[re.Pattern] = [
    re.compile(r"\brefund\b", re.IGNORECASE),
    re.compile(r"\bmoney back\b", re.IGNORECASE),
    re.compile(r"\breimburse\b", re.IGNORECASE),
    re.compile(r"\bchargeback\b", re.IGNORECASE),
    re.compile(r"\bfull (refund|return)\b", re.IGNORECASE),
    re.compile(r"\bguarantee.*money\b", re.IGNORECASE),
]

FORBIDDEN_PROFANITY: list[str] = [
    "kill yourself",
    "go die",
    "i will hurt",
]


class RateLimitExceeded(Exception):
    """Raised when a user exceeds the allowed rate limit."""


@dataclass
class RateLimitState:
    timestamps: list[float] = field(default_factory=list)


@dataclass
class EscalationDecision:
    escalate: bool = False
    reason: str = ""
    target_tier: str = ""
    confidence: float = 0.0


class SupportGuardrail(Guardrail):
    """Domain-specific guardrails for customer support agents.

    Extends the base Guardrail with business rules for ticket categories,
    escalation logic, per-user rate limiting, content policy enforcement,
    and budget-aware decision making.
    """

    def __init__(
        self,
        budget_controller: BudgetController | None = None,
        rate_limit_per_minute: int = 30,
    ):
        super().__init__()
        self.budget = budget_controller
        self.rate_limit_per_minute = rate_limit_per_minute
        self._rate_states: dict[str, RateLimitState] = {}

    # ── Category-based action control ──────────────────────────────

    def check_ticket_action(self, category: str, action: str, user_id: str) -> dict:
        """Verify an action is allowed for the given ticket category."""
        category = category.lower()
        if category not in TICKET_CATEGORIES:
            return {
                "action": "block",
                "reason": f"Unknown ticket category: {category}",
                "user_id": user_id,
            }

        rules = TICKET_CATEGORIES[category]
        if action in rules.get("requires_authorization", set()):
            return {
                "action": "require_auth",
                "reason": f"Action '{action}' in category '{category}' requires authorization",
                "user_id": user_id,
            }

        if action not in rules.get("allowed_actions", set()):
            return {
                "action": "block",
                "reason": f"Action '{action}' is not allowed in category '{category}'",
                "user_id": user_id,
            }

        return {"action": "allow"}

    # ── Escalation rules ───────────────────────────────────────────

    def check_escalation(
        self,
        issue_type: str,
        sentiment_score: float = 0.0,
        message_count: int = 0,
    ) -> EscalationDecision:
        """Determine whether to escalate to a human agent."""
        issue_type = issue_type.lower()

        if issue_type in ESCALATION_RULES:
            rule = ESCALATION_RULES[issue_type]
            confidence = min(1.0, 0.7 + abs(sentiment_score) * 0.3)

            # Automatic escalation for negative sentiment (frustration)
            if sentiment_score < -0.5:
                confidence = min(1.0, confidence + 0.2)
                return EscalationDecision(
                    escalate=True,
                    reason=rule["reason"] + " (negative sentiment detected)",
                    target_tier=rule["target_tier"],
                    confidence=round(confidence, 2),
                )

            # Low-confidence or repeated issues get escalated
            if message_count >= 5:
                return EscalationDecision(
                    escalate=True,
                    reason=f"{rule['reason']} after {message_count} messages",
                    target_tier=rule["target_tier"],
                    confidence=round(confidence, 2),
                )

            return EscalationDecision(
                escalate=True,
                reason=rule["reason"],
                target_tier=rule["target_tier"],
                confidence=round(confidence, 2),
            )

        # Sentiment-only escalation for unknown issue types
        if sentiment_score < -0.8:
            return EscalationDecision(
                escalate=True,
                reason="Highly negative sentiment detected",
                target_tier="lead",
                confidence=0.9,
            )

        return EscalationDecision()

    # ── Rate limiting ──────────────────────────────────────────────

    def check_rate_limit(self, user_id: str) -> dict:
        """Enforce N requests per minute per user."""
        now = time.time()
        window = 60.0

        if user_id not in self._rate_states:
            self._rate_states[user_id] = RateLimitState()

        state = self._rate_states[user_id]

        # Prune old timestamps
        cutoff = now - window
        state.timestamps = [t for t in state.timestamps if t > cutoff]
        state.timestamps.append(now)

        if len(state.timestamps) > self.rate_limit_per_minute:
            retry_after = int(window - (now - state.timestamps[0]))
            return {
                "action": "block",
                "reason": f"Rate limit exceeded ({self.rate_limit_per_minute}/minute)",
                "user_id": user_id,
                "retry_after_seconds": max(retry_after, 1),
            }

        remaining = self.rate_limit_per_minute - len(state.timestamps)
        return {"action": "allow", "remaining": remaining}

    # ── Content policy ─────────────────────────────────────────────

    def check_content_policy(self, text: str, user_role: str = "agent") -> dict:
        """Enforce content policies — no unauthorized refund promises, no profanity."""
        # Refund promises without authorization
        for pattern in REFUND_PATTERNS:
            if pattern.search(text):
                return {
                    "action": "block",
                    "reason": "Refund-related content requires authorization before discussing",
                    "requires_role": "senior_agent",
                }

        # Profanity / harassment
        for phrase in FORBIDDEN_PROFANITY:
            if phrase in text.lower():
                return {
                    "action": "block",
                    "reason": f"Prohibited language detected: '{phrase}'",
                }

        # Secrets in output (delegates to base class check_output)
        output_check = super().check_output(text)
        if output_check["action"] != "allow":
            return output_check

        return {"action": "allow"}

    # ── Budget integration ─────────────────────────────────────────

    def check_with_budget(self, step_cost: float) -> dict:
        """Run budget check and return combined guardrail decision."""
        if self.budget is None:
            return {"action": "allow"}

        budget_decision = self.budget.check(step_cost)
        if budget_decision == "block":
            return {
                "action": "block",
                "reason": f"Budget exceeded (${self.budget.spent:.2f} spent)",
                "budget_spent": round(self.budget.spent, 4),
            }

        if budget_decision == "warn":
            return {
                "action": "warn",
                "reason": f"Budget approaching limit (${self.budget.spent:.2f} / ${self.budget.config.max_cost_per_session:.2f})",
                "budget_spent": round(self.budget.spent, 4),
            }

        return {"action": "allow"}

    # ── Check aggregation ──────────────────────────────────────────

    def check_input(self, user_input: str, user_id: str = "") -> dict:
        """Run all applicable input checks and return the first blocking result."""
        # 1. Base class security checks
        base_result = super().check_input(user_input)
        if base_result["action"] != "allow":
            return base_result

        # 2. Rate limit (if user_id provided)
        if user_id:
            rate_result = self.check_rate_limit(user_id)
            if rate_result["action"] != "allow":
                return rate_result

        # 3. Content policy
        policy_result = self.check_content_policy(user_input)
        if policy_result["action"] != "allow":
            return policy_result

        return {"action": "allow"}

    def check_tool_call(self, tool_name: str, args: dict) -> dict:
        """Extend base tool-check with budget-awareness."""
        base_result = super().check_tool_call(tool_name, args)
        if base_result["action"] != "allow":
            return base_result

        if self.budget is not None:
            tool_budget = self.budget.record_tool_call()
            if tool_budget == "block":
                return {
                    "action": "block",
                    "reason": "Tool call budget exceeded",
                    "tool": tool_name,
                    "args": args,
                }

        return {"action": "allow"}
