# User stories

## US-USA-KYC-001

As a prospective customer, I want the system to we want customers to open an account fully digitally on the mobile app, so that customers complete onboarding without help.

**Acceptance criteria**

- Given a valid onboarding application, when the system is required to We want customers to open an account fully digitally on the mobile app, then it does so and records the outcome.
- Given invalid or incomplete input, when the step is attempted, then the system rejects it with a specific error and no partial record is created.

## US-PERF-KYC-001

As a prospective customer, I want the system to the onboarding journey must be completed within 5 minutes for a normal customer, so that onboarding feels responsive.

**Acceptance criteria**

- Given peak production load, when the step is executed, then it completes within 5 minutes at the 95th percentile.

## US-PERF-KYC-002

As a prospective customer, I want the system to we need the onboarding to be fast and user-friendly so that drop-off falls below 20%, so that onboarding feels responsive.

**Acceptance criteria**

- Given peak production load, when the step is executed, then it completes within 20% at the 95th percentile.

## US-INT-KYC-001

As a compliance officer, I want the system to customers should be able to fetch their identity details from DigiLocker or Aadhaar e-KYC instead of typing them, so that onboarding works end-to-end with existing systems.

**Acceptance criteria**

- Given a valid onboarding application, when the system is required to Customers should be able to fetch their identity details from DigiLocker or Aadhaar e-KYC instead of typing them, then it does so and records the outcome.
- Given invalid or incomplete input, when the step is attempted, then the system rejects it with a specific error and no partial record is created.

## US-OPS-KYC-001

As a compliance officer, I want the system to to keep it frictionless, onboarding should be approved automatically without manual review for every customer, so that operations can run the process efficiently.

**Acceptance criteria**

- Given a valid onboarding application, when the system is required to To keep it frictionless, onboarding should be approved automatically without manual review for every customer, then it does so and records the outcome.
- Given invalid or incomplete input, when the step is attempted, then the system rejects it with a specific error and no partial record is created.

## US-DAT-KYC-001

As a compliance officer, I want the system to delete customer data after 3 years to reduce storage cost, so that records are kept exactly as long as required.

**Acceptance criteria**

- Given a closed relationship, when the retention period elapses, then the records are purged and the purge is logged; before that, records are retrievable within 1 business day.

## US-FR-KYC-001

As a prospective customer, I want the system to customers must be able to save a partially completed application and resume it within 7 days, so that onboarding is completed correctly.

**Acceptance criteria**

- Given a valid onboarding application, when the system is required to Customers must be able to save a partially completed application and resume it within 7 days, then it does so and records the outcome.
- Given invalid or incomplete input, when the step is attempted, then the system rejects it with a specific error and no partial record is created.

## US-FR-KYC-002

As a prospective customer, I want the system to support English and Hindi in phase 1, so that onboarding is completed correctly.

**Acceptance criteria**

- Given a valid onboarding application, when the system is required to support English and Hindi in phase 1, then it does so and records the outcome.
- Given invalid or incomplete input, when the step is attempted, then the system rejects it with a specific error and no partial record is created.

## US-BR-KYC-001

As a prospective customer, I want the system to releases should happen every two weeks because competitors change their journeys frequently, so that onboarding is completed correctly.

**Acceptance criteria**

- Given a valid onboarding application, when the system is required to Releases should happen every two weeks because competitors change their journeys frequently, then it does so and records the outcome.
- Given invalid or incomplete input, when the step is attempted, then the system rejects it with a specific error and no partial record is created.

## US-FR-KYC-003

As a compliance officer, I want the system to screen every applicant against UN, domestic and internal sanctions lists before the account is opened, so that onboarding is completed correctly.

**Acceptance criteria**

- Given a valid onboarding application, when the system is required to screen every applicant against UN, domestic and internal sanctions lists before the account is opened, then it does so and records the outcome.
- Given an internal audit sample, when the control evidence is reviewed, then 100% of sampled cases show the control was applied with traceable evidence.
- Given invalid or incomplete input, when the step is attempted, then the system rejects it with a specific error and no partial record is created.

## US-REG-KYC-001

As a compliance officer, I want the system to all customers must be screened for PEP status and PEP relationships must be approved by a senior compliance officer, so that the bank meets its KYC/AML obligations.

