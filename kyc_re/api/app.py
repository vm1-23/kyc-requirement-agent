"""REST API and web UI.

Authentication here is a demo stand-in: the caller identifies with `X-User` and
`X-Role` headers, and RBAC is enforced on every approval decision. In production, put
the API behind the bank's IdP (OIDC with MFA) and derive the role from verified token
claims.
"""
from __future__ import annotations

import base64
import io
import json
import os
import re
import tempfile
import threading
import time
import zipfile
from collections.abc import Iterator
from contextlib import contextmanager
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
from ..speakers import split_speakers

ROOT = Path(__file__).resolve().parents[2]
SAMPLES = ROOT / "samples"
DATA = Path(os.getenv("KYC_RE_DATA", ROOT / "data"))
STATIC = Path(__file__).parent / "static"

app = FastAPI(title="KYC Agentic Requirement Engineering", version="0.1.0")
PROJECTS: dict[str, Coordinator] = {}
INTERVIEWS: dict[str, dict[str, InterviewSession]] = {}
_LOCKS: dict[str, threading.Lock] = {}
_LOCKS_GUARD = threading.Lock()


@contextmanager
def _busy(pid: str) -> Iterator[None]:
    """One pipeline run / mutation per project at a time. A run on a local LLM can take minutes,
    so a second request fails fast with 409 instead of queueing another full run."""
    with _LOCKS_GUARD:
        lock = _LOCKS.setdefault(pid, threading.Lock())
    if not lock.acquire(blocking=False):
        raise HTTPException(409, "This project is still being analysed. Wait for the current run to finish.")
    try:
        yield
    finally:
        lock.release()


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


class DocBatchIn(BaseModel):
    documents: list[DocIn]
    run: bool = True


class TextIn(BaseModel):
    text: str


class ConversationIn(BaseModel):
    text: str
    title: str = ""
    roles: dict[str, str | None] = {}  # speaker label -> role, overriding the guess from the designation
    names: dict[str, str] = {}  # speaker label -> stakeholder name (e.g. to name the "Unattributed" part)
    run: bool = True


class FileIn(BaseModel):
    filename: str
    content_b64: str


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


DEMO_FILE = "demo_state.json"


def _demo_pid(case: str) -> str:
    return "demo-" + case.replace("_", "-")


@app.get("/api/demos")
def demos() -> list[dict[str, Any]]:
    """Pre-analysed sample projects (built with `kyc-re build-demos`) that open instantly."""
    out = []
    for d in sorted(SAMPLES.iterdir()):
        if not (d / DEMO_FILE).exists() or not (d / "project.json").exists():
            continue
        proj = json.loads((d / "project.json").read_text())["project"]
        st = json.loads((d / DEMO_FILE).read_text())
        m = st.get("metrics", {})
        out.append({"id": d.name, "project_id": _demo_pid(d.name), "name": st["project"]["name"], "description": proj.get("description", ""),
                    "jurisdictions": proj.get("jurisdictions", []), "documents": len(st.get("documents", [])),
                    "requirements": m.get("requirements_total", 0), "questions": m.get("open_questions", 0),
                    "conflicts": m.get("conflicts_total", 0), "sdlc": (st.get("sdlc") or {}).get("selected"),
                    "opened": (_pdir(_demo_pid(d.name)) / "state.json").exists()})
    return out


@app.post("/api/demos/{case}")
def open_demo(case: str, reset: bool = False) -> dict[str, Any]:
    """Open a demo: copies the pre-analysed snapshot into its own project (no agents run, so it's instant).
    An already-opened demo keeps any answers and decisions made during a presentation unless `reset` is set."""
    src = SAMPLES / case / DEMO_FILE
    if not re.fullmatch(r"[a-z0-9_]+", case) or not src.exists():
        raise HTTPException(404, "demo not found")
    pid = _demo_pid(case)
    with _busy(pid):
        if reset or not (_pdir(pid) / "state.json").exists():
            d = _pdir(pid)
            d.mkdir(parents=True, exist_ok=True)
            (d / "state.json").write_text(src.read_text())
            (d / "audit.jsonl").unlink(missing_ok=True)
            PROJECTS.pop(pid, None)
            _get(pid).audit.record("coordinator", "demo_loaded", case, snapshot=DEMO_FILE)
    return {"id": pid}


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
    co.run("case study load")
    _save(pid)
    return {"id": pid}


