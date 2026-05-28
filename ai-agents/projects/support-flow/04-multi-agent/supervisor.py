"""SupportFlow — Supervisor Agent (Модуль 4)."""

import time
import uuid
import hashlib
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional


class TicketCategory(Enum):
    BILLING = "billing"
    TECHNICAL = "technical"
    ACCOUNT = "account"
    GENERAL = "general"


@dataclass
class Ticket:
    ticket_id: str
    message: str
    user_info: dict
    category: Optional[TicketCategory] = None
    status: str = "open"
    assigned_agent: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    resolved_at: Optional[float] = None


class SupervisorAgent:
    """Supervisor — классифицирует и маршрутизирует тикеты."""

    def __init__(self):
        self._task_registry: set[str] = set()
        self._escalations: list[dict] = []

    def classify_ticket(self, message: str, user_info: dict) -> Ticket:
        ticket_id = uuid.uuid4().hex[:12]
        dedup_key = self._dedup_key(message, user_info.get("user_id", "anon"))
        is_dupe = dedup_key in self._task_registry
        if not is_dupe:
            self._task_registry.add(dedup_key)

        category = self._classify_keywords(message)
        return Ticket(
            ticket_id=ticket_id,
            message=message,
            user_info=user_info,
            category=category,
            status="duplicate" if is_dupe else "classified",
        )

    def route(self, ticket: Ticket) -> str:
        routes = {
            TicketCategory.BILLING: "billing_agent",
            TicketCategory.TECHNICAL: "technical_agent",
            TicketCategory.ACCOUNT: "account_agent",
            TicketCategory.GENERAL: "general_agent",
        }
        category = ticket.category or TicketCategory.GENERAL
        agent = routes[category]
        ticket.assigned_agent = agent
        ticket.status = "routed"
        return agent

    def escalate_to_human(self, ticket: Ticket, reason: str) -> dict:
        ticket.status = "escalated"
        record = {
            "ticket_id": ticket.ticket_id,
            "reason": reason,
            "category": ticket.category.value if ticket.category else None,
            "assigned_agent": ticket.assigned_agent,
            "timestamp": time.time(),
        }
        self._escalations.append(record)
        return record

    def _dedup_key(self, message: str, user_id: str) -> str:
        normalized = message.strip().lower()
        content_hash = hashlib.sha256(normalized.encode()).hexdigest()[:16]
        return f"{user_id}:{content_hash}"

    def _classify_keywords(self, message: str) -> TicketCategory:
        msg = message.lower()
        if any(
            kw in msg
            for kw in (
                "billing",
                "bill",
                "refund",
                "payment",
                "invoice",
                "charge",
                "plan",
                "pricing",
                "subscription",
            )
        ):
            return TicketCategory.BILLING
        if any(
            kw in msg
            for kw in (
                "bug",
                "error",
                "crash",
                "not working",
                "technical",
                "install",
                "broken",
                "fail",
                "timeout",
            )
        ):
            return TicketCategory.TECHNICAL
        if any(
            kw in msg
            for kw in (
                "account",
                "password",
                "reset",
                "profile",
                "username",
                "delete account",
                "settings",
                "2fa",
            )
        ):
            return TicketCategory.ACCOUNT
        return TicketCategory.GENERAL


if __name__ == "__main__":
    supervisor = SupervisorAgent()
    ticket = supervisor.classify_ticket(
        "I need a refund for my last payment", {"user_id": "user_42"}
    )
    print(f"Category: {ticket.category}")
    agent = supervisor.route(ticket)
    print(f"Routed to: {agent}")
    print(f"Status: {ticket.status}")
    dup = supervisor.classify_ticket(
        "I need a refund for my last payment", {"user_id": "user_42"}
    )
    print(f"Duplicate: {dup.status}")

    escalated = supervisor.escalate_to_human(ticket, "Customer requesting $2000 refund")
    print(f"Escalated: {escalated}")
