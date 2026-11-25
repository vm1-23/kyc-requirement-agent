"""Security gate: classify and mask sensitive data, screen and quarantine injected text."""
from __future__ import annotations

from ..models import SourceDocument
from ..security import injection
from ..security.pii import classify_sensitivity
from .base import Agent, sentences


class IngestionAgent(Agent):
    name = "interaction"  # runs under the interaction agent's scopes
    description = "Masks PII and quarantines prompt-injection content before any agent or LLM sees it."

    def ingest(self, doc: SourceDocument) -> SourceDocument:
        self.need("read:masked_text", "write:documents")
        masked, findings = self.ctx.masker.mask(doc.text)
        doc.pii_findings = [f.as_dict() for f in findings]
        kept, quarantined = [], []
        for s in sentences(masked):
            flags = injection.scan(s)
            if flags:
                quarantined.append(s)
                doc.injection_flags.extend(f for f in flags if f not in doc.injection_flags)
            else:
                kept.append(s)
        doc.masked_text = "\n".join(kept)
        doc.quarantined = bool(quarantined)
        if quarantined:
            self.ctx.state.open_issues.append(
                f"{doc.id}: {len(quarantined)} sentence(s) quarantined for suspected prompt injection "
                f"({', '.join(doc.injection_flags)}); a human should review the source.")
        self.log("ingest", doc.id, type=doc.type.value, stakeholder=doc.stakeholder,
                 sensitivity=classify_sensitivity(findings), pii_types=sorted({f.type for f in findings}),
                 injection_flags=doc.injection_flags, quarantined_sentences=len(quarantined))
        self.ctx.bump("pii_masked", len(findings))
        self.ctx.bump("injection_quarantined", len(quarantined))
        return doc

    def run(self) -> None:
        for d in self.ctx.state.documents:
            if not d.masked_text:
                self.ingest(d)
