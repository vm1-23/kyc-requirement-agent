"""REST API and web UI.

Authentication here is a demo stand-in: the caller identifies with `X-User` and
`X-Role` headers, and RBAC is enforced on every approval decision. In production, put
the API behind the bank's IdP (OIDC with MFA) and derive the role from verified token
claims.
"""
from __future__ import annotations

import io
import json
import os
import re
import tempfile
import zipfile
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from ..agents.interaction import InterviewSession
from ..cli import load_case
from ..coordinator import AGENT_REGISTRY, Coordinator
from ..knowledge.kb import default_kb
from ..models import ProjectContext, ProjectState, StakeholderRole
from ..security.rbac import PermissionDenied

ROOT = Path(__file__).resolve().parents[2]
SAMPLES = ROOT / "samples"
DATA = Path(os.getenv("KYC_RE_DATA", ROOT / "data"))
STATIC = Path(__file__).parent / "static"

app = FastAPI(title="KYC Agentic Requirement Engineering", version="0.1.0")
PROJECTS: dict[str, Coordinator] = {}
INTERVIEWS: dict[str, dict[str, InterviewSession]] = {}


# ---- persistence ---------------------------------------------------------------------------
def _pdir(pid: str) -> Path:
    return DATA / "projects" / pid


def _save(pid: str) -> None:
    d = _pdir(pid)
    d.mkdir(parents=True, exist_ok=True)
    (d / "state.json").write_text(PROJECTS[pid].state.model_dump_json(indent=1))


def _get(pid: str) -> Coordinator:
    if pid not in PROJECTS:
        f = _pdir(pid) / "state.json"
        if not f.exists():
            raise HTTPException(404, "project not found")
        st = ProjectState.model_validate_json(f.read_text())
        PROJECTS[pid] = Coordinator(st.project, state=st, audit_path=_pdir(pid) / "audit.jsonl")
    return PROJECTS[pid]


def _slug(name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.lower())[:40].strip("-") or "project"
    i, pid = 1, base
    while pid in PROJECTS or _pdir(pid).exists():
        i += 1
        pid = f"{base}-{i}"
    return pid


def _role(x_role: str | None) -> StakeholderRole:
    try:
        return StakeholderRole(x_role or "")
    except ValueError:
        raise HTTPException(401, f"X-Role header must be one of {[r.value for r in StakeholderRole]}")


# ---- schemas -------------------------------------------------------------------------------
class DocIn(BaseModel):
    title: str
    text: str
    type: str = "meeting_notes"
    stakeholder: str = ""
    role: str | None = None


class AnswerIn(BaseModel):
    answer: str


class DecisionIn(BaseModel):
    decision: str
    comment: str = ""
    modification: str | None = None


class InterviewIn(BaseModel):
    stakeholder: str
    role: str


class ChangeIn(BaseModel):
    statement: str


# ---- endpoints -----------------------------------------------------------------------------
@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.get("/api/health")
def health() -> dict[str, Any]:
    from ..llm import make_llm

    return {"status": "ok", "llm": make_llm().name, "kb_version": default_kb().version}


@app.get("/api/kb")
def kb() -> dict[str, Any]:
    k = default_kb()
    return {**k.manifest(), "control_catalogue": [{"id": c["id"], "title": c["title"], "mandatory": c["mandatory"],
                                                   "jurisdictions": c["jurisdictions"], "kb_refs": c["kb_refs"]} for c in k.controls]}


@app.get("/api/agents")
def agents() -> list[dict[str, str]]:
    return [{"agent": a, "responsibility": d} for a, d in AGENT_REGISTRY]


@app.get("/api/samples")
def samples() -> list[dict[str, Any]]:
    return [{"id": p.name, **json.loads((p / "project.json").read_text())["project"]}
            for p in sorted(SAMPLES.iterdir()) if (p / "project.json").exists()]


@app.get("/api/projects")
def list_projects() -> list[dict[str, Any]]:
    ids = set(PROJECTS) | ({p.name for p in (DATA / "projects").iterdir()} if (DATA / "projects").exists() else set())
    out = []
    for pid in sorted(ids):
        try:
            st = _get(pid).state
            out.append({"id": pid, "name": st.project.name, "requirements": len(st.requirements)})
        except HTTPException:
            pass
    return out


@app.post("/api/projects")
def create_project(ctx: ProjectContext) -> dict[str, str]:
    pid = _slug(ctx.name)
    _pdir(pid).mkdir(parents=True, exist_ok=True)
    PROJECTS[pid] = Coordinator(ctx, audit_path=_pdir(pid) / "audit.jsonl")
    _save(pid)
    return {"id": pid}


