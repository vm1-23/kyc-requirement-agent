"""LocalLLM against a fake Ollama server (no real model needed)."""
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from kyc_re.llm import LocalLLM, make_llm


class _Handler(BaseHTTPRequestHandler):
    replies: list = []
    requests: list = []

    def log_message(self, *a):
        pass

    def do_GET(self):
        body = json.dumps({"models": [{"name": "qwen2.5:7b-instruct"}]}).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(body)

    def do_POST(self):
        req = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        _Handler.requests.append(req)
        content = _Handler.replies.pop(0) if _Handler.replies else "{}"
        body = json.dumps({"message": {"content": content}, "done_reason": "stop", "prompt_eval_count": 10, "eval_count": 5}).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(body)


@pytest.fixture
def ollama(monkeypatch):
    srv = HTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{srv.server_port}"
    monkeypatch.setenv("OLLAMA_HOST", url)
    _Handler.replies, _Handler.requests = [], []
    yield url
    srv.shutdown()


SCHEMA = {"type": "object", "properties": {"ok": {"type": "boolean"}, "kind": {"type": "string", "enum": ["a", "b"]}},
          "required": ["ok", "kind"], "additionalProperties": False}


def test_schema_constrained_call(ollama):
    llm = LocalLLM("ollama")
    _Handler.replies = ['{"ok": true, "kind": "a"}']
    assert llm.json("t", "sys", "user", SCHEMA) == {"ok": True, "kind": "a"}
    req = _Handler.requests[0]
    assert req["format"] == SCHEMA and req["options"]["temperature"] == 0 and req["stream"] is False


def test_invalid_or_nonconforming_output_falls_back(ollama):
    llm = LocalLLM("ollama")
    _Handler.replies = ["not json", '{"ok": true, "kind": "zzz"}']
    assert llm.json("t", "s", "u", SCHEMA) is None
    assert llm.json("t", "s", "u", SCHEMA) is None


def test_auto_prefers_reachable_local_model(ollama, monkeypatch):
    monkeypatch.setenv("KYC_RE_LLM", "auto")
    monkeypatch.setenv("KYC_RE_LOCAL_URL", "http://127.0.0.1:9")  # nothing there
    llm = make_llm()
    assert llm.name == "ollama:qwen2.5:7b-instruct"


def test_unreachable_server_is_an_error(monkeypatch):
    monkeypatch.setenv("OLLAMA_HOST", "http://127.0.0.1:9")
    with pytest.raises(RuntimeError):
        make_llm("ollama")


def test_pipeline_runs_with_local_llm_and_guards(ollama):
    from kyc_re.coordinator import Coordinator
    from kyc_re.models import ProjectContext

    # extraction reply includes one hallucinated item; other calls return empty objects -> rules fallback
    _Handler.replies = [json.dumps({"requirements": [
        {"statement": "The system shall screen applicants against sanctions lists.", "source_excerpt": "screen every applicant against sanctions lists",
         "kind": "functional", "priority": "must", "business_justification": "AML"},
        {"statement": "The system shall accept crypto.", "source_excerpt": "we accept crypto payments",
         "kind": "functional", "priority": "could", "business_justification": "x"}]})]
    co = Coordinator(ProjectContext(name="t", jurisdictions=["IN"]), llm="ollama")
    co.add_document("e", "The system must screen every applicant against sanctions lists before opening.", "email", "A", "compliance")
    co.run()
    assert co.llm.name.startswith("ollama:")
    assert co.state.metrics["hallucinated_extractions"] == 1
    assert any(e["action"] == "llm_call" and e["payload"].get("local") for e in co.audit.events)
