"""Evaluation harness: compares system output with gold annotations.

Metrics (problem statement section 19): extraction precision/recall/F1, classification
accuracy, ambiguity- and conflict-detection P/R, regulatory-control mapping P/R, gap
detection, citation validity, hallucination rate, SDLC agreement, traceability
coverage, processing time and estimated time saved.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from ..models import Requirement


def _prf(tp: int, fp: int, fn: int) -> dict[str, float]:
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return {"precision": round(p, 3), "recall": round(r, 3), "f1": round(f, 3), "tp": tp, "fp": fp, "fn": fn}


def match_gold(reqs: list[Requirement], gold: list[dict[str, Any]]) -> dict[str, str]:
    """Map gold id -> system requirement id (first stakeholder-derived requirement containing all match terms)."""
    out: dict[str, str] = {}
    used: set[str] = set()
    for g in gold:
        for r in reqs:
            low = r.statement.lower()
            if r.id not in used and all(t in low for t in g["match"]):
                out[g["id"]] = r.id
                used.add(r.id)
                break
    return out


def evaluate_state(co, gold: dict[str, Any], elapsed: float) -> dict[str, Any]:
    st = co.state
    extracted = [r for r in st.requirements if r.origin in ("extracted", "clarified")]
    gmap = match_gold(extracted, gold["requirements"])
    rid_to_gold = {v: k for k, v in gmap.items()}
    G = {g["id"]: g for g in gold["requirements"]}

    extraction = _prf(len(gmap), len(extracted) - len(gmap), len(G) - len(gmap))
    extraction["unmatched_system"] = [f"{r.id}: {r.statement[:90]}" for r in extracted if r.id not in rid_to_gold]
    extraction["missed_gold"] = [g for g in G if g not in gmap]

    correct = sum(1 for gid, rid in gmap.items() if st.req(rid).categories and st.req(rid).categories[0].value in G[gid]["primary"])
    classification = {"primary_accuracy": round(correct / max(len(gmap), 1), 3), "evaluated": len(gmap)}

    flagged = {rid for rid in gmap.values() if any(i.type in ("ambiguity", "untestable", "infeasibility") for i in st.req(rid).quality_issues)}
    truth = {gmap[g] for g in G if G[g].get("ambiguous") and g in gmap}
    ambiguity = _prf(len(flagged & truth), len(flagged - truth), len(truth - flagged))

    sys_pairs = {frozenset(c.requirement_ids) for c in st.conflicts if c.type == "contradiction"}
    gold_pairs = {frozenset((gmap[a], gmap[b])) for a, b in gold["conflicts"] if a in gmap and b in gmap}
    conflicts = _prf(len(sys_pairs & gold_pairs), len(sys_pairs - gold_pairs), len(gold_pairs - sys_pairs))
    reg_sys = {c.requirement_ids[0] for c in st.conflicts if c.type == "regulatory"}
    reg_gold = {gmap[g] for g in gold["regulatory_conflicts"] if g in gmap}
    conflicts["regulatory_conflict_recall"] = round(len(reg_sys & reg_gold) / max(len(reg_gold), 1), 3)

    tp = fp = fn = 0
    for gid, rid in gmap.items():
        exp = set(G[gid].get("controls", []))
        got = {c for c in st.req(rid).controls if c.startswith("KYC-")}
        tp, fp, fn = tp + len(exp & got), fp + len(got - exp), fn + len(exp - got)
    mapping = _prf(tp, fp, fn)

    sys_gaps = {c.control_id for c in st.coverage if c.mandatory and c.status in ("gap", "derived")}
    exp_gaps = set(gold["expected_control_gaps"])
    gaps = _prf(len(sys_gaps & exp_gaps), len(sys_gaps - exp_gaps), len(exp_gaps - sys_gaps))
    gaps["system_gaps"], gaps["expected_gaps"] = sorted(sys_gaps), sorted(exp_gaps)

    m = st.metrics
    produced = len(extracted) + m["citations_total"]
    hallucinated = m["hallucinated_extractions"] + m["hallucinated_citations"]
    ranked = [o.model for o in st.sdlc.ranked] if st.sdlc else []
    sdlc = {
        "expert_choice": gold["sdlc"]["expert_choice"],
        "system_top1": ranked[0] if ranked else None,
        "top1_match": bool(ranked) and ranked[0] == gold["sdlc"]["expert_choice"],
        "top2_contains_expert": gold["sdlc"]["expert_choice"] in ranked[:2],
        "top1_acceptable": bool(ranked) and ranked[0] in gold["sdlc"]["acceptable"],
        "ranking": [(o.model, o.score) for o in st.sdlc.ranked] if st.sdlc else [],
    }

    mb = gold.get("manual_baseline", {})
    manual_min = (mb.get("minutes_per_source_document", 0) * len(st.documents)
                  + (mb.get("minutes_per_requirement_compliance_mapping", 0) + mb.get("minutes_per_requirement_documentation", 0)) * len(st.requirements))

    return {
        "case": st.project.name,
        "llm": co.llm.name,
        "kb_version": co.ctx.kb.version,
        "extraction": extraction,
        "classification": classification,
        "ambiguity_detection": ambiguity,
        "conflict_detection": conflicts,
        "regulatory_control_mapping": mapping,
        "control_gap_detection": gaps,
        "regulatory_control_coverage": {"stakeholder_only": m["control_coverage_stakeholder"], "after_derivation": m["control_coverage_after_derivation"]},
        "citation_validity": m["citation_validity"],
        "hallucination_rate": round(hallucinated / max(produced + hallucinated, 1), 4),
        "hallucinations_blocked": hallucinated,
        "sdlc": sdlc,
        "traceability_coverage": m["traceability_coverage"],
        "acceptance_criteria_coverage": m["acceptance_criteria_coverage"],
        "security_gate": {"pii_masked": m["pii_masked"], "injection_quarantined": m["injection_quarantined"]},
        "processing_time_s": round(elapsed, 3),
        "estimated_manual_minutes": manual_min,
        "estimated_time_saved_pct": round(100 * (1 - (elapsed / 60) / manual_min), 1) if manual_min else None,
        "human_review_load": {"open_questions": m["open_questions"], "pending_approvals": sum(1 for a in st.approvals if a.status.value == "pending_approval")},
    }


def evaluate_case(case_dir: str | Path, llm: str | None = None) -> dict[str, Any]:
    from ..cli import load_case

    case = Path(case_dir)
    gold = json.loads((case / "gold.json").read_text())
    t0 = time.perf_counter()
    co = load_case(case, llm=llm)
    co.run()
    return evaluate_state(co, gold, time.perf_counter() - t0)
