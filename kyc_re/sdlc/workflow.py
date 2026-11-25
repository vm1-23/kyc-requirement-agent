"""Project-specific SDLC workflow generation.

Phase templates are shared across models and then specialised: each selected model
has its own phase sequence, and KYC-specific security activities, compliance
checkpoints and approval gates are injected from the analysed requirements.
"""
from __future__ import annotations

from ..models import ProjectState, SDLCPhase

P = SDLCPhase


def _kyc_controls(st: ProjectState) -> list[str]:
    return [f"{c.control_id} {c.title}" for c in st.coverage if c.mandatory][:8]


def _phases(st: ProjectState) -> dict[str, SDLCPhase]:
    ctrl = _kyc_controls(st)
    high_risk = [r.id for r in st.requirements if r.risk_level.value in ("high", "critical")][:10]
    return {
        "inception": P(
            name="Inception & regulatory scoping",
            activities=["Confirm jurisdictions, customer segments and channels", "ML/TF risk assessment of the digital onboarding channel (FATF R.15)",
                        "DPIA kick-off for biometric and identity data", "Stakeholder map and interview plan"],
            roles=["Product owner", "Compliance officer", "Business analyst", "Project manager"],
            deliverables=["Project charter", "Regulatory applicability register", "Initial risk register"],
            security_activities=["Data classification of KYC data elements"],
            testing=[], compliance_checkpoints=["Applicable regulations confirmed by compliance"],
            approval_gate="Scope & applicability approval (product owner + compliance)",
            entry_criteria=["Business case approved"], exit_criteria=["Jurisdictions and mandatory controls confirmed"],
            traceability=["Regulation -> control register created"]),
        "requirements": P(
            name="Requirements engineering & baseline",
            activities=["Agent-assisted elicitation and extraction", "Clarification of ambiguous or conflicting requirements",
                        "Compliance mapping and gap closure", "Acceptance criteria definition"],
            roles=["Business analyst", "Product owner", "Compliance officer", "Security architect"],
            deliverables=["SRS", "User stories & use cases", "Requirements traceability matrix", "Compliance-control matrix"],
            security_activities=["Security & privacy requirement derivation (threat model v0)"],
            testing=["Requirement testability review"],
            compliance_checkpoints=[f"Mandatory control coverage: {', '.join(ctrl)}" if ctrl else "Mandatory control coverage"],
            approval_gate="Requirements baseline approval (product owner, BA; compliance for regulatory items)",
            entry_criteria=["Stakeholder inputs ingested and masked"],
            exit_criteria=["0 open critical conflicts", "100% mandatory control coverage", "All MUST requirements testable"],
            traceability=["Stakeholder statement -> requirement -> regulation/control"]),
        "design": P(
            name="Architecture & secure design",
            activities=["Target architecture (onboarding orchestration, vendor adapters, CBS integration)", "Data model with retention schedule",
                        "Threat modelling (STRIDE) of onboarding flows", "Privacy by design review"],
            roles=["Solution architect", "Security architect", "Data protection officer"],
            deliverables=["Architecture decision records", "Threat model", "Interface specifications", "DPIA"],
            security_activities=["Threat modelling", "Cryptography and key-management design (HSM)", "IAM / RBAC design"],
            testing=["Design review against OWASP ASVS L2"],
            compliance_checkpoints=["DPIA sign-off", "Retention schedule approved by compliance"],
            approval_gate="Architecture & security design approval (architect + security)",
            entry_criteria=["Requirements baseline approved"], exit_criteria=["Threat model with mitigations mapped to requirements"],
            traceability=["Requirement -> design element -> threat mitigation"]),
        "iteration": P(
            name="Iterative build (sprints)",
            activities=["Sprint planning from prioritised backlog", "Implement user stories with acceptance tests", "Sprint review with business and compliance"],
            roles=["Scrum team", "Product owner", "Compliance champion"],
            deliverables=["Working increment", "Updated RTM", "Definition-of-done evidence"],
            security_activities=["SAST and secret scanning on every commit", "Software composition analysis (SCA)", "Secure code review for PII paths"],
            testing=["Unit and contract tests (vendor/CBS simulators)", "Automated acceptance tests"],
            compliance_checkpoints=["Compliance champion reviews stories touching KYC controls"],
            approval_gate="Sprint review acceptance (product owner)",
            entry_criteria=["Stories meet definition of ready"], exit_criteria=["Definition of done incl. security checks passed"],
            traceability=["Story -> commit -> test case"]),
        "pipeline": P(
            name="DevSecOps pipeline & compliance-as-code",
            activities=["Pipeline with policy gates (OPA/conftest)", "Infrastructure as code with security baselines", "Automated evidence collection for audits"],
            roles=["DevOps engineer", "Security engineer"],
            deliverables=["CI/CD pipeline", "Policy-as-code rules", "Evidence store"],
            security_activities=["DAST against staging", "Container/IaC scanning", "Secrets management"],
            testing=["Automated regression", "Performance smoke tests"],
            compliance_checkpoints=["Pipeline blocks release if a mandatory control test fails"],
            approval_gate="Pipeline readiness (security)",
            entry_criteria=["Architecture approved"], exit_criteria=["All gates automated and evidenced"],
            traceability=["Build -> test evidence -> control"]),
        "verification": P(
            name="System verification & validation",
            activities=["System integration testing with vendors, CKYCR and CBS", "Transaction-integrity and data-reconciliation tests",
                        "Performance & resilience testing at peak load", "UAT with operations and compliance"],
            roles=["QA lead", "Operations", "Compliance officer", "Security tester"],
            deliverables=["Test summary report", "Penetration-test report", "Liveness/PAD test evidence", "UAT sign-off"],
            security_activities=["Independent penetration test", "PAD testing (ISO/IEC 30107-3)", "Access-control verification"],
            testing=["SIT", "Transaction-integrity tests", "Load/soak tests", "DR failover test", "Bias testing of face-match and risk models"],
            compliance_checkpoints=[f"High-risk requirements verified: {', '.join(high_risk)}" if high_risk else "High-risk requirements verified",
                                    "Control testing evidence for every mandatory KYC control"],
            approval_gate="Verification & UAT sign-off (QA, operations, compliance)",
            entry_criteria=["Feature complete", "Test environments with masked data"],
            exit_criteria=["No open critical/high defects", "All MUST acceptance criteria passed"],
            traceability=["Requirement -> test case -> result (RTM complete)"]),
        "release": P(
            name="Release & production readiness",
            activities=["Production readiness review", "Runbooks and monitoring dashboards", "Phased rollout (pilot cohort, then general availability)"],
            roles=["Project manager", "Operations", "Security", "Compliance officer"],
            deliverables=["Go-live checklist", "Runbooks", "Rollback plan"],
            security_activities=["Security sign-off", "Key ceremony / HSM configuration check"],
            testing=["Smoke tests in production", "Monitoring alert tests"],
            compliance_checkpoints=["Compliance approval before deployment", "Regulatory notification if required"],
            approval_gate="Production-readiness approval (PM, security, compliance, operations; unanimous)",
            entry_criteria=["Verification sign-off"], exit_criteria=["Go-live approved"],
            traceability=["Release notes -> requirement IDs"]),
        "operate": P(
            name="Operate, monitor & re-certify",
            activities=["Monitor onboarding KPIs, false positives and drop-off", "Model drift and bias monitoring", "Regulatory change watch -> change requests"],
            roles=["Operations", "Model risk management", "Compliance officer"],
            deliverables=["MIS and regulator reports", "Periodic control-testing reports"],
            security_activities=["SIEM monitoring", "Quarterly access recertification", "Annual penetration test"],
            testing=["Periodic control testing"],
            compliance_checkpoints=["Annual KYC policy review", "Audit evidence retained per retention schedule"],
            approval_gate="Change approval for regulatory updates (compliance + product owner)",
            entry_criteria=["Go-live"], exit_criteria=["Continuous"],
            traceability=["Regulatory change -> impacted requirements -> regression tests"]),
        "risk_analysis": P(
            name="Risk analysis & prototyping cycle",
            activities=["Identify top technical risks (liveness accuracy, CBS latency, vendor reliability)", "Build throw-away prototypes / spikes", "Evaluate alternatives and decide"],
            roles=["Architect", "Risk manager", "Security architect"],
            deliverables=["Risk-resolution report", "Prototype results"],
            security_activities=["Security spike for biometric pipeline"],
            testing=["Prototype benchmark tests"],
            compliance_checkpoints=["Compliance review of prototype data handling"],
            approval_gate="Cycle go/no-go (architect + risk)",
            entry_criteria=["Objectives for the cycle"], exit_criteria=["Top risks resolved or accepted"],
            traceability=["Risk -> spike -> decision record"]),
        "implementation": P(
            name="Implementation",
            activities=["Implement per approved design", "Code reviews"],
            roles=["Development team"], deliverables=["Source code", "Unit tests"],
            security_activities=["SAST", "Secure code review"], testing=["Unit tests"],
            compliance_checkpoints=["Code touching PII reviewed by security"],
            approval_gate="Code complete (tech lead)", entry_criteria=["Design approved"], exit_criteria=["Unit tests pass"],
            traceability=["Design -> code module"]),
    }


