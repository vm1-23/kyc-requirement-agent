"""Security & privacy agent: threat-driven derivation of security and privacy requirements.

A lightweight STRIDE pass over the KYC assets mentioned in the requirements. Every
trigger that fires (asset or feature present) and has no requirement covering its
mitigation yields a derived requirement for the security team to approve.
"""
from __future__ import annotations

import re

from ..models import ApprovalStatus, Category as C, Evidence, Level, Priority, Requirement
from .base import Agent

# (id, trigger regex over all requirement text, coverage regex, STRIDE, threat, derived requirement, categories, kb_refs, level)
THREATS = [
    ("T-DOC-UPLOAD", r"upload|document image|scan|photo", r"malware|file (type|size)|content[- ]type",
     "Tampering / Elevation", "Malicious file uploaded as an identity document.",
     "The system shall validate uploaded identity files by type, size and content signature, scan them for malware before processing, and store them outside the web root.",
     [C.SECURITY], ["OWASP-ASVS"], Level.HIGH),
    ("T-SPOOF-BIO", r"selfie|liveness|face|video|biometric", r"liveness|presentation attack|deepfake|injection attack",
     "Spoofing", "Presentation or injection attacks (photos, masks, deepfakes, virtual cameras) during remote verification.",
     "The system shall detect presentation and video-injection attacks (ISO/IEC 30107-3 tested, APCER ≤ 5% at BPCER ≤ 5%) and block virtual-camera sources during remote verification.",
     [C.SECURITY, C.REGULATORY], ["ISO-30107-3", "IN-RBI-VCIP"], Level.CRITICAL),
    ("T-BIO-PRIV", r"selfie|face|biometric|video", r"biometric (consent|template)|template protection|explicit consent",
     "Information disclosure", "Biometric data misuse or over-retention.",
     "The system shall obtain explicit, separate consent for biometric processing, store only protected biometric templates (never raw images beyond the regulatory evidence requirement), and delete them at the end of the retention period.",
     [C.PRIVACY, C.SECURITY], ["EU-GDPR-9", "IN-DPDP"], Level.HIGH),
    ("T-API", r"api|integrat|vendor|third[- ]party|registry|core banking", r"mtls|mutual tls|signed request|oauth|api (key|authentication)",
     "Spoofing / Tampering", "Unauthenticated or tampered calls to identity, screening and core-banking APIs.",
     "The system shall authenticate all service-to-service calls with mutual TLS or OAuth 2.0 client credentials, sign and validate response payloads from verification vendors, and rate-limit public onboarding APIs.",
     [C.SECURITY, C.INTEGRATION], ["OWASP-ASVS", "ISO-27001-A"], Level.HIGH),
    ("T-STAFF", r"officer|staff|back-?office|agent|reviewer|analyst", r"rbac|role-based|least privilege|access recertification|privileged",
     "Elevation of privilege / Repudiation", "Insider misuse of customer identity data.",
     "The system shall restrict back-office access to KYC data by role, display national identifiers masked by default, log every unmask/view of restricted data, and require just-in-time approval for privileged access.",
     [C.SECURITY, C.PRIVACY, C.AUDIT], ["POL-ORG-SEC-03", "ISO-27001-A"], Level.HIGH),
    ("T-ACCOUNT-TAKEOVER", r"otp|login|account|mobile|app", r"rate[- ]limit|otp (expiry|attempt)|sim[- ]swap|device binding",
     "Spoofing", "OTP brute force, SIM-swap and account-takeover during onboarding.",
     "The system shall limit OTP validity to 5 minutes and 3 attempts, bind the onboarding session to the device, and apply SIM-swap / device-risk checks before account activation.",
     [C.SECURITY], ["NIST-800-63B"], Level.HIGH),
    ("T-SYNTHETIC", r"onboard|account opening|application", r"synthetic identit|fraud (score|check)|velocity|device fingerprint",
     "Spoofing", "Synthetic identities and mule-account onboarding at scale.",
     "The system shall apply fraud checks at onboarding (device fingerprint, velocity of applications per device/address/identifier, and synthetic-identity signals) and refer high-scoring applications for review.",
     [C.SECURITY, C.FUNCTIONAL], ["FATF-R15"], Level.HIGH),
    ("T-DOS", r"onboard|api|portal|app", r"rate[- ]limit|ddos|throttl|waf",
     "Denial of service", "Volumetric attacks exhausting verification-vendor quotas or onboarding capacity.",
     "The system shall protect onboarding endpoints with a WAF, per-client throttling and vendor-quota circuit breakers.",
     [C.SECURITY, C.AVAILABILITY], ["OWASP-ASVS"], Level.MEDIUM),
    ("T-AI", r"\bai\b|machine learning|model|automated decision|auto-?approve|score", r"bias|drift|model validation|explainab",
     "Repudiation / Fairness", "Opaque or biased automated KYC decisions.",
     "Automated risk-scoring and face-match models shall be validated before deployment, monitored monthly for drift and demographic bias, and every automated decision shall store the model version and top contributing factors.",
     [C.REGULATORY, C.OPERATIONAL], ["POL-ORG-AI-04", "EU-GDPR-22"], Level.MEDIUM),
    ("T-NONPROD", r"test|uat|staging|analytics|report", r"mask(ed)? in non-?prod|synthetic test data|anonymi",
     "Information disclosure", "Real KYC data leaking into test and analytics environments.",
     "The system shall use synthetic or irreversibly masked data in non-production and analytics environments; production KYC data shall not be copied to lower environments.",
     [C.PRIVACY, C.DATA], ["POL-ORG-DATA-02"], Level.MEDIUM),
]


