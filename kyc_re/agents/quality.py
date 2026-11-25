"""Validation / quality agent: checks each requirement and drafts acceptance criteria.

Checks: ambiguity, incompleteness, lack of testability, infeasibility, undefined
terminology, missing source and missing security controls. Requirements that fail a
medium- or higher-severity check go back to the clarification agent.
"""
from __future__ import annotations

import re

from ..models import ApprovalStatus, Category as C, Level, QualityIssue, Requirement
from .base import Agent

NUM = re.compile(r"\d+(\.\d+)?\s*(%|ms|milliseconds?|s\b|sec(ond)?s?|min(ute)?s?|hours?|days?|months?|years?|x|times|tps|users?|requests?)", re.I)

INCOMPLETE_RULES: list[tuple[C, str, str, str]] = [
    (C.PERFORMANCE, r"\d", "Performance requirement has no measurable target.", "State the target, such as p95 latency in seconds at N concurrent users."),
    (C.AVAILABILITY, r"\d", "Availability requirement has no measurable target.", "State the availability percentage, RTO and RPO."),
]
TOPIC_INCOMPLETE: list[tuple[str, str, str, str]] = [
    (r"\b(retain|retention|store|kept|keep)\b", r"\d+\s*(years?|months?|days?)", "Retention is stated without a period.", "State the retention period and its trigger (from account closure or from collection)."),
    (r"\b(limit|cap|threshold)\b", r"\d", "Limit or threshold has no value.", "State the threshold value and its currency or unit."),
    (r"\b(timeout|time out|expire|expiry)\b", r"\d", "Timeout or expiry has no duration.", "State the duration."),
    (r"\b(notify|alert|escalate)\b", r"\b(to|officer|team|customer|compliance|within)\b", "Notification target or deadline is unclear.", "State who is notified and within what time."),
]
INFEASIBLE = [
    (r"\b100\s*%\s*(uptime|availability|accura|detection)", "100% target is not achievable or verifiable."),
    (r"\bzero (false positives?|false negatives?|fraud|downtime|errors?)\b", "Zero-error target is not achievable or verifiable."),
    (r"\b(instant(ly)?|immediately|in no time)\b", "'Instant' is not measurable; state a latency bound."),
    (r"\bnever (fail|go down)\b", "Absolute reliability claim is not verifiable."),
]
SECURITY_TRIGGERS = [
    (r"\b(upload|document image|photo|selfie|video)\b", r"\b(encrypt|malware|scan|virus|file type|size)\b",
     "Handles uploaded identity media but states no protection (encryption, file validation, malware scan)."),
    (r"\b(api|integrat|third[- ]party|vendor)\b", r"\b(tls|mtls|authenticat|oauth|signed|encrypt|secure)\b",
     "Defines an external integration without transport or authentication security."),
    (r"\b(staff|officer|agent|admin|back-?office) (can|may|shall|should)? ?(view|see|access|edit|override)", r"\b(role|rbac|mfa|authori|permission|mask|maker[- ]checker|log)\b",
     "Gives staff access to customer data without access control or logging."),
]


def acceptance_criteria(r: Requirement) -> list[str]:
    s = r.statement.rstrip(".")
    core = re.sub(r"^The system shall\s+", "", s, flags=re.I)
    cats = set(r.categories)
    ac: list[str] = []
    nums = [m.group(0) for m in NUM.finditer(s)]
    if C.PERFORMANCE in cats and nums:
        ac.append(f"Given peak production load, when the step is executed, then it completes within {nums[0]} at the 95th percentile.")
    if C.AVAILABILITY in cats and nums:
        ac.append(f"Given a calendar month, when availability is measured by synthetic monitoring, then it meets {nums[0]}.")
    if C.DATA in cats and re.search(r"retain|retention|delete", s, re.I):
        ac.append("Given a closed relationship, when the retention period elapses, then the records are purged and the purge is logged; before that, records are retrievable within 1 business day.")
    if C.SECURITY in cats:
        ac.append(f"Given an unauthorised or unauthenticated actor, when they attempt to {core[:80]}, then access is denied and a security event is logged.")
    if C.REGULATORY in cats:
        ac.append("Given an internal audit sample, when the control evidence is reviewed, then 100% of sampled cases show the control was applied with traceable evidence.")
    if C.PRIVACY in cats:
        ac.append("Given a data-protection review, when processing records are inspected, then the lawful basis or consent and the purpose are recorded for each data item.")
    if C.AUDIT in cats:
        ac.append("Given any KYC decision, when the audit trail is queried, then actor, timestamp, action, reason and evidence references are returned and the hash chain verifies.")
    if not ac or C.FUNCTIONAL in cats:
        ac.insert(0, f"Given a valid onboarding application, when the system is required to {core[:120]}, then it does so and records the outcome.")
        ac.append("Given invalid or incomplete input, when the step is attempted, then the system rejects it with a specific error and no partial record is created.")
    return ac


