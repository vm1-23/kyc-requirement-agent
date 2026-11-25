"""Artefact writers: SRS (.docx), RTM / compliance matrix / risk register (.csv), Markdown and JSON."""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt, RGBColor

from ..models import Category as C, ProjectState

if TYPE_CHECKING:
    from ..agents.base import Context

DISCLAIMER = ("AI-assisted draft. Regulatory references are paraphrased knowledge-base summaries and must be verified "
              "against official texts. Regulatory interpretation, requirement approval and SDLC adoption remain the "
              "responsibility of authorised human stakeholders.")

EXTERNAL_DEPS = {
    r"core banking|cbs": "Core banking system (account creation)",
    r"ckyc|central kyc|cersai": "Central KYC Records Registry",
    r"digilocker": "DigiLocker document fetch",
    r"uidai|aadhaar|<aadhaar": "Aadhaar e-KYC / authentication service",
    r"sanction|watch ?list|pep|screen": "Sanctions/PEP screening data provider",
    r"video|v-?cip": "Video KYC platform",
    r"liveness|face match|selfie": "Liveness / face-match engine",
    r"crm": "CRM",
    r"sms|otp": "SMS/OTP gateway",
    r"e-?sign": "e-Sign provider",
}


def assumptions_and_dependencies(st: ProjectState) -> tuple[list[str], list[str]]:
    corpus = " ".join(r.statement for r in st.requirements).lower() + " " + " ".join(d.masked_text for d in st.documents).lower()
    deps = [v for k, v in EXTERNAL_DEPS.items() if re.search(k, corpus)] + [f"Legacy system: {s}" for s in st.project.legacy_systems]
    assumptions = [
        f"Applicable jurisdictions are {', '.join(st.project.jurisdictions)}; customers outside them are out of scope.",
        "Regulatory knowledge base version is current at the time of baseline; regulatory change triggers re-analysis.",
        "Verification and screening vendors provide contractual SLAs and audit rights.",
        "Derived control requirements are valid only after compliance confirms applicability.",
    ] + [a for r in st.requirements for a in r.assumptions]
    return assumptions, deps


