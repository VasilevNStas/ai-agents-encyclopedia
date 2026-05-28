"""SupportFlow — Specialist Agents (Модуль 4)."""

import time
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Callable

from .supervisor import Ticket


class HandoffProtocol(Enum):
    RESOLVED = "resolved"
    ESCALATE = "escalate"
    CLARIFY = "clarify"


@dataclass
class AgentResponse:
    status: HandoffProtocol
    message: str
    ticket_id: str
    agent_name: str
    actions_taken: list[str] = field(default_factory=list)
    escalation_reason: Optional[str] = None


# --- Mock tools ---


def check_billing_history(user_id: str) -> str:
    return f"Billing history for {user_id}: last payment $29.99 on 2026-04-15, status active."


def process_refund(ticket_id: str, amount: float) -> str:
    return (
        f"Refund of ${amount:.2f} for ticket {ticket_id} requested — pending approval."
    )


def change_plan(user_id: str, new_plan: str) -> str:
    return f"Plan change for {user_id} to {new_plan} initiated."


def search_knowledge_base(query: str) -> str:
    return f"KB result for '{query}': see doc KB-{hash(query) % 1000:04d}."


def check_service_status(service: str = "all") -> str:
    statuses = {
        "api": "ok",
        "web": "ok",
        "database": "degraded",
        "all": "api: ok, web: ok, db: degraded",
    }
    return f"Service status: {statuses.get(service, 'unknown')}"


def run_diagnostics(user_id: str) -> str:
    return (
        f"Diagnostics for {user_id}: network ok, config ok, recent errors: 2 timeouts."
    )


def reset_password(user_id: str) -> str:
    return f"Password reset link sent for {user_id}."


def update_profile(user_id: str, field: str, value: str) -> str:
    return f"Profile '{field}' updated to '{value}' for {user_id}."


def manage_users(account_id: str, action: str, target: str = "") -> str:
    return f"User '{target}' {action} on account {account_id}."


# --- Base agent ---


class BaseSpecialistAgent:
    name: str = "base"
    system_prompt: str = ""
    permitted_tools: dict[str, Callable] = {}
    timeout_seconds: float = 10.0

    def handle(self, ticket: Ticket) -> AgentResponse:
        raise NotImplementedError

    def _check_timeout(self, start: float) -> bool:
        return time.time() - start > self.timeout_seconds


# --- Billing ---


class BillingAgent(BaseSpecialistAgent):
    name = "billing_agent"
    system_prompt = (
        "You are a billing support specialist. Handle billing inquiries, "
        "refunds, invoices, and plan changes. Escalate if refund exceeds $500 "
        "or if the issue requires account-level changes."
    )
    permitted_tools = {
        "check_billing_history": check_billing_history,
        "process_refund": process_refund,
        "change_plan": change_plan,
    }

    def handle(self, ticket: Ticket) -> AgentResponse:
        start = time.time()
        message = ticket.message.lower()
        user_id = ticket.user_info.get("user_id", "unknown")
        actions = []

        if self._check_timeout(start):
            return AgentResponse(
                status=HandoffProtocol.ESCALATE,
                message="Billing agent processing timed out",
                ticket_id=ticket.ticket_id,
                agent_name=self.name,
                escalation_reason="Timeout exceeded",
            )

        if "refund" in message or "return" in message:
            actions.append("check_billing_history")
            self.permitted_tools["check_billing_history"](user_id)
            if amount_match := next(
                (w for w in message.split() if w.startswith("$")), None
            ):
                try:
                    amount = float(amount_match.replace("$", ""))
                except ValueError:
                    amount = 29.99
            else:
                amount = 29.99
            if amount > 500 or "large" in message:
                return AgentResponse(
                    status=HandoffProtocol.ESCALATE,
                    message=f"Refund ${amount:.2f} exceeds threshold",
                    ticket_id=ticket.ticket_id,
                    agent_name=self.name,
                    actions_taken=actions,
                    escalation_reason=f"Refund ${amount:.2f} requires human approval",
                )
            self.permitted_tools["process_refund"](ticket.ticket_id, amount)
            actions.append("process_refund")

        elif "plan" in message or "upgrade" in message or "downgrade" in message:
            plan = "premium" if "upgrade" in message else "basic"
            self.permitted_tools["change_plan"](user_id, plan)
            actions.append("change_plan")

        elif "history" in message or "invoice" in message:
            self.permitted_tools["check_billing_history"](user_id)
            actions.append("check_billing_history")

        else:
            return AgentResponse(
                status=HandoffProtocol.ESCALATE,
                message="Billing query not recognized — unclear request",
                ticket_id=ticket.ticket_id,
                agent_name=self.name,
                escalation_reason="Unrecognized billing query",
            )

        return AgentResponse(
            status=HandoffProtocol.RESOLVED,
            message=f"Billing issue resolved (actions: {', '.join(actions)})",
            ticket_id=ticket.ticket_id,
            agent_name=self.name,
            actions_taken=actions,
        )


# --- Technical ---