class QualityAgent(Agent):
    name = "quality"
    description = "Checks requirement quality and drafts testable acceptance criteria."

    def check(self, r: Requirement) -> list[QualityIssue]:
        issues: list[QualityIssue] = []
        low = r.statement.lower()
        vague = [v for v in self.ctx.kb.interview["vague_terms"] if re.search(rf"\b{re.escape(v)}\b", low)]
        if vague:
            issues.append(QualityIssue(type="ambiguity", severity=Level.MEDIUM,
                                       detail=f"Vague term(s): {', '.join(vague)}.",
                                       suggestion="Replace with measurable criteria."))
        for cat, need, detail, sugg in INCOMPLETE_RULES:
            if cat in r.categories[:2] and not re.search(need, low):
                issues.append(QualityIssue(type="untestable", severity=Level.HIGH, detail=detail, suggestion=sugg))
        for trig, need, detail, sugg in TOPIC_INCOMPLETE:
            if re.search(trig, low) and not re.search(need, low):
                issues.append(QualityIssue(type="incompleteness", severity=Level.MEDIUM, detail=detail, suggestion=sugg))
        for rx, detail in INFEASIBLE:
            if re.search(rx, low):
                issues.append(QualityIssue(type="infeasibility", severity=Level.HIGH, detail=detail,
                                           suggestion="Agree a realistic, measurable target."))
        for trig, need, detail in SECURITY_TRIGGERS:
            if re.search(trig, low) and not re.search(need, low):
                issues.append(QualityIssue(type="missing_security_control", severity=Level.MEDIUM, detail=detail,
                                           suggestion="Link to the corresponding security requirement or add the control."))
        acronyms = set(re.findall(r"\b[A-Z][A-Z0-9-]{1,6}\b", r.statement)) - {"KYC", "API", "ID", "UI", "OTP", "PAN", "SMS", "PDF", "MFA", "TLS", "AES", "HSM", "IT"}
        acronyms = {a for a in acronyms if not a.startswith("<") and a not in self.ctx.kb.glossary and not re.match(r"^(FR|SEC|PRV|REG|PERF|AVL|USA|DAT|INT|AUD|OPS|BR|SR)$", a)}
        if acronyms:
            issues.append(QualityIssue(type="undefined_term", severity=Level.LOW,
                                       detail=f"Undefined term(s): {', '.join(sorted(acronyms))}.",
                                       suggestion="Add to the glossary or expand."))
        if not r.evidence and r.origin == "extracted":
            issues.append(QualityIssue(type="missing_source", severity=Level.HIGH, detail="No source evidence.",
                                       suggestion="Link the stakeholder statement or document."))
        if re.search(r"\b(and|or)\b.*\b(and|or)\b.*\b(and|or)\b", low) and len(low.split()) > 35:
            issues.append(QualityIssue(type="non_atomic", severity=Level.LOW, detail="Requirement bundles several needs.",
                                       suggestion="Split into atomic requirements."))
        return issues

    def assess(self, r: Requirement) -> None:
        r.quality_issues = self.check(r)
        if not r.acceptance_criteria or r.origin != "human":
            r.acceptance_criteria = acceptance_criteria(r)
        blocking = [i for i in r.quality_issues if i.severity in (Level.MEDIUM, Level.HIGH, Level.CRITICAL)]
        if r.status in (ApprovalStatus.DRAFT, ApprovalStatus.NEEDS_CLARIFICATION, ApprovalStatus.MODIFIED):
            r.status = ApprovalStatus.NEEDS_CLARIFICATION if blocking else ApprovalStatus.PENDING_APPROVAL
        r.confidence = round(max(0.2, min(0.99, r.confidence - 0.08 * len(blocking) + (0.05 if r.regulations else 0))), 2)

    def run(self, only_origin: str | None = None) -> None:
        self.need("read:requirements", "write:requirements")
        for r in self.ctx.state.requirements:
            if only_origin and r.origin != only_origin:
                continue
            if r.status in (ApprovalStatus.APPROVED, ApprovalStatus.REJECTED):
                continue
            self.assess(r)
        issues = sum(len(r.quality_issues) for r in self.ctx.state.requirements)
        self.log("quality_checked", "project", requirements=len(self.ctx.state.requirements), issues=issues)
