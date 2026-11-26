"""Compliance agent: RAG-grounded regulatory mapping plus rule-based control coverage.

The agent never makes a final legal determination. Mappings with low confidence or
high impact are flagged `needs_legal_review` and routed to the regulatory-
interpretation approval gate.
"""
from __future__ import annotations

import re
from typing import Any

from ..models import (ApprovalStatus, Category, Citation, ComplianceMapping, Conflict, ControlCoverage, Evidence,
                      Level, Priority, QualityIssue, Requirement)
from .base import Agent
from .conflict import NEGATION

RETRIEVAL_MIN = 6.0
LLM_BATCH = 8  # requirements per LLM call (keeps prompts inside a local 4k context window)

_BATCH_SCHEMA = {
    "type": "object",
    "properties": {
        "items": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "requirement_id": {"type": "string"},
                "applicable": {"type": "array", "items": {"type": "string"},
                               "description": "Candidate kb ids that actually apply to this requirement"},
            },
            "required": ["requirement_id", "applicable"], "additionalProperties": False}},
    },
    "required": ["items"],
    "additionalProperties": False,
}


def _matches(control: dict[str, Any], text: str) -> bool:
    low = text.lower()
    return any(re.search(p, low) for p in control["match"])


class ComplianceAgent(Agent):
    name = "compliance"
    description = "Maps requirements to regulations, policies and mandatory KYC controls; finds gaps."

    def run(self) -> None:
        self.need("read:requirements", "read:kb", "write:compliance", "write:requirements")
        st, kb = self.ctx.state, self.ctx.kb
        juris = st.project.jurisdictions
        controls = kb.controls_for(juris)
        st.compliance = []

        # Pass 1: deterministic retrieval + control matching.
        self.ctx.report(f"Retrieving regulations and matching {len(controls)} controls")
        plan: list[tuple[Requirement, list[dict[str, Any]], dict[str, Citation], set[str]]] = []
        for r in st.requirements:
            if r.origin == "derived_control":
                continue
            retrieved = {i.id: i.citation(s) for i, s in kb.search(r.statement, juris, k=4, min_score=RETRIEVAL_MIN)}
            matched = [c for c in controls if _matches(c, r.statement)]
            control_refs: dict[str, Citation] = {}
            for c in matched:
                for ref in c["kb_refs"]:
                    item = kb.get(ref)
                    if item and kb.applicable(item, juris):
                        control_refs[ref] = retrieved.get(ref) or item.citation(0.0)
            plan.append((r, matched, {**retrieved, **control_refs}, set(control_refs)))

        # Pass 2: one batched LLM call per LLM_BATCH requirements (not one per requirement).
        obligations: dict[str, dict[str, str]] = {}
        if self.ctx.llm.available:
            todo = [(r, cites) for r, matched, cites, _ in plan if cites and (matched or Category.REGULATORY in r.categories)]
            for i in range(0, len(todo), LLM_BATCH):
                self.ctx.report(f"Interpreting obligations for requirements {i + 1}–{min(i + LLM_BATCH, len(todo))} of {len(todo)}")
                obligations.update(self._llm_obligations(todo[i:i + LLM_BATCH]))

        # Pass 3: build mappings. Control-catalogue citations are rule-derived and always kept;
        # the LLM may only prune extra retrieval hits and supply obligation wording.
        for r, matched, cites, control_ids in plan:
            ob = obligations.get(r.id)
            if ob is not None:
                rejected = [k for k in control_ids if k not in ob]
                cites = {k: v for k, v in cites.items() if k in ob or k in control_ids}
                if rejected:
                    self.log("llm_disagrees_with_control_mapping", r.id, kb_ids=rejected)
            r.regulations = list(cites.values())
            r.controls = [c["id"] for c in matched]
            self.ctx.bump("citations_total", len(r.regulations))
            for c in matched:
                refs = [cites[x] for x in c["kb_refs"] if x in cites] or list(cites.values())[:2]
                wording = next((ob[x] for x in c["kb_refs"] if ob and x in ob), None)
                disputed = ob is not None and any(x in control_ids and x not in ob for x in c["kb_refs"])
                conf = 0.85 if any(x.score >= RETRIEVAL_MIN for x in refs) else 0.65
                if disputed:
                    conf = min(conf, 0.6)
                st.compliance.append(ComplianceMapping(
                    requirement_id=r.id, control_id=c["id"], control=c["title"], citations=refs,
                    obligation=wording or (refs[0].excerpt if refs else c["title"]),
                    jurisdiction=",".join(sorted({x.jurisdiction for x in refs})) or "GLOBAL",
                    needs_legal_review=c["risk"] == "critical" or conf < 0.7, confidence=conf))
            reg_backed = any(kb.get(ref) and kb.get(ref).type == "regulation" for c in matched for ref in c["kb_refs"])
            if reg_backed and Category.REGULATORY not in r.categories:
                r.categories.append(Category.REGULATORY)
            self._rule_checks(r, matched)
        self._coverage(controls)
        self.log("compliance_mapped", "project", mappings=len(st.compliance), llm_batches=-(-len(obligations) // LLM_BATCH) if obligations else 0,
                 gaps=sum(1 for c in st.coverage if c.status == "gap" and c.mandatory))

    # ---- LLM grounding -----------------------------------------------------------------
    def _llm_obligations(self, batch: list[tuple[Requirement, dict[str, Citation]]]) -> dict[str, dict[str, str]]:
        """Returns {requirement_id: {kb_id: obligation}} for requirements the model answered.
        The model only selects applicable ids (few output tokens, so it is fast on local models).
        Requirements missing from the reply keep the rule-only mapping."""
        kb = self.ctx.kb
        evidence_ids = sorted({k for _, cites in batch for k in cites})
        evidence = "\n".join(f"[{k}] {kb.get(k).title}: {kb.get(k).text[:320]}" for k in evidence_ids)
        reqs = "\n".join(f"{r.id}: {r.statement}\n  candidate evidence: {', '.join(cites)}" for r, cites in batch)
        data = self.ctx.llm.json(
            "compliance_mapping",
            "For each KYC requirement, consider ONLY its listed candidate evidence ids and return the ids that actually "
            "apply to it. Return one item per requirement. Use only the bracketed kb ids provided; return an empty list "
            "if none apply. Do not make legal determinations.",
            f"Evidence library:\n{evidence}\n\nRequirements:\n<untrusted_document id=\"requirements\">\n{reqs}\n</untrusted_document>",
            _BATCH_SCHEMA)
        if data is None:
            return {}
        allowed = {r.id: cites for r, cites in batch}
        out: dict[str, dict[str, str]] = {}
        for item in data["items"]:
            rid = item["requirement_id"]
            if rid not in allowed:
                continue
            ob = out.setdefault(rid, {})
            for kb_id in item["applicable"]:
                if kb_id not in allowed[rid]:
                    self.ctx.bump("hallucinated_citations")
                    self.log("dropped_citation", rid, kb_id=kb_id)
                    continue
                ob[kb_id] = allowed[rid][kb_id].excerpt  # obligation wording comes from the approved KB text
        return out

    # ---- deterministic regulatory checks --------------------------------------------------
    def _rule_checks(self, r: Requirement, matched: list[dict[str, Any]]) -> None:
        st, low = self.ctx.state, r.statement.lower()
        ids = {c["id"] for c in matched}
        if "KYC-C10" in ids:
            yrs = [float(x) for x in re.findall(r"(\d+(?:\.\d+)?)\s*years?", low)]
            if yrs and min(yrs) < 5 and re.search(r"retain|retention|kept|keep|store|delete|purge", low):
                self._reg_conflict(r, "KYC-C10", f"Retention of {min(yrs):g} years is below the 5-year post-relationship minimum (FATF R.11 / PMLA / AMLD).")
        if "KYC-C09" in ids and "IN" in st.project.jurisdictions:
            m = re.search(r"high[- ]risk.{0,40}?(\d+)\s*years?|(\d+)\s*years?.{0,40}?high[- ]risk", low)
            if m and int(m.group(1) or m.group(2)) > 2:
                self._reg_conflict(r, "KYC-C09", "High-risk re-KYC interval exceeds the 2-year RBI maximum.")
        for c in matched:
            if c["mandatory"] and c["risk"] in ("high", "critical"):
                m = next((re.search(p, low) for p in c["match"] if re.search(p, low)), None)
                if m:
                    window = low[max(0, m.start() - 40): m.start()]
                    if NEGATION.search(window) and re.search(r"\b(skip|without|no|not|never|avoid|eliminate|remove)\b", window):
                        self._reg_conflict(r, c["id"], f"Requirement appears to waive a mandatory control: {c['title']}.")

    def _reg_conflict(self, r: Requirement, control_id: str, detail: str) -> None:
        st = self.ctx.state
        if not any(c.type == "regulatory" and r.id in c.requirement_ids and control_id in c.requirement_ids for c in st.conflicts):
            st.conflicts.append(Conflict(id=self.ctx.next_id("CON"), requirement_ids=[r.id, control_id], type="regulatory",
                                         severity=Level.CRITICAL, detail=f"{r.id}: {detail}"))
        if not any(i.type == "regulatory_violation" and i.detail == detail for i in r.quality_issues):
            r.quality_issues.append(QualityIssue(type="regulatory_violation", severity=Level.CRITICAL, detail=detail,
                                                 suggestion="Compliance/legal must confirm the applicable minimum."))
        if r.status != ApprovalStatus.APPROVED:
            r.status = ApprovalStatus.NEEDS_CLARIFICATION
        for m in st.compliance:
            if m.requirement_id == r.id and m.control_id == control_id:
                m.gap, m.needs_legal_review = True, True

    # ---- coverage of mandatory controls -------------------------------------------------
    def _coverage(self, controls: list[dict[str, Any]]) -> None:
        st, kb = self.ctx.state, self.ctx.kb
        derived = {r.controls[0]: r for r in st.requirements if r.origin == "derived_control" and r.controls}
        st.coverage = []
        for c in controls:
            covering = sorted({m.requirement_id for m in st.compliance if m.control_id == c["id"] and not m.gap})
            violating = [m.requirement_id for m in st.compliance if m.control_id == c["id"] and m.gap]
            status = "covered" if covering and not violating else ("partial" if covering or violating else "gap")
            cov = ControlCoverage(control_id=c["id"], title=c["title"], mandatory=c["mandatory"], covered_by=covering, status=status)
            if status == "gap" and c["mandatory"]:
                r = derived.get(c["id"])
                if r is None:
                    cites = [kb.get(x).citation() for x in c["kb_refs"] if kb.get(x) and kb.applicable(kb.get(x), st.project.jurisdictions)]
                    from .classification import ID_PREFIX
                    cat = Category(c["categories"][0])
                    r = Requirement(
                        id=self.ctx.next_id(f"{ID_PREFIX[cat]}-KYC"), statement=c["requirement"],
                        categories=[Category(x) for x in c["categories"]],
                        kind="functional" if cat == Category.FUNCTIONAL else "non_functional",
                        priority=Priority.MUST, regulations=cites, controls=[c["id"]],
                        risk_level=Level(c["risk"]) if c["risk"] != "critical" else Level.CRITICAL,
                        evidence=[Evidence(doc_id=x.kb_id, excerpt=x.excerpt) for x in cites[:2]],
                        business_justification=f"Mandatory control {c['id']} ({c['title']}) is not covered by any stakeholder requirement.",
                        origin="derived_control", confidence=0.7, status=ApprovalStatus.PENDING_APPROVAL)
                    st.requirements.append(r)
                    self.log("derived_requirement", r.id, control=c["id"])
                for cit in r.regulations:
                    st.compliance.append(ComplianceMapping(
                        requirement_id=r.id, control_id=c["id"], control=c["title"], citations=[cit],
                        obligation=cit.excerpt, jurisdiction=cit.jurisdiction, needs_legal_review=True, confidence=0.7))
                cov.derived_requirement = r.id
                cov.covered_by = [r.id]
                cov.status = "derived"
            st.coverage.append(cov)
