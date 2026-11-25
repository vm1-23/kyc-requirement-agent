"""Conflict-detection agent: contradictions, duplicates and overlaps across stakeholders."""
from __future__ import annotations

import re
from itertools import combinations

from ..models import Conflict, Level, Requirement
from .base import Agent, jaccard

# Topic lexicon: two requirements are comparable only if they share a topic.
TOPICS: dict[str, str] = {
    "retention": r"\b(retain|retention|kept|keep|store|delete|purge)\w*",
    "onboarding_time": r"\b(onboard\w*|account opening|sign-?up|journey)\b.{0,40}\b(complet\w*|within|takes?|under)\b.{0,20}\d+\s*(minutes?|seconds?|hours?|days?)\b",
    "availability": r"\b(availability|uptime|99\.\d+)",
    "manual_review": r"\b(manual(ly)? review\w*|human review\w*|reviewed manually|manually (reviewed|checked|verified))\b",
    "video_kyc": r"\b(video|v-?cip)\b",
    "liveness": r"\b(liveness|selfie|face match)\b",
    "documents": r"\b(document|ovd|passport|driving licen[cs]e|utility bill|proof of address)\w*",
    "limits": r"\b(limit|cap|threshold)\b",
    "session": r"\b(session|timeout|time out|log ?out)\b",
    "rekyc": r"\b(re-?kyc|periodic (update|updation|review))\b",
    "data_location": r"\b(cloud|data residency|locali[sz]|on-?prem|within india|in-country|offshore)\w*",
    "screening": r"\b(sanction|pep|screen)\w*",
    "authentication": r"\b(otp|mfa|password|biometric login|authenticat)\w*",
}
NEGATION = re.compile(r"\b(no|not|never|without|avoid|skip|eliminate|remove|don'?t|doesn'?t|cannot|must not|shall not|zero)\b", re.I)
QUANT = re.compile(r"(at least|minimum of|min\.?|no less than|not less than|at most|maximum of|max\.?|no more than|up to|within|under)?\s*"
                   r"(\d+(?:\.\d+)?)\s*(%|years?|months?|days?|hours?|minutes?|mins?|seconds?|secs?)", re.I)
LOWER = {"at least", "minimum of", "min", "min.", "no less than", "not less than"}

_UNIT = {"year": "years", "years": "years", "month": "months", "months": "months", "day": "days", "days": "days",
         "hour": "hours", "hours": "hours", "minute": "minutes", "minutes": "minutes", "min": "minutes", "mins": "minutes",
         "second": "seconds", "seconds": "seconds", "sec": "seconds", "secs": "seconds", "%": "%"}


def topics_of(text: str) -> set[str]:
    low = text.lower()
    return {t for t, rx in TOPICS.items() if re.search(rx, low)}


def quantities(text: str) -> dict[str, set[float]]:
    out: dict[str, set[float]] = {}
    for _, v, u in QUANT.findall(text):
        out.setdefault(_UNIT[u.lower()], set()).add(float(v))
    return out


def ranges(text: str) -> dict[str, list[tuple[float, float]]]:
    """Value ranges per unit: 'at least 5 years' -> (5, inf); 'within 5 minutes' -> (0, 5); '10 years' -> (10, 10)."""
    out: dict[str, list[tuple[float, float]]] = {}
    for q, v, u in QUANT.findall(text):
        x, q = float(v), q.lower().strip()
        rng = (x, float("inf")) if q in LOWER else (0.0, x) if q else (x, x)
        out.setdefault(_UNIT[u.lower()], []).append(rng)
    return out


def compatible(a: list[tuple[float, float]], b: list[tuple[float, float]]) -> bool:
    return any(max(x[0], y[0]) <= min(x[1], y[1]) for x in a for y in b)


def polarity(text: str, topic: str) -> int:
    """-1 if the topic is negated in the clause where it appears, else +1."""
    low = text.lower()
    m = re.search(TOPICS[topic], low)
    if not m:
        return 1
    window = low[max(0, m.start() - 60): m.end() + 10]
    return -1 if NEGATION.search(window) else 1


class ConflictAgent(Agent):
    name = "conflict"
    description = "Detects contradictions and duplicates between requirements."

    def run(self) -> None:
        self.need("read:requirements", "write:conflicts")
        st = self.ctx.state
        reqs = [r for r in st.requirements if r.origin != "derived_control"]
        by_id = {r.id: r for r in reqs}
        # Re-check open stakeholder conflicts: a clarification may have resolved them.
        for c in st.conflicts:
            if c.resolution is None and c.type in ("contradiction", "duplicate", "overlap") and all(i in by_id for i in c.requirement_ids):
                again = self.compare(*(by_id[i] for i in c.requirement_ids), dry=True)
                if again is None or again.type != c.type:
                    c.resolution = "auto-resolved: no longer detected after clarification"
                    self.log("conflict_auto_resolved", c.id)
        seen = {tuple(sorted(c.requirement_ids)) for c in st.conflicts}
        for a, b in combinations(reqs, 2):
            key = tuple(sorted((a.id, b.id)))
            if key in seen:
                continue
            c = self.compare(a, b)
            if c:
                st.conflicts.append(c)
                seen.add(key)
        self.log("conflicts", "project", count=len(st.conflicts))

    def compare(self, a: Requirement, b: Requirement, dry: bool = False) -> Conflict | None:
        sim = jaccard(a.statement, b.statement)
        shared = topics_of(a.statement) & topics_of(b.statement)
        cross_stakeholder = a.source_stakeholder != b.source_stakeholder
        if sim >= 0.7:
            return Conflict(id=("CON-?" if dry else self.ctx.next_id("CON")), requirement_ids=[a.id, b.id], type="duplicate",
                            severity=Level.LOW, detail=f"{a.id} and {b.id} state the same need (similarity {sim:.2f}).")
        for t in sorted(shared):
            qa, qb = quantities(a.statement), quantities(b.statement)
            ra, rb = ranges(a.statement), ranges(b.statement)
            for unit in set(qa) & set(qb):
                if not compatible(ra[unit], rb[unit]):
                    sev = Level.HIGH if t in ("retention", "screening", "rekyc", "availability") else Level.MEDIUM
                    return Conflict(id=("CON-?" if dry else self.ctx.next_id("CON")), requirement_ids=[a.id, b.id], type="contradiction",
                                    severity=sev,
                                    detail=f"Conflicting {t.replace('_', ' ')} values: {a.id} ({a.source_stakeholder or 'n/a'}) says "
                                           f"{sorted(qa[unit])} {unit}, {b.id} ({b.source_stakeholder or 'n/a'}) says {sorted(qb[unit])} {unit}.")
            if polarity(a.statement, t) != polarity(b.statement, t):
                return Conflict(id=("CON-?" if dry else self.ctx.next_id("CON")), requirement_ids=[a.id, b.id], type="contradiction",
                                severity=Level.HIGH if cross_stakeholder else Level.MEDIUM,
                                detail=f"Opposing positions on {t.replace('_', ' ')}: {a.id} ({a.source_stakeholder or 'n/a'}) vs "
                                       f"{b.id} ({b.source_stakeholder or 'n/a'}).")
        if shared and sim >= 0.45:
            return Conflict(id=("CON-?" if dry else self.ctx.next_id("CON")), requirement_ids=[a.id, b.id], type="overlap", severity=Level.LOW,
                            detail=f"{a.id} and {b.id} overlap on {', '.join(sorted(shared))}; consider merging.")
        return None