@app.post("/api/projects/from-sample/{case}")
def from_sample(case: str) -> dict[str, Any]:
    if not re.fullmatch(r"[a-z0-9_]+", case) or not (SAMPLES / case / "project.json").exists():
        raise HTTPException(404, "sample not found")
    name = json.loads((SAMPLES / case / "project.json").read_text())["project"]["name"]
    pid = _slug(name)
    _pdir(pid).mkdir(parents=True, exist_ok=True)
    co = load_case(SAMPLES / case, audit_path=_pdir(pid) / "audit.jsonl")
    PROJECTS[pid] = co
    co.run()
    _save(pid)
    return {"id": pid}


@app.get("/api/projects/{pid}")
def get_project(pid: str) -> dict[str, Any]:
    co = _get(pid)
    st = json.loads(co.state.model_dump_json())
    st["stories"] = co.stories()
    st["use_cases"] = co.use_cases()
    st["llm"] = co.llm.name
    st["threat_model"] = co.ctx.stats.get("threat_model", [])
    return st


@app.post("/api/projects/{pid}/documents")
def add_document(pid: str, doc: DocIn) -> dict[str, Any]:
    co = _get(pid)
    d = co.add_document(doc.title, doc.text, doc.type, doc.stakeholder, doc.role)
    _save(pid)
    return {"id": d.id, "pii_masked": len(d.pii_findings), "injection_flags": d.injection_flags, "masked_text": d.masked_text}


@app.post("/api/projects/{pid}/run")
def run(pid: str) -> dict[str, Any]:
    co = _get(pid)
    co.run()
    _save(pid)
    return co.state.metrics


@app.post("/api/projects/{pid}/questions/{qid}/answer")
def answer(pid: str, qid: str, body: AnswerIn, x_user: str = Header("anonymous")) -> dict[str, Any]:
    co = _get(pid)
    if not any(q.id == qid for q in co.state.questions):
        raise HTTPException(404, "question not found")
    co.answer(qid, body.answer, user=x_user)
    _save(pid)
    return co.state.metrics


@app.post("/api/projects/{pid}/approvals/{aid}")
def decide(pid: str, aid: str, body: DecisionIn, x_user: str = Header(...), x_role: str = Header(...)) -> dict[str, Any]:
    co = _get(pid)
    if not any(a.id == aid for a in co.state.approvals):
        raise HTTPException(404, "approval item not found")
    try:
        item = co.decide(aid, x_user, _role(x_role), body.decision, body.comment, body.modification)
    except PermissionDenied as e:
        raise HTTPException(403, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))
    _save(pid)
    return json.loads(item.model_dump_json())


@app.post("/api/projects/{pid}/requirements/{rid}/change")
def change(pid: str, rid: str, body: ChangeIn, x_user: str = Header(...), x_role: str = Header(...)) -> dict[str, Any]:
    co = _get(pid)
    try:
        co.change_requirement(rid, body.statement, x_user, _role(x_role))
    except KeyError:
        raise HTTPException(404, "requirement not found")
    _save(pid)
    return json.loads(co.state.req(rid).model_dump_json())


@app.post("/api/projects/{pid}/interviews")
def start_interview(pid: str, body: InterviewIn) -> dict[str, Any]:
    co = _get(pid)
    sid = f"INT-{len(INTERVIEWS.get(pid, {})) + 1}"
    s = co.interviewer().start(sid, body.stakeholder, _role(body.role))
    INTERVIEWS.setdefault(pid, {})[sid] = s
    return json.loads(s.model_dump_json())


@app.post("/api/projects/{pid}/interviews/{sid}/answer")
def interview_answer(pid: str, sid: str, body: AnswerIn) -> dict[str, Any]:
    co = _get(pid)
    s = INTERVIEWS.get(pid, {}).get(sid)
    if s is None:
        raise HTTPException(404, "interview not found")
    s = co.interviewer().answer(s, co.mask(body.answer))
    INTERVIEWS[pid][sid] = s
    return json.loads(s.model_dump_json())


@app.post("/api/projects/{pid}/interviews/{sid}/finish")
def interview_finish(pid: str, sid: str) -> dict[str, Any]:
    co = _get(pid)
    s = INTERVIEWS.get(pid, {}).pop(sid, None)
    if s is None:
        raise HTTPException(404, "interview not found")
    doc = co.interviewer().to_document(s, f"DOC-{sid}")
    d = co.add_document(doc.title, doc.text, "conversation", s.stakeholder, s.role)
    co.run()
    _save(pid)
    return {"document": d.id, "metrics": co.state.metrics}


@app.get("/api/projects/{pid}/audit")
def audit(pid: str) -> dict[str, Any]:
    co = _get(pid)
    return {"verified": co.audit.verify(), "head": co.audit.head, "events": co.audit.events[-500:]}


@app.get("/api/projects/{pid}/export")
def export(pid: str) -> StreamingResponse:
    co = _get(pid)
    with tempfile.TemporaryDirectory() as tmp:
        paths = co.export(tmp)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            for p in paths.values():
                z.write(p, Path(p).name)
    buf.seek(0)
    return StreamingResponse(buf, media_type="application/zip",
                             headers={"Content-Disposition": f'attachment; filename="{pid}-artefacts.zip"'})