def _rtm_rows(st: ProjectState, stories: list[dict[str, Any]], use_cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    story_by_req = {s["requirement_id"]: s["id"] for s in stories}
    rows = []
    for r in st.requirements:
        rows.append({
            "requirement_id": r.id,
            "statement": r.statement,
            "categories": ";".join(c.value for c in r.categories),
            "priority": r.priority.value,
            "origin": r.origin,
            "source_stakeholder": r.source_stakeholder or "",
            "source_documents": ";".join(sorted({e.doc_id for e in r.evidence})),
            "source_excerpt": (r.evidence[0].excerpt[:200] if r.evidence else ""),
            "regulations": ";".join(c.kb_id for c in r.regulations),
            "controls": ";".join(r.controls),
            "user_story": story_by_req.get(r.id, ""),
            "use_cases": ";".join(u["id"] for u in use_cases if r.id in u["requirements"]),
            "test_cases": ";".join(f"TC-{r.id}-{i + 1}" for i in range(len(r.acceptance_criteria))),
            "risks": ";".join(x.id for x in st.risks if r.id in x.linked_requirements),
            "risk_level": r.risk_level.value,
            "confidence": r.confidence,
            "status": r.status.value,
        })
    return rows


def _csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", newline="") as fh:
        if not rows:
            fh.write("")
            return
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


USABLE_WIDTH_IN = 7.3  # letter page with 0.6" margins


def _auto_widths(headers: list[str], rows: list[list[Any]]) -> list[float]:
    """Column widths proportional to (capped) typical content length, with a readable minimum."""
    n = len(headers)
    weights = []
    for i in range(n):
        lens = sorted(len(str(r[i])) for r in rows) or [0]
        typical = lens[int(len(lens) * 0.8)] if lens else 0
        weights.append(max(len(headers[i]), min(typical, 220)) ** 0.8 + 4)
    total = sum(weights)
    mins = []
    for i in range(n):  # short identifier columns must not wrap
        longest = max([len(str(r[i])) for r in rows] + [len(headers[i])])
        mins.append(max(0.55, 0.075 * longest + 0.15) if longest <= 16 else 0.55)
    widths = [max(m, USABLE_WIDTH_IN * w / total) for m, w in zip(mins, weights)]
    scale = USABLE_WIDTH_IN / sum(widths)
    return [w * scale for w in widths]


def _table(doc, headers: list[str], rows: list[list[Any]], widths: list[float] | None = None) -> None:
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = "Light Grid Accent 1"
    t.autofit = False
    widths = widths or _auto_widths(headers, rows)
    for i, h in enumerate(headers):
        cell = t.rows[0].cells[i]
        cell.text = h
        for p in cell.paragraphs:
            for run in p.runs:
                run.bold = True
                run.font.size = Pt(8.5)
    for row in rows:
        cells = t.add_row().cells
        for i, v in enumerate(row):
            cells[i].text = str(v)
            for p in cells[i].paragraphs:
                for run in p.runs:
                    run.font.size = Pt(8.5)
    for i, w in enumerate(widths):
        t.columns[i].width = Inches(w)  # grid columns (used by LibreOffice / Google Docs)
    for r in t.rows:
        for i, w in enumerate(widths):
            r.cells[i].width = Inches(w)  # cell widths (used by Word)


def write_srs(ctx: "Context", path: Path, stories: list[dict[str, Any]], use_cases: list[dict[str, Any]]) -> None:
    st, kb = ctx.state, ctx.kb
    doc = Document()
    for sec in doc.sections:
        sec.left_margin = sec.right_margin = Inches(0.6)
        sec.top_margin = sec.bottom_margin = Inches(0.7)
    doc.styles["Normal"].font.name = "Calibri"
    doc.styles["Normal"].font.size = Pt(10)
    title = doc.add_heading(f"Software Requirements Specification\n{st.project.name}", 0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    meta = doc.add_paragraph()
    meta.add_run(f"Domain: Customer onboarding & KYC | Jurisdictions: {', '.join(st.project.jurisdictions)} | "
                 f"Knowledge base: v{kb.version} | Generated by: {ctx.llm.name} + rule engines | Created: {st.created_at}").italic = True
    warn = doc.add_paragraph()
    r = warn.add_run(DISCLAIMER)
    r.font.color.rgb = RGBColor(0x9C, 0x27, 0x06)
    r.font.size = Pt(9)

    doc.add_heading("1. Introduction", 1)
    doc.add_heading("1.1 Purpose", 2)
    doc.add_paragraph("This SRS specifies the requirements for the digital customer onboarding and KYC platform. It was "
                      "elicited from stakeholder conversations and documents by a multi-agent requirement-engineering "
                      "system, grounded in an approved regulatory knowledge base, and subject to human approval.")
    doc.add_heading("1.2 Scope", 2)
    doc.add_paragraph(st.project.description or "Digital onboarding, identity verification, screening, risk rating, "
                      "enhanced due diligence, record keeping and periodic re-KYC.")
    if st.project.channels or st.project.customer_types:
        doc.add_paragraph(f"Channels: {', '.join(st.project.channels) or 'n/a'}. Customer types: {', '.join(st.project.customer_types) or 'n/a'}.")
    doc.add_heading("1.3 Definitions", 2)
    _table(doc, ["Term", "Definition"], [[k, v] for k, v in kb.glossary.items()])
    doc.add_heading("1.4 References", 2)
    cited = sorted({c.kb_id for r_ in st.requirements for c in r_.regulations})
    _table(doc, ["KB id", "Title", "Source", "Jurisdiction", "Version", "Effective"],
           [[i, kb.get(i).title, kb.get(i).source, kb.get(i).jurisdiction, kb.get(i).version, kb.get(i).effective_date] for i in cited if kb.get(i)])

    doc.add_heading("2. Overall description", 1)
    doc.add_heading("2.1 Stakeholders and sources", 2)
    _table(doc, ["Source", "Type", "Stakeholder", "Role", "PII masked", "Injection flags"],
           [[d.id, d.type.value, d.stakeholder, d.role.value if d.role else "", len(d.pii_findings), ", ".join(d.injection_flags) or "-"] for d in st.documents])
    assumptions, deps = assumptions_and_dependencies(st)
    doc.add_heading("2.2 Assumptions", 2)
    for a in assumptions:
        doc.add_paragraph(a, style="List Bullet")
    doc.add_heading("2.3 Dependencies", 2)
    for d in deps:
        doc.add_paragraph(d, style="List Bullet")

    doc.add_heading("3. Specific requirements", 1)
    section = 1
    for cat in [C.FUNCTIONAL, C.REGULATORY, C.SECURITY, C.PRIVACY, C.DATA, C.INTEGRATION, C.PERFORMANCE,
                C.AVAILABILITY, C.USABILITY, C.AUDIT, C.OPERATIONAL, C.BUSINESS, C.STAKEHOLDER]:
        reqs = [x for x in st.requirements if x.categories and x.categories[0] == cat]
        if not reqs:
            continue
        doc.add_heading(f"3.{section} {cat.value.replace('_', ' ').title()} requirements", 2)
        section += 1
        _table(doc, ["ID", "Requirement", "Pri.", "Source", "Regulations", "Risk", "Conf.", "Status"],
               [[x.id, x.statement, x.priority.value, x.source_stakeholder or x.origin, ", ".join(c.kb_id for c in x.regulations) or "-",
                 x.risk_level.value, f"{x.confidence:.2f}", x.status.value] for x in reqs])
        for x in reqs:
            p = doc.add_paragraph()
            p.add_run(f"{x.id} acceptance criteria").bold = True
            for ac in x.acceptance_criteria:
                doc.add_paragraph(ac, style="List Bullet")
            if x.quality_issues:
                p = doc.add_paragraph()
                p.add_run("Open quality issues: ").italic = True
                p.add_run("; ".join(f"[{i.type}] {i.detail}" for i in x.quality_issues))

    doc.add_heading("4. Use cases", 1)
    for uc in use_cases:
        doc.add_heading(f"{uc['id']} {uc['name']}", 2)
        doc.add_paragraph(f"Primary actor: {uc['actor']}")
        doc.add_paragraph("Preconditions: " + "; ".join(uc["pre"]))
        doc.add_paragraph("Main success scenario:")
        for i, s in enumerate(uc["main"], 1):
            doc.add_paragraph(f"{i}. {s}")
        doc.add_paragraph("Alternate flows: " + " | ".join(uc["alt"]))
        doc.add_paragraph("Postconditions: " + "; ".join(uc["post"]))
        doc.add_paragraph("Linked requirements: " + (", ".join(uc["requirements"]) or "-"))

    doc.add_heading("5. User stories", 1)
    for s in stories:
        doc.add_paragraph(f"{s['id']}: {s['story']}", style="List Bullet")

    doc.add_heading("6. Compliance-control matrix", 1)
    _table(doc, ["Control", "Title", "Mandatory", "Status", "Covered by"],
           [[c.control_id, c.title, "yes" if c.mandatory else "no", c.status, ", ".join(c.covered_by) or "-"] for c in st.coverage])
    doc.add_paragraph()
    _table(doc, ["Requirement", "Control", "Citations", "Obligation", "Gap", "Legal review", "Conf."],
           [[m.requirement_id, m.control_id, ", ".join(c.kb_id for c in m.citations), m.obligation[:160],
             "YES" if m.gap else "", "yes" if m.needs_legal_review else "", f"{m.confidence:.2f}"] for m in st.compliance])

    doc.add_heading("7. Threat & risk register", 1)
    _table(doc, ["ID", "Risk", "Category", "L", "I", "Level", "Mitigation", "Owner", "Requirements"],
           [[x.id, f"{x.title}: {x.description}", x.category, x.likelihood, x.impact, x.level.value, x.mitigation, x.owner.value,
             ", ".join(x.linked_requirements[:6])] for x in st.risks])

    doc.add_heading("8. Requirements traceability matrix", 1)
    rtm = _rtm_rows(st, stories, use_cases)
    _table(doc, ["Req", "Source docs", "Regulations", "Controls", "Story", "Use cases", "Tests", "Risks", "Status"],
           [[x["requirement_id"], x["source_documents"], x["regulations"], x["controls"], x["user_story"], x["use_cases"],
             x["test_cases"], x["risks"], x["status"]] for x in rtm])

    if st.sdlc:
        doc.add_heading("9. SDLC recommendation", 1)
        doc.add_paragraph(st.sdlc.explanation)
        _table(doc, ["Rank", "Model", "Suitability", "Reasons"],
               [[i + 1, o.model, f"{o.score}%", " | ".join(o.reasons)] for i, o in enumerate(st.sdlc.ranked)])
        doc.add_paragraph()
        _table(doc, ["Decision factor", "Score (1-5)", "Rationale"], [[f.name, f.score, f.rationale] for f in st.sdlc.factors])
        doc.add_heading(f"9.1 Project-specific workflow: {st.sdlc.selected}", 2)
        for i, ph in enumerate(st.sdlc.workflow, 1):
            doc.add_heading(f"Phase {i}: {ph.name}", 3)
            for label, items in [("Activities", ph.activities), ("Roles", ph.roles), ("Deliverables", ph.deliverables),
                                 ("Security activities", ph.security_activities), ("Testing", ph.testing),
                                 ("Compliance checkpoints", ph.compliance_checkpoints), ("Entry criteria", ph.entry_criteria),
                                 ("Exit criteria", ph.exit_criteria), ("Traceability", ph.traceability)]:
                if items:
                    p = doc.add_paragraph()
                    p.add_run(f"{label}: ").bold = True
                    p.add_run("; ".join(items))
            p = doc.add_paragraph()
            p.add_run("Approval gate: ").bold = True
            p.add_run(ph.approval_gate)

    doc.add_heading("10. Open issues", 1)
    doc.add_heading("10.1 Conflicts", 2)
    _table(doc, ["ID", "Type", "Severity", "Detail", "Resolution"],
           [[c.id, c.type, c.severity.value, c.detail, c.resolution or "OPEN"] for c in st.conflicts])
    doc.add_heading("10.2 Clarification questions", 2)
    _table(doc, ["ID", "Req", "To", "Question", "Answer"],
           [[q.id, q.requirement_id or "-", q.target_role.value if q.target_role else "-", q.question, q.answer or "OPEN"] for q in st.questions])
    if st.open_issues:
        doc.add_heading("10.3 Other issues", 2)
        for i in st.open_issues:
            doc.add_paragraph(i, style="List Bullet")

    doc.add_heading("11. Approvals & quality gates", 1)
    _table(doc, ["Gate", "Result"], [[k, "PASS" if v else "FAIL"] for k, v in st.metrics.get("gates", {}).items()])
    doc.add_paragraph()
    _table(doc, ["ID", "Gate", "Subject", "Required roles", "Status"],
           [[a.id, a.gate, a.subject_id, ", ".join(x.value for x in a.required_roles), a.status.value] for a in st.approvals])
    doc.add_paragraph(f"Audit trail: {len(ctx.audit.events)} events; hash chain {'verified' if ctx.audit.verify() else 'BROKEN'}; head {ctx.audit.head[:16]}…")
    doc.save(path)


def write_all(ctx: "Context", out: Path, stories: list[dict[str, Any]], use_cases: list[dict[str, Any]]) -> dict[str, str]:
    out.mkdir(parents=True, exist_ok=True)
    st = ctx.state
    paths: dict[str, str] = {}

    p = out / "SRS.docx"; write_srs(ctx, p, stories, use_cases); paths["srs"] = str(p)
    p = out / "requirements_traceability_matrix.csv"; _csv(p, _rtm_rows(st, stories, use_cases)); paths["rtm"] = str(p)
    p = out / "compliance_control_matrix.csv"
    _csv(p, [{"requirement_id": m.requirement_id, "control_id": m.control_id, "control": m.control,
              "citations": ";".join(c.kb_id for c in m.citations), "jurisdiction": m.jurisdiction, "obligation": m.obligation,
              "gap": m.gap, "needs_legal_review": m.needs_legal_review, "confidence": m.confidence} for m in st.compliance])
    paths["compliance_matrix"] = str(p)
    p = out / "control_coverage.csv"
    _csv(p, [{"control_id": c.control_id, "title": c.title, "mandatory": c.mandatory, "status": c.status,
              "covered_by": ";".join(c.covered_by)} for c in st.coverage]); paths["coverage"] = str(p)
    p = out / "risk_register.csv"
    _csv(p, [{"id": x.id, "title": x.title, "category": x.category, "description": x.description, "likelihood": x.likelihood,
              "impact": x.impact, "level": x.level.value, "mitigation": x.mitigation, "owner": x.owner.value,
              "linked_requirements": ";".join(x.linked_requirements)} for x in st.risks]); paths["risk_register"] = str(p)

    md = ["# User stories\n"]
    for s in stories:
        md.append(f"## {s['id']}\n\n{s['story']}\n\n**Acceptance criteria**\n")
        md += [f"- {a}" for a in s["acceptance_criteria"]]
        md.append("")
    p = out / "user_stories.md"; p.write_text("\n".join(md)); paths["user_stories"] = str(p)

    md = ["# Use cases\n"]
    for uc in use_cases:
        md += [f"## {uc['id']} {uc['name']}\n", f"**Actor:** {uc['actor']}\n", "**Preconditions:** " + "; ".join(uc["pre"]) + "\n",
               "**Main flow**\n"] + [f"{i}. {s}" for i, s in enumerate(uc["main"], 1)] + \
              ["", "**Alternate flows**\n"] + [f"- {a}" for a in uc["alt"]] + \
              ["", "**Postconditions:** " + "; ".join(uc["post"]), "", "**Requirements:** " + ", ".join(uc["requirements"]), ""]
    p = out / "use_cases.md"; p.write_text("\n".join(md)); paths["use_cases"] = str(p)

    if st.sdlc:
        md = [f"# SDLC recommendation: {st.sdlc.selected}\n", st.sdlc.explanation, "", "| Rank | Model | Suitability |", "|---|---|---|"]
        md += [f"| {i + 1} | {o.model} | {o.score}% |" for i, o in enumerate(st.sdlc.ranked)]
        md += ["", "## Decision factors", "", "| Factor | Score | Rationale |", "|---|---|---|"]
        md += [f"| {f.name} | {f.score} | {f.rationale} |" for f in st.sdlc.factors]
        md += ["", "## Workflow"]
        for i, ph in enumerate(st.sdlc.workflow, 1):
            md += [f"\n### Phase {i}: {ph.name}", f"- **Activities:** {'; '.join(ph.activities)}", f"- **Roles:** {'; '.join(ph.roles)}",
                   f"- **Deliverables:** {'; '.join(ph.deliverables)}", f"- **Security:** {'; '.join(ph.security_activities)}",
                   f"- **Testing:** {'; '.join(ph.testing)}", f"- **Compliance checkpoints:** {'; '.join(ph.compliance_checkpoints)}",
                   f"- **Entry:** {'; '.join(ph.entry_criteria)}", f"- **Exit:** {'; '.join(ph.exit_criteria)}",
                   f"- **Approval gate:** {ph.approval_gate}", f"- **Traceability:** {'; '.join(ph.traceability)}"]
        p = out / "sdlc_workflow.md"; p.write_text("\n".join(md)); paths["sdlc"] = str(p)

    assumptions, deps = assumptions_and_dependencies(st)
    md = ["# Assumptions, dependencies & open issues\n", "## Assumptions"] + [f"- {a}" for a in assumptions] + \
         ["", "## Dependencies"] + [f"- {d}" for d in deps] + ["", "## Open conflicts"] + \
         [f"- **{c.id}** ({c.type}, {c.severity.value}): {c.detail}" for c in st.conflicts if c.resolution is None] + \
         ["", "## Open questions"] + [f"- **{q.id}** → {q.target_role.value if q.target_role else '-'}: {q.question}" for q in st.questions if q.answer is None] + \
         ["", "## Other"] + [f"- {i}" for i in st.open_issues]
    p = out / "assumptions_dependencies_open_issues.md"; p.write_text("\n".join(md)); paths["open_issues"] = str(p)

    p = out / "project_state.json"; p.write_text(st.model_dump_json(indent=2)); paths["state"] = str(p)
    p = out / "audit_log.jsonl"; p.write_text("\n".join(json.dumps(e, default=str) for e in ctx.audit.events)); paths["audit"] = str(p)
    return paths
