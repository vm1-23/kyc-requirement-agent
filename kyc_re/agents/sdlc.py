"""SDLC selection agent."""
from __future__ import annotations

from ..models import SDLCRecommendation
from ..sdlc.engine import extract_factors, score_models
from ..sdlc.workflow import build_workflow
from .base import Agent

_EXPLAIN_SCHEMA = {
    "type": "object",
    "properties": {"explanation": {"type": "string"}},
    "required": ["explanation"],
    "additionalProperties": False,
}


class SDLCAgent(Agent):
    name = "sdlc"
    description = "Derives decision factors and recommends a ranked, justified SDLC model and workflow."

    def run(self) -> None:
        self.need("read:requirements", "read:risks", "read:project", "read:kb", "write:sdlc")
        st = self.ctx.state
        factors = extract_factors(st)
        ranked = score_models(factors, self.ctx.kb.sdlc_models)
        top = ranked[0]
        explanation = self._template_explanation(factors, ranked)
        if self.ctx.llm.available:
            data = self.ctx.llm.json(
                "sdlc_explanation",
                "Write a concise (120-180 words) justification for the top-ranked SDLC model for this KYC project, "
                "referring ONLY to the provided factor scores and engine reasons. Do not change the ranking.",
                "Factors:\n" + "\n".join(f"- {f.name}: {f.score}/5 ({f.rationale})" for f in factors)
                + "\n\nRanking:\n" + "\n".join(f"- {o.model}: {o.score}% | {'; '.join(o.reasons)}" for o in ranked[:3]),
                _EXPLAIN_SCHEMA, effort="low")
            if data:
                explanation = data["explanation"]
        st.sdlc = SDLCRecommendation(factors=factors, ranked=ranked, selected=top.model, explanation=explanation,
                                     workflow=build_workflow(top.model, st))
        self.log("sdlc_recommended", "sdlc", ranked=[(o.model, o.score) for o in ranked[:3]])

    @staticmethod
    def _template_explanation(factors, ranked) -> str:
        fv = {f.name: f.score for f in factors}
        top, second = ranked[0], ranked[1]
        hi = [k.replace("_", " ") for k, v in sorted(fv.items(), key=lambda x: -x[1]) if v >= 4][:5]
        lo = [k.replace("_", " ") for k, v in fv.items() if v <= 2][:3]
        txt = (f"{top.model} ranks first ({top.score}%) ahead of {second.model} ({second.score}%). "
               f"The project scores high on {', '.join(hi) or 'no single dominant factor'}"
               + (f" and low on {', '.join(lo)}" if lo else "") + ". ")
        if top.reasons:
            txt += "Engine reasons: " + "; ".join(top.reasons[:3]) + ". "
        txt += ("This is a recommendation; the project manager, architect, security lead and compliance officer "
                "must jointly approve the final SDLC choice.")
        return txt
