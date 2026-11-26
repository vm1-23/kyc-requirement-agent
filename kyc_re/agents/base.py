"""Agent base class and the shared run context."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from ..audit import AuditLog
from ..knowledge.kb import KnowledgeBase
from ..llm import LLM
from ..models import ProjectState
from ..security.pii import PIIMasker
from ..security.rbac import check_agent


@dataclass
class Context:
    state: ProjectState
    kb: KnowledgeBase
    llm: LLM
    audit: AuditLog
    masker: PIIMasker = field(default_factory=PIIMasker)
    counters: dict[str, int] = field(default_factory=dict)
    stats: dict[str, Any] = field(default_factory=dict)
    progress: Any = None  # RunProgress while a pipeline run is in flight

    def report(self, text: str) -> None:
        """Tell the UI what the current stage is doing right now (e.g. which document)."""
        if self.progress is not None:
            self.progress.detail(text)

    def next_id(self, prefix: str) -> str:
        self.counters[prefix] = self.counters.get(prefix, 0) + 1
        return f"{prefix}-{self.counters[prefix]:03d}"

    def bump(self, key: str, n: int = 1) -> None:
        self.stats[key] = self.stats.get(key, 0) + n


class Agent:
    name = "agent"
    description = ""

    def __init__(self, ctx: Context):
        self.ctx = ctx

    # least-privilege guard
    def need(self, *scopes: str) -> None:
        for s in scopes:
            check_agent(self.name, s)

    def log(self, action: str, subject: str = "", **payload: Any) -> None:
        self.ctx.audit.record(f"agent:{self.name}", action, subject, **payload)

    def run(self) -> None:  # pragma: no cover - interface
        raise NotImplementedError


# ---- shared text helpers ---------------------------------------------------------------

_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(<])|\n+|;\s+|•|^\s*[-*]\s+", re.M)


def sentences(text: str) -> list[str]:
    parts = [p.strip(" \t-*•") for p in _SENT_SPLIT.split(text) if p and p.strip()]
    return [p for p in parts if len(p) > 3]


def words(text: str) -> set[str]:
    return set(re.findall(r"[a-z][a-z0-9-]+", text.lower()))


def jaccard(a: str, b: str) -> float:
    stop = {"the", "system", "shall", "must", "should", "be", "a", "an", "to", "of", "and", "for", "all", "any", "is", "are", "in", "on", "with", "by"}
    wa, wb = words(a) - stop, words(b) - stop
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / len(wa | wb)
