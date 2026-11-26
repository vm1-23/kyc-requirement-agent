"""Live progress of a pipeline run, so the UI can show which agent is working and what it found.

The coordinator runs in a request thread; the UI polls a snapshot from another thread, so every
access goes through a lock and snapshots are deep copies.
"""
from __future__ import annotations

import copy
import threading
import time
from typing import Any

# stage id -> (label, what the agent does). Order is the pipeline order.
STAGES: dict[str, tuple[str, str]] = {
    "ingestion": ("Security gate", "Masks PII and quarantines prompt-injection attempts"),
    "topic_coverage": ("Topic coverage", "Checks which interview topics the inputs already cover"),
    "extraction": ("Requirement extraction", "Pulls requirement statements out of each input"),
    "classification": ("Classification", "Assigns multi-label categories and requirement IDs"),
    "quality": ("Quality checks", "Flags ambiguity, incompleteness and untestable wording"),
    "conflict": ("Conflict detection", "Finds contradictions and duplicates between stakeholders"),
    "compliance": ("Compliance mapping", "Maps requirements to regulations and mandatory controls"),
    "security_privacy": ("Security & privacy", "Threat-models the scope and derives missing controls"),
    "quality_derived": ("Quality (derived)", "Checks the requirements the compliance agent added"),
    "clarification": ("Clarification", "Writes questions for stakeholders about weak requirements"),
    "risk": ("Risk analysis", "Builds the risk register from requirements and gaps"),
    "sdlc": ("SDLC selection", "Scores project factors and recommends a lifecycle"),
    "validation": ("Validation", "Evaluates baseline quality gates"),
    "approval": ("Approval routing", "Creates human-approval items for critical decisions"),
}
FULL_RUN = list(STAGES)
ANALYSIS = FULL_RUN[3:]


class RunProgress:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._d: dict[str, Any] | None = None

    # ---- writers (pipeline thread) -----------------------------------------------------
    def start(self, trigger: str, stages: list[str], llm: str) -> None:
        with self._lock:
            self._d = {"running": True, "trigger": trigger, "llm": llm, "started": time.time(), "finished": None,
                       "error": None, "current": None, "detail": "", "llm_calls": 0, "llm_failed": 0, "llm_active": None,
                       "stages": [{"id": s, "label": STAGES[s][0], "about": STAGES[s][1], "status": "pending",
                                   "seconds": None, "note": "", "llm_calls": 0} for s in stages]}

    def _stage(self, sid: str) -> dict[str, Any] | None:
        return next((s for s in self._d["stages"] if s["id"] == sid), None) if self._d else None

    def stage_start(self, sid: str) -> None:
        with self._lock:
            if (s := self._stage(sid)) is not None:
                s["status"] = "running"
                self._d["current"], self._d["detail"] = sid, ""

    def stage_end(self, sid: str, seconds: float, note: str) -> None:
        with self._lock:
            if (s := self._stage(sid)) is not None:
                s.update(status="done", seconds=round(seconds, 3), note=note)
                self._d["detail"] = ""

    def detail(self, text: str) -> None:
        with self._lock:
            if self._d and self._d["running"]:
                self._d["detail"] = text

    def llm_start(self, purpose: str) -> None:
        with self._lock:
            if self._d and self._d["running"]:
                self._d["llm_active"] = {"purpose": purpose, "since": time.time()}

    def llm_end(self, ok: bool) -> None:
        with self._lock:
            if not (self._d and self._d["running"]):
                return
            self._d["llm_active"] = None
            self._d["llm_calls"] += 1
            self._d["llm_failed"] += 0 if ok else 1
            if (s := self._stage(self._d["current"] or "")) is not None:
                s["llm_calls"] += 1

    def finish(self, error: str | None = None) -> None:
        with self._lock:
            if not self._d:
                return
            self._d.update(running=False, finished=time.time(), error=error, llm_active=None, detail="")
            if error:
                for s in self._d["stages"]:
                    if s["status"] == "running":
                        s["status"] = "failed"

    # ---- readers -----------------------------------------------------------------------
    def snapshot(self) -> dict[str, Any] | None:
        with self._lock:
            if self._d is None:
                return None
            d = copy.deepcopy(self._d)
        d["elapsed"] = round((d["finished"] or time.time()) - d["started"], 3)
        if d["llm_active"]:
            d["llm_active"]["seconds"] = round(time.time() - d["llm_active"]["since"], 1)
        return d

    @property
    def running(self) -> bool:
        with self._lock:
            return bool(self._d and self._d["running"])


class ProgressLLM:
    """Wraps an LLM client so every call is counted against the current stage."""

    def __init__(self, inner: Any, progress: RunProgress):
        object.__setattr__(self, "_inner", inner)
        object.__setattr__(self, "_progress", progress)

    def json(self, purpose: str, *args: Any, **kwargs: Any) -> Any:
        self._progress.llm_start(purpose)
        out = None
        try:
            out = self._inner.json(purpose, *args, **kwargs)
            return out
        finally:
            self._progress.llm_end(out is not None)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)

    def __setattr__(self, name: str, value: Any) -> None:
        setattr(self._inner, name, value)
