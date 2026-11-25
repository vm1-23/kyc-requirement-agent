# Approach: Agentic Requirement Engineering for KYC / Customer Onboarding

## 1. Why KYC

Of the financial domains listed in the problem statement (digital banking, lending,
payments, fraud, insurance, regulatory reporting, **customer onboarding & KYC**,
analytics), KYC is the best first use case because:

* **It is regulation-dense.** Almost every requirement traces to a rule (customer
  due diligence, beneficial ownership, sanctions/PEP screening, record retention,
  periodic re-KYC, suspicious-transaction reporting, data-privacy consent). That
  makes *regulatory-control coverage* and *citation correctness* measurable.
* **It handles highly sensitive PII.** Identity numbers, biometrics, addresses and
  documents. This forces the PII masking, least-privilege and audit controls the
  problem statement asks for.
* **Stakeholders disagree in predictable ways.** Product wants a 3-minute, low-friction
  onboarding; compliance wants enhanced due diligence; security wants step-up auth;
  operations wants fewer manual reviews. These conflicts give the conflict-detection
  and human-approval paths realistic work.
* **It is bounded.** One customer journey (capture → verify → screen → risk-rate →
  approve → monitor/re-KYC) small enough to build end-to-end and evaluate.

## 2. Design principles

| Principle | How it is realised |
|---|---|
| Deterministic orchestration | A code-driven **coordinator** runs agents in a fixed DAG with approval gates. The LLM never decides control flow. |
| LLM is optional and fenced | Every agent has a **rule-based baseline**, so the system runs offline and stays testable. When an LLM is configured (Claude), it *augments* extraction, classification, clarification and explanations, and its output is schema-validated and checked against the retrieved evidence. |
| Retrieval-grounded | A version-controlled KYC knowledge base (regulations, internal policies, security standards, SDLC rules). Each item carries source, jurisdiction, effective date, version and applicability. Compliance mappings may only cite retrieved items; any other citation counts as a hallucination and is dropped. |
| Rules before generation | Compliance coverage (mandatory KYC controls), requirement-quality checks, and SDLC scoring are deterministic rule and MCDA engines. The LLM only explains them. |
| Privacy by default | PII is detected and masked (Aadhaar, PAN, passport, SSN, IBAN, card numbers with Luhn check, phone, e-mail, DOB) **before** any text reaches an LLM or the log. |
| Injection-resistant | Stakeholder text and documents are untrusted data. They are scanned for prompt-injection patterns, quarantined and delimited, and never placed in the system prompt. |
| Least privilege | Every agent declares the tools/data scopes it needs; the orchestrator enforces them. Human users have RBAC roles that limit which approval gates they can sign. |
| Accountability | Hash-chained, append-only audit log of every agent action, retrieval, LLM call (prompt hash, model, version), human decision and artefact. |
| Human-in-the-loop | Mandatory approval for requirement baselines, regulatory interpretations, high-risk security requirements, conflict resolutions and SDLC selection. Users can accept, reject, modify or regenerate each item. |

## 3. Agent pipeline

```
 inputs (transcripts, emails, policies, interview answers)
   │
   ▼
 [Security gate] PII masking + injection scan ──► audit
   │
   ▼
 Stakeholder-interaction agent (adaptive interview, role templates)
   │
   ▼
 Requirement-extraction agent ──► Classification agent (multi-label)
   │
   ▼
 Clarification agent ◄── Validation/quality agent (ambiguity, testability, ...)
   │
   ▼
 Conflict-detection agent (contradictions, duplicates)
   │
   ▼
 Compliance agent (RAG + rule coverage) ── Security & privacy agent
   │
   ▼
 Risk-analysis agent (risk register)
   │
   ▼
 SDLC-selection agent (decision factors → rules + MCDA → ranked models → workflow)
   │
   ▼
 Documentation agent (SRS .docx, user stories, use cases, RTM, compliance matrix)
   │
   ▼
 Human-approval agent (gates) ──► baseline
```

## 4. SDLC selection

1. **Factor extraction:** 13 decision factors (requirement stability, regulatory
   criticality, security risk, complexity, size, legacy dependence, change frequency,
   CD need, stakeholder availability, documentation need, budget/schedule pressure,
   formal-verification need, failure consequence), each scored 1–5 with evidence.
2. **Hard rules:** for example, regulatory criticality ≥ 4 *and* change frequency ≥ 4
   promotes the regulated hybrids, and formal-verification need ≥ 4 penalises pure Agile.
3. **MCDA:** a weighted fit of each candidate model's profile against the project
   factors, normalised to a 0–100 % suitability score.
4. **Explanation:** a ranked list with reasons. The project-specific workflow
   (phases, activities, roles, deliverables, security activities, compliance
   checkpoints, approval gates, entry/exit criteria) comes from templates plus
   KYC-specific controls.

## 5. Evaluation

A gold-annotated KYC case study (`samples/kyc_onboarding`) with expected requirements,
categories, ambiguities, conflicts, mandatory controls and the architect-chosen SDLC.
The evaluation harness reports extraction P/R/F1, classification accuracy, ambiguity-
and conflict-detection accuracy, regulatory-control coverage, citation correctness and
hallucination rate, SDLC top-1 / top-2 agreement, traceability coverage and processing
time compared with a manual-analysis baseline estimate.

## 6. Scope note

The regulatory knowledge base holds **paraphrased summaries** for prototyping, covering
FATF Recommendations, the RBI KYC Master Direction / PMLA (India), the EU AMLD and
GDPR, the US FinCEN CDD Rule, and India's DPDP Act. Check each item against the official
text before using it in production. The compliance agent does not make legal
determinations; it routes high-impact interpretations to compliance or legal officers.
