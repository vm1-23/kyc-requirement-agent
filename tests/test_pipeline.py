import pytest

from kyc_re.agents.conflict import compatible, ranges
from kyc_re.agents.extraction import normalise
from kyc_re.coordinator import Coordinator
from kyc_re.knowledge.kb import default_kb
from kyc_re.models import ApprovalStatus, ProjectContext
from kyc_re.sdlc.engine import score_models
from kyc_re.security.rbac import PermissionDenied


def test_kb_items_have_provenance_and_jurisdiction_filter():
    kb = default_kb()
    for item in kb.items.values():
        assert item.source and item.jurisdiction and item.effective_date and item.version
    ids_in = {i.id for i, _ in kb.search("periodic re-KYC high risk", ["IN"], k=10)}
    ids_us = {i.id for i, _ in kb.search("periodic re-KYC high risk", ["US"], k=10)}
    assert "IN-RBI-REKYC" in ids_in and "IN-RBI-REKYC" not in ids_us


def test_normalise_to_shall_form():
    assert normalise("We need the system to send an SMS when KYC expires") == "The system shall send an SMS when KYC expires."
    assert normalise("The app must support Hindi.") == "The system shall support Hindi."


def test_bounded_quantities_are_compatible():
    assert compatible(ranges("at least 5 years")["years"], ranges("10 years")["years"])
    assert not compatible(ranges("3 years")["years"], ranges("at least 5 years")["years"])


def test_pipeline_end_to_end(neobank):
    st = neobank.state
    m = st.metrics
    assert m["requirements_extracted"] >= 35
    assert all(r.id and r.categories for r in st.requirements)
    assert m["citation_validity"] == 1.0
    assert m["control_coverage_after_derivation"] == 1.0
    assert m["injection_quarantined"] == 1
    assert not any("ignore all previous" in d.masked_text.lower() for d in st.documents)
    assert not any("ABCPK1234Z" in d.masked_text for d in st.documents)
    assert all(d.text == "" for d in st.documents)  # raw text not retained
    assert neobank.audit.verify()


def test_seeded_conflicts_and_regulatory_violation_detected(neobank):
    st = neobank.state
    reg = [c for c in st.conflicts if c.type == "regulatory"]
    assert any("3 years" in c.detail for c in reg)
    stmt = {r.id: r.statement for r in st.requirements}
    pairs = [{stmt[i] for i in c.requirement_ids} for c in st.conflicts if c.type == "contradiction"]
    assert any(any("without manual review" in s for s in p) and any("manually reviewed" in s for s in p) for p in pairs)


def test_missing_mandatory_controls_are_derived(neobank):
    st = neobank.state
    derived = {r.controls[0] for r in st.requirements if r.origin == "derived_control"}
    assert {"KYC-C04", "KYC-C19"} <= derived
    for r in st.requirements:
        if r.origin == "derived_control" and r.controls[0].startswith("KYC-"):
            assert r.regulations, r.id  # every derived requirement cites its source


def test_ambiguous_requirement_triggers_clarification(neobank):
    st = neobank.state
    vague = next(r for r in st.requirements if "robust against attacks" in r.statement)
    assert vague.status == ApprovalStatus.NEEDS_CLARIFICATION
    assert any(q.requirement_id == vague.id for q in st.questions)


def test_answering_question_updates_requirement(neobank):
    st = neobank.state
    vague = next(r for r in st.requirements if "fast and user-friendly" in r.statement)
    q = next(q for q in st.questions if q.requirement_id == vague.id and q.answer is None)
    neobank.answer(q.id, "Each onboarding step responds within 2 seconds at p95 and the journey has at most 6 screens")
    assert "2 seconds" in vague.statement
    assert vague.history and vague.history[-1]["event"] == "clarified"


def test_sdlc_ranking_is_ranked_and_regulated_hybrid_wins(neobank):
    sd = neobank.state.sdlc
    scores = [o.score for o in sd.ranked]
    assert scores == sorted(scores, reverse=True)
    assert sd.selected.startswith("Hybrid")
    assert len(sd.workflow) >= 6
    assert all(p.approval_gate and p.exit_criteria for p in sd.workflow)


def test_sdlc_engine_prefers_waterfall_for_stable_low_change_projects():
    from kyc_re.models import SDLCFactor

    vals = dict(requirement_stability=5, regulatory_criticality=2, security_risk=2, complexity=2, system_size=2,
                legacy_dependence=2, change_frequency=1, continuous_delivery_need=1, stakeholder_availability=2,
                documentation_need=5, budget_schedule_pressure=2, formal_verification_need=2, failure_consequence=2,
                technical_uncertainty=1)
    ranked = score_models([SDLCFactor(name=k, score=v, rationale="") for k, v in vals.items()], default_kb().sdlc_models)
    assert ranked[0].model == "Waterfall"


def test_approval_rbac_and_baseline_gate(neobank):
    st = neobank.state
    reg = next(a for a in st.approvals if a.gate == "regulatory_interpretation")
    with pytest.raises(PermissionDenied):
        neobank.decide(reg.id, "pat", "product_owner", "approve")
    neobank.decide(reg.id, "arjun", "compliance", "approve", "Confirmed")
    assert reg.status == ApprovalStatus.APPROVED
    base = next(a for a in st.approvals if a.gate == "baseline")
    with pytest.raises(PermissionDenied):  # quality gates still failing
        neobank.decide(base.id, "priya", "product_owner", "approve")


def test_sdlc_gate_requires_all_roles(neobank):
    item = next(a for a in neobank.state.approvals if a.gate == "sdlc")
    neobank.decide(item.id, "pm", "project_manager", "approve")
    assert item.status == ApprovalStatus.PENDING_APPROVAL
    for user, role in [("arch", "architect"), ("sec", "security"), ("comp", "compliance")]:
        neobank.decide(item.id, user, role, "approve")
    assert item.status == ApprovalStatus.APPROVED
    assert neobank.state.sdlc.status == ApprovalStatus.APPROVED


def test_export_writes_all_artefacts(neobank, tmp_path):
    paths = neobank.export(tmp_path)
    for key in ["srs", "rtm", "compliance_matrix", "risk_register", "user_stories", "use_cases", "sdlc", "state", "audit"]:
        assert key in paths
    from docx import Document

    doc = Document(paths["srs"])
    text = "\n".join(p.text for p in doc.paragraphs)
    assert "Software Requirements Specification" in text and "SDLC recommendation" in text
    assert "ABCPK1234Z" not in (tmp_path / "project_state.json").read_text()


def test_change_to_approved_requirement_creates_change_gate(neobank):
    st = neobank.state
    r = next(r for r in st.requirements if "TLS 1.2" in r.statement)
    r.status = ApprovalStatus.APPROVED
    neobank.change_requirement(r.id, "All traffic must use TLS 1.3.", "meera", "security")
    assert any(a.gate == "change" and a.subject_id == r.id for a in st.approvals)


def test_interview_is_adaptive():
    co = Coordinator(ProjectContext(name="t", jurisdictions=["IN"]), llm="offline")
    agent = co.interviewer()
    from kyc_re.models import StakeholderRole

    s = agent.start("S1", "Arjun", StakeholderRole.COMPLIANCE)
    assert s.turns[0].topic == "regulatory"
    s = agent.answer(s, "not sure")
    assert s.turns[-1].followup  # vague answer -> follow-up on same topic
    s = agent.answer(s, "RBI KYC Master Direction and PMLA apply; we must screen sanctions and PEP lists for every applicant.")
    assert s.turns[-1].topic != "regulatory" and not s.turns[-1].followup
