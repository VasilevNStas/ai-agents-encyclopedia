"""Role-based access control for agent tools.

Defines roles, maps them to permitted tools, and provides runtime
permission verification integrated with SecurityConfig.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Role(Enum):
    """Access roles ordered from most to least privileged."""

    ADMIN = "admin"
    AGENT = "agent"
    USER = "user"
    VIEWER = "viewer"

    @property
    def level(self) -> int:
        levels = {
            Role.ADMIN: 100,
            Role.AGENT: 75,
            Role.USER: 50,
            Role.VIEWER: 25,
        }
        return levels[self]


DEFAULT_TOOL_PERMISSIONS: dict[Role, set[str]] = {
    Role.ADMIN: {
        "delete",
        "send_email",
        "admin",
        "user_impersonate",
        "configure",
        "audit_view",
        "permissions_manage",
        "search_knowledge_base",
        "summarize_ticket",
        "escalate",
        "create_ticket",
        "update_ticket",
        "read_ticket",
        "run_sql",
        "export_data",
        "invoke_agent",
    },
    Role.AGENT: {
        "search_knowledge_base",
        "summarize_ticket",
        "escalate",
        "create_ticket",
        "update_ticket",
        "read_ticket",
        "run_sql",
        "send_email",
    },
    Role.USER: {
        "create_ticket",
        "update_ticket",
        "read_ticket",
        "search_knowledge_base",
    },
    Role.VIEWER: {
        "read_ticket",
        "search_knowledge_base",
    },
}


class PermissionRegistry:
    """Maps roles to permitted tools and manages custom grants."""

    def __init__(self, base_permissions: Optional[dict[Role, set[str]]] = None):
        self._permissions: dict[Role, set[str]] = {
            role: set(tools)
            for role, tools in (base_permissions or DEFAULT_TOOL_PERMISSIONS).items()
        }
        self._custom_grants: list[tuple[str, str, str]] = []

    def permitted_tools(self, role: Role) -> set[str]:
        return self._permissions.get(role, set()).copy()

    def grant(self, role: Role, tool: str, granted_by: str = "system") -> None:
        self._permissions.setdefault(role, set()).add(tool)
        self._custom_grants.append((role.value, tool, granted_by))

    def revoke(self, role: Role, tool: str) -> bool:
        if tool in self._permissions.get(role, set()):
            self._permissions[role].discard(tool)
            return True
        return False

    def can(
        self, role: Role, tool: str, require_hitl_tools: tuple[str, ...] = ()
    ) -> bool:
        return tool in self._permissions.get(role, set())

    def audit_grants(self) -> list[dict]:
        return [
            {"role": r, "tool": t, "granted_by": g} for r, t, g in self._custom_grants
        ]


class PermissionChecker:
    """Runtime permission verification with HITL escalation support.

    Integrates with SecurityConfig.require_hitl_for to enforce
    human-in-the-loop for sensitive tools.
    """

    def __init__(
        self,
        registry: Optional[PermissionRegistry] = None,
        require_hitl_for: tuple[str, ...] = ("delete", "send_email", "admin"),
    ):
        self.registry = registry or PermissionRegistry()
        self.require_hitl_for = require_hitl_for

    def check(self, role: Role, tool: str) -> dict:
        """Check if a role can call a tool before execution.

        Returns a dict with:
            - "allowed": bool
            - "requires_hitl": bool (if tool is in the sensitive list)
            - "reason": str
        """
        if not self.registry.can(role, tool):
            return {
                "allowed": False,
                "requires_hitl": False,
                "reason": f"Role '{role.value}' is not permitted to call '{tool}'",
            }

        if tool in self.require_hitl_for:
            return {
                "allowed": True,
                "requires_hitl": True,
                "reason": f"Tool '{tool}' requires human-in-the-loop approval",
            }

        return {
            "allowed": True,
            "requires_hitl": False,
            "reason": "ok",
        }

    def verify_runtime(
        self, role: Role, tool: str, context: Optional[dict] = None
    ) -> dict:
        """Runtime verification with additional context checks.

        Checks:
            1. Base permission
            2. HITL requirement
            3. Context-based restrictions (e.g., data scope)
        """
        result = self.check(role, tool)
        if not result["allowed"]:
            return result

        context = context or {}
        if role == Role.VIEWER and context.get("write_operation"):
            return {
                "allowed": False,
                "requires_hitl": False,
                "reason": "VIEWER role cannot perform write operations",
            }

        if role == Role.USER and tool == "run_sql" and not context.get("sandboxed"):
            return {
                "allowed": False,
                "requires_hitl": True,
                "reason": "User SQL queries must be sandboxed",
            }

        return result
