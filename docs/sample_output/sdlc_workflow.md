# SDLC recommendation: Hybrid Agile-DevSecOps

Hybrid Agile-DevSecOps ranks first (94.6%) ahead of Hybrid Agile-V-Model (90.4%). The project scores high on regulatory criticality, security risk, complexity, legacy dependence, documentation need and low on requirement stability, continuous delivery need. Engine reasons: Fits: regulatory criticality = 5 (ideal 5), security risk = 5 (ideal 5), change frequency = 4 (ideal 4); +5: high regulation with evolving requirements favours a regulated hybrid. This is a recommendation; the project manager, architect, security lead and compliance officer must jointly approve the final SDLC choice.

| Rank | Model | Suitability |
|---|---|---|
| 1 | Hybrid Agile-DevSecOps | 94.6% |
| 2 | Hybrid Agile-V-Model | 90.4% |
| 3 | Spiral | 80.0% |
| 4 | V-Model | 67.9% |
| 5 | DevSecOps | 66.7% |
| 6 | Agile (Scrum) | 61.7% |
| 7 | Waterfall | 19.3% |

## Decision factors

| Factor | Score | Rationale |
|---|---|---|
| requirement_stability | 1 | 5 contradictions, 10/50 ambiguous or incomplete requirements, 1 volatility cues. |
| regulatory_criticality | 5 | 54% of requirements are regulatory; 20 mandatory KYC controls apply. |
| security_risk | 5 | 30% security/privacy requirements; biometric processing=yes; restricted identity data in scope. |
| complexity | 5 | 4 external integrations, 13 requirement dimensions, 50 requirements. |
| system_size | 4 | 50 requirements across 7 sources. |
| legacy_dependence | 5 | 8 legacy-dependency signals; declared legacy systems: Core banking system (batch account creation). |
| change_frequency | 4 | 2 change-frequency cues; regulatory content changes with new circulars. |
| continuous_delivery_need | 2 | 0 continuous-delivery cues. |
| stakeholder_availability | 4 | 7 distinct stakeholders contributed input; 1 availability constraints mentioned. |
| documentation_need | 5 | Regulator inspection and audit evidence required; 4 audit/reporting requirements. |
| budget_schedule_pressure | 3 | Timeline 6 months; 0 deadline cues; budget flexibility medium. |
| formal_verification_need | 3 | 1 formal verification/certification cues; regulatory criticality 5. |
| failure_consequence | 4 | 58% high/critical-risk requirements; failures expose the firm to AML penalties and licence risk. |
| technical_uncertainty | 4 | 2 novel-technology cues; 20 open clarification questions. |

## Workflow

### Phase 1: Inception & regulatory scoping
- **Activities:** Confirm jurisdictions, customer segments and channels; ML/TF risk assessment of the digital onboarding channel (FATF R.15); DPIA kick-off for biometric and identity data; Stakeholder map and interview plan
- **Roles:** Product owner; Compliance officer; Business analyst; Project manager
- **Deliverables:** Project charter; Regulatory applicability register; Initial risk register
- **Security:** Data classification of KYC data elements
- **Testing:** 
- **Compliance checkpoints:** Applicable regulations confirmed by compliance
- **Entry:** Business case approved
- **Exit:** Jurisdictions and mandatory controls confirmed
- **Approval gate:** Scope & applicability approval (product owner + compliance)
- **Traceability:** Regulation -> control register created

### Phase 2: Requirements engineering & baseline
- **Activities:** Agent-assisted elicitation and extraction; Clarification of ambiguous or conflicting requirements; Compliance mapping and gap closure; Acceptance criteria definition
- **Roles:** Business analyst; Product owner; Compliance officer; Security architect
- **Deliverables:** SRS; User stories & use cases; Requirements traceability matrix; Compliance-control matrix
- **Security:** Security & privacy requirement derivation (threat model v0)
- **Testing:** Requirement testability review
- **Compliance checkpoints:** Mandatory control coverage: KYC-C01 Customer identification data capture, KYC-C02 Identity document verification against independent sources, KYC-C03 Liveness / presentation-attack detection and face match for remote onboarding, KYC-C04 Beneficial ownership identification for legal entities, KYC-C05 Sanctions screening at onboarding and on list updates, KYC-C06 PEP screening with enhanced due diligence, KYC-C07 Customer risk rating (risk-based approach), KYC-C08 Enhanced due diligence for high-risk customers
- **Entry:** Stakeholder inputs ingested and masked
- **Exit:** 0 open critical conflicts; 100% mandatory control coverage; All MUST requirements testable
- **Approval gate:** Requirements baseline approval (product owner, BA; compliance for regulatory items)
- **Traceability:** Stakeholder statement -> requirement -> regulation/control