@app.get("/api/progress")
def progress_all() -> list[dict[str, Any]]:
    """Runs in flight (and ones that ended in the last 30 s), so a page that doesn't know the project id yet,
    e.g. while a case study loads, or a page reloaded mid-run, can still show progress."""
    out = []
    for pid, co in list(PROJECTS.items()):
        snap = co.progress.snapshot()
        if snap and (snap["running"] or time.time() - (snap["finished"] or 0) < 30):
            out.append({"project": pid, "name": co.state.project.name, **snap})
    return out


@app.get("/api/projects/{pid}/progress")
def progress(pid: str) -> dict[str, Any]:
    return _get(pid).progress.snapshot() or {"running": False}


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
    with _busy(pid):
        d = co.add_document(doc.title, doc.text, doc.type, doc.stakeholder, doc.role)
        _save(pid)
    return {"id": d.id, "pii_masked": len(d.pii_findings), "injection_flags": d.injection_flags, "masked_text": d.masked_text}


@app.post("/api/projects/{pid}/documents/batch")
def add_documents(pid: str, body: DocBatchIn) -> dict[str, Any]:
    """Add several inputs under one lock and (by default) analyse once, instead of once per input."""
    co = _get(pid)
    docs = [d for d in body.documents if d.text.strip()]
    if not docs:
        raise HTTPException(400, "no input text")
    with _busy(pid):
        added = [co.add_document(d.title or "Input", d.text, d.type, d.stakeholder, d.role) for d in docs]
        if body.run:
            co.run(f"analysis of {len(added)} new input{'s' if len(added) != 1 else ''}")
        _save(pid)
    return {"documents": [{"id": d.id, "title": d.title, "pii_masked": len(d.pii_findings), "injection_flags": d.injection_flags}
                          for d in added], "analysed": body.run, "metrics": co.state.metrics}


@app.post("/api/split-speakers")
def split(body: TextIn) -> dict[str, Any]:
    """Preview who said what in a pasted text. Nothing is stored or sent to a model."""
    return {"speakers": [sp.as_dict() for sp in split_speakers(body.text)]}


@app.post("/api/projects/{pid}/conversation")
def add_conversation(pid: str, body: ConversationIn) -> dict[str, Any]:
    """Add one pasted text as one input per person, so each requirement is attributed to who said it."""
    co = _get(pid)
    speakers = split_speakers(body.text)
    if not speakers:
        raise HTTPException(400, "no input text")
    valid = {r.value for r in StakeholderRole}
    kind = "conversation" if len(speakers) > 1 else "meeting_notes"
    with _busy(pid):
        added = []
        for sp in speakers:
            role = body.roles.get(sp.label, sp.role)
            if role not in valid:
                role = None
            who = (body.names.get(sp.label) or "").strip() or (sp.label if sp.attributed else "")
            title = f"{body.title.strip() or 'Stakeholder input'} · {who or 'unattributed'}"
            added.append(co.add_document(title, sp.text, kind, who, role))
        if body.run:
            co.run(f"analysis of input from {len(added)} {'people' if len(added) != 1 else 'person'}")
        _save(pid)
    return {"documents": [{"id": d.id, "title": d.title, "stakeholder": d.stakeholder, "role": d.role.value if d.role else None,
                           "pii_masked": len(d.pii_findings), "injection_flags": d.injection_flags} for d in added],
            "analysed": body.run, "metrics": co.state.metrics}


MAX_UPLOAD = 10 * 1024 * 1024
TEXT_EXT = {".txt", ".md", ".eml", ".csv", ".json", ".yaml", ".yml", ".xml", ".html", ".htm", ".log", ".rtf"}


