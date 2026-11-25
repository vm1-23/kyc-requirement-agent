"""Risk-analysis agent: business, technical, compliance, security and operational risk register."""
from __future__ import annotations

import re

from ..models import Level, Risk, StakeholderRole as R
from .base import Agent


def level_of(likelihood: int, impact: int) -> Level:
    s = likelihood * impact
    return Level.CRITICAL if s >= 16 else Level.HIGH if s >= 10 else Level.MEDIUM if s >= 5 else Level.LOW


class RiskAgent(Agent):
    name = "risk"
    description = "Builds the threat and risk register linked to requirements."

    def _add(self, title: str, category: str, desc: str, lik: int, imp: int, mitigation: str, owner: R, linked: list[str]) -> None:
        self.ctx.state.risks.append(Risk(id=self.ctx.next_id("RSK"), title=title, category=category, description=desc,
                                         likelihood=lik, impact=imp, level=level_of(lik, imp), mitigation=mitigation,
                                         owner=owner, linked_requirements=linked))

    def run(self) -> None:
        self.need("read:requirements", "read:compliance", "write:risks")
        st = self.ctx.state
        st.risks = []
        corpus = " ".join(r.statement for r in st.requirements).lower()

        gaps = [c for c in st.coverage if c.mandatory and c.status in ("gap", "derived")]
        if gaps:
            self._add("Mandatory KYC controls not requested by stakeholders", "compliance",
                      f"{len(gaps)} mandatory controls were absent from stakeholder input and were derived from the control catalogue: "
                      + ", ".join(g.control_id for g in gaps) + ".",
                      4, 5, "Compliance officer validates derived requirements before baseline; include them in sprint 0 scope.",
                      R.COMPLIANCE, [g.derived_requirement for g in gaps if g.derived_requirement])
        for c in st.conflicts:
            if c.type == "regulatory":
                self._add(f"Regulatory conflict: {c.requirement_ids[1]}", "compliance", c.detail, 4, 5,
                          "Legal/compliance interpretation and requirement rewrite before baseline.", R.LEGAL, [c.requirement_ids[0]])
            elif c.type == "contradiction":
                self._add(f"Stakeholder contradiction ({', '.join(c.requirement_ids)})", "business", c.detail, 4, 3 if c.severity != Level.HIGH else 4,
                          "Facilitated decision by product owner; record the resolution in the conflict log.", R.PRODUCT_OWNER, c.requirement_ids)
        for t in self.ctx.stats.get("threat_model", []):
            lik = 4 if t["level"] in ("high", "critical") else 3
            imp = 5 if t["level"] == "critical" else 4 if t["level"] == "high" else 3
            linked = t["covered_by"] or [r.id for r in st.requirements if t["id"] in r.controls]
            self._add(f"Threat {t['id']}", "security", f"{t['stride']}: {t['threat']}", lik, imp,
                      "Implement linked security requirements; verify with threat-model review, SAST/DAST and penetration test.",
                      R.SECURITY, linked)
        if re.search(r"core banking|cbs|legacy|mainframe|batch", corpus) or st.project.legacy_systems:
            self._add("Legacy core-banking integration", "technical",
                      "Account creation depends on legacy core banking interfaces (batch windows, limited APIs) that may break real-time onboarding targets.",
                      4, 4, "Spike in sprint 1; asynchronous account creation with status callbacks; contract tests against a CBS simulator.",
                      R.ARCHITECT, [r.id for r in st.requirements if re.search(r"core banking|cbs|legacy", r.statement.lower())])
        if re.search(r"vendor|third[- ]party|provider|digilocker|uidai|ckyc", corpus):
            self._add("Verification-vendor dependency", "operational",
                      "Outage or degradation of identity, screening or registry vendors stops onboarding.", 3, 4,
                      "Dual-vendor strategy or graceful queueing; vendor SLAs and exit plan; circuit breakers.", R.OPERATIONS,
                      [r.id for r in st.requirements if re.search(r"vendor|provider|registry|ckyc", r.statement.lower())])
        if re.search(r"biometric|selfie|face|video", corpus):
            self._add("Biometric data breach", "privacy", "Compromise of face images or templates is irreversible for customers.", 2, 5,
                      "Template protection, encryption with HSM keys, minimal retention, DPIA.", R.SECURITY,
                      [r.id for r in st.requirements if re.search(r"biometric|selfie|face|video", r.statement.lower())])
        ambiguous = [r.id for r in st.requirements if any(i.type in ("ambiguity", "untestable", "incompleteness") for i in r.quality_issues)]
        if ambiguous:
            self._add("Ambiguous or untestable requirements", "business",
                      f"{len(ambiguous)} requirements are vague or incomplete, which risks scope creep and failed UAT.",
                      4 if len(ambiguous) > 5 else 3, 3, "Resolve the clarification questions before the baseline gate.",
                      R.BUSINESS_ANALYST, ambiguous)
        if re.search(r"\b(auto-?approve|automated decision|straight[- ]through|without manual)", corpus):
            self._add("Automated adverse decisions without human review", "compliance",
                      "Fully automated rejection may breach automated-decision rules and fairness expectations.", 3, 4,
                      "Human review for rejections; reason codes; contest channel.", R.COMPLIANCE,
                      [r.id for r in st.requirements if re.search(r"auto-?approve|automated|straight[- ]through|without manual", r.statement.lower())])
        tl = st.project.timeline_months
        if tl and tl <= 4:
            self._add("Aggressive delivery timeline", "business", f"{tl}-month timeline for a regulated onboarding platform.", 4, 3,
                      "Phase scope (MVP for individuals first); keep compliance gates and do not compress them.", R.PROJECT_MANAGER, [])
        for r in st.requirements:
            linked = [x for x in st.risks if r.id in x.linked_requirements]
            if linked:
                worst = max(linked, key=lambda x: ["low", "medium", "high", "critical"].index(x.level.value))
                if ["low", "medium", "high", "critical"].index(worst.level.value) > ["low", "medium", "high", "critical"].index(r.risk_level.value):
                    r.risk_level = worst.level
        self.log("risk_register", "project", risks=len(st.risks))
