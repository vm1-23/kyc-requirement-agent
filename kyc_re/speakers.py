"""Split one free-text input into per-person statements.

Stakeholder input often arrives as a single paste: meeting notes or a chat where each person's words are
introduced by their name and designation, e.g.

    Priya (Product Owner): Customers must be able to open an account on the mobile app.
    Arjun, Chief Compliance Officer: Every applicant must be screened against sanctions lists.
    Meera - CISO said that biometric data must be encrypted at rest.

Each person becomes their own source document, so every extracted requirement is attributed to the person
who said it, with a role inferred from the designation (which the user can correct before analysis).
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

from .models import StakeholderRole as R

# Designation keywords -> role. Order matters: more specific phrases first.
ROLE_HINTS: list[tuple[str, R]] = [
    (r"business analyst|\bba\b", R.BUSINESS_ANALYST),
    (r"compliance|\bcco\b|\bmlro\b|\baml\b|\bbsa\b|money.laundering|financial crime|fincrime|kyc officer|nodal officer", R.COMPLIANCE),
    (r"legal|counsel|lawyer|\bdpo\b|data protection|privacy officer", R.LEGAL),
    (r"secur|\bciso\b|infosec|cyber|\bsoc\b", R.SECURITY),
    (r"architect|\bcto\b|platform|tech(nical)? lead|engineering (lead|head|manager)|head of it|\bit head\b|infrastructure|\bcio\b", R.ARCHITECT),
    (r"project manager|program(me)? manager|\bpm\b|\bpmo\b|delivery|scrum master", R.PROJECT_MANAGER),
    (r"\brisk\b|\bcro\b", R.RISK),
    (r"audit|regulator|examiner|inspector", R.AUDITOR),
    (r"operations|\bops\b|back.office|service desk|support|onboarding (team|lead|manager)|kyc (analyst|team|lead)", R.OPERATIONS),
    (r"developer|engineer|\bdev\b|programmer|\bqa\b|tester", R.DEVELOPER),
    (r"product|\bpo\b|\bcpo\b|head of digital|business (head|owner|lead)|sales|marketing|branch|\bceo\b|\bcoo\b|relationship manager", R.PRODUCT_OWNER),
    (r"customer|client|end.user|\buser\b|merchant|applicant|account holder|research panel", R.CUSTOMER),
    (r"analyst", R.BUSINESS_ANALYST),
]

# A name is 1-4 capitalised words on one line. Only short tokens (initials, "Dr.") may end in a period, so the end of
# the previous sentence ("... must use MFA.") is never glued onto the next speaker's name.
_WORD = r"[A-Z](?:[\w'’\-]*(?<!\.)|\w{0,2}\.)"
_NAME = rf"(?:(?:Dr|Mr|Mrs|Ms|Mx|Prof)\.?[ \t]+)?{_WORD}(?:[ \t]+{_WORD}){{0,3}}"
_VERBS = r"(?:said|says|wrote|writes|noted|notes|added|adds|mentioned|explained|stated|asked|commented|replied|responded)"
SPEAKER = re.compile(
    # A speaker starts a line or a sentence/clause, or appears mid-sentence when clearly marked with a
    # designation ("... we spoke to Lena, Head of Sales: ...").
    rf"""(?:^|(?<=[.!?;,]\s)|(?<=\s)(?={_NAME}\s*(?:\([^()\n]{{2,60}}\)|,\s*[^,:\n]{{2,60}}?\s*:|\s[-–—]\s)))[ \t>*•\-]*
    (?P<name>{_NAME})
    (?:\s*\((?P<d1>[^()\n]{{2,60}})\)
      |\s*,\s*(?P<d2>[^,:\n]{{2,60}}?)(?=\s*(?::|{_VERBS}\b))
      |\s+[-–—]\s+(?P<d3>[^:\n]{{2,60}}?)(?=\s*(?::|{_VERBS}\b))
    )?
    \s*(?:(?P<verb>{_VERBS})(?:\s+that)?\s*[:,]?|:)[ \t]*""",
    re.M | re.X)

# Labels that look like "Name:" but are not people.
NOT_A_PERSON = {
    "from", "sent", "note", "notes", "nb", "ps", "subject", "re", "fw", "fwd", "to", "cc", "bcc", "date", "time", "example", "e.g",
    "requirement", "requirements", "summary", "action", "actions", "action items", "decision", "decisions", "background",
    "context", "update", "important", "agenda", "minutes", "attendees", "participants", "step", "phase", "option", "goal",
    "goals", "objective", "objectives", "issue", "issues", "problem", "solution", "comment", "response", "reply",
    "feedback", "answer", "a", "outcome", "result", "results", "next steps", "todo", "warning", "tip", "source",
    "title", "status", "priority", "owner", "deadline", "scope", "out of scope", "in scope", "assumption", "assumptions",
    "risk", "risks", "dependency", "dependencies", "constraint", "constraints", "http", "https", "monday", "tuesday",
    "wednesday", "thursday", "friday", "saturday", "sunday", "today", "yesterday", "also", "however", "finally", "first",
    "second", "third", "then", "and", "but", "so", "the", "this", "that", "we", "i", "they", "it",
}
# Sentence openers that the capitalised-name pattern can swallow ("Then Marco (Platform) said ...").
LEADERS = {"then", "and", "but", "so", "also", "finally", "next", "later", "meanwhile", "however", "here", "there", "when",
           "while", "after", "before", "in", "at", "on", "we", "our", "per", "from", "according"}
INTERVIEWER = {"interviewer", "moderator", "facilitator", "host", "q", "question", "analyst (interviewer)"}


def role_for(*texts: str) -> R | None:
    for t in texts:
        low = (t or "").lower()
        if not low:
            continue
        for pat, role in ROLE_HINTS:
            if re.search(pat, low):
                return role
    return None


@dataclass
class Speaker:
    name: str
    designation: str = ""
    role: str | None = None
    role_source: str = ""  # "designation" | "name" | ""
    text: str = ""
    turns: int = 0
    attributed: bool = True
    _parts: list[str] = field(default_factory=list, repr=False)

    @property
    def label(self) -> str:
        if not self.attributed:
            return "Unattributed"
        return f"{self.name} ({self.designation})" if self.designation else self.name

    def as_dict(self) -> dict:
        d = asdict(self)
        d.pop("_parts")
        d["label"] = self.label
        d["words"] = len(self.text.split())
        return d


def _is_person(name: str) -> bool:
    low = name.lower().strip(" .")
    first = low.split()[0] if low else ""
    return bool(low) and low not in NOT_A_PERSON and first not in NOT_A_PERSON and not low.isdigit()


def split_speakers(text: str) -> list[Speaker]:
    """Return one Speaker per distinct person, in order of first appearance.

    Text before the first recognised speaker, or the whole text if nobody is named, comes back as a single
    unattributed entry (an email's ``From:`` line names its sender when present)."""
    text = (text or "").replace("\r\n", "\n").strip()
    if not text:
        return []
    marks = []
    for m in SPEAKER.finditer(text):
        words = m.group("name").split()
        while len(words) > 1 and words[0].lower().strip(".,") in LEADERS:
            words.pop(0)
        # An initial ("J. Smith") only counts at the start of a line or sentence; mid-sentence, "X." is the end of
        # the previous sentence ("... we need X. Arjun, CCO: ...").
        before = text[: m.start("name")].rstrip(" \t")
        if len(words) > 1 and re.fullmatch(r"[A-Z]\w?\.", words[0]) and before and before[-1] not in "\n.!?;:":
            words.pop(0)
        name = " ".join(words)
        if name.lower() in INTERVIEWER:
            marks.append((m, None))
        elif _is_person(name):
            marks.append((m, name))

    people: dict[str, Speaker] = {}
    pending_questions: list[str] = []

    def add(name: str | None, desig: str, chunk: str) -> None:
        chunk = chunk.strip()
        if name is None:  # interviewer: keep their question as context for whoever answers next
            if chunk:
                pending_questions.append(f"Interviewer: {chunk}")
            return
        if not chunk:
            return
        key = name.lower()
        sp = people.get(key)
        if sp is None:
            sp = people[key] = Speaker(name=name)
        if desig and not sp.designation:
            sp.designation = desig
        sp._parts.extend(pending_questions)
        pending_questions.clear()
        sp._parts.append(chunk)
        sp.turns += 1

    head = text[: marks[0][0].start()] if marks else text
    for i, (m, name) in enumerate(marks):
        end = marks[i + 1][0].start() if i + 1 < len(marks) else len(text)
        desig = next((g.strip(" .,") for g in (m.group("d1"), m.group("d2"), m.group("d3")) if g), "")
        add(name, desig, text[m.end():end])

    out = list(people.values())
    head = head.strip()
    if head and out and len(head.split()) <= 12 and not re.search(r"\b(must|shall|should|need|needs|require|requires|want|wants|has to|have to)\b", head, re.I):
        head = ""  # a lead-in like "In the workshop," before the first speaker, not a statement
    if head:
        frm = re.search(r"^from:\s*\"?([^\"<\n]+?)\"?\s*(?:<[^>]*>)?\s*$", head, re.I | re.M)
        if frm and not out:
            sp = Speaker(name=frm.group(1).strip(), _parts=[head], turns=1)
        else:
            sp = Speaker(name="", attributed=False, _parts=[head], turns=1)
        out.insert(0, sp)
    if pending_questions and out:  # trailing questions nobody answered
        out[-1]._parts.extend(pending_questions)

    for sp in out:
        sp.text = "\n".join(sp._parts).strip()
        if sp.attributed:
            r = role_for(sp.designation)
            src = "designation" if r else ""
            if r is None:
                r, src = role_for(sp.name), "name" if role_for(sp.name) else ""
            sp.role, sp.role_source = (r.value if r else None), src
    return out
