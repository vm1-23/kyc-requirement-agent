"""Conflict-detection agent: contradictions, duplicates and overlaps across stakeholders."""
from __future__ import annotations

import re
from itertools import combinations

from ..models import Conflict, Level, Requirement
from .base import Agent, jaccard

# Topic lexicon: two requirements are comparable only if they share a topic.
TOPICS: dict[str, str] = {
    "retention": r"\b(retain|retention|kept|keep|store|delete|purge)\w*",
    "onboarding_time": r"\b(onboard\w*|account opening|sign-?up|end-to-end|complete)\b.*\b(minutes?|seconds?|hours?|days?)\b",
    "availability": r"\b(availability|uptime|99\.\d+)",
    "manual_review": r"\b(manual(ly)?|human|officer|maker[- ]checker)\b.*\b(review|check|approv|verif)\w*",
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
QUANT = re.compile(r"(\d+(?:\.\d+)?)\s*(%|years?|months?|days?|hours?|minutes?|mins?|seconds?|secs?)", re.I)

_UNIT = {"year": "years", "years": "years", "month": "months", "months": "months", "day": "days", "days": "days",
         "hour": "hours", "hours": "hours", "minute": "minutes", "minutes": "minutes", "min": "minutes", "mins": "minutes",
         "second": "seconds", "seconds": "seconds", "sec": "seconds", "secs": "seconds", "%": "%"}


def topics_of(text: str) -> set[str]:
    low = text.lower()
    return {t for t, rx in TOPICS.items() if re.search(rx, low)}


def quantities(text: str) -> dict[str, set[float]]:
    out: dict[str, set[float]] = {}
    for v, u in QUANT.findall(text):
        out.setdefault(_UNIT[u.lower()], set()).add(float(v))
    return out


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
        seen = {tuple(sorted(c.requirement_ids)) for c in st.conflicts}
        reqs = [r for r in st.requirements if r.origin != "derived_control"]
        for a, b in combinations(reqs, 2):
            key = tuple(sorted((a.id, b.id)))
            if key in seen:
                continue
            c = self.compare(a, b)
            if c:
                st.conflicts.append(c)
                seen.add(key)
        self.log("conflicts", "project", count=len(st.conflicts))

    def compare(self, a: Requirement, b: Requirement) -> Conflict | None:
        sim = jaccard(a.statement, b.statement)
        shared = topics_of(a.statement) & topics_of(b.statement)
        cross_stakeholder = a.source_stakeholder != b.source_stakeholder
        if sim >= 0.7:
            return Conflict(id=self.ctx.next_id("CON"), requirement_ids=[a.id, b.id], type="duplicate",
                            severity=Level.LOW, detail=f"{a.id} and {b.id} state the same need (similarity {sim:.2f}).")
        for t in sorted(shared):
            qa, qb = quantities(a.statement), quantities(b.statement)
            for unit in set(qa) & set(qb):
                if qa[unit] != qb[unit] and not (qa[unit] & qb[unit]):
                    sev = Level.HIGH if t in ("retention", "screening", "rekyc", "availability") else Level.MEDIUM
                    return Conflict(id=self.ctx.next_id("CON"), requirement_ids=[a.id, b.id], type="contradiction",
                                    severity=sev,
                                    detail=f"Conflicting {t.replace('_', ' ')} values: {a.id} ({a.source_stakeholder or 'n/a'}) says "
                                           f"{sorted(qa[unit])} {unit}, {b.id} ({b.source_stakeholder or 'n/a'}) says {sorted(qb[unit])} {unit}.")
            if polarity(a.statement, t) != polarity(b.statement, t):
                return Conflict(id=self.ctx.next_id("CON"), requirement_ids=[a.id, b.id], type="contradiction",
                                severity=Level.HIGH if cross_stakeholder else Level.MEDIUM,
                                detail=f"Opposing positions on {t.replace('_', ' ')}: {a.id} ({a.source_stakeholder or 'n/a'}) vs "
                                       f"{b.id} ({b.source_stakeholder or 'n/a'}).")
        if shared and sim >= 0.45:
            return Conflict(id=self.ctx.next_id("CON"), requirement_ids=[a.id, b.id], type="overlap", severity=Level.LOW,
                            detail=f"{a.id} and {b.id} overlap on {', '.join(sorted(shared))}; consider merging.")
        return None
