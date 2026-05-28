"""Immutable audit log with chain hashing and tamper detection.

Extends concepts from core.AuditTrail with persistent JSONL storage,
chain-of-hash integrity, and compliance export.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class AuditRecord:
    """Single audit record with chain hash."""

    record_id: str
    user_id: str
    action: str
    details: dict
    timestamp: float = field(default_factory=time.time)
    previous_hash: str = ""
    hash: str = ""

    def compute_hash(self) -> str:
        payload = {
            "record_id": self.record_id,
            "user_id": self.user_id,
            "action": self.action,
            "details": self.details,
            "timestamp": self.timestamp,
            "previous_hash": self.previous_hash,
        }
        raw = json.dumps(payload, sort_keys=True, default=str).encode()
        return hashlib.sha256(raw).hexdigest()

    def to_dict(self) -> dict:
        return {
            "record_id": self.record_id,
            "user_id": self.user_id,
            "action": self.action,
            "details": self.details,
            "timestamp": self.timestamp,
            "previous_hash": self.previous_hash,
            "hash": self.hash,
        }

    @classmethod
    def from_dict(cls, data: dict) -> AuditRecord:
        return cls(
            record_id=data["record_id"],
            user_id=data["user_id"],
            action=data["action"],
            details=data.get("details", {}),
            timestamp=data.get("timestamp", time.time()),
            previous_hash=data.get("previous_hash", ""),
            hash=data.get("hash", ""),
        )


class SecureAudit:
    """Immutable, persistent audit log with chain-of-hash integrity.

    Writes every record to a JSONL file for crash-safe persistence.
    Each record's hash includes the previous record's hash, forming an
    immutable chain that can be verified for tamper detection.
    """

    def __init__(self, log_path: str = "audit_log.jsonl"):
        self.log_path = log_path
        self._cache: list[AuditRecord] = []
        self._load()

    def record(
        self,
        user_id: str,
        action: str,
        details: Optional[dict] = None,
    ) -> AuditRecord:
        previous_hash = self._cache[-1].hash if self._cache else ""
        record = AuditRecord(
            record_id=f"{int(time.time() * 1_000_000):x}",
            user_id=user_id,
            action=action,
            details=details or {},
            previous_hash=previous_hash,
        )
        record.hash = record.compute_hash()

        self._cache.append(record)
        self._append_to_file(record)
        return record

    def query(
        self,
        user_id: Optional[str] = None,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        action: Optional[str] = None,
        limit: int = 100,
    ) -> list[AuditRecord]:
        results = list(self._cache)

        if user_id is not None:
            results = [r for r in results if r.user_id == user_id]
        if start_time is not None:
            results = [r for r in results if r.timestamp >= start_time]
        if end_time is not None:
            results = [r for r in results if r.timestamp <= end_time]
        if action is not None:
            results = [r for r in results if r.action == action]

        return results[-limit:]

    def verify_chain(self) -> dict:
        """Verify the integrity of the entire hash chain.

        Returns:
            dict with "valid" bool, "records_checked" count, and
            optional "first_broken_index" if tampering is detected.
        """
        for i, record in enumerate(self._cache):
            expected_prev = self._cache[i - 1].hash if i > 0 else ""

            if record.previous_hash != expected_prev:
                return {
                    "valid": False,
                    "reason": f"previous_hash mismatch at index {i}",
                    "first_broken_index": i,
                    "records_checked": len(self._cache),
                }

            computed = record.compute_hash()
            if record.hash != computed:
                return {
                    "valid": False,
                    "reason": f"hash mismatch at index {i} (tampered record)",
                    "first_broken_index": i,
                    "records_checked": len(self._cache),
                }

        return {
            "valid": True,
            "records_checked": len(self._cache),
        }

    def get_by_user(self, user_id: str) -> list[AuditRecord]:
        return self.query(user_id=user_id)

    def export_csv(self) -> str:
        """Export all records as CSV string for compliance reporting."""
        output = io.StringIO()
        fieldnames = [
            "record_id",
            "user_id",
            "action",
            "timestamp",
            "previous_hash",
            "hash",
        ]
        writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for record in self._cache:
            writer.writerow(record.to_dict())
        return output.getvalue()

    def clear(self) -> None:
        self._cache.clear()
        if os.path.exists(self.log_path):
            os.remove(self.log_path)

    def _load(self) -> None:
        if not os.path.exists(self.log_path):
            return
        with open(self.log_path) as f:
            for line in f:
                line = line.strip()
                if line:
                    self._cache.append(AuditRecord.from_dict(json.loads(line)))

    def _append_to_file(self, record: AuditRecord) -> None:
        with open(self.log_path, "a") as f:
            f.write(json.dumps(record.to_dict(), default=str) + "\n")
