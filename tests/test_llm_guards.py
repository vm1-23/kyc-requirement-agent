"""LLM-mode guardrails, tested with a scripted fake LLM (no network)."""
from kyc_re.coordinator import Coordinator
from kyc_re.models import ProjectContext


class FakeLLM:
    name = "fake-llm"
    available = True
    audit = None

    def __init__(self):
        self.calls = []

    def json(self, purpose, system, user, schema, effort="medium", max_tokens=16000):
        self.calls.append((purpose, user))
        if purpose == "extract_requirements":
            return {"requirements": [
                {"statement": "The system shall screen applicants against sanctions lists.",
                 "source_excerpt": "screen every applicant against sanctions lists", "kind": "functional",
                 "priority": "must", "business_justification": "AML"},
                {"statement": "The system shall support cryptocurrency wallets.",  # not in the document
                 "source_excerpt": "customers can pay with crypto wallets", "kind": "functional",
                 "priority": "could", "business_justification": "invented"},
            ]}
        if purpose == "compliance_mapping":
            import re
            ids = re.findall(r"^([A-Z]+-KYC-\d+):", user, re.M)
            return {"items": [{"requirement_id": rid, "applicable": ["FATF-R6", "FAKE-REG-99"]} for rid in ids]}
        return None  # other purposes fall back to rules


def test_ungrounded_outputs_are_dropped_and_counted():
    llm = FakeLLM()
    co = Coordinator(ProjectContext(name="t", jurisdictions=["IN"]), llm=llm)
    co.add_document("email", "The system must screen every applicant against sanctions lists before opening.",
                    "email", "Arjun", "compliance")
    co.run()
    st = co.state
    stmts = [r.statement for r in st.requirements if r.origin == "extracted"]
    assert stmts == ["The system shall screen applicants against sanctions lists."]
    assert st.metrics["hallucinated_extractions"] == 1
    assert st.metrics["hallucinated_citations"] == 1
    cited = {c.kb_id for r in st.requirements for c in r.regulations}
    assert "FAKE-REG-99" not in cited and "FATF-R6" in cited
    assert st.metrics["citation_validity"] == 1.0


def test_untrusted_content_is_delimited_and_masked():
    llm = FakeLLM()
    co = Coordinator(ProjectContext(name="t", jurisdictions=["IN"]), llm=llm)
    co.add_document("n", "Customer PAN ABCDE1234F must be verified. The system must screen every applicant against sanctions lists.",
                    "email", "A", "compliance")
    co.run()
    purpose, user = next(c for c in llm.calls if c[0] == "extract_requirements")
    assert "<untrusted_document" in user and "ABCDE1234F" not in user and "<PAN_1>" in user


def test_compliance_calls_are_batched_and_cannot_drop_control_citations():
    class RejectAll(FakeLLM):
        def json(self, purpose, system, user, schema, effort="medium", max_tokens=16000):
            self.calls.append((purpose, user))
            if purpose == "compliance_mapping":
                import re
                return {"items": [{"requirement_id": rid, "applicable": []} for rid in re.findall(r"^([A-Z]+-KYC-\d+):", user, re.M)]}
            return None

    from kyc_re.cli import load_case
    from tests.conftest import SAMPLES

    llm = RejectAll()
    co = load_case(SAMPLES / "kyc_onboarding", llm=llm)
    co.run()
    n_calls = sum(1 for p, _ in llm.calls if p == "compliance_mapping")
    mapped = sum(1 for r in co.state.requirements if r.controls and r.origin != "derived_control")
    assert 0 < n_calls <= -(-mapped // 8) + 1  # batched, not one call per requirement
    sanctions = next(r for r in co.state.requirements if "sanctions lists" in r.statement and r.origin == "extracted")
    assert "FATF-R6" in {c.kb_id for c in sanctions.regulations}  # rule-derived citation survives LLM rejection