class SecurityPrivacyAgent(Agent):
    name = "security_privacy"
    description = "Identifies cybersecurity and privacy requirements via threat modelling."

    def run(self) -> None:
        self.need("read:requirements", "read:kb", "write:requirements")
        st, kb = self.ctx.state, self.ctx.kb
        corpus = " ".join(r.statement for r in st.requirements).lower()
        existing = {r.controls[0] for r in st.requirements if r.origin == "derived_control" and r.controls}
        threats = []
        for tid, trig, cover, stride, threat, req, cats, refs, lvl in THREATS:
            if not re.search(trig, corpus):
                continue
            covered_by = [r.id for r in st.requirements if re.search(cover, r.statement.lower())]
            threats.append({"id": tid, "stride": stride, "threat": threat, "level": lvl.value, "covered_by": covered_by})
            if covered_by or tid in existing:
                continue
            cites = [kb.get(x).citation() for x in refs if kb.get(x) and kb.applicable(kb.get(x), st.project.jurisdictions)]
            from .classification import ID_PREFIX
            r = Requirement(
                id=self.ctx.next_id(f"{ID_PREFIX[cats[0]]}-KYC"), statement=req, categories=list(cats),
                kind="non_functional", priority=Priority.MUST if lvl in (Level.HIGH, Level.CRITICAL) else Priority.SHOULD,
                regulations=cites, controls=[tid], risk_level=lvl, origin="derived_control", confidence=0.7,
                evidence=[Evidence(doc_id=f"threat-model:{tid}", excerpt=threat)],
                business_justification=f"Threat model ({stride}): {threat}", status=ApprovalStatus.PENDING_APPROVAL)
            st.requirements.append(r)
            self.log("derived_security_requirement", r.id, threat=tid)
        self.ctx.stats["threat_model"] = threats
        # Raise risk level on existing requirements that handle restricted data.
        for r in st.requirements:
            low = r.statement.lower()
            if re.search(r"biometric|aadhaar|<aadhaar|<pan|passport|national id|identity document|video", low) and r.risk_level == Level.LOW:
                r.risk_level = Level.HIGH
            elif C.SECURITY in r.categories and r.risk_level == Level.LOW:
                r.risk_level = Level.MEDIUM
            if r.controls and r.risk_level == Level.LOW:
                r.risk_level = Level.MEDIUM
        self.log("threat_model", "project", threats=len(threats))
