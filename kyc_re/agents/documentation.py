"""Documentation agent: user stories, use cases and artefact generation."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from ..models import Category as C, Requirement, StakeholderRole as R
from .base import Agent

ROLE_PERSONA = {
    R.CUSTOMER: "prospective customer", R.COMPLIANCE: "compliance officer", R.SECURITY: "security officer",
    R.OPERATIONS: "KYC operations officer", R.RISK: "risk manager", R.AUDITOR: "internal auditor",
    R.PRODUCT_OWNER: "product owner", R.ARCHITECT: "solution architect", R.LEGAL: "legal counsel",
}

USE_CASES = [
    {"id": "UC-01", "name": "Individual digital onboarding", "trigger": r"onboard|account opening|sign-?up|individual",
     "actor": "Prospective customer", "link": r"onboard|capture|document|otp|consent|account|upload|verify",
     "pre": ["Customer has a supported identity document and mobile number", "Consent notice displayed"],
     "main": ["Customer starts onboarding and accepts the privacy notice and consent", "System verifies mobile number via OTP",
              "Customer provides identity details or fetches them from an e-KYC source", "System verifies document authenticity and data",
              "Customer completes liveness check and face match", "System screens against sanctions and PEP lists",
              "System calculates customer risk rating", "Low/medium-risk customer is approved; account is created in core banking",
              "System uploads KYC record to the registry and records the audit trail"],
     "alt": ["4a. Document verification fails: customer may retry once with an alternate document, then the case is referred to manual review",
             "6a. Potential sanctions/PEP match: onboarding paused; alert routed to compliance (no tipping-off)",
             "7a. High-risk rating: routed to EDD (UC-04)", "8a. Core banking unavailable: application queued and the customer notified"],
     "post": ["Customer record, evidence and decision are retained per the retention schedule"]},
    {"id": "UC-02", "name": "Video-based customer identification (V-CIP)", "trigger": r"video|v-?cip",
     "actor": "Prospective customer; KYC official", "link": r"video|v-?cip|liveness|geo|official|recording",
     "pre": ["Customer consents to the video session", "Customer is located within the permitted geography"],
     "main": ["Customer joins the live video session with a trained official", "System captures geo-location and checks liveness",
              "Official verifies the document live and the system performs a face match", "Official asks randomised questions",
              "Session recording is stored securely with timestamp", "Official records the decision; maker-checker review completes it"],
     "alt": ["2a. Location outside permitted area or liveness fails: session terminated", "3a. Poor video quality: reschedule"],
     "post": ["Recording and evidence are retained and auditable"]},
    {"id": "UC-03", "name": "Legal-entity onboarding with beneficial ownership", "trigger": r"legal entit|company|corporate|sme|beneficial own|ubo",
     "actor": "Authorised signatory; KYC operations officer", "link": r"entity|company|beneficial|ubo|ownership|director|signator",
     "pre": ["Entity registration documents available"],
     "main": ["Signatory submits entity documents", "System verifies the entity against the company registry",
              "System captures ownership structure and identifies beneficial owners above threshold",
              "Each beneficial owner is identified and verified (UC-01 steps 3-6)", "System risk-rates the entity"],
     "alt": ["3a. Complex or opaque ownership: refer to EDD"], "post": ["UBO records linked to the entity"]},
    {"id": "UC-04", "name": "Screening alert handling & enhanced due diligence", "trigger": r"sanction|pep|screen|edd|enhanced|high[- ]risk",
     "actor": "Compliance analyst; senior compliance officer", "link": r"sanction|pep|screen|edd|enhanced|high[- ]risk|source of (wealth|funds)|approv",
     "pre": ["Alert or high-risk rating generated"],
     "main": ["Analyst reviews the match details and evidence", "Analyst discounts false positives with a recorded rationale",
              "For true or likely matches, EDD collects source of funds and wealth", "Senior compliance officer approves or declines the relationship",
              "Decision and rationale recorded in the audit trail"],
     "alt": ["2a. Confirmed sanctions match: block, freeze per law, report", "4a. Suspicion formed: escalate STR (UC-07)"],
     "post": ["Alert closed with an audit trail"]},
    {"id": "UC-05", "name": "Periodic re-KYC", "trigger": r"re-?kyc|periodic|ongoing|refresh",
     "actor": "Existing customer; system scheduler", "link": r"re-?kyc|periodic|refresh|expir|update",
     "pre": ["Re-KYC due date reached for the customer's risk tier"],
     "main": ["System notifies the customer ahead of the due date", "Customer confirms or updates details",
              "System re-verifies changed documents and re-screens", "Risk rating recalculated"],
     "alt": ["3a. Customer does not respond: restrictions applied per policy after the grace period"], "post": ["Next due date scheduled"]},
    {"id": "UC-06", "name": "Manual review and override (maker-checker)", "trigger": r"manual|review|override|officer|maker",
     "actor": "KYC operations officer (maker); supervisor (checker)", "link": r"manual|review|override|maker|checker|queue|case",
     "pre": ["Case referred from automated flow"],
     "main": ["Maker reviews evidence and proposes a decision with reason", "Checker approves or returns the decision",
              "System applies the decision and notifies the customer with a reason code"],
     "alt": ["2a. Checker rejects: case returned to maker"], "post": ["Override audit-logged"]},
    {"id": "UC-07", "name": "Suspicious activity escalation", "trigger": r"suspicious|str|sar|fiu",
     "actor": "Onboarding staff; principal officer/MLRO", "link": r"suspicious|str|sar|fiu|escalat",
     "pre": ["Staff forms a suspicion during onboarding"],
     "main": ["Staff raises an internal suspicious activity report", "Principal officer reviews and decides to file",
              "System generates the STR in the FIU format within the deadline"],
     "alt": ["2a. Not filed: rationale recorded"], "post": ["Customer not tipped off; records retained"]},
]


def user_story(r: Requirement) -> dict[str, str]:
    core = re.sub(r"^(The system shall|The system should|The system must)\s+", "", r.statement.rstrip("."), flags=re.I)
    low = core.lower()
    if r.source_role in ROLE_PERSONA and r.source_role != R.PRODUCT_OWNER:
        persona = ROLE_PERSONA[r.source_role]
    elif re.search(r"officer|staff|analyst|back-?office|review queue|maker|checker", low):
        persona = "KYC operations officer"
    elif C.REGULATORY in r.categories or C.AUDIT in r.categories:
        persona = "compliance officer"
    elif C.SECURITY in r.categories:
        persona = "security officer"
    else:
        persona = "prospective customer"
    benefit = {
        C.REGULATORY: "the bank meets its KYC/AML obligations", C.SECURITY: "customer identities and data are protected",
        C.PRIVACY: "customers' personal data is handled lawfully", C.PERFORMANCE: "onboarding feels responsive",
        C.AVAILABILITY: "customers can onboard at any time", C.USABILITY: "customers complete onboarding without help",
        C.AUDIT: "every decision can be evidenced to auditors and regulators", C.DATA: "records are kept exactly as long as required",
        C.INTEGRATION: "onboarding works end-to-end with existing systems", C.OPERATIONAL: "operations can run the process efficiently",
    }.get(r.categories[0] if r.categories else C.FUNCTIONAL, "onboarding is completed correctly")
    return {"id": f"US-{r.id}", "requirement_id": r.id,
            "story": f"As a {persona}, I want the system to {core[0].lower() + core[1:] if core else core}, so that {benefit}.",
            "acceptance_criteria": r.acceptance_criteria}


class DocumentationAgent(Agent):
    name = "documentation"
    description = "Generates SRS, user stories, use cases, RTM, compliance matrix, risk register and SDLC workflow."

    def stories(self) -> list[dict[str, Any]]:
        return [user_story(r) for r in self.ctx.state.requirements if r.status.value != "rejected"]

    def use_cases(self) -> list[dict[str, Any]]:
        st = self.ctx.state
        corpus = " ".join(r.statement for r in st.requirements).lower()
        out = []
        for uc in USE_CASES:
            if re.search(uc["trigger"], corpus):
                linked = [r.id for r in st.requirements if re.search(uc["link"], r.statement.lower())]
                out.append({**{k: v for k, v in uc.items() if k not in ("trigger", "link")}, "requirements": linked})
        return out

    def run(self, out_dir: str | Path | None = None) -> dict[str, str]:
        self.need("read:requirements", "read:compliance", "read:risks", "read:sdlc", "write:artefacts")
        if out_dir is None:
            return {}
        from ..artefacts import writers

        paths = writers.write_all(self.ctx, Path(out_dir), self.stories(), self.use_cases())
        self.log("artefacts_generated", "project", files=sorted(paths))
        return paths