**Acceptance criteria**

- Given an internal audit sample, when the control evidence is reviewed, then 100% of sampled cases show the control was applied with traceable evidence.

## US-FR-KYC-004

As a compliance officer, I want the system to assign every customer a low, medium or high risk rating based on the approved risk-scoring model, so that onboarding is completed correctly.

**Acceptance criteria**

- Given a valid onboarding application, when the system is required to assign every customer a low, medium or high risk rating based on the approved risk-scoring model, then it does so and records the outcome.
- Given invalid or incomplete input, when the step is attempted, then the system rejects it with a specific error and no partial record is created.

## US-REG-KYC-002

As a compliance officer, I want the system to high-risk customers must be manually reviewed and go through enhanced due diligence with source of funds evidence, so that the bank meets its KYC/AML obligations.

**Acceptance criteria**

- Given an internal audit sample, when the control evidence is reviewed, then 100% of sampled cases show the control was applied with traceable evidence.

## US-DAT-KYC-002

As a compliance officer, I want the system to periodic re-KYC must be scheduled every 2 years for high-risk, 8 years for medium-risk and 10 years for low-risk customers, so that records are kept exactly as long as required.

**Acceptance criteria**

- Given an internal audit sample, when the control evidence is reviewed, then 100% of sampled cases show the control was applied with traceable evidence.

## US-DAT-KYC-003

As a compliance officer, I want the system to kYC records must be retained for at least 5 years after the account is closed, so that records are kept exactly as long as required.

**Acceptance criteria**

- Given a closed relationship, when the retention period elapses, then the records are purged and the purge is logged; before that, records are retrievable within 1 business day.

## US-DAT-KYC-004

As a compliance officer, I want the system to kYC records of new customers must be uploaded to CKYCR within the regulatory timeline, so that records are kept exactly as long as required.

**Acceptance criteria**

- Given an internal audit sample, when the control evidence is reviewed, then 100% of sampled cases show the control was applied with traceable evidence.

## US-SEC-KYC-001

As a compliance officer, I want the system to where video KYC is used, the session must include liveness check, geo-tagging and face match by a trained official, and the recording must be stored securely, so that customer identities and data are protected.

**Acceptance criteria**

- Given a valid onboarding application, when the system is required to Where video KYC is used, the session must include liveness check, geo-tagging and face match by a trained official, and , then it does so and records the outcome.
- Given an unauthorised or unauthenticated actor, when they attempt to Where video KYC is used, the session must include liveness check, geo-tagging an, then access is denied and a security event is logged.
- Given invalid or incomplete input, when the step is attempted, then the system rejects it with a specific error and no partial record is created.

## US-REG-KYC-003

As a compliance officer, I want the system to staff must be able to escalate suspicious applications to the Principal Officer for STR filing without alerting the customer, so that the bank meets its KYC/AML obligations.

**Acceptance criteria**

- Given a valid onboarding application, when the system is required to Staff must be able to escalate suspicious applications to the Principal Officer for STR filing without alerting the cust, then it does so and records the outcome.
- Given an internal audit sample, when the control evidence is reviewed, then 100% of sampled cases show the control was applied with traceable evidence.
- Given invalid or incomplete input, when the step is attempted, then the system rejects it with a specific error and no partial record is created.

## US-SEC-KYC-002

As a security officer, I want the system to all identity documents and Aadhaar numbers must be encrypted at rest using AES-256 with keys in the HSM, so that customer identities and data are protected.

**Acceptance criteria**

- Given an unauthorised or unauthenticated actor, when they attempt to All identity documents and Aadhaar numbers must be encrypted at rest using AES-2, then access is denied and a security event is logged.

## US-SEC-KYC-003

As a security officer, I want the system to all traffic must use TLS 1.2 or higher, so that customer identities and data are protected.

**Acceptance criteria**

- Given an unauthorised or unauthenticated actor, when they attempt to All traffic must use TLS 1.2 or higher, then access is denied and a security event is logged.

## US-SEC-KYC-004

As a security officer, I want the system to customers must log in with OTP plus device binding, so that customer identities and data are protected.

**Acceptance criteria**

- Given an unauthorised or unauthenticated actor, when they attempt to Customers must log in with OTP plus device binding, then access is denied and a security event is logged.

## US-SEC-KYC-005

