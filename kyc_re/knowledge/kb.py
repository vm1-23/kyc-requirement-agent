"""Version-controlled financial knowledge base with BM25 retrieval.

A dependency-free BM25 index is used so the prototype runs anywhere. The `Retriever`
interface is small, so a vector store (pgvector, FAISS, ...) can replace it without
changes to the agents.
"""
from __future__ import annotations

import json
import math
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any

from ..models import Citation

DATA_DIR = Path(__file__).parent / "data"

_STOP = set("""a an the of to and or for in on at by with from as is are be been shall should must will may can
this that these those it its into than then such any all each per not no if when where which who whom what
customer customers system app want wants need needs every two able also our we they their them have has
""".split())


_SYNONYMS = {
    "retain": "retention record", "kept": "retention", "keep": "retention", "store": "retention",
    "selfie": "liveness biometric", "mfa": "multi-factor authentication", "otp": "multi-factor",
    "2fa": "multi-factor", "pep": "politically exposed", "ubo": "beneficial owner",
    "watchlist": "sanctions screening", "consent": "consent notice privacy", "breach": "breach notification",
    "uptime": "availability", "aadhaar": "e-kyc officially valid document", "video": "v-cip",
}


def expand(text: str) -> str:
    low = text.lower()
    extra = [v for k, v in _SYNONYMS.items() if re.search(rf"\b{re.escape(k)}", low)]
    return text + " " + " ".join(extra)


def tokenize(text: str) -> list[str]:
    toks = re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)*", text.lower())
    out = []
    for t in toks:
        if t in _STOP or len(t) < 2:
            continue
        # light stemming
        for suf in ("ing", "ation", "ions", "ion", "ers", "es", "ed", "s"):
            if len(t) > len(suf) + 3 and t.endswith(suf):
                t = t[: -len(suf)]
                break
        out.append(t)
    return out


@dataclass
class KBItem:
    id: str
    type: str
    title: str
    source: str
    jurisdiction: str
    effective_date: str
    version: str
    applicability: list[str]
    tags: list[str]
    text: str

    def citation(self, score: float = 0.0, excerpt_len: int = 220) -> Citation:
        ex = self.text if len(self.text) <= excerpt_len else self.text[:excerpt_len].rsplit(" ", 1)[0] + "…"
        return Citation(kb_id=self.id, title=self.title, source=self.source, jurisdiction=self.jurisdiction,
                        version=self.version, excerpt=ex, score=round(score, 3))


@dataclass
class BM25:
    docs: list[list[str]]
    k1: float = 1.5
    b: float = 0.75
    df: Counter = field(default_factory=Counter)

    def __post_init__(self) -> None:
        for d in self.docs:
            self.df.update(set(d))
        self.N = len(self.docs)
        self.avgdl = sum(len(d) for d in self.docs) / max(self.N, 1)
        self.tfs = [Counter(d) for d in self.docs]

    def idf(self, t: str) -> float:
        n = self.df.get(t, 0)
        return math.log(1 + (self.N - n + 0.5) / (n + 0.5))

    def score(self, q: list[str], i: int) -> float:
        tf, dl, s = self.tfs[i], len(self.docs[i]), 0.0
        for t in q:
            f = tf.get(t, 0)
            if f:
                s += self.idf(t) * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * dl / self.avgdl))
        return s


class KnowledgeBase:
    def __init__(self, data_dir: Path = DATA_DIR):
        self.data_dir = data_dir
        reg = self._load("regulations.json")
        std = self._load("standards_policies.json")
        self.version = reg.get("kb_version", "unknown")
        self.disclaimer = reg.get("disclaimer", "")
        self.items: dict[str, KBItem] = {}
        for raw in reg["items"] + std["items"]:
            self.items[raw["id"]] = KBItem(**raw)
        self.controls: list[dict[str, Any]] = self._load("controls.json")["controls"]
        self.interview: dict[str, Any] = self._load("interview.json")
        sg = self._load("sdlc_glossary.json")
        self.sdlc_models: dict[str, Any] = {k: v for k, v in sg["sdlc_models"].items() if not k.startswith("_")}
        self.glossary: dict[str, str] = sg["glossary"]
        self._ids = list(self.items)
        self._bm25 = BM25([tokenize(" ".join([i.title, " ".join(i.tags) * 2, i.text])) for i in self.items.values()])

    def _load(self, name: str) -> dict[str, Any]:
        return json.loads((self.data_dir / name).read_text())

    # ---- retrieval -----------------------------------------------------------------
    def applicable(self, item: KBItem, jurisdictions: list[str], on: date | None = None) -> bool:
        juris = set(jurisdictions) | {"GLOBAL", "ORG"}
        if item.jurisdiction not in juris:
            return False
        if on and date.fromisoformat(item.effective_date) > on:
            return False
        return True

    def search(self, query: str, jurisdictions: list[str] | None = None, k: int = 5,
               types: set[str] | None = None, min_score: float = 0.5) -> list[tuple[KBItem, float]]:
        q = tokenize(expand(query))
        if not q:
            return []
        juris = jurisdictions or ["GLOBAL"]
        scored = []
        for i, kid in enumerate(self._ids):
            item = self.items[kid]
            if not self.applicable(item, juris, date.today()):
                continue
            if types and item.type not in types:
                continue
            s = self._bm25.score(q, i)
            if s >= min_score:
                scored.append((item, s))
        scored.sort(key=lambda x: -x[1])
        if scored:
            floor = scored[0][1] * 0.45  # drop weak tail matches relative to the best hit
            scored = [x for x in scored if x[1] >= floor]
        return scored[:k]

    def get(self, kb_id: str) -> KBItem | None:
        return self.items.get(kb_id)

    def controls_for(self, jurisdictions: list[str]) -> list[dict[str, Any]]:
        juris = set(jurisdictions) | {"GLOBAL", "ORG"}
        return [c for c in self.controls if set(c["jurisdictions"]) & juris]

    def manifest(self) -> dict[str, Any]:
        return {
            "kb_version": self.version,
            "disclaimer": self.disclaimer,
            "items": [{"id": i.id, "title": i.title, "source": i.source, "jurisdiction": i.jurisdiction,
                       "effective_date": i.effective_date, "version": i.version, "type": i.type}
                      for i in self.items.values()],
            "controls": len(self.controls),
        }


@lru_cache(maxsize=1)
def default_kb() -> KnowledgeBase:
    return KnowledgeBase()
