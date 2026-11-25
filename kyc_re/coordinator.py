"""Coordinator (central orchestrator).

Runs the agents in a fixed, auditable order over a shared `ProjectState`, applies
the security gate before any analysis, and exposes the human-in-the-loop operations
(answer a question, decide an approval, modify a requirement). Control flow is plain
code: LLMs never decide which agent runs next.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from .agents.approval import ApprovalAgent
from .agents.base import Context
from .agents.clarification import ClarificationAgent
from .agents.classification import ClassificationAgent
from .agents.compliance import ComplianceAgent
from .agents.conflict import ConflictAgent
from .agents.documentation import DocumentationAgent
from .agents.extraction import ExtractionAgent
from .agents.ingestion import IngestionAgent
from .agents.interaction import InteractionAgent
from .agents.quality import QualityAgent
from .agents.risk import RiskAgent
from .agents.sdlc import SDLCAgent
from .agents.security_privacy import SecurityPrivacyAgent
from .agents.validation import ValidationAgent
from .audit import AuditLog
from .knowledge.kb import KnowledgeBase, default_kb
from .llm import LLM, make_llm
from .models import ApprovalStatus, ProjectContext, ProjectState, SourceDocument, SourceType, StakeholderRole

AGENT_REGISTRY = [
    ("Coordinator", "Controls the workflow, shared context and approval gates"),
    ("Stakeholder interaction", InteractionAgent.description),
    ("Security gate", IngestionAgent.description),
    ("Requirement extraction", ExtractionAgent.description),
    ("Classification", ClassificationAgent.description),
    ("Quality / validation", QualityAgent.description),
    ("Clarification", ClarificationAgent.description),
    ("Conflict detection", ConflictAgent.description),
    ("Compliance", ComplianceAgent.description),
    ("Security & privacy", SecurityPrivacyAgent.description),
    ("Risk analysis", RiskAgent.description),
    ("SDLC selection", SDLCAgent.description),
    ("Documentation", DocumentationAgent.description),
    ("Validation", ValidationAgent.description),
    ("Human approval", ApprovalAgent.description),
]


class Coordinator:
    def __init__(self, project: ProjectContext, llm: LLM | str | None = None, kb: KnowledgeBase | None = None,
                 audit_path: str | Path | None = None, state: ProjectState | None = None):
        self.audit = AuditLog(audit_path)
        self.llm = llm if (llm is not None and not isinstance(llm, str)) else make_llm(llm, self.audit)
        if getattr(self.llm, "audit", None) is None:
            self.llm.audit = self.audit  # type: ignore[attr-defined]
        self.ctx = Context(state=state or ProjectState(project=project), kb=kb or default_kb(), llm=self.llm, audit=self.audit)
        self._sync_counters()
        if state is not None:  # resuming: restore agent stats and masking-token counters
            self.ctx.stats = dict(state.metrics.get("agent_stats", {}))
            import re as _re
            for d in state.documents:
                for label, n in _re.findall(r"<([A-Z]+)_(\d+)>", d.masked_text):
                    self.ctx.masker._counters[label] = max(self.ctx.masker._counters.get(label, 0), int(n))
        self.audit.record("coordinator", "session_start", project.name, llm=self.llm.name, kb_version=self.ctx.kb.version,
                          jurisdictions=project.jurisdictions)

    @property
    def state(self) -> ProjectState:
        return self.ctx.state

    def _sync_counters(self) -> None:
        """Continue ID sequences when resuming a saved state."""
        st = self.ctx.state
        ids = [r.id for r in st.requirements] + [q.id for q in st.questions] + [c.id for c in st.conflicts] + \
              [r.id for r in st.risks] + [a.id for a in st.approvals]
        for i in ids:
            prefix, _, num = i.rpartition("-")
            if num.isdigit():
                self.ctx.counters[prefix] = max(self.ctx.counters.get(prefix, 0), int(num))

    # ---- inputs ------------------------------------------------------------------------
    def add_document(self, title: str, text: str, type: SourceType | str = SourceType.MEETING_NOTES,
                     stakeholder: str = "", role: StakeholderRole | str | None = None, doc_id: str | None = None) -> SourceDocument:
        doc = SourceDocument(id=doc_id or self.ctx.next_id("DOC"), title=title, type=SourceType(type), stakeholder=stakeholder,
                             role=StakeholderRole(role) if role else None, text=text)
        IngestionAgent(self.ctx).ingest(doc)
        doc.text = ""  # raw text is not retained after masking (data minimisation)
        self.state.documents.append(doc)
        return doc

    def interviewer(self) -> InteractionAgent:
        return InteractionAgent(self.ctx)

    def mask(self, text: str) -> str:
        return self.ctx.masker.mask(text)[0]

    # ---- pipeline ----------------------------------------------------------------------
    def _stage(self, name: str, fn) -> None:
        t0 = time.perf_counter()
        fn()
        self.state.metrics.setdefault("timing_s", {})[name] = round(time.perf_counter() - t0, 4)

    def run(self) -> ProjectState:
        t0 = time.perf_counter()
        c = self.ctx
        self._stage("ingestion", IngestionAgent(c).run)
        self._stage("topic_coverage", InteractionAgent(c).run)
        self._stage("extraction", ExtractionAgent(c).run)
        self._analyse()
        self.state.metrics["processing_time_s"] = round(time.perf_counter() - t0, 3)
        self.audit.record("coordinator", "pipeline_complete", self.state.project.name,
                          requirements=len(self.state.requirements), baseline_ready=self.state.metrics.get("baseline_ready"))
        return self.state

    def _analyse(self) -> None:
        c = self.ctx
        self._stage("classification", ClassificationAgent(c).run)
        self._stage("quality", QualityAgent(c).run)
        self._stage("conflict", ConflictAgent(c).run)
        self._stage("compliance", ComplianceAgent(c).run)
        self._stage("security_privacy", SecurityPrivacyAgent(c).run)
        self._stage("quality_derived", lambda: QualityAgent(c).run(only_origin="derived_control"))
        self._stage("clarification", ClarificationAgent(c).run)
        self._stage("risk", RiskAgent(c).run)
        self._stage("sdlc", SDLCAgent(c).run)
        self._stage("validation", ValidationAgent(c).run)
        self._stage("approval", ApprovalAgent(c).run)
        self.state.metrics["agent_stats"] = {k: v for k, v in c.stats.items()}

    def reanalyse(self) -> ProjectState:
        self._analyse()
        return self.state

    # ---- human in the loop -------------------------------------------------------------
    def answer(self, question_id: str, answer: str, user: str = "stakeholder") -> ProjectState:
        masked = self.mask(answer)
        self.audit.record(f"user:{user}", "answer_question", question_id)
        ClarificationAgent(self.ctx).apply_answer(question_id, masked)
        q = next(q for q in self.state.questions if q.id == question_id)
        conflict = next((x for x in self.state.conflicts if x.id == q.requirement_id), None)
        if conflict and conflict.resolution is None:
            conflict.resolution = f"stakeholder answer: {masked}"
        return self.reanalyse()

    def decide(self, approval_id: str, user: str, role: StakeholderRole | str, decision: str, comment: str = "",
               modification: str | None = None) -> Any:
        agent = ApprovalAgent(self.ctx)
        item = agent.decide(approval_id, user, StakeholderRole(role), decision, comment,
                            self.mask(modification) if modification else None)
        if item.status in (ApprovalStatus.MODIFIED, ApprovalStatus.REGENERATE) or (item.gate == "conflict" and item.status == ApprovalStatus.APPROVED):
            self.reanalyse()
        else:
            ValidationAgent(self.ctx).run()
        return item

    def change_requirement(self, req_id: str, new_statement: str, user: str, role: StakeholderRole | str) -> ProjectState:
        """Change to a (possibly approved) requirement: goes through the 'change' approval gate."""
        from .agents.approval import ApprovalAgent as AA
        from .models import ApprovalItem
        from .security.rbac import GATE_APPROVERS

        r = self.state.req(req_id)
        if r is None:
            raise KeyError(req_id)
        masked = self.mask(new_statement)
        r.history.append({"event": "change_requested", "by": user, "before": r.statement, "after": masked})
        was_approved = r.status == ApprovalStatus.APPROVED
        r.statement, r.origin, r.status = masked, "human", ApprovalStatus.MODIFIED
        if was_approved:
            self.state.approvals.append(ApprovalItem(id=self.ctx.next_id("APR"), gate="change", subject_id=req_id,
                                                     summary=f"Change to approved requirement {req_id}: {masked[:140]}",
                                                     required_roles=sorted(GATE_APPROVERS["change"], key=lambda x: x.value)))
        self.audit.record(f"user:{user}", "change_requirement", req_id, role=str(role), was_approved=was_approved)
        return self.reanalyse()

    # ---- outputs -----------------------------------------------------------------------
    def export(self, out_dir: str | Path) -> dict[str, str]:
        return DocumentationAgent(self.ctx).run(out_dir)

    def stories(self) -> list[dict[str, Any]]:
        return DocumentationAgent(self.ctx).stories()

    def use_cases(self) -> list[dict[str, Any]]:
        return DocumentationAgent(self.ctx).use_cases()
