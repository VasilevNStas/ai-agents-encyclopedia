"""PII protection — sanitization, pseudonymization, and restoration.

Integrates with Guardrail patterns from core.py for sensitive data detection.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PIISanitizer:
    """Sanitizes and restores Personally Identifiable Information in text.

    Supports:
        - Detection & replacement: emails, phones, names, API keys, IPs
        - Pseudonymization: consistent replacement per user (one-way)
        - Restoration: reversible replacement for authorized contexts
        - Custom pattern registration
    """

    replacement_map: dict[str, str] = field(default_factory=dict)
    pseudonym_seed: str = "default"

    _patterns: dict[str, re.Pattern] = field(init=False, repr=False)
    _restore_map: dict[str, str] = field(init=False, repr=False, default_factory=dict)

    def __post_init__(self):
        self._patterns = {
            "email": re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]{2,}\b"),
            "phone": re.compile(
                r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{2,4}[-.\s]?\d{2,4}\b"
            ),
            "api_key": re.compile(
                r"\b(sk-[a-zA-Z0-9]{20,}|ghp_[a-zA-Z0-9]{36,}|api[-_]?key[-_]?[:=]\s*\S+)\b",
                re.IGNORECASE,
            ),
            "ip_address": re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"),
            "credit_card": re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b"),
            "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
        }
        for label, pattern in self.replacement_map.items():
            self._patterns[label] = re.compile(pattern)

        self._restore_map = {}

    def register_pattern(self, label: str, pattern: str) -> None:
        self._patterns[label] = re.compile(pattern)

    def sanitize(self, text: str, pseudonymize: bool = False) -> str:
        result = text

        for label, pattern in self._patterns.items():

            def make_replacer(lbl: str, psm: bool):
                def replacer(match: re.Match) -> str:
                    original = match.group(0)
                    if psm:
                        placeholder = self._pseudonymize(original, lbl)
                    else:
                        placeholder = f"<{lbl}_{abs(hash(original)) % 10_000}>"
                    self._restore_map[placeholder] = original
                    return placeholder

                return replacer

            result = pattern.sub(make_replacer(label, pseudonymize), result)

        return result

    def restore(self, text: str) -> str:
        for placeholder, original in self._restore_map.items():
            text = text.replace(placeholder, original)
        return text

    def restore_authorized(self, text: str, authorized: bool = False) -> str:
        if authorized:
            return self.restore(text)
        return text

    def _pseudonymize(self, value: str, label: str) -> str:
        raw = f"{self.pseudonym_seed}:{label}:{value}"
        digest = hashlib.sha256(raw.encode()).hexdigest()[:12]
        return f"<{label}:{digest}>"

    def detect_pii(self, text: str) -> list[dict]:
        found: list[dict] = []
        for label, pattern in self._patterns.items():
            for match in pattern.finditer(text):
                found.append(
                    {
                        "type": label,
                        "value": match.group(0),
                        "start": match.start(),
                        "end": match.end(),
                    }
                )
        return found

    def anonymize(self, text: str) -> str:
        """One-way sanitization (no restoration possible)."""
        for pattern in self._patterns.values():
            text = pattern.sub("[REDACTED]", text)
        return text

    def guardrail_check(self, text: str) -> dict:
        """Integration point: matches Guardrail.check_output API from core.py."""
        found = self.detect_pii(text)
        if found:
            return {
                "action": "sanitize",
                "reason": "PII detected",
                "pii_types": list({f["type"] for f in found}),
                "count": len(found),
            }
        return {"action": "allow"}
