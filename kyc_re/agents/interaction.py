"""Stakeholder-interaction agent: adaptive, role-aware interviews.

The agent tracks which interview topics a stakeholder's answers already cover and
asks about the most relevant uncovered topic for that role. A vague, very short or
evasive answer gets a targeted follow-up before the interview moves on.
"""
from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field

from ..models import SourceDocument, SourceType, StakeholderRole
from .base import Agent


class InterviewTurn(BaseModel):
    topic: str
    question: str
    answer: str = ""
    followup: bool = False


class InterviewSession(BaseModel):
    id: str
    stakeholder: str
    role: StakeholderRole
    turns: list[InterviewTurn] = Field(default_factory=list)
    done: bool = False


_FOLLOWUP_SCHEMA = {
    "type": "object",
    "properties": {
        "needs_followup": {"type": "boolean"},
        "question": {"type": "string"},
    },
    "required": ["needs_followup", "question"],
    "additionalProperties": False,
}


class InteractionAgent(Agent):
    name = "interaction"
    description = "Conducts adaptive interviews using role-specific templates."
    MAX_TURNS = 14

    @property
    def topics(self) -> list[dict[str, Any]]:
        return self.ctx.kb.interview["topics"]

    def covered_topics(self, text: str) -> set[str]:
        low = text.lower()
        return {t["id"] for t in self.topics if sum(s in low for s in t["signals"]) >= 2}

    def vague_terms(self, text: str) -> list[str]:
        low = text.lower()
        return [v for v in self.ctx.kb.interview["vague_terms"] if re.search(rf"\b{re.escape(v)}\b", low)]

    def template_for(self, role: StakeholderRole) -> list[dict[str, Any]]:
        focus = self.ctx.kb.interview["role_focus"].get(role.value, [])
        by_id = {t["id"]: t for t in self.topics}
        ordered = [by_id[f] for f in focus] + [t for t in self.topics if t["id"] not in focus]
        return ordered

    def start(self, session_id: str, stakeholder: str, role: StakeholderRole) -> InterviewSession:
        self.need("read:templates")
        s = InterviewSession(id=session_id, stakeholder=stakeholder, role=role)
        first = self.template_for(role)[0]
        s.turns.append(InterviewTurn(topic=first["id"], question=first["question"]))
        self.log("interview_start", session_id, role=role.value)
        return s

    def answer(self, s: InterviewSession, answer: str) -> InterviewSession:
        """Record an answer (already PII-masked by the caller) and choose the next question."""
        turn = s.turns[-1]
        turn.answer = answer
        if len(s.turns) >= self.MAX_TURNS:
            s.done = True
            return s
        nxt = self._followup(turn) if not turn.followup else None
        if nxt:
            s.turns.append(nxt)
            return s
        asked = {t.topic for t in s.turns}
        covered = self.covered_topics(" ".join(t.answer for t in s.turns))
        focus = self.ctx.kb.interview["role_focus"].get(s.role.value, [])
        for t in self.template_for(s.role):
            if t["id"] in asked or (t["id"] in covered and t["id"] not in focus):
                continue
            s.turns.append(InterviewTurn(topic=t["id"], question=t["question"]))
            return s
        s.done = True
        return s

    def _followup(self, turn: InterviewTurn) -> InterviewTurn | None:
        topic = next(t for t in self.topics if t["id"] == turn.topic)
        if self.ctx.llm.available:
            out = self.ctx.llm.json(
                "interview_followup",
                "Decide whether the stakeholder's answer is specific, measurable and complete enough "
                "to write testable requirements. If not, write ONE short follow-up question.",
                f"Topic: {topic['title']}\nQuestion: {turn.question}\nAnswer:\n<untrusted_document id=\"answer\">\n"
                f"{turn.answer}\n</untrusted_document>",
                _FOLLOWUP_SCHEMA, effort="low", max_tokens=2000)
            if out is not None:
                return InterviewTurn(topic=turn.topic, question=out["question"], followup=True) if out["needs_followup"] else None
        vague = self.vague_terms(turn.answer)
        if len(turn.answer.split()) < 6 or re.search(r"\b(not sure|don'?t know|tbd|later|depends)\b", turn.answer, re.I):
            return InterviewTurn(topic=turn.topic, question=topic["followup"], followup=True)
        if vague:
            return InterviewTurn(topic=turn.topic, followup=True,
                                 question=f"You used the term(s) {', '.join(repr(v) for v in vague[:3])}. "
                                          "Can you quantify them as a measurable target, threshold or example?")
        return None

    def to_document(self, s: InterviewSession, doc_id: str) -> SourceDocument:
        self.need("write:documents")
        text = "\n".join(t.answer for t in s.turns if t.answer)
        return SourceDocument(id=doc_id, title=f"Interview - {s.stakeholder} ({s.role.value})",
                              type=SourceType.CONVERSATION, stakeholder=s.stakeholder, role=s.role, text=text)

    def coverage_gaps(self) -> list[dict[str, Any]]:
        """Interview topics no ingested input covers, so the clarification agent can ask about them."""
        all_text = " ".join(d.masked_text for d in self.ctx.state.documents)
        covered = self.covered_topics(all_text)
        return [t for t in self.topics if t["id"] not in covered]

    def run(self) -> None:
        gaps = self.coverage_gaps()
        self.ctx.stats["uncovered_topics"] = [g["id"] for g in gaps]
        self.log("topic_coverage", "project", uncovered=[g["id"] for g in gaps])