As a security officer, I want the system to staff must use MFA to access the back-office, so that customer identities and data are protected.

**Acceptance criteria**

- Given an unauthorised or unauthenticated actor, when they attempt to Staff must use MFA to access the back-office, then access is denied and a security event is logged.

## US-PRV-KYC-001

As a security officer, I want the system to aadhaar numbers must be masked in all screens, showing only the last 4 digits, so that customers' personal data is handled lawfully.

**Acceptance criteria**

- Given a data-protection review, when processing records are inspected, then the lawful basis or consent and the purpose are recorded for each data item.

## US-SEC-KYC-006

As a security officer, I want the system to keep a tamper-evident audit trail of every KYC decision and every access to customer documents, so that customer identities and data are protected.

**Acceptance criteria**

- Given an unauthorised or unauthenticated actor, when they attempt to keep a tamper-evident audit trail of every KYC decision and every access to cust, then access is denied and a security event is logged.
- Given any KYC decision, when the audit trail is queried, then actor, timestamp, action, reason and evidence references are returned and the hash chain verifies.

## US-SEC-KYC-007

As a security officer, I want the system to be secure and robust against attacks, so that customer identities and data are protected.

**Acceptance criteria**

- Given an unauthorised or unauthenticated actor, when they attempt to be secure and robust against attacks, then access is denied and a security event is logged.

## US-FR-KYC-005

As a KYC operations officer, I want the system to any manual override of an automated KYC decision must go through maker-checker approval with a reason, so that onboarding is completed correctly.

**Acceptance criteria**

- Given a valid onboarding application, when the system is required to Any manual override of an automated KYC decision must go through maker-checker approval with a reason, then it does so and records the outcome.
- Given invalid or incomplete input, when the step is attempted, then the system rejects it with a specific error and no partial record is created.

## US-REG-KYC-004

As a KYC operations officer, I want the system to potential sanctions matches need a case management queue where analysts can review evidence and close alerts with comments, so that the bank meets its KYC/AML obligations.

**Acceptance criteria**

- Given an internal audit sample, when the control evidence is reviewed, then 100% of sampled cases show the control was applied with traceable evidence.

## US-OPS-KYC-002

As a KYC operations officer, I want the system to we need the review queue to show cases sorted by risk and SLA age, so that operations can run the process efficiently.

**Acceptance criteria**

- Given a valid onboarding application, when the system is required to We need the review queue to show cases sorted by risk and SLA age, then it does so and records the outcome.
- Given invalid or incomplete input, when the step is attempted, then the system rejects it with a specific error and no partial record is created.

## US-AUD-KYC-001

As a KYC operations officer, I want the system to ops needs a daily MIS report of applications approved, rejected and pending, by channel, so that every decision can be evidenced to auditors and regulators.

**Acceptance criteria**

- Given any KYC decision, when the audit trail is queried, then actor, timestamp, action, reason and evidence references are returned and the hash chain verifies.

## US-INT-KYC-002

As a KYC operations officer, I want the system to if the e-KYC vendor is down, applications should be queued and customers notified, not rejected, so that onboarding works end-to-end with existing systems.

**Acceptance criteria**

- Given a valid onboarding application, when the system is required to If the e-KYC vendor is down, applications should be queued and customers notified, not rejected, then it does so and records the outcome.
- Given invalid or incomplete input, when the step is attempted, then the system rejects it with a specific error and no partial record is created.

## US-DAT-KYC-005

As a KYC operations officer, I want the system to customer data must be retained for 10 years after the account is closed, so that records are kept exactly as long as required.

**Acceptance criteria**

- Given a closed relationship, when the retention period elapses, then the records are purged and the purge is logged; before that, records are retrievable within 1 business day.

## US-INT-KYC-003

As a solution architect, I want the system to the onboarding platform must integrate with the core banking system through an asynchronous adapter and report account status back to the customer, so that onboarding works end-to-end with existing systems.

**Acceptance criteria**

- Given a valid onboarding application, when the system is required to The onboarding platform must integrate with the core banking system through an asynchronous adapter and report account s, then it does so and records the outcome.
- Given invalid or incomplete input, when the step is attempted, then the system rejects it with a specific error and no partial record is created.

## US-PERF-KYC-003