class TechnicalAgent(BaseSpecialistAgent):
    name = "technical_agent"
    system_prompt = (
        "You are a technical support specialist. Diagnose and resolve technical "
        "issues. Use knowledge base and diagnostics. Escalate if unresolved "
        "after diagnostics or if infrastructure changes are needed."
    )
    permitted_tools = {
        "search_knowledge_base": search_knowledge_base,
        "check_service_status": check_service_status,
        "run_diagnostics": run_diagnostics,
    }

    def handle(self, ticket: Ticket) -> AgentResponse:
        start = time.time()
        message = ticket.message.lower()
        user_id = ticket.user_info.get("user_id", "unknown")
        actions = []

        if self._check_timeout(start):
            return AgentResponse(
                status=HandoffProtocol.ESCALATE,
                message="Technical agent processing timed out",
                ticket_id=ticket.ticket_id,
                agent_name=self.name,
                escalation_reason="Timeout exceeded",
            )

        if "status" in message or "down" in message or "outage" in message:
            result = self.permitted_tools["check_service_status"]()
            actions.append("check_service_status")
            if "degraded" in result.lower():
                return AgentResponse(
                    status=HandoffProtocol.ESCALATE,
                    message=result,
                    ticket_id=ticket.ticket_id,
                    agent_name=self.name,
                    actions_taken=actions,
                    escalation_reason="Service degradation detected — infrastructure team needed",
                )

        elif "error" in message or "bug" in message or "crash" in message:
            self.permitted_tools["search_knowledge_base"](message)
            actions.append("search_knowledge_base")
            if "login" in message or "password" in message:
                self.permitted_tools["run_diagnostics"](user_id)
                actions.append("run_diagnostics")

        elif "install" in message or "setup" in message or "configure" in message:
            self.permitted_tools["search_knowledge_base"](message)
            actions.append("search_knowledge_base")

        else:
            self.permitted_tools["run_diagnostics"](user_id)
            actions.append("run_diagnostics")
            return AgentResponse(
                status=HandoffProtocol.ESCALATE,
                message="Technical issue not resolved by diagnostics",
                ticket_id=ticket.ticket_id,
                agent_name=self.name,
                actions_taken=actions,
                escalation_reason="Diagnostics insufficient — escalation needed",
            )

        return AgentResponse(
            status=HandoffProtocol.RESOLVED,
            message=f"Technical issue resolved (actions: {', '.join(actions)})",
            ticket_id=ticket.ticket_id,
            agent_name=self.name,
            actions_taken=actions,
        )


# --- Account ---


class AccountAgent(BaseSpecialistAgent):
    name = "account_agent"
    system_prompt = (
        "You are an account management specialist. Handle password resets, "
        "profile updates, and user management. Escalate if account deletion "
        "is requested or if admin-level changes are needed."
    )
    permitted_tools = {
        "reset_password": reset_password,
        "update_profile": update_profile,
        "manage_users": manage_users,
    }

    def handle(self, ticket: Ticket) -> AgentResponse:
        start = time.time()
        message = ticket.message.lower()
        user_id = ticket.user_info.get("user_id", "unknown")
        actions = []

        if self._check_timeout(start):
            return AgentResponse(
                status=HandoffProtocol.ESCALATE,
                message="Account agent processing timed out",
                ticket_id=ticket.ticket_id,
                agent_name=self.name,
                escalation_reason="Timeout exceeded",
            )

        if "delete" in message and "account" in message:
            return AgentResponse(
                status=HandoffProtocol.ESCALATE,
                message="Account deletion requested",
                ticket_id=ticket.ticket_id,
                agent_name=self.name,
                escalation_reason="Account deletion requires human approval",
            )

        if "password" in message or "reset" in message:
            self.permitted_tools["reset_password"](user_id)
            actions.append("reset_password")

        elif "profile" in message or "update" in message or "change" in message:
            field = (
                "email"
                if "email" in message
                else "phone"
                if "phone" in message
                else "name"
            )
            self.permitted_tools["update_profile"](user_id, field, "updated")
            actions.append("update_profile")

        elif "user" in message or "manage" in message or "team" in message:
            action = (
                "removed" if ("remove" in message or "delete" in message) else "added"
            )
            target = message.split()[-1] if len(message.split()) > 1 else "user"
            self.permitted_tools["manage_users"](
                ticket.user_info.get("account_id", user_id), action, target
            )
            actions.append("manage_users")

        else:
            return AgentResponse(
                status=HandoffProtocol.ESCALATE,
                message="Account query not recognized",
                ticket_id=ticket.ticket_id,
                agent_name=self.name,
                escalation_reason="Unrecognized account query",
            )

        return AgentResponse(
            status=HandoffProtocol.RESOLVED,
            message=f"Account issue resolved (actions: {', '.join(actions)})",
            ticket_id=ticket.ticket_id,
            agent_name=self.name,
            actions_taken=actions,
        )


if __name__ == "__main__":
    from .supervisor import TicketCategory

    ticket = Ticket(
        ticket_id="abc123",
        message="I need a refund of $200 for my last subscription payment",
        user_info={"user_id": "user_42", "account_id": "acc_99"},
        category=TicketCategory.BILLING,
    )

    billing = BillingAgent()
    response = billing.handle(ticket)
    print(f"[{response.agent_name}] {response.status.value}: {response.message}")
    if response.escalation_reason:
        print(f"  Escalation reason: {response.escalation_reason}")

    tech_ticket = Ticket(
        ticket_id="def456",
        message="The database is down and I'm getting timeout errors",
        user_info={"user_id": "user_7"},
        category=TicketCategory.TECHNICAL,
    )
    tech = TechnicalAgent()
    response2 = tech.handle(tech_ticket)
    print(f"[{response2.agent_name}] {response2.status.value}: {response2.message}")

    acct_ticket = Ticket(
        ticket_id="ghi789",
        message="Please delete my account permanently",
        user_info={"user_id": "user_99"},
        category=TicketCategory.ACCOUNT,
    )
    acct = AccountAgent()
    response3 = acct.handle(acct_ticket)
    print(f"[{response3.agent_name}] {response3.status.value}: {response3.message}")
