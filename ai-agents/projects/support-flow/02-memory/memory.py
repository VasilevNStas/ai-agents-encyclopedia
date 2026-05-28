"""Three-layer memory system for SupportFlow.

Implements short-term, working, and long-term memory with
file-based persistence for the long-term layer (LLM Wiki approach).
"""

import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


@dataclass
class MemoryConfig:
    storage_dir: str = ".memory"
    max_short_term: int = 20


class ShortTermMemory:
    """Conversation buffer — keeps the last N messages.

    Maintains a sliding window of recent conversation history
    for immediate context during agent reasoning.
    """

    def __init__(self, max_messages: int = 20):
        self.max_messages = max_messages
        self.messages: list[dict] = []

    def add(self, role: str, content: str) -> None:
        """Add a message to the buffer, trimming if over limit."""
        self.messages.append(
            {
                "role": role,
                "content": content,
                "timestamp": datetime.now().isoformat(),
            }
        )
        if len(self.messages) > self.max_messages:
            self.messages = self.messages[-self.max_messages :]

    def get_context(self, limit: Optional[int] = None) -> list[dict]:
        """Return last N messages as context for the LLM."""
        limit = limit or self.max_messages
        return self.messages[-limit:]

    def clear(self) -> None:
        self.messages.clear()

    @property
    def count(self) -> int:
        return len(self.messages)


class WorkingMemory:
    """Key-value store for current task's intermediate data.

    Holds ephemeral state during a single agent run:
    plan steps, extracted facts, conclusions, tool results.
    """

    def __init__(self):
        self._data: dict[str, Any] = {}

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def update(self, key: str, value: Any) -> None:
        """Merge value into existing data (dict merge or list extend)."""
        existing = self._data.get(key)
        if isinstance(existing, dict) and isinstance(value, dict):
            existing.update(value)
        elif isinstance(existing, list) and isinstance(value, list):
            existing.extend(value)
        else:
            self._data[key] = value

    def items(self) -> dict[str, Any]:
        return dict(self._data)

    def clear(self) -> None:
        self._data.clear()

    def __contains__(self, key: str) -> bool:
        return key in self._data


class LongTermMemory:
    """File-based persistent memory using markdown files.

    Similar to LLM Wiki approach — knowledge is stored as
    structured markdown files in a designated directory.
    """

    def __init__(self, storage_dir: str = ""):
        self.storage_dir = storage_dir or ".memory"
        os.makedirs(self.storage_dir, exist_ok=True)

    def save(self, key: str, content: str, metadata: Optional[dict] = None) -> str:
        """Save content as a markdown file.

        Args:
            key: Human-readable name (used as filename).
            content: Markdown content to persist.
            metadata: Optional frontmatter dict.

        Returns:
            Path to the saved file.
        """
        safe_name = key.replace(" ", "_").replace("/", "_")
        filepath = os.path.join(self.storage_dir, f"{safe_name}.md")

        parts: list[str] = []
        if metadata:
            parts.append("---\n")
            for k, v in metadata.items():
                parts.append(f"{k}: {v}\n")
            parts.append("---\n\n")
        parts.append(f"# {key}\n\n")
        parts.append(content)
        if not content.endswith("\n"):
            parts.append("\n")

        with open(filepath, "w") as f:
            f.writelines(parts)
        return filepath

    def load(self, key: str) -> Optional[str]:
        """Load content from a markdown file.

        Returns:
            Raw file content, or None if file does not exist.
        """
        safe_name = key.replace(" ", "_").replace("/", "_")
        filepath = os.path.join(self.storage_dir, f"{safe_name}.md")
        if not os.path.exists(filepath):
            return None
        with open(filepath) as f:
            return f.read()

    def list_keys(self) -> list[str]:
        """List all stored keys (filenames without extension)."""
        if not os.path.isdir(self.storage_dir):
            return []
        return [
            f.replace(".md", "")
            for f in os.listdir(self.storage_dir)
            if f.endswith(".md")
        ]

    def delete(self, key: str) -> bool:
        """Delete a stored file. Returns True if deleted."""
        safe_name = key.replace(" ", "_").replace("/", "_")
        filepath = os.path.join(self.storage_dir, f"{safe_name}.md")
        if os.path.exists(filepath):
            os.remove(filepath)
            return True
        return False

    def clear(self) -> None:
        """Delete all stored files."""
        for key in self.list_keys():
            self.delete(key)


class AgentMemory:
    """Orchestrator combining short-term, working, and long-term memory.

    Provides a unified interface for the agent to access all
    three memory layers during a conversation.
    """

    def __init__(self, config: Optional[MemoryConfig] = None):
        self.config = config or MemoryConfig()
        self.short_term = ShortTermMemory(max_messages=self.config.max_short_term)
        self.working = WorkingMemory()
        self.long_term = LongTermMemory()

    def add_message(self, role: str, content: str) -> None:
        self.short_term.add(role, content)

    def get_conversation_context(self, limit: Optional[int] = None) -> list[dict]:
        return self.short_term.get_context(limit)

    def remember(self, key: str, value: Any) -> None:
        self.working.set(key, value)

    def recall(self, key: str, default: Any = None) -> Any:
        return self.working.get(key, default)

    def save_knowledge(
        self, key: str, content: str, metadata: Optional[dict] = None
    ) -> str:
        return self.long_term.save(key, content, metadata)

    def load_knowledge(self, key: str) -> Optional[str]:
        return self.long_term.load(key)

    def list_knowledge_keys(self) -> list[str]:
        return self.long_term.list_keys()

    def clear_session(self) -> None:
        self.short_term.clear()
        self.working.clear()

    def clear_all(self) -> None:
        self.short_term.clear()
        self.working.clear()
        self.long_term.clear()
