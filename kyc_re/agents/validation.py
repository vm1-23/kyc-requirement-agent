"""Validation agent: verifies completeness, consistency, evidence and traceability."""
from __future__ import annotations

from ..models import ApprovalStatus, Category as C, Level
from .base import Agent


class ValidationAgent(Agent):
    name = "validation"
    description = "Computes readiness metrics and blocks the baseline if quality gates fail."

    def run(self) -> None:
        self.need("read:requirements", "read:compliance", "write:metrics")
        st, kb = self.ctx.state, self.ctx.kb
        reqs = st.requirements
        n = max(len(reqs), 1)
        cites = [c for r in reqs for c in r.regulations]
        valid_cites = [c for c in cites if kb.get(c.kb_id) and kb.applicable(kb.get(c.kb_id), st.project.jurisdictions)]
        mandatory = [c for c in st.coverage if c.mandatory]
        covered_by_stakeholders = [c for c in mandatory if c.status == "covered"]
        covered_total = [c for c in mandatory if c.status in ("covered", "derived", "partial")]
        traced = [r for r in reqs if r.evidence and (r.acceptance_criteria) and (r.regulations or C.REGULATORY not in r.categories)]
        open_crit = [c for c in st.conflicts if c.resolution is None and c.severity in (Level.HIGH, Level.CRITICAL)]
        m = {
            "requirements_total": len(reqs),
            "requirements_extracted": sum(1 for r in reqs if r.origin in ("extracted", "clarified")),
            "requirements_derived": sum(1 for r in reqs if r.origin == "derived_control"),
            "with_quality_issues": sum(1 for r in reqs if r.quality_issues),
            "needs_clarification": sum(1 for r in reqs if r.status == ApprovalStatus.NEEDS_CLARIFICATION),
            "ambiguity_flags": sum(1 for r in reqs for i in r.quality_issues if i.type == "ambiguity"),
            "conflicts_total": len(st.conflicts),
            "conflicts_open_high": len(open_crit),
            "mandatory_controls": len(mandatory),
            "control_coverage_stakeholder": round(len(covered_by_stakeholders) / max(len(mandatory), 1), 3),
            "control_coverage_after_derivation": round(len(covered_total) / max(len(mandatory), 1), 3),
            "citations_total": len(cites),
            "citation_validity": round(len(valid_cites) / max(len(cites), 1), 3),
            "hallucinated_extractions": self.ctx.stats.get("hallucinated_extractions", 0),
            "hallucinated_citations": self.ctx.stats.get("hallucinated_citations", 0),
            "traceability_coverage": round(len(traced) / n, 3),
            "acceptance_criteria_coverage": round(sum(1 for r in reqs if r.acceptance_criteria) / n, 3),
            "avg_confidence": round(sum(r.confidence for r in reqs) / n, 3),
            "low_confidence": sum(1 for r in reqs if r.confidence < 0.5),
            "open_questions": sum(1 for q in st.questions if q.answer is None),
            "risks": len(st.risks),
            "pii_masked": self.ctx.stats.get("pii_masked", 0),
            "injection_quarantined": self.ctx.stats.get("injection_quarantined", 0),
            "by_category": {c.value: sum(1 for r in reqs if c in r.categories) for c in C},
        }
        gates = {
            "no_open_high_conflicts": not open_crit,
            "full_mandatory_coverage": m["control_coverage_after_derivation"] == 1.0,
            "all_citations_valid": m["citation_validity"] == 1.0,
            "no_pending_clarifications": m["needs_clarification"] == 0,
            "traceability_complete": m["traceability_coverage"] >= 0.95,
        }
        m["baseline_ready"] = all(gates.values())
        m["gates"] = gates
        st.metrics.update(m)
        self.log("validated", "project", baseline_ready=m["baseline_ready"], gates=gates)
