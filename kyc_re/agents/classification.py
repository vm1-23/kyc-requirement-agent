"""Classification agent: multi-label requirement classification and ID assignment."""
from __future__ import annotations

import re

from ..models import NON_FUNCTIONAL, Category as C, Requirement
from .base import Agent

LEXICON: dict[C, list[str]] = {
    C.BUSINESS: [r"\b(revenue|cost|conversion|drop-?off|market|kpi|business goal|objective|reduce .* (time|cost)|increase|competitive|customer acquisition)\b"],
    C.STAKEHOLDER: [r"\b(customers? (want|expect|need)|agents? (want|need)|officers? need|branch staff)\b"],
    C.FUNCTIONAL: [r"\b(capture|upload|verify|validate|screen|calculate|assign|generate|display|notify|send|allow|enable|route|create|submit|scan|match|schedule|store|search|block|reject|approve|escalate|download|select|fetch|record)\b"],
    C.SECURITY: [r"\b(secur|encrypt|mfa|multi-factor|two-factor|otp|authenticat|authori[sz]|access control|rbac|role-based|least privilege|tls|aes|hsm|malware|penetration|vulnerab|tamper|fraud|spoof|deepfake|liveness|presentation attack|session timeout|step-up|firewall|threat|password|token)\w*"],
    C.PRIVACY: [r"\b(privacy|consent|personal data|pii|gdpr|dpdp|data principal|data subject|minimi[sz]|purpose limitation|erasure|right to|mask|anonymi[sz]|pseudonymi[sz]|biometric data|notice)\w*"],
    C.REGULATORY: [r"\b(regulat|rbi|fatf|pmla|aml|cft|kyc norms|compliance|sanction|pep|politically exposed|beneficial own|ubo|ckyc|v-?cip|fiu|str|sar|due diligence|edd|cdd|re-?kyc|law|statutory|master direction|amld|fincen|ofac)\w*"],
    C.PERFORMANCE: [r"\b(\d+\s*(ms|milliseconds?|seconds?|secs?|minutes?|mins?)|latency|response time|throughput|tps|concurrent|peak load|per (second|minute|hour)|fast|quick|speed|performance)\b"],
    C.AVAILABILITY: [r"\b(availability|uptime|99\.\d+|downtime|disaster recovery|\bdr\b|rto|rpo|failover|fail over|redundan|resilien|24x7|24/7|outage|fallback)\w*"],
    C.USABILITY: [r"\b(usab|user-?friendly|intuitive|accessib|wcag|language|vernacular|mobile|ui|ux|screen reader|easy|simple|steps|guidance|error message|drop-?off)\w*"],
    C.DATA: [r"\b(retain|retention|store|storage|archive|delete|deletion|purge|data quality|backup|master data|record(s)? (for|of)|years|database|data residency|localisation|localization)\w*"],
    C.INTEGRATION: [r"\b(integrat|api|core banking|cbs|crm|vendor|third[- ]party|registry|ckyc|digilocker|uidai|webhook|interface|connector|legacy|bureau|e-?sign|nsdl|message queue|batch)\w*"],
    C.AUDIT: [r"\b(audit|log|trail|report|mis|dashboard|evidence|record (who|every|each)|regulator(y)? report|inspection)\w*"],
    C.OPERATIONAL: [r"\b(operations?|ops|monitor|alert|support|queue|backlog|sla|maintenance|on-?call|runbook|incident|manual review|case management|workload|staff)\w*"],
}

ID_PREFIX = {
    C.FUNCTIONAL: "FR", C.SECURITY: "SEC", C.PRIVACY: "PRV", C.REGULATORY: "REG", C.PERFORMANCE: "PERF",
    C.AVAILABILITY: "AVL", C.USABILITY: "USA", C.DATA: "DAT", C.INTEGRATION: "INT", C.AUDIT: "AUD",
    C.OPERATIONAL: "OPS", C.BUSINESS: "BR", C.STAKEHOLDER: "SR",
}