SEQUENCES = {
    "Waterfall": ["inception", "requirements", "design", "implementation", "verification", "release", "operate"],
    "V-Model": ["inception", "requirements", "design", "implementation", "verification", "release", "operate"],
    "Spiral": ["inception", "risk_analysis", "requirements", "design", "iteration", "verification", "release", "operate"],
    "Agile (Scrum)": ["inception", "requirements", "iteration", "verification", "release", "operate"],
    "DevSecOps": ["inception", "requirements", "pipeline", "iteration", "verification", "release", "operate"],
    "Hybrid Agile-V-Model": ["inception", "requirements", "design", "iteration", "verification", "release", "operate"],
    "Hybrid Agile-DevSecOps": ["inception", "requirements", "design", "pipeline", "iteration", "verification", "release", "operate"],
}


def build_workflow(model: str, st: ProjectState) -> list[SDLCPhase]:
    phases = _phases(st)
    seq = [phases[k].model_copy(deep=True) for k in SEQUENCES.get(model, SEQUENCES["Hybrid Agile-DevSecOps"])]
    if model in ("V-Model", "Hybrid Agile-V-Model"):
        for p in seq:
            if p.name.startswith("Requirements"):
                p.testing.append("Acceptance test plan derived from requirements (V: left <-> right pairing)")
            if p.name.startswith("Architecture"):
                p.testing.append("System/integration test plan derived from design")
    if model.startswith("Hybrid") or model == "DevSecOps":
        for p in seq:
            if p.name.startswith("Iterative"):
                p.security_activities.append("Pipeline compliance gates on every merge")
    return seq
