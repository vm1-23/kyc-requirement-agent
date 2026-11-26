"""Requirement-extraction agent.

Rule baseline: sentence-level detection of need statements (modal verbs and need
phrases), normalised to "The system shall ..." form, with the source excerpt kept
as evidence.

LLM mode: Claude extracts atomic requirements from each masked document. Every
extracted item must quote a `source_excerpt` that appears in the document. Items
that do not are counted as hallucinations and dropped.
"""
from __future__ import annotations

import re

from ..models import Evidence, Priority, Requirement, SourceDocument
from .base import Agent, jaccard, sentences

NEED = re.compile(
    r"\b(shall|must|should|need(s|ed)? to|needs?|required?|requires|has to|have to|want(s)?|expect(s)?|"
    r"cannot|can't|must not|mustn't|never|always|at least|at most|no more than|within|mandatory|"
    r"is not allowed|are not allowed|not permitted|ensure|has to be|important that|would like)\b",
    re.I,
)
SPEAKER = re.compile(r"^\s*(?:[A-Z][\w .()'-]{0,40}):\s+")
HEADER = re.compile(r"^(subject|from|to|cc|date|re|interviewer|regards|note|recommendation)\b", re.I)
NOT_REQ = re.compile(r"^(hi|hello|thanks|thank you|ok|okay|yes|no|sure|great|regards|best)\b|\?\s*$", re.I)
CONTEXT_ONLY = re.compile(r"^(today|currently|at the moment|right now|last (year|quarter|month)|we (had|saw|used))\b", re.I)

_LEADS = [
    (re.compile(r"^(?:we|i|the bank|the business|compliance|security|operations|ops|product)\s+(?:also\s+|really\s+)?"
                r"(?:need|needs|want|wants|require|requires|expect|expects|would like)\s+(?:the\s+(?:system|app|platform|solution)\s+)?to\s+", re.I),
     "The system shall "),
    (re.compile(r"^(?:the\s+)?(?:system|app|application|platform|solution|portal)\s+(?:must|shall|should|needs to|has to|will)\s+", re.I),
     "The system shall "),
    (re.compile(r"^(?:it|this)\s+(?:must|should|needs to|has to)\s+", re.I), "The system shall "),
]

_EXTRACT_SCHEMA = {
    "type": "object",
    "properties": {
        "requirements": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "statement": {"type": "string", "description": "Atomic, testable 'The system shall ...' statement"},
                    "source_excerpt": {"type": "string", "description": "Verbatim span from the document"},
                    "kind": {"type": "string", "enum": ["functional", "non_functional", "business", "constraint"]},
                    "priority": {"type": "string", "enum": ["must", "should", "could", "wont"]},
                    "business_justification": {"type": "string"},
                },
                "required": ["statement", "source_excerpt", "kind", "priority", "business_justification"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["requirements"],
    "additionalProperties": False,
}


def normalise(sentence: str) -> str:
    s = sentence.strip().rstrip(".").strip()
    for rx, rep in _LEADS:
        if rx.search(s):
            s = rx.sub(rep, s, count=1)
            break
    s = s[0].upper() + s[1:] if s else s
    return s + "."


def priority_of(text: str) -> Priority:
    low = text.lower()
    if re.search(r"\b(could|nice to have|would like|optional|ideally|maybe)\b", low):
        return Priority.COULD
    if re.search(r"\b(must|shall|mandatory|required|cannot|never|always|regulat|law|not allowed|not permitted)\b", low):
        return Priority.MUST
    if re.search(r"\b(won'?t|out of scope|not in scope|phase 2)\b", low):
        return Priority.WONT
    return Priority.SHOULD


def _norm_ws(s: str) -> str:
    return re.sub(r"\s+", " ", s.lower()).strip(" .")


class ExtractionAgent(Agent):
    name = "extraction"
    description = "Extracts candidate requirements from masked conversations and documents."

    def run(self) -> None:
        self.need("read:masked_text", "write:requirements")
        docs = [d for d in self.ctx.state.documents if d.masked_text]
        for i, doc in enumerate(docs, 1):
            self.ctx.report(f"Reading {doc.id} “{doc.title}” ({i} of {len(docs)})"
                            + (" with the language model" if self.ctx.llm.available else ""))
            items = self._llm_extract(doc) if self.ctx.llm.available else None
            if items is None:
                items = self._rule_extract(doc)
            for r in items:
                self._add(r)
        self.log("extracted", "project", count=len(self.ctx.state.requirements),
                 mode="llm" if self.ctx.llm.available else "rules")

    def _add(self, r: Requirement) -> None:
        for existing in self.ctx.state.requirements:
            if _norm_ws(existing.statement) == _norm_ws(r.statement):
                existing.evidence.extend(r.evidence)  # same need, more sources
                return
        self.ctx.state.requirements.append(r)

    def _new(self, doc: SourceDocument, statement: str, excerpt: str, **kw) -> Requirement:
        return Requirement(
            id=self.ctx.next_id("TMP"), statement=statement,
            source_stakeholder=doc.stakeholder, source_role=doc.role,
            evidence=[Evidence(doc_id=doc.id, excerpt=excerpt, stakeholder=doc.stakeholder)],
            **kw)

    def _rule_extract(self, doc: SourceDocument) -> list[Requirement]:
        out = []
        for s in sentences(doc.masked_text):
            if re.match(r"^\s*(interviewer|subject|from|to|cc|date)\s*:", s, re.I) or s.rstrip().endswith("?"):
                continue
            s = SPEAKER.sub("", s, count=1).strip()
            if NOT_REQ.search(s) or CONTEXT_ONLY.search(s) or not NEED.search(s) or len(s.split()) < 5:
                continue
            out.append(self._new(doc, normalise(s), s, priority=priority_of(s), confidence=0.6,
                                 business_justification=f"Stated by {doc.stakeholder or doc.type.value} in {doc.title}."))
        return out

    def _llm_extract(self, doc: SourceDocument) -> list[Requirement] | None:
        from ..security.injection import wrap_untrusted

        data = self.ctx.llm.json(
            "extract_requirements",
            "Extract every distinct software requirement stated or clearly implied in the document. "
            "Split compound statements into atomic requirements. Do not add requirements that the "
            "document does not support. Each item must quote its source_excerpt verbatim from the document. "
            "Skip background facts, greetings and questions.",
            f"Stakeholder: {doc.stakeholder} (role: {doc.role.value if doc.role else 'unknown'}); "
            f"document type: {doc.type.value}\n\n{wrap_untrusted(doc.id, doc.masked_text)}",
            _EXTRACT_SCHEMA)
        if data is None:
            return None
        out, source = [], _norm_ws(doc.masked_text)
        for item in data["requirements"]:
            ex = _norm_ws(item["source_excerpt"])
            grounded = ex and (ex in source or max((jaccard(ex, s) for s in sentences(doc.masked_text)), default=0) >= 0.6)
            if not grounded:
                self.ctx.bump("hallucinated_extractions")
                self.log("dropped_ungrounded", doc.id, statement=item["statement"][:200])
                continue
            self.ctx.bump("llm_extractions")
            out.append(self._new(doc, item["statement"], item["source_excerpt"], kind=item["kind"],
                                 priority=Priority(item["priority"]), confidence=0.8,
                                 business_justification=item["business_justification"]))
        return out