As a solution architect, I want the system to the onboarding APIs must handle a peak of 200 applications per minute during campaigns, so that onboarding feels responsive.

**Acceptance criteria**

- Given a valid onboarding application, when the system is required to The onboarding APIs must handle a peak of 200 applications per minute during campaigns, then it does so and records the outcome.
- Given invalid or incomplete input, when the step is attempted, then the system rejects it with a specific error and no partial record is created.

## US-PERF-KYC-004

As a solution architect, I want the system to the onboarding service must have 99.9% monthly availability with an RTO of 4 hours and RPO of 15 minutes, so that onboarding feels responsive.

**Acceptance criteria**

- Given peak production load, when the step is executed, then it completes within 99.9% at the 95th percentile.
- Given a calendar month, when availability is measured by synthetic monitoring, then it meets 99.9%.

## US-INT-KYC-004

As a solution architect, I want the system to all integrations with vendors (e-KYC, video KYC, screening) must go through the API gateway, so that onboarding works end-to-end with existing systems.

**Acceptance criteria**

- Given a valid onboarding application, when the system is required to All integrations with vendors (e-KYC, video KYC, screening) must go through the API gateway, then it does so and records the outcome.
- Given invalid or incomplete input, when the step is attempted, then the system rejects it with a specific error and no partial record is created.

## US-SR-KYC-001

As a prospective customer, I want the system to customers want to know what is happening, so that onboarding is completed correctly.

**Acceptance criteria**

- Given a valid onboarding application, when the system is required to Customers want to know what is happening, then it does so and records the outcome.
- Given invalid or incomplete input, when the step is attempted, then the system rejects it with a specific error and no partial record is created.

## US-FR-KYC-006

As a prospective customer, I want the system to show clear progress and the reason if an application is rejected, so that onboarding is completed correctly.

**Acceptance criteria**

- Given a valid onboarding application, when the system is required to show clear progress and the reason if an application is rejected, then it does so and records the outcome.
- Given invalid or incomplete input, when the step is attempted, then the system rejects it with a specific error and no partial record is created.

## US-SR-KYC-002

As a prospective customer, I want the system to customers expect the selfie step to work in low light and on older Android phones, so that onboarding is completed correctly.

**Acceptance criteria**

- Given a valid onboarding application, when the system is required to Customers expect the selfie step to work in low light and on older Android phones, then it does so and records the outcome.
- Given invalid or incomplete input, when the step is attempted, then the system rejects it with a specific error and no partial record is created.

## US-SR-KYC-003

As a prospective customer, I want the system to customers want to be able to contest a rejection and talk to a human, so that onboarding is completed correctly.

**Acceptance criteria**

- Given a valid onboarding application, when the system is required to Customers want to be able to contest a rejection and talk to a human, then it does so and records the outcome.
- Given invalid or incomplete input, when the step is attempted, then the system rejects it with a specific error and no partial record is created.

## US-FR-KYC-007

As a prospective customer, I want the system to several customers said they do not want their data used for marketing without asking them, so that onboarding is completed correctly.

**Acceptance criteria**

- Given a valid onboarding application, when the system is required to Several customers said they do not want their data used for marketing without asking them, then it does so and records the outcome.
- Given invalid or incomplete input, when the step is attempted, then the system rejects it with a specific error and no partial record is created.

## US-AUD-KYC-002

As a internal auditor, I want the system to the new system must record who changed a customer risk rating, when, and why, and the change must be approved by a second user, so that every decision can be evidenced to auditors and regulators.

**Acceptance criteria**

- Given a valid onboarding application, when the system is required to The new system must record who changed a customer risk rating, when, and why, and the change must be approved by a secon, then it does so and records the outcome.
- Given any KYC decision, when the audit trail is queried, then actor, timestamp, action, reason and evidence references are returned and the hash chain verifies.
- Given invalid or incomplete input, when the step is attempted, then the system rejects it with a specific error and no partial record is created.

## US-PRV-KYC-002

As a internal auditor, I want the system to the new system must capture and store explicit consent before collecting personal data, so that customers' personal data is handled lawfully.

**Acceptance criteria**

- Given a valid onboarding application, when the system is required to The new system must capture and store explicit consent before collecting personal data, then it does so and records the outcome.
- Given a data-protection review, when processing records are inspected, then the lawful basis or consent and the purpose are recorded for each data item.
- Given invalid or incomplete input, when the step is attempted, then the system rejects it with a specific error and no partial record is created.