def _docx_text(raw: bytes) -> str:
    from docx import Document

    d = Document(io.BytesIO(raw))
    parts = [p.text for p in d.paragraphs if p.text.strip()]
    for t in d.tables:
        for row in t.rows:
            cells = [c.text.strip() for c in row.cells]
            if any(cells):
                parts.append(" | ".join(cells))
    return "\n".join(parts)


def _pdf_text(raw: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        raise HTTPException(415, "PDF upload needs the pypdf package: pip install -e '.[docs]'. Or paste the text instead.")
    return "\n".join((pg.extract_text() or "") for pg in PdfReader(io.BytesIO(raw)).pages).strip()


@app.post("/api/extract-text")
def extract_text(f: FileIn) -> dict[str, Any]:
    """Turn an uploaded file into plain text for the input form. Nothing is stored: the text goes back to the
    browser for review, and is masked only when it is actually added to a project."""
    try:
        raw = base64.b64decode(f.content_b64, validate=True)
    except ValueError:
        raise HTTPException(400, "content_b64 is not valid base64")
    if len(raw) > MAX_UPLOAD:
        raise HTTPException(413, "file is larger than 10 MB")
    ext = Path(f.filename).suffix.lower()
    try:
        if ext == ".docx":
            text = _docx_text(raw)
        elif ext == ".pdf":
            text = _pdf_text(raw)
        elif ext in TEXT_EXT or not ext:
            text = raw.decode("utf-8", errors="replace")
        else:
            raise HTTPException(415, f"unsupported file type {ext}: use .txt, .md, .eml, .docx or .pdf")
    except HTTPException:
        raise
    except Exception as e:  # corrupt docx/pdf
        raise HTTPException(422, f"could not read {f.filename}: {e}")
    if not text.strip():
        raise HTTPException(422, f"no text found in {f.filename} (scanned PDFs need OCR first)")
    return {"filename": f.filename, "text": text, "chars": len(text)}


@app.post("/api/projects/{pid}/run")
def run(pid: str) -> dict[str, Any]:
    co = _get(pid)
    with _busy(pid):
        co.run("manual re-run")
        _save(pid)
    return co.state.metrics


@app.post("/api/projects/{pid}/questions/{qid}/answer")
def answer(pid: str, qid: str, body: AnswerIn, x_user: str = Header("anonymous")) -> dict[str, Any]:
    co = _get(pid)
    if not any(q.id == qid for q in co.state.questions):
        raise HTTPException(404, "question not found")
    with _busy(pid):
        co.answer(qid, body.answer, user=x_user)
        _save(pid)
    return co.state.metrics


@app.post("/api/projects/{pid}/approvals/{aid}")
def decide(pid: str, aid: str, body: DecisionIn, x_user: str = Header(...), x_role: str = Header(...)) -> dict[str, Any]:
    co = _get(pid)
    if not any(a.id == aid for a in co.state.approvals):
        raise HTTPException(404, "approval item not found")
    role = _role(x_role)
    with _busy(pid):
        try:
            item = co.decide(aid, x_user, role, body.decision, body.comment, body.modification)
        except PermissionDenied as e:
            raise HTTPException(403, str(e))
        except ValueError as e:
            raise HTTPException(400, str(e))
        _save(pid)
    return json.loads(item.model_dump_json())


@app.post("/api/projects/{pid}/requirements/{rid}/change")
def change(pid: str, rid: str, body: ChangeIn, x_user: str = Header(...), x_role: str = Header(...)) -> dict[str, Any]:
    co = _get(pid)
    role = _role(x_role)
    with _busy(pid):
        try:
            co.change_requirement(rid, body.statement, x_user, role)
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
    with _busy(pid):  # take the lock before popping, so a 409 doesn't lose the interview
        s = INTERVIEWS.get(pid, {}).pop(sid, None)
        if s is None:
            raise HTTPException(404, "interview not found")
        doc = co.interviewer().to_document(s, f"DOC-{sid}")
        d = co.add_document(doc.title, doc.text, "conversation", s.stakeholder, s.role)
        co.run(f"interview with {s.stakeholder}")
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
