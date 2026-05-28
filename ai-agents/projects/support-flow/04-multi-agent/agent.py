"""SupportFlow Stage 4: Multi-Agent — Supervisor + Specialists + Escalation."""

import json
import os
import sys
import time
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "03-production"))
sys.path.insert(0, os.path.dirname(__file__))

from supervisor import SupervisorAgent, Ticket, TicketCategory
from specialists import BillingAgent, TechnicalAgent, AccountAgent


# ============================================================
# LLM Classifier
# ============================================================


class LLMClassifier:
    """Использует LLM для классификации тикета вместо keyword matching."""

    def __init__(self, provider: str = "openai", model: str = "gpt-4o-mini"):
        self.provider = provider
        self.model = model
        self.api_key = os.environ.get(
            {
                "openai": "OPENAI_API_KEY",
                "anthropic": "ANTHROPIC_API_KEY",
                "deepseek": "DEEPSEEK_API_KEY",
            }[provider]
        )

    def classify(self, message: str) -> TicketCategory:
        categories = {
            "billing": "billing, payment, invoice, refund, plan, subscription, charge",
            "technical": "technical, error, bug, crash, performance, api, integration",
            "security": "security, breach, hack, password, phishing, suspicious",
            "account": "account, profile, email, settings, login, delete account",
        }
        prompt = f"""
Classify this support ticket into exactly one category: {", ".join(categories.keys())}.

Message: {message}

Category:"""
        try:
            from openai import OpenAI

            client = OpenAI(api_key=self.api_key)
            resp = client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                max_tokens=20,
            )
            label = resp.choices[0].message.content.strip().lower()
            for cat in TicketCategory:
                if cat.value in label:
                    return cat
        except Exception:
            pass
        return TicketCategory.GENERAL


# ============================================================
# Multi-Agent Orchestrator
# ============================================================


class MultiAgentSupport:
    """Оркестратор: Supervisor → Specialist → Response."""

    SPECIALISTS = {
        "billing_agent": BillingAgent,
        "technical_agent": TechnicalAgent,
        "account_agent": AccountAgent,
    }

    def __init__(self, use_llm_classifier: bool = True):
        self.supervisor = SupervisorAgent()
        self.classifier = LLMClassifier() if use_llm_classifier else None

    def handle_ticket(self, message: str, user_info: dict | None = None) -> dict:
        user_info = user_info or {"user_id": "anon", "name": "User"}
        start = time.time()

        # 1. Classify
        category = None
        if self.classifier:
            category = self.classifier.classify(message)
        ticket = self.supervisor.classify_ticket(message, user_info)
        if category:
            ticket.category = category  # override keyword with LLM

        # 2. Route
        agent_name = self.supervisor.route(ticket)
        specialist_cls = self.SPECIALISTS.get(agent_name)

        if not specialist_cls:
            return self._escalate(ticket, f"No specialist for: {agent_name}")

        # 3. Process
        specialist = specialist_cls()
        try:
            response = specialist.handle(ticket)
        except Exception as e:
            return self._escalate(ticket, str(e))

        # 4. Handle handoff
        if response.status.value == "escalate":
            self.supervisor.escalate_to_human(
                ticket, response.escalation_reason or "Specialist escalated"
            )
            return {
                "response": response.message,
                "ticket_id": ticket.ticket_id,
                "category": ticket.category.value if ticket.category else "general",
                "agent": agent_name,
                "status": "escalated",
                "duration_ms": (time.time() - start) * 1000,
            }

        if response.status.value == "clarify":
            return {
                "response": response.message,
                "ticket_id": ticket.ticket_id,
                "category": ticket.category.value if ticket.category else "general",
                "agent": agent_name,
                "status": "needs_info",
                "duration_ms": (time.time() - start) * 1000,
            }

        return {
            "response": response.message,
            "ticket_id": ticket.ticket_id,
            "category": ticket.category.value if ticket.category else "general",
            "agent": agent_name,
            "actions": response.actions_taken,
            "status": "resolved",
            "duration_ms": (time.time() - start) * 1000,
        }

    def _escalate(self, ticket: Ticket, reason: str) -> dict:
        self.supervisor.escalate_to_human(ticket, reason)
        return {
            "response": f"I've escalated this to a human agent. Reason: {reason}",
            "ticket_id": ticket.ticket_id,
            "status": "escalated",
            "escalation": reason,
        }


# ============================================================
# CLI
# ============================================================


def main():
    import argparse

    parser = argparse.ArgumentParser(description="SupportFlow Multi-Agent")
    parser.add_argument(
        "--keyword-only", action="store_true", help="Use keyword classification only"
    )
    parser.add_argument("query", nargs="*")
    args = parser.parse_args()

    system = MultiAgentSupport(use_llm_classifier=not args.keyword_only)

    query = " ".join(args.query)
    if query:
        result = system.handle_ticket(query)
        print(f"\n=== Ticket {result.get('ticket_id', 'N/A')} ===")
        print(f"Category: {result.get('category', 'N/A')}")
        print(f"Agent: {result.get('agent', 'N/A')}")
        print(f"Status: {result['status']}")
        print(f"Response: {result['response']}")
        print(f"Duration: {result.get('duration_ms', 0):.0f}ms")
    else:
        print("\nSupportFlow Multi-Agent (interactive)")
        print("Type 'exit' to quit.\n")
        while True:
            try:
                q = input("You: ")
                if q.lower() in ("exit", "quit"):
                    break
                result = system.handle_ticket(q)
                print(f"[{result['status'].upper()}] {result['response']}\n")
            except KeyboardInterrupt:
                break


if __name__ == "__main__":
    main()
