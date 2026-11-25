"""Sensitive-data classification and masking.

Text is masked *before* it reaches an LLM, a log or a generated artefact. Masking is
deterministic (same value -> same token within a session), so requirements can still
refer to "<PAN_1>" consistently without exposing the value.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


def _luhn_ok(digits: str) -> bool:
    d = [int(c) for c in digits if c.isdigit()]
    if len(d) < 13:
        return False
    total = 0
    for i, n in enumerate(reversed(d)):
        if i % 2 == 1:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0


# (label, regex, sensitivity, validator)
_PATTERNS: list[tuple[str, re.Pattern[str], str, object]] = [
    ("ACCOUNT", re.compile(r"\b(?:a/c|account(?:\s*(?:no\.?|number))?)\s*[:#]?\s*(\d{9,18})\b", re.I), "restricted", None),
    ("DOB", re.compile(r"\b(?:dob|date of birth|born on)\s*[:\-]?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})", re.I), "confidential", None),
    ("EMAIL", re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"), "confidential", None),
    ("CARD", re.compile(r"\b(?:\d[ -]?){13,19}\b"), "restricted", _luhn_ok),
    ("IBAN", re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b"), "restricted", None),
    ("AADHAAR", re.compile(r"\b[2-9]\d{3}[ -]?\d{4}[ -]?\d{4}\b"), "restricted", None),
    ("PAN", re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b"), "restricted", None),
    ("SSN", re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "restricted", None),
    ("PASSPORT", re.compile(r"\b(?:passport\s*(?:no\.?|number)?\s*[:#]?\s*)([A-Z]\d{7})\b", re.I), "restricted", None),
    ("PHONE", re.compile(r"(?<![\w<])(?:\+\d{1,3}[ -]?)?\d[\d -]{8,13}\d(?!\w)"), "confidential", None),
    ("IP", re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"), "internal", None),
]


@dataclass
class PIIFinding:
    type: str
    sensitivity: str
    token: str
    start: int
    end: int

    def as_dict(self) -> dict:
        # The raw value is intentionally NOT stored.
        return {"type": self.type, "sensitivity": self.sensitivity, "token": self.token,
                "start": self.start, "end": self.end}


@dataclass
class PIIMasker:
    """Session-scoped masker; keeps a reversible vault in memory only."""
    _vault: dict[str, str] = field(default_factory=dict)
    _reverse: dict[str, str] = field(default_factory=dict)
    _counters: dict[str, int] = field(default_factory=dict)

    def _token(self, label: str, value: str) -> str:
        key = f"{label}:{value}"
        if key in self._reverse:
            return self._reverse[key]
        self._counters[label] = self._counters.get(label, 0) + 1
        tok = f"<{label}_{self._counters[label]}>"
        self._vault[tok] = value
        self._reverse[key] = tok
        return tok

    def mask(self, text: str) -> tuple[str, list[PIIFinding]]:
        spans: list[tuple[int, int, str, str]] = []
        for label, rx, sens, validator in _PATTERNS:
            for m in rx.finditer(text):
                g = 1 if m.groups() else 0
                start, end = m.span(g)
                value = m.group(g)
                if validator and not validator(value):  # type: ignore[operator]
                    continue
                if label == "PHONE" and not 10 <= sum(c.isdigit() for c in value) <= 13:
                    continue
                if any(s < end and start < e for s, e, _, _ in spans):
                    continue  # earlier (more specific) pattern already claimed it
                spans.append((start, end, label, sens))
        spans.sort()
        out, findings, cursor = [], [], 0
        for start, end, label, sens in spans:
            tok = self._token(label, text[start:end])
            out.append(text[cursor:start])
            out.append(tok)
            findings.append(PIIFinding(label, sens, tok, start, end))
            cursor = end
        out.append(text[cursor:])
        return "".join(out), findings

    def unmask(self, text: str) -> str:
        """Only for authorised, audited display; never used on LLM paths."""
        for tok, val in self._vault.items():
            text = text.replace(tok, val)
        return text


def classify_sensitivity(findings: list[PIIFinding]) -> str:
    order = ["public", "internal", "confidential", "restricted"]
    level = "public"
    for f in findings:
        if order.index(f.sensitivity) > order.index(level):
            level = f.sensitivity
    return level
