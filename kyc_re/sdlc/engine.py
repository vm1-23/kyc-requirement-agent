"""SDLC selection engine: decision factors -> hard rules + MCDA -> ranked recommendations.

The engine is deterministic and explainable. An LLM (if configured) only writes the
narrative explanation; it never changes scores.
"""
from __future__ import annotations

import re
from typing import Any

from ..models import Category as C, Level, ProjectState, SDLCFactor, SDLCOption

FACTORS = [
    "requirement_stability", "regulatory_criticality", "security_risk", "complexity", "system_size",
    "legacy_dependence", "change_frequency", "continuous_delivery_need", "stakeholder_availability",
    "documentation_need", "budget_schedule_pressure", "formal_verification_need", "failure_consequence",
    "technical_uncertainty",
]


def _clamp(x: float) -> int:
    return int(max(1, min(5, round(x))))


def _count(rx: str, text: str) -> int:
    return len(re.findall(rx, text, re.I))


def extract_factors(st: ProjectState) -> list[SDLCFactor]:
    reqs = st.requirements
    n = max(len(reqs), 1)
    corpus = " ".join(d.masked_text for d in st.documents) + " " + " ".join(r.statement for r in reqs)
    low = corpus.lower()
    f: dict[str, tuple[int, str]] = {}

    contradictions = sum(1 for c in st.conflicts if c.type in ("contradiction", "regulatory"))
    ambiguous = sum(1 for r in reqs if any(i.type in ("ambiguity", "incompleteness", "untestable") for i in r.quality_issues))
    volatile = _count(r"\b(tbd|to be decided|may change|might change|evolving|not sure|phase 2|later|pilot|experiment|iterate|feedback)\b", low)
    instability = contradictions * 0.5 + ambiguous / n * 5 + volatile * 0.3
    f["requirement_stability"] = (_clamp(5 - instability),
                                  f"{contradictions} contradictions, {ambiguous}/{n} ambiguous or incomplete requirements, {volatile} volatility cues.")

    reg_share = sum(1 for r in reqs if C.REGULATORY in r.categories) / n
    crit_controls = sum(1 for c in st.coverage if c.mandatory)
    f["regulatory_criticality"] = (_clamp(2 + reg_share * 4 + (1 if crit_controls >= 10 else 0)),
                                   f"{reg_share:.0%} of requirements are regulatory; {crit_controls} mandatory KYC controls apply.")

    restricted = sum(1 for d in st.documents for p in d.pii_findings if p["sensitivity"] == "restricted")
    sec_share = sum(1 for r in reqs if C.SECURITY in r.categories or C.PRIVACY in r.categories) / n
    biometric = bool(re.search(r"biometric|selfie|liveness|face|video", low))
    f["security_risk"] = (_clamp(2 + sec_share * 3 + (1 if biometric else 0) + (0.5 if restricted else 0) + 0.5),
                          f"{sec_share:.0%} security/privacy requirements; biometric processing={'yes' if biometric else 'no'}; restricted identity data in scope.")

    integrations = len(set(re.findall(r"\b(core banking|cbs|crm|ckyc\w*|digilocker|uidai|sanctions? (?:vendor|provider|list)|screening vendor|e-?sign|credit bureau|aml system|video kyc vendor|payment gateway)\b", low)))
    cats = len({c for r in reqs for c in r.categories})
    f["complexity"] = (_clamp(1 + integrations * 0.6 + cats * 0.2 + n / 40),
                       f"{integrations} external integrations, {cats} requirement dimensions, {n} requirements.")
    f["system_size"] = (_clamp(1 + n / 15), f"{n} requirements across {len(st.documents)} sources.")

    legacy = _count(r"\b(legacy|core banking|cbs|mainframe|batch|cobol|existing system)\b", low) + 2 * len(st.project.legacy_systems)
    f["legacy_dependence"] = (_clamp(1 + legacy * 0.5), f"{legacy} legacy-dependency signals; declared legacy systems: {', '.join(st.project.legacy_systems) or 'none'}.")

    change = _count(r"\b(frequent(ly)?|regular(ly)? (update|change)|regulatory changes?|new circular|change requests?|iterat\w*|a/b|experiment\w*|evolv\w*|monthly releases?|every sprint|competitor)\b", low)
    f["change_frequency"] = (_clamp(2 + change * 0.6 + (1 if reg_share > 0.3 else 0)),
                             f"{change} change-frequency cues; regulatory content changes with new circulars.")

    cd = _count(r"\b(continuous(ly)? (deliver|deploy)\w*|ci/?cd|devops|release (every|weekly|fortnightly)|weekly releases?|frequent releases?|zero[- ]downtime|feature flags?|hotfix)\b", low)
    f["continuous_delivery_need"] = (_clamp(2 + cd * 0.8), f"{cd} continuous-delivery cues.")

    stakeholders = len({d.stakeholder for d in st.documents if d.stakeholder})
    unavailable = _count(r"\b(limited availability|not available|busy|hard to reach|only available)\b", low)
    f["stakeholder_availability"] = (_clamp(2 + stakeholders * 0.4 - unavailable), f"{stakeholders} distinct stakeholders contributed input; {unavailable} availability constraints mentioned.")

    audit = sum(1 for r in reqs if C.AUDIT in r.categories)
    f["documentation_need"] = (_clamp(2 + reg_share * 3 + audit / n * 3 + (1 if re.search(r"audit|inspection|regulator", low) else 0)),
                               f"Regulator inspection and audit evidence required; {audit} audit/reporting requirements.")

    months = st.project.timeline_months
    deadline = _count(r"\b(deadline|asap|urgent|by (q[1-4]|january|february|march|april|may|june|july|august|september|october|november|december)|go-?live)\b", low)
    budget = {"low": 1.0, "medium": 0.0, "high": -1.0}.get(st.project.budget_flexibility, 0.0)
    f["budget_schedule_pressure"] = (_clamp(2 + (2 if months and months <= 4 else 1 if months and months <= 8 else 0) + deadline * 0.4 + budget),
                                     f"Timeline {months or 'unspecified'} months; {deadline} deadline cues; budget flexibility {st.project.budget_flexibility}.")

    formal = _count(r"\b(certif\w*|validated|validation|independent (testing|audit)|regulator(y)? (approval|inspection)|v-?cip|accredit\w*|penetration test|traceab\w*|sign-?off)\b", low)
    f["formal_verification_need"] = (_clamp(2 + formal * 0.4 + (1 if f["regulatory_criticality"][0] >= 4 else 0)),
                                     f"{formal} formal verification/certification cues; regulatory criticality {f['regulatory_criticality'][0]}.")

    crit = sum(1 for r in reqs if r.risk_level in (Level.HIGH, Level.CRITICAL)) / n
    f["failure_consequence"] = (_clamp(3 + crit * 2 + (1 if re.search(r"penalt|fine|licen[cs]e|money laundering|terroris", low) else 0)),
                                f"{crit:.0%} high/critical-risk requirements; failures expose the firm to AML penalties and licence risk.")

    novel = _count(r"\b(ai|machine learning|ml model|llm|deepfake|biometric|liveness|new vendor|first time|proof of concept|poc|unproven|novel)\b", low)
    open_q = sum(1 for q in st.questions if q.answer is None)
    f["technical_uncertainty"] = (_clamp(1 + novel * 0.4 + open_q / 10), f"{novel} novel-technology cues; {open_q} open clarification questions.")

    return [SDLCFactor(name=k, score=v[0], rationale=v[1]) for k, v in f.items()]