### Phase 3: Architecture & secure design
- **Activities:** Target architecture (onboarding orchestration, vendor adapters, CBS integration); Data model with retention schedule; Threat modelling (STRIDE) of onboarding flows; Privacy by design review
- **Roles:** Solution architect; Security architect; Data protection officer
- **Deliverables:** Architecture decision records; Threat model; Interface specifications; DPIA
- **Security:** Threat modelling; Cryptography and key-management design (HSM); IAM / RBAC design
- **Testing:** Design review against OWASP ASVS L2
- **Compliance checkpoints:** DPIA sign-off; Retention schedule approved by compliance
- **Entry:** Requirements baseline approved
- **Exit:** Threat model with mitigations mapped to requirements
- **Approval gate:** Architecture & security design approval (architect + security)
- **Traceability:** Requirement -> design element -> threat mitigation

### Phase 4: DevSecOps pipeline & compliance-as-code
- **Activities:** Pipeline with policy gates (OPA/conftest); Infrastructure as code with security baselines; Automated evidence collection for audits
- **Roles:** DevOps engineer; Security engineer
- **Deliverables:** CI/CD pipeline; Policy-as-code rules; Evidence store
- **Security:** DAST against staging; Container/IaC scanning; Secrets management
- **Testing:** Automated regression; Performance smoke tests
- **Compliance checkpoints:** Pipeline blocks release if a mandatory control test fails
- **Entry:** Architecture approved
- **Exit:** All gates automated and evidenced
- **Approval gate:** Pipeline readiness (security)
- **Traceability:** Build -> test evidence -> control

### Phase 5: Iterative build (sprints)
- **Activities:** Sprint planning from prioritised backlog; Implement user stories with acceptance tests; Sprint review with business and compliance
- **Roles:** Scrum team; Product owner; Compliance champion
- **Deliverables:** Working increment; Updated RTM; Definition-of-done evidence
- **Security:** SAST and secret scanning on every commit; Software composition analysis (SCA); Secure code review for PII paths; Pipeline compliance gates on every merge
- **Testing:** Unit and contract tests (vendor/CBS simulators); Automated acceptance tests
- **Compliance checkpoints:** Compliance champion reviews stories touching KYC controls
- **Entry:** Stories meet definition of ready
- **Exit:** Definition of done incl. security checks passed
- **Approval gate:** Sprint review acceptance (product owner)
- **Traceability:** Story -> commit -> test case

### Phase 6: System verification & validation
- **Activities:** System integration testing with vendors, CKYCR and CBS; Transaction-integrity and data-reconciliation tests; Performance & resilience testing at peak load; UAT with operations and compliance
- **Roles:** QA lead; Operations; Compliance officer; Security tester
- **Deliverables:** Test summary report; Penetration-test report; Liveness/PAD test evidence; UAT sign-off
- **Security:** Independent penetration test; PAD testing (ISO/IEC 30107-3); Access-control verification
- **Testing:** SIT; Transaction-integrity tests; Load/soak tests; DR failover test; Bias testing of face-match and risk models
- **Compliance checkpoints:** High-risk requirements verified: PERF-KYC-002, INT-KYC-001, OPS-KYC-001, DAT-KYC-001, REG-KYC-002, DAT-KYC-003, DAT-KYC-004, SEC-KYC-001, SEC-KYC-002, SEC-KYC-004; Control testing evidence for every mandatory KYC control
- **Entry:** Feature complete; Test environments with masked data
- **Exit:** No open critical/high defects; All MUST acceptance criteria passed
- **Approval gate:** Verification & UAT sign-off (QA, operations, compliance)
- **Traceability:** Requirement -> test case -> result (RTM complete)

### Phase 7: Release & production readiness
- **Activities:** Production readiness review; Runbooks and monitoring dashboards; Phased rollout (pilot cohort, then general availability)
- **Roles:** Project manager; Operations; Security; Compliance officer
- **Deliverables:** Go-live checklist; Runbooks; Rollback plan
- **Security:** Security sign-off; Key ceremony / HSM configuration check
- **Testing:** Smoke tests in production; Monitoring alert tests
- **Compliance checkpoints:** Compliance approval before deployment; Regulatory notification if required
- **Entry:** Verification sign-off
- **Exit:** Go-live approved
- **Approval gate:** Production-readiness approval (PM, security, compliance, operations; unanimous)
- **Traceability:** Release notes -> requirement IDs

### Phase 8: Operate, monitor & re-certify
- **Activities:** Monitor onboarding KPIs, false positives and drop-off; Model drift and bias monitoring; Regulatory change watch -> change requests
- **Roles:** Operations; Model risk management; Compliance officer
- **Deliverables:** MIS and regulator reports; Periodic control-testing reports
- **Security:** SIEM monitoring; Quarterly access recertification; Annual penetration test
- **Testing:** Periodic control testing
- **Compliance checkpoints:** Annual KYC policy review; Audit evidence retained per retention schedule
- **Entry:** Go-live
- **Exit:** Continuous
- **Approval gate:** Change approval for regulatory updates (compliance + product owner)
- **Traceability:** Regulatory change -> impacted requirements -> regression tests