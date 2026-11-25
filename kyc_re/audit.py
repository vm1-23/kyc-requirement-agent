"""Append-only, hash-chained audit trail.

Each event stores the SHA-256 of the previous event, so tampering with any record
breaks the chain and `verify()` detects it. Payloads must already be PII-masked.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .models import utcnow

GENESIS = "0" * 64


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class AuditLog:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else None
        self.events: list[dict[str, Any]] = []
        if self.path and self.path.exists():
            self.events = [json.loads(line) for line in self.path.read_text().splitlines() if line.strip()]

    @property
    def head(self) -> str:
        return self.events[-1]["hash"] if self.events else GENESIS

    def record(self, actor: str, action: str, subject: str = "", **payload: Any) -> dict[str, Any]:
        event = {
            "seq": len(self.events) + 1,
            "ts": utcnow(),
            "actor": actor,
            "action": action,
            "subject": subject,
            "payload": payload,
            "prev": self.head,
        }
        event["hash"] = sha256(json.dumps(event, sort_keys=True, default=str))
        self.events.append(event)
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a") as fh:
                fh.write(json.dumps(event, default=str) + "\n")
        return event

    def verify(self) -> bool:
        prev = GENESIS
        for e in self.events:
            body = {k: v for k, v in e.items() if k != "hash"}
            if e["prev"] != prev or sha256(json.dumps(body, sort_keys=True, default=str)) != e["hash"]:
                return False
            prev = e["hash"]
        return True

    def by_subject(self, subject: str) -> list[dict[str, Any]]:
        return [e for e in self.events if e["subject"] == subject]
