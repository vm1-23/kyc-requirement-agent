# Use cases

## UC-01 Individual digital onboarding

**Actor:** Prospective customer

**Preconditions:** Customer has a supported identity document and mobile number; Consent notice displayed

**Main flow**

1. Customer starts onboarding and accepts the privacy notice and consent
2. System verifies mobile number via OTP
3. Customer provides identity details or fetches them from an e-KYC source
4. System verifies document authenticity and data
5. Customer completes liveness check and face match
6. System screens against sanctions and PEP lists
7. System calculates customer risk rating
8. Low/medium-risk customer is approved; account is created in core banking
9. System uploads KYC record to the registry and records the audit trail

**Alternate flows**

- 4a. Document verification fails: customer may retry once with an alternate document, then the case is referred to manual review
- 6a. Potential sanctions/PEP match: onboarding paused; alert routed to compliance (no tipping-off)
- 7a. High-risk rating: routed to EDD (UC-04)
- 8a. Core banking unavailable: application queued and the customer notified

**Postconditions:** Customer record, evidence and decision are retained per the retention schedule

**Requirements:** USA-KYC-001, PERF-KYC-001, PERF-KYC-002, OPS-KYC-001, FR-KYC-003, DAT-KYC-003, DAT-KYC-004, SEC-KYC-002, SEC-KYC-004, SEC-KYC-006, DAT-KYC-005, INT-KYC-003, PERF-KYC-003, PERF-KYC-004, PRV-KYC-002, FR-KYC-008, SEC-KYC-008, SEC-KYC-009, SEC-KYC-011

## UC-02 Video-based customer identification (V-CIP)

**Actor:** Prospective customer; KYC official

**Preconditions:** Customer consents to the video session; Customer is located within the permitted geography

**Main flow**

1. Customer joins the live video session with a trained official
2. System captures geo-location and checks liveness
3. Official verifies the document live and the system performs a face match
4. Official asks randomised questions
5. Session recording is stored securely with timestamp
6. Official records the decision; maker-checker review completes it

**Alternate flows**

- 2a. Location outside permitted area or liveness fails: session terminated
- 3a. Poor video quality: reschedule

**Postconditions:** Recording and evidence are retained and auditable

**Requirements:** SEC-KYC-001, INT-KYC-004

## UC-03 Legal-entity onboarding with beneficial ownership

**Actor:** Authorised signatory; KYC operations officer

**Preconditions:** Entity registration documents available

**Main flow**

1. Signatory submits entity documents
2. System verifies the entity against the company registry
3. System captures ownership structure and identifies beneficial owners above threshold
4. Each beneficial owner is identified and verified (UC-01 steps 3-6)
5. System risk-rates the entity

**Alternate flows**

- 3a. Complex or opaque ownership: refer to EDD

**Postconditions:** UBO records linked to the entity

**Requirements:** INT-KYC-001, SEC-KYC-002, FR-KYC-008, SEC-KYC-008, SEC-KYC-011

## UC-04 Screening alert handling & enhanced due diligence

**Actor:** Compliance analyst; senior compliance officer

**Preconditions:** Alert or high-risk rating generated

**Main flow**

1. Analyst reviews the match details and evidence
2. Analyst discounts false positives with a recorded rationale
3. For true or likely matches, EDD collects source of funds and wealth
4. Senior compliance officer approves or declines the relationship
5. Decision and rationale recorded in the audit trail

**Alternate flows**

- 2a. Confirmed sanctions match: block, freeze per law, report
- 4a. Suspicion formed: escalate STR (UC-07)

**Postconditions:** Alert closed with an audit trail

**Requirements:** OPS-KYC-001, FR-KYC-003, REG-KYC-001, FR-KYC-004, REG-KYC-002, DAT-KYC-002, PRV-KYC-001, FR-KYC-005, REG-KYC-004, AUD-KYC-001, INT-KYC-004, AUD-KYC-002, SEC-KYC-010

## UC-05 Periodic re-KYC

**Actor:** Existing customer; system scheduler

**Preconditions:** Re-KYC due date reached for the customer's risk tier

**Main flow**

1. System notifies the customer ahead of the due date
2. Customer confirms or updates details
3. System re-verifies changed documents and re-screens
4. Risk rating recalculated

**Alternate flows**

- 3a. Customer does not respond: restrictions applied per policy after the grace period

**Postconditions:** Next due date scheduled

**Requirements:** DAT-KYC-002

## UC-06 Manual review and override (maker-checker)

**Actor:** KYC operations officer (maker); supervisor (checker)

**Preconditions:** Case referred from automated flow

**Main flow**

1. Maker reviews evidence and proposes a decision with reason
2. Checker approves or returns the decision
3. System applies the decision and notifies the customer with a reason code

**Alternate flows**

- 2a. Checker rejects: case returned to maker

**Postconditions:** Override audit-logged

**Requirements:** OPS-KYC-001, REG-KYC-002, FR-KYC-005, REG-KYC-004, OPS-KYC-002, INT-KYC-002, SEC-KYC-011

## UC-07 Suspicious activity escalation

**Actor:** Onboarding staff; principal officer/MLRO

**Preconditions:** Staff forms a suspicion during onboarding

**Main flow**

1. Staff raises an internal suspicious activity report
2. Principal officer reviews and decides to file
3. System generates the STR in the FIU format within the deadline

**Alternate flows**

- 2a. Not filed: rationale recorded

**Postconditions:** Customer not tipped off; records retained

**Requirements:** REG-KYC-003, SEC-KYC-010