## US-FR-KYC-008

As a compliance officer, I want the system to for legal-entity customers the system shall identify and verify all beneficial owners above the jurisdictional ownership threshold and at least one controlling person, so that onboarding is completed correctly.

**Acceptance criteria**

- Given a valid onboarding application, when the system is required to For legal-entity customers the system shall identify and verify all beneficial owners above the jurisdictional ownership, then it does so and records the outcome.
- Given an internal audit sample, when the control evidence is reviewed, then 100% of sampled cases show the control was applied with traceable evidence.
- Given invalid or incomplete input, when the step is attempted, then the system rejects it with a specific error and no partial record is created.

## US-PRV-KYC-003

As a security officer, I want the system to support detection and notification of personal-data breaches to the regulator and affected customers within statutory deadlines (for example 72 hours under GDPR), so that customers' personal data is handled lawfully.

**Acceptance criteria**

- Given an unauthorised or unauthenticated actor, when they attempt to support detection and notification of personal-data breaches to the regulator an, then access is denied and a security event is logged.
- Given a data-protection review, when processing records are inspected, then the lawful basis or consent and the purpose are recorded for each data item.

## US-SEC-KYC-008

As a security officer, I want the system to validate uploaded identity files by type, size and content signature, scan them for malware before processing, and store them outside the web root, so that customer identities and data are protected.

**Acceptance criteria**

- Given an unauthorised or unauthenticated actor, when they attempt to validate uploaded identity files by type, size and content signature, scan them , then access is denied and a security event is logged.

## US-SEC-KYC-009

As a security officer, I want the system to authenticate all service-to-service calls with mutual TLS or OAuth 2.0 client credentials, sign and validate response payloads from verification vendors, and rate-limit public onboarding APIs, so that customer identities and data are protected.

**Acceptance criteria**

- Given an unauthorised or unauthenticated actor, when they attempt to authenticate all service-to-service calls with mutual TLS or OAuth 2.0 client cr, then access is denied and a security event is logged.

## US-SEC-KYC-010

As a KYC operations officer, I want the system to restrict back-office access to KYC data by role, display national identifiers masked by default, log every unmask/view of restricted data, and require just-in-time approval for privileged access, so that customer identities and data are protected.

**Acceptance criteria**

- Given an unauthorised or unauthenticated actor, when they attempt to restrict back-office access to KYC data by role, display national identifiers ma, then access is denied and a security event is logged.
- Given a data-protection review, when processing records are inspected, then the lawful basis or consent and the purpose are recorded for each data item.
- Given any KYC decision, when the audit trail is queried, then actor, timestamp, action, reason and evidence references are returned and the hash chain verifies.

## US-SEC-KYC-011

As a security officer, I want the system to apply fraud checks at onboarding (device fingerprint, velocity of applications per device/address/identifier, and synthetic-identity signals) and refer high-scoring applications for review, so that customer identities and data are protected.

**Acceptance criteria**

- Given a valid onboarding application, when the system is required to apply fraud checks at onboarding (device fingerprint, velocity of applications per device/address/identifier, and synthe, then it does so and records the outcome.
- Given an unauthorised or unauthenticated actor, when they attempt to apply fraud checks at onboarding (device fingerprint, velocity of applications p, then access is denied and a security event is logged.
- Given invalid or incomplete input, when the step is attempted, then the system rejects it with a specific error and no partial record is created.

## US-REG-KYC-005

As a compliance officer, I want the system to automated risk-scoring and face-match models shall be validated before deployment, monitored monthly for drift and demographic bias, and every automated decision shall store the model version and top contributing factors, so that the bank meets its KYC/AML obligations.

**Acceptance criteria**

- Given an internal audit sample, when the control evidence is reviewed, then 100% of sampled cases show the control was applied with traceable evidence.

## US-PRV-KYC-004

As a prospective customer, I want the system to use synthetic or irreversibly masked data in non-production and analytics environments; production KYC data shall not be copied to lower environments, so that customers' personal data is handled lawfully.

**Acceptance criteria**

- Given a data-protection review, when processing records are inspected, then the lawful basis or consent and the purpose are recorded for each data item.
