"""Clarification agent: asks context-aware questions and applies answers."""
from __future__ import annotations

from ..models import ApprovalStatus, ClarificationQuestion, Requirement, StakeholderRole as R
from .base import Agent

_ROLE_FOR_ISSUE = {
    "missing_security_control": R.SECURITY,
    "infeasibility": R.ARCHITECT,
    "untestable": R.PRODUCT_OWNER,
    "undefined_term": R.BUSINESS_ANALYST,
}

_REWRITE_SCHEMA = {
    "type": "object",
    "properties": {"statement": {"type": "string"}, "resolved": {"type": "boolean"}},
    "required": ["statement", "resolved"],
    "additionalProperties": False,
}

_Q_SCHEMA = {
    "type": "object",
    "properties": {"questions": {"type": "array", "items": {
        "type": "object",
        "properties": {"requirement_id": {"type": "string"}, "question": {"type": "string"}},
        "required": ["requirement_id", "question"], "additionalProperties": False}}},
    "required": ["questions"],
    "additionalProperties": False,
}


class ClarificationAgent(Agent):
    name = "clarification"
    description = "Turns quality issues, conflicts and coverage gaps into targeted stakeholder questions."

    def _template_question(self, r: Requirement) -> str:
        parts = [f"Regarding {r.id} (\"{r.statement}\"):"]
        for i in r.quality_issues:
            if i.severity.value != "low":
                parts.append(f"{i.detail} {i.suggestion}")
        return " ".join(parts)

    def run(self) -> None:
        self.need("read:requirements", "write:questions")
        st = self.ctx.state
        asked = {q.requirement_id for q in st.questions if q.answer is None}
        pending = [r for r in st.requirements if r.status == ApprovalStatus.NEEDS_CLARIFICATION and r.id not in asked]
        llm_q: dict[str, str] = {}
        if self.ctx.llm.available and pending:
            self.ctx.report(f"Wording {len(pending)} clarification questions with the language model")
            listing = "\n".join(f"{r.id}: {r.statement} | issues: " + "; ".join(i.detail for i in r.quality_issues) for r in pending)
            data = self.ctx.llm.json(
                "clarification_questions",
                "For each requirement, write ONE concise, specific clarification question a business stakeholder "
                "can answer, aimed at resolving the listed issues in a KYC onboarding context.",
                f"<untrusted_document id=\"pending\">\n{listing}\n</untrusted_document>", _Q_SCHEMA, effort="low")
            if data:
                llm_q = {q["requirement_id"]: q["question"] for q in data["questions"]}
        for r in pending:
            worst = max(r.quality_issues, key=lambda i: ["low", "medium", "high", "critical"].index(i.severity.value), default=None)
            role = _ROLE_FOR_ISSUE.get(worst.type, r.source_role) if worst else r.source_role
            st.questions.append(ClarificationQuestion(
                id=self.ctx.next_id("Q"), requirement_id=r.id, target_role=role or R.BUSINESS_ANALYST,
                question=llm_q.get(r.id) or self._template_question(r),
                reason=", ".join(sorted({i.type for i in r.quality_issues}))))
        for c in st.conflicts:
            if c.resolution is None and not any(q.requirement_id == c.id for q in st.questions):
                st.questions.append(ClarificationQuestion(
                    id=self.ctx.next_id("Q"), requirement_id=c.id, target_role=R.PRODUCT_OWNER,
                    question=f"{c.detail} Which should prevail, or what is the agreed compromise?",
                    reason=f"conflict:{c.type}"))
        for topic in self.ctx.stats.get("uncovered_topics", []):
            if not any(q.reason == f"coverage:{topic}" for q in st.questions):
                t = next(x for x in self.ctx.kb.interview["topics"] if x["id"] == topic)
                st.questions.append(ClarificationQuestion(
                    id=self.ctx.next_id("Q"), target_role=R.BUSINESS_ANALYST, question=t["question"],
                    reason=f"coverage:{topic}"))
        self.log("questions", "project", open=sum(1 for q in st.questions if q.answer is None))

    def apply_answer(self, qid: str, answer: str) -> Requirement | None:
        """Fold a stakeholder's answer into the requirement it clarifies (answer must be PII-masked)."""
        self.need("write:questions")
        st = self.ctx.state
        q = next(q for q in st.questions if q.id == qid)
        q.answer = answer
        r = st.req(q.requirement_id) if q.requirement_id else None
        self.log("answered", qid, requirement=q.requirement_id)
        if r is None:
            return None
        new = None
        if self.ctx.llm.available:
            data = self.ctx.llm.json(
                "apply_clarification",
                "Rewrite the requirement as ONE atomic, testable 'The system shall ...' statement that incorporates "
                "the stakeholder's clarification. Keep PII tokens unchanged. Set resolved=false if the answer does not "
                "resolve the issues.",
                f"Requirement {r.id}: {r.statement}\nIssues: {'; '.join(i.detail for i in r.quality_issues)}\n"
                f"<untrusted_document id=\"answer\">\n{answer}\n</untrusted_document>", _REWRITE_SCHEMA, effort="low")
            if data:
                new = data["statement"]
        if new is None:
            base = r.statement.rstrip(".")
            new = f"{base}, where: {answer.strip().rstrip('.')}."
        r.history.append({"event": "clarified", "question": qid, "before": r.statement})
        r.statement = new
        r.origin = "clarified" if r.origin == "extracted" else r.origin
        r.status = ApprovalStatus.MODIFIED
        return r
