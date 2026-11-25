"""Human-approval agent: routes critical decisions to authorised people and records outcomes."""
from __future__ import annotations

from typing import Any

from ..models import ApprovalItem, ApprovalStatus as S, Category as C, Level, StakeholderRole as R, utcnow
from ..security.rbac import GATE_APPROVERS, UNANIMOUS_GATES, PermissionDenied, can_approve
from .base import Agent

DECISIONS = {"approve": S.APPROVED, "reject": S.REJECTED, "modify": S.MODIFIED, "regenerate": S.REGENERATE}


class ApprovalAgent(Agent):
    name = "approval"
    description = "Creates approval items for mandatory human checkpoints and enforces RBAC on decisions."

    def _item(self, gate: str, subject: str, summary: str) -> None:
        st = self.ctx.state
        if any(a.gate == gate and a.subject_id == subject and a.status == S.PENDING_APPROVAL for a in st.approvals):
            return
        if any(a.gate == gate and a.subject_id == subject and a.status == S.APPROVED for a in st.approvals):
            return
        st.approvals.append(ApprovalItem(id=self.ctx.next_id("APR"), gate=gate, subject_id=subject, summary=summary,
                                         required_roles=sorted(GATE_APPROVERS[gate], key=lambda r: r.value)))

    def run(self) -> None:
        self.need("read:requirements", "write:approvals")
        st = self.ctx.state
        for m in st.compliance:
            if m.needs_legal_review:
                self._item("regulatory_interpretation", f"{m.requirement_id}:{m.control_id}",
                           f"Confirm that {m.requirement_id} satisfies {m.control_id} ({m.control}) under {m.jurisdiction}.")
        for r in st.requirements:
            if C.SECURITY in r.categories and r.risk_level in (Level.HIGH, Level.CRITICAL):
                self._item("high_risk_security", r.id, f"High-risk security requirement: {r.statement[:140]}")
            if r.categories and r.categories[0] in (C.INTEGRATION, C.PERFORMANCE, C.AVAILABILITY) and r.priority.value == "must":
                self._item("architecture", r.id, f"Architecture-critical requirement: {r.statement[:140]}")
        for c in st.conflicts:
            if c.type in ("contradiction", "regulatory") and c.resolution is None:
                self._item("conflict", c.id, c.detail)
        if st.sdlc:
            self._item("sdlc", "sdlc", f"Adopt {st.sdlc.selected} ({st.sdlc.ranked[0].score}%) as the project SDLC.")
        self._item("baseline", "baseline", f"Approve requirements baseline of {len(st.requirements)} requirements.")
        self.log("approvals_routed", "project", pending=sum(1 for a in st.approvals if a.status == S.PENDING_APPROVAL))

    def decide(self, item_id: str, user: str, role: R, decision: str, comment: str = "",
               modification: str | None = None) -> ApprovalItem:
        st = self.ctx.state
        item = next(a for a in st.approvals if a.id == item_id)
        if not can_approve(role, item.gate):
            self.ctx.audit.record(f"user:{user}", "approval_denied", item_id, role=role.value, gate=item.gate)
            raise PermissionDenied(f"role '{role.value}' may not decide gate '{item.gate}'")
        if decision not in DECISIONS:
            raise ValueError(f"decision must be one of {list(DECISIONS)}")
        if item.gate == "baseline" and decision == "approve" and not st.metrics.get("baseline_ready", False):
            failing = [k for k, v in st.metrics.get("gates", {}).items() if not v]
            raise PermissionDenied(f"baseline cannot be approved; failing quality gates: {failing}")
        item.decisions.append({"user": user, "role": role.value, "decision": decision, "comment": comment,
                               "modification": modification, "ts": utcnow()})
        outcome = DECISIONS[decision]
        if outcome == S.APPROVED and item.gate in UNANIMOUS_GATES:
            approved_roles = {R(d["role"]) for d in item.decisions if d["decision"] == "approve"}
            if not set(item.required_roles) <= approved_roles:
                outcome = S.PENDING_APPROVAL
        item.status = outcome
        self._apply(item, outcome, modification, user)
        self.ctx.audit.record(f"user:{user}", f"approval_{decision}", item_id, role=role.value, gate=item.gate,
                              approval_subject=item.subject_id, comment=comment, resulting_status=outcome.value)
        return item

    def _apply(self, item: ApprovalItem, outcome: S, modification: str | None, user: str) -> None:
        st = self.ctx.state
        subject = item.subject_id.split(":")[0]
        r = st.req(subject)
        if r is not None:
            if outcome == S.MODIFIED and modification:
                r.history.append({"event": "human_modified", "by": user, "before": r.statement})
                r.statement, r.origin = modification, "human"
            if outcome in (S.APPROVED, S.REJECTED, S.MODIFIED, S.REGENERATE):
                r.status = outcome
        c = next((c for c in st.conflicts if c.id == subject), None)
        if c is not None and outcome in (S.APPROVED, S.MODIFIED):
            c.resolution = item.decisions[-1]["comment"] or modification or "resolved by approver"
        if subject == "sdlc" and st.sdlc is not None:
            st.sdlc.status = outcome
        if subject == "baseline" and outcome == S.APPROVED:
            for req in st.requirements:
                if req.status in (S.PENDING_APPROVAL, S.MODIFIED):
                    req.status = S.APPROVED

    def summary(self) -> dict[str, Any]:
        st = self.ctx.state
        out: dict[str, Any] = {}
        for a in st.approvals:
            out.setdefault(a.gate, {"pending": 0, "approved": 0, "other": 0})
            key = "pending" if a.status == S.PENDING_APPROVAL else "approved" if a.status == S.APPROVED else "other"
            out[a.gate][key] += 1
        return out
