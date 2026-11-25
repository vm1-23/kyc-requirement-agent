"""Prompt-injection screening for untrusted stakeholder text and documents.

Defence in depth:
1. Heuristic detection of instruction-like content aimed at the model.
2. Untrusted content is always wrapped in delimited <untrusted_document> blocks in
   the *user* turn, never placed in the system prompt.
3. LLM output is schema-validated; citations must reference retrieved KB ids.
"""
from __future__ import annotations

import re

_RULES: list[tuple[str, re.Pattern[str]]] = [
    ("override_instructions", re.compile(r"\b(ignore|disregard|forget|override)\b.{0,40}\b(previous|prior|above|all|system)\b.{0,20}\b(instructions?|prompts?|rules?)\b", re.I)),
    ("role_hijack", re.compile(r"\b(you are now|act as|pretend to be|from now on you)\b", re.I)),
    ("system_prompt_probe", re.compile(r"\b(reveal|print|show|repeat)\b.{0,30}\b(system prompt|hidden instructions|your instructions)\b", re.I)),
    ("approval_bypass", re.compile(r"\b(mark|set|treat)\b.{0,40}\b(as )?(approved|compliant|baseline)\b.{0,40}\b(without|skip|bypass)\b", re.I)),
    ("control_bypass", re.compile(r"\b(skip|bypass|disable|turn off)\b.{0,30}\b(kyc|aml|sanction|screening|audit|approval|verification)\b.{0,40}\b(for (the )?(ai|model|assistant)|silently|do not (log|record))", re.I)),
    ("exfiltration", re.compile(r"\b(send|post|upload|exfiltrate|email)\b.{0,40}\b(https?://|www\.|@[\w-]+\.)", re.I)),
    ("delimiter_spoof", re.compile(r"</?(system|assistant|untrusted_document|instructions)>", re.I)),
]


def scan(text: str) -> list[str]:
    return [name for name, rx in _RULES if rx.search(text)]


def neutralise(text: str) -> str:
    """Defang delimiter spoofing so documents cannot close our wrapper tags."""
    return re.sub(r"<(/?)(system|assistant|untrusted_document|instructions)>", r"&lt;\1\2&gt;", text, flags=re.I)


def wrap_untrusted(doc_id: str, text: str) -> str:
    return (f'<untrusted_document id="{doc_id}">\n{neutralise(text)}\n</untrusted_document>')