def score_models(factors: list[SDLCFactor], models: dict[str, Any]) -> list[SDLCOption]:
    fv = {f.name: f.score for f in factors}
    ranked = []
    for name, spec in models.items():
        num = den = 0.0
        fits, misfits = [], []
        for factor, (target, weight) in spec["profile"].items():
            v = fv.get(factor, 3)
            closeness = 1 - abs(v - target) / 4
            num += weight * closeness
            den += weight
            if weight >= 2 and closeness >= 0.75:
                fits.append(f"{factor.replace('_', ' ')} = {v} (ideal {target})")
            elif weight >= 2 and closeness <= 0.25:
                misfits.append(f"{factor.replace('_', ' ')} = {v} vs ideal {target}")
        score = 100 * num / den
        adj = []
        # Hard rules (domain heuristics from the problem statement).
        if fv["regulatory_criticality"] >= 4 and fv["change_frequency"] >= 4 and name.startswith("Hybrid"):
            score += 5; adj.append("+5: high regulation with evolving requirements favours a regulated hybrid")
        if fv["formal_verification_need"] >= 4 and name == "Agile (Scrum)":
            score -= 10; adj.append("-10: pure Agile lacks formal verification gates")
        if fv["continuous_delivery_need"] >= 4 and name in ("Waterfall", "V-Model"):
            score -= 10; adj.append("-10: sequential model conflicts with continuous delivery")
        if fv["requirement_stability"] <= 2 and name == "Waterfall":
            score -= 15; adj.append("-15: unstable requirements make a fixed baseline risky")
        if fv["security_risk"] >= 4 and name in ("Agile (Scrum)", "Waterfall"):
            score -= 5; adj.append("-5: no built-in security activities for a high-risk system")
        if fv["technical_uncertainty"] >= 4 and name == "Spiral":
            score += 5; adj.append("+5: high technical uncertainty favours risk-driven cycles")
        reasons = ([f"Fits: {', '.join(fits)}"] if fits else []) + ([f"Misfits: {', '.join(misfits)}"] if misfits else []) + adj
        ranked.append(SDLCOption(model=name, score=round(max(0, min(100, score)), 1), reasons=reasons))
    ranked.sort(key=lambda o: -o.score)
    return ranked
