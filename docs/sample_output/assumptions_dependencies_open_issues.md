# Assumptions, dependencies & open issues

## Assumptions
- Applicable jurisdictions are IN; customers outside them are out of scope.
- Regulatory knowledge base version is current at the time of baseline; regulatory change triggers re-analysis.
- Verification and screening vendors provide contractual SLAs and audit rights.
- Derived control requirements are valid only after compliance confirms applicability.

## Dependencies
- Core banking system (account creation)
- Central KYC Records Registry
- DigiLocker document fetch
- Aadhaar e-KYC / authentication service
- Sanctions/PEP screening data provider
- Video KYC platform
- Liveness / face-match engine
- SMS/OTP gateway
- Legacy system: Core banking system (batch account creation)

## Open conflicts
- **CON-001** (contradiction, high): Opposing positions on manual review: OPS-KYC-001 (Priya (Product Owner)) vs REG-KYC-002 (Arjun (Chief Compliance Officer)).
- **CON-002** (contradiction, high): Opposing positions on control KYC-C17 (Human review of automated adverse decisions): OPS-KYC-001 (Priya (Product Owner)) vs SR-KYC-003 (Customer research panel).
- **CON-003** (contradiction, medium): Conflicting control KYC-C10 (Record retention) values: DAT-KYC-001 (Priya (Product Owner)) says [3.0] years, DAT-KYC-003 (Arjun (Chief Compliance Officer)) says [5.0] years.
- **CON-004** (contradiction, medium): Conflicting control KYC-C10 (Record retention) values: DAT-KYC-001 (Priya (Product Owner)) says [3.0] years, DAT-KYC-005 (Rahul (Operations Lead)) says [10.0] years.
- **CON-005** (overlap, low): DAT-KYC-003 and DAT-KYC-005 overlap on control KYC-C10 (Record retention), retention; consider merging.
- **CON-006** (regulatory, critical): DAT-KYC-001: Retention of 3 years is below the 5-year post-relationship minimum (FATF R.11 / PMLA / AMLD).

## Open questions
- **Q-001** → product_owner: Regarding PERF-KYC-002 ("We need the onboarding to be fast and user-friendly so that drop-off falls below 20%."): Vague term(s): fast, user-friendly. Replace with measurable criteria.
- **Q-002** → product_owner: Regarding INT-KYC-001 ("Customers should be able to fetch their identity details from DigiLocker or Aadhaar e-KYC instead of typing them."): Vague term(s): should be able to. Replace with measurable criteria.
- **Q-003** → product_owner: Regarding OPS-KYC-001 ("To keep it frictionless, onboarding should be approved automatically without manual review for every customer."): Vague term(s): frictionless. Replace with measurable criteria. Retention is stated without a period. State the retention period and its trigger (from account closure or from collection).
- **Q-004** → product_owner: Regarding DAT-KYC-001 ("The system shall delete customer data after 3 years to reduce storage cost."): Retention of 3 years is below the 5-year post-relationship minimum (FATF R.11 / PMLA / AMLD). Compliance/legal must confirm the applicable minimum.
- **Q-005** → security: Regarding SEC-KYC-001 ("Where video KYC is used, the session must include liveness check, geo-tagging and face match by a trained official, and the recording must be stored securely."): Handles uploaded identity media but states no protection (encryption, file validation, malware scan). Link to the corresponding security requirement or add the control.
- **Q-006** → security: Regarding SEC-KYC-006 ("The system shall keep a tamper-evident audit trail of every KYC decision and every access to customer documents."): Retention is stated without a period. State the retention period and its trigger (from account closure or from collection).
- **Q-007** → security: Regarding SEC-KYC-007 ("The system shall be secure and robust against attacks."): Vague term(s): secure, robust. Replace with measurable criteria.
- **Q-008** → security: Regarding INT-KYC-002 ("If the e-KYC vendor is down, applications should be queued and customers notified, not rejected."): Defines an external integration without transport or authentication security. Link to the corresponding security requirement or add the control.
- **Q-009** → security: Regarding INT-KYC-004 ("All integrations with vendors (e-KYC, video KYC, screening) must go through the API gateway."): Handles uploaded identity media but states no protection (encryption, file validation, malware scan). Link to the corresponding security requirement or add the control. Defines an external integration without transport or authentication security. Link to the corresponding security requirement or add the control.
- **Q-010** → security: Regarding SR-KYC-002 ("Customers expect the selfie step to work in low light and on older Android phones."): Handles uploaded identity media but states no protection (encryption, file validation, malware scan). Link to the corresponding security requirement or add the control.
- **Q-011** → customer: Regarding FR-KYC-007 ("Several customers said they do not want their data used for marketing without asking them."): Vague term(s): several. Replace with measurable criteria.
- **Q-012** → auditor: Regarding PRV-KYC-002 ("The new system must capture and store explicit consent before collecting personal data."): Retention is stated without a period. State the retention period and its trigger (from account closure or from collection).
- **Q-013** → product_owner: Opposing positions on manual review: OPS-KYC-001 (Priya (Product Owner)) vs REG-KYC-002 (Arjun (Chief Compliance Officer)). Which should prevail, or what is the agreed compromise?
- **Q-014** → product_owner: Opposing positions on control KYC-C17 (Human review of automated adverse decisions): OPS-KYC-001 (Priya (Product Owner)) vs SR-KYC-003 (Customer research panel). Which should prevail, or what is the agreed compromise?
- **Q-015** → product_owner: Conflicting control KYC-C10 (Record retention) values: DAT-KYC-001 (Priya (Product Owner)) says [3.0] years, DAT-KYC-003 (Arjun (Chief Compliance Officer)) says [5.0] years. Which should prevail, or what is the agreed compromise?
- **Q-016** → product_owner: Conflicting control KYC-C10 (Record retention) values: DAT-KYC-001 (Priya (Product Owner)) says [3.0] years, DAT-KYC-005 (Rahul (Operations Lead)) says [10.0] years. Which should prevail, or what is the agreed compromise?
- **Q-017** → product_owner: DAT-KYC-003 and DAT-KYC-005 overlap on control KYC-C10 (Record retention), retention; consider merging. Which should prevail, or what is the agreed compromise?
- **Q-018** → product_owner: DAT-KYC-001: Retention of 3 years is below the 5-year post-relationship minimum (FATF R.11 / PMLA / AMLD). Which should prevail, or what is the agreed compromise?
- **Q-019** → business_analyst: What should happen when something goes wrong, such as a vendor timeout, name mismatch, blurred document or partial sanctions match?
- **Q-020** → business_analyst: Are there account or transaction limits tied to the KYC level (for example minimum-KYC or small accounts) before full verification is complete?

## Other
- DOC-003: 1 sentence(s) quarantined for suspected prompt injection (override_instructions, approval_bypass); a human should review the source.