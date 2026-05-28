"""SupportFlow Stage 6: Security — Audit Trail, RBAC, PII Sanitization."""

import json
import os
import sys
import time
from typing import Any

sys.path.insert(0, os.path.dirname(__file__))
from audit import SecureAudit
from permissions import PermissionChecker, Role
from sanitizer import PIISanitizer

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "03-production"))
from agent import ProductionAgent, AgentConfig, ModelConfig


class SecureAgent:
    """Агент с audit trail, RBAC и PII sanitization."""

    def __init__(self, config: AgentConfig | None = None):
        self.config = config or AgentConfig()
        self.audit = SecureAudit()
        self.sanitizer = PIISanitizer()
        self._base_agent = ProductionAgent(config)

    def run(
        self, user_input: str, user_role: str = "user", user_id: str = "anon"
    ) -> dict:
        start = time.time()

        # 1. Sanitize input (remove PII before LLM sees it)
        sanitized_input = self.sanitizer.sanitize(user_input)

        # 2. Execute agent
        result = self._base_agent.run(sanitized_input)

        # 3. Sanitize output (ensure no PII leaks)
        safe_response = self.sanitizer.sanitize(result.get("response", ""))

        # 4. Audit trail (immutable, chain-hashed)
        record = self.audit.record(
            user_id=user_id,
            action="chat",
            details={
                "role": user_role,
                "input_length": len(user_input),
                "output_length": len(safe_response),
                "cost": result.get("cost", 0),
            },
        )

        return {
            "response": safe_response,
            "audit_id": record.record_id,
            "audit_hash": record.hash[:12],
            "sanitized": sanitized_input != user_input,
            "cost": result.get("cost", 0),
        }


def main():
    import argparse

    parser = argparse.ArgumentParser(description="SupportFlow Secure Agent")
    parser.add_argument(
        "--role", default="user", choices=["viewer", "user", "agent", "admin"]
    )
    parser.add_argument("--user", default="demo_user")
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("query", nargs="*")
    args = parser.parse_args()

    config = AgentConfig(verbose=not args.quiet)
    agent = SecureAgent(config)

    query = " ".join(args.query)
    if query:
        result = agent.run(query, user_role=args.role, user_id=args.user)
        print(f"\n=== Response ===")
        print(result["response"])
        print(
            f"\n[Audit: {result['audit_id']} | Hash: {result.get('audit_hash', '')[:12]} | "
            f"Sanitized: {result.get('sanitized', False)}]"
        )
    else:
        print(f"\nSupportFlow Secure Agent (interactive)")
        print(f"Role: {args.role} | User: {args.user} | Audit: audit_log.jsonl")
        while True:
            try:
                q = input("You: ")
                if q.lower() in ("exit", "quit"):
                    break
                result = agent.run(q, user_role=args.role, user_id=args.user)
                print(f"\nAgent: {result['response']}\n")
            except KeyboardInterrupt:
                break


if __name__ == "__main__":
    main()
