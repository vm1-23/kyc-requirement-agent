"""Command-line interface.

  kyc-re run samples/kyc_onboarding -o output/       # full pipeline + artefacts
  kyc-re interview --role compliance                 # adaptive interview in the terminal
  kyc-re evaluate samples/kyc_onboarding             # metrics vs gold annotations
  kyc-re serve                                       # web UI + REST API
  kyc-re kb                                          # list knowledge-base items
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .coordinator import Coordinator
from .models import ProjectContext, StakeholderRole


def load_case(case_dir: str | Path, llm: str | None = None, audit_path: str | Path | None = None) -> Coordinator:
    case = Path(case_dir)
    spec = json.loads((case / "project.json").read_text())
    co = Coordinator(ProjectContext(**spec["project"]), llm=llm, audit_path=audit_path)
    for d in spec["documents"]:
        co.add_document(title=d["title"], text=(case / "inputs" / d["file"]).read_text(), type=d["type"],
                        stakeholder=d.get("stakeholder", ""), role=d.get("role"), doc_id=d.get("id"))
    return co


def _summary(co: Coordinator) -> str:
    st, m = co.state, co.state.metrics
    lines = [
        f"Project: {st.project.name}  (LLM: {co.llm.name}, KB v{co.ctx.kb.version})",
        f"Requirements: {m['requirements_total']} ({m['requirements_extracted']} extracted, {m['requirements_derived']} derived from controls/threats)",
        f"Quality: {m['with_quality_issues']} with issues, {m['needs_clarification']} need clarification, {m['open_questions']} open questions",
        f"Conflicts: {m['conflicts_total']} ({m['conflicts_open_high']} open high/critical)",
        f"Mandatory control coverage: stakeholder input {m['control_coverage_stakeholder']:.0%} -> after derivation {m['control_coverage_after_derivation']:.0%}",
        f"Citations: {m['citations_total']} (validity {m['citation_validity']:.0%}); hallucinations dropped: "
        f"{m['hallucinated_extractions']} extractions, {m['hallucinated_citations']} citations",
        f"Security gate: {m['pii_masked']} PII values masked, {m['injection_quarantined']} injected sentence(s) quarantined",
        f"Risks: {m['risks']}; traceability coverage {m['traceability_coverage']:.0%}",
    ]
    if st.sdlc:
        lines.append("SDLC ranking: " + ", ".join(f"{o.model} {o.score}%" for o in st.sdlc.ranked[:3]))
    lines.append(f"Baseline ready: {m['baseline_ready']}  gates={m['gates']}")
    lines.append(f"Pending approvals: {sum(1 for a in st.approvals if a.status.value == 'pending_approval')}  "
                 f"processing time {m['processing_time_s']}s")
    return "\n".join(lines)


def cmd_run(a) -> None:
    out = Path(a.output)
    co = load_case(a.case, a.llm, out / "audit_log.live.jsonl" if a.persist_audit else None)
    co.run()
    paths = co.export(out)
    print(_summary(co))
    print("\nArtefacts:")
    for k, v in paths.items():
        print(f"  {k:18s} {v}")


def cmd_interview(a) -> None:
    co = Coordinator(ProjectContext(name=a.project, jurisdictions=a.jurisdictions), llm=a.llm)
    agent = co.interviewer()
    s = agent.start("CLI-1", a.name, StakeholderRole(a.role))
    print(f"Adaptive interview for {a.name} ({a.role}). Empty line to finish.\n")
    while not s.done:
        print(f"[{s.turns[-1].topic}] {s.turns[-1].question}")
        try:
            ans = input("> ").strip()
        except EOFError:
            break
        if not ans:
            break
        s = agent.answer(s, co.mask(ans))
    doc = agent.to_document(s, "DOC-CLI")
    co.add_document(doc.title, doc.text, "conversation", a.name, a.role)
    co.run()
    for r in co.state.requirements:
        print(f"{r.id:14s} {r.status.value:20s} {r.statement}")
    if a.output:
        co.export(a.output)


def cmd_evaluate(a) -> None:
    from .evaluation.evaluate import evaluate_case

    report = evaluate_case(a.case, llm=a.llm)
    print(json.dumps(report, indent=2))
    if a.output:
        Path(a.output).parent.mkdir(parents=True, exist_ok=True)
        Path(a.output).write_text(json.dumps(report, indent=2))


def cmd_serve(a) -> None:
    import uvicorn

    uvicorn.run("kyc_re.api.app:app", host=a.host, port=a.port, reload=False)


def cmd_kb(a) -> None:
    from .knowledge.kb import default_kb

    print(json.dumps(default_kb().manifest(), indent=2))


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="kyc-re", description="Agentic requirement engineering for KYC onboarding")
    p.add_argument("--llm", choices=["auto", "claude", "offline"], default=None, help="LLM mode (default: env KYC_RE_LLM or auto)")
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run"); r.add_argument("case"); r.add_argument("-o", "--output", default="output")
    r.add_argument("--persist-audit", action="store_true"); r.set_defaults(fn=cmd_run)
    i = sub.add_parser("interview"); i.add_argument("--role", default="product_owner", choices=[x.value for x in StakeholderRole])
    i.add_argument("--name", default="Stakeholder"); i.add_argument("--project", default="KYC onboarding")
    i.add_argument("--jurisdictions", nargs="+", default=["IN"]); i.add_argument("-o", "--output"); i.set_defaults(fn=cmd_interview)
    e = sub.add_parser("evaluate"); e.add_argument("case"); e.add_argument("-o", "--output"); e.set_defaults(fn=cmd_evaluate)
    s = sub.add_parser("serve"); s.add_argument("--host", default="127.0.0.1"); s.add_argument("--port", type=int, default=8000); s.set_defaults(fn=cmd_serve)
    k = sub.add_parser("kb"); k.set_defaults(fn=cmd_kb)
    a = p.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":  # pragma: no cover
    main(sys.argv[1:])