# Primary category precedence (most specific first) for ID prefix.
PRIMARY_ORDER = [C.SECURITY, C.PRIVACY, C.PERFORMANCE, C.AVAILABILITY, C.DATA, C.AUDIT, C.INTEGRATION,
                 C.USABILITY, C.OPERATIONAL, C.REGULATORY, C.FUNCTIONAL, C.BUSINESS, C.STAKEHOLDER]

_CLASSIFY_SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "categories": {"type": "array", "items": {"type": "string", "enum": [c.value for c in C]}},
                    "primary": {"type": "string", "enum": [c.value for c in C]},
                },
                "required": ["id", "categories", "primary"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["items"],
    "additionalProperties": False,
}


def rule_labels(text: str) -> list[C]:
    low = text.lower()
    labels = [c for c, pats in LEXICON.items() if any(re.search(p, low) for p in pats)]
    return labels


def primary_of(labels: list[C], text: str) -> C:
    low = text.lower()
    # A capability statement ("shall capture/verify/screen ...") is functional even if it is regulatory.
    if C.FUNCTIONAL in labels and re.search(r"shall (capture|verify|screen|allow|route|generate|display|upload|assign|schedule|notify|block|escalate|support)", low):
        if not ({C.SECURITY, C.PERFORMANCE, C.AVAILABILITY} & set(labels) and re.search(r"(encrypt|mfa|latency|uptime|\d+\s*seconds)", low)):
            return C.FUNCTIONAL
    for c in PRIMARY_ORDER:
        if c in labels:
            return c
    return C.FUNCTIONAL


class ClassificationAgent(Agent):
    name = "classification"
    description = "Multi-label classification across 13 requirement dimensions; assigns stable IDs."

    def run(self) -> None:
        self.need("read:requirements", "write:requirements")
        reqs = [r for r in self.ctx.state.requirements if r.id.startswith("TMP-") or not r.categories]
        llm_out = self._llm(reqs) if (self.ctx.llm.available and reqs) else {}
        for r in reqs:
            rule = rule_labels(r.statement)
            if r.id in llm_out:
                labels_llm, primary = llm_out[r.id]
                labels = list(dict.fromkeys(labels_llm + [c for c in rule if c in (C.REGULATORY, C.SECURITY, C.PRIVACY)]))
                r.confidence = min(0.95, r.confidence + (0.1 if set(rule) & set(labels_llm) else 0))
            else:
                labels = rule or [C.FUNCTIONAL]
                primary = primary_of(labels, r.statement)
            if primary not in labels:
                labels.insert(0, primary)
            else:
                labels.remove(primary)
                labels.insert(0, primary)
            r.categories = labels
            r.kind = ("business" if primary == C.BUSINESS else
                      "non_functional" if primary in NON_FUNCTIONAL or primary in (C.DATA, C.AUDIT) else
                      "functional")
            if r.id.startswith("TMP-"):
                old = r.id
                r.id = self.ctx.next_id(f"{ID_PREFIX[primary]}-KYC")
                r.history.append({"event": "id_assigned", "from": old})
        self.log("classified", "project", count=len(reqs))

    def _llm(self, reqs: list[Requirement]) -> dict[str, tuple[list[C], C]]:
        listing = "\n".join(f"{r.id}: {r.statement}" for r in reqs)
        data = self.ctx.llm.json(
            "classify_requirements",
            "Classify each KYC/onboarding requirement into ALL applicable categories (multi-label) and pick "
            "the single primary category. Categories: " + ", ".join(c.value for c in C) + ".",
            f"<untrusted_document id=\"requirements\">\n{listing}\n</untrusted_document>",
            _CLASSIFY_SCHEMA, effort="low")
        if not data:
            return {}
        valid = {r.id for r in reqs}
        return {i["id"]: ([C(c) for c in i["categories"]], C(i["primary"])) for i in data["items"] if i["id"] in valid}
