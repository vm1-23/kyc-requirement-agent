"""Role-based access control for humans and least-privilege scopes for agents."""
from __future__ import annotations

from ..models import StakeholderRole as R

# Which human roles may sign which approval gate.
GATE_APPROVERS: dict[str, set[R]] = {
    "baseline": {R.PRODUCT_OWNER, R.BUSINESS_ANALYST, R.PROJECT_MANAGER},
    "regulatory_interpretation": {R.COMPLIANCE, R.LEGAL},
    "high_risk_security": {R.SECURITY},
    "conflict": {R.PRODUCT_OWNER, R.PROJECT_MANAGER},
    "architecture": {R.ARCHITECT},
    "sdlc": {R.PROJECT_MANAGER, R.ARCHITECT, R.SECURITY, R.COMPLIANCE},
    "change": {R.PRODUCT_OWNER, R.COMPLIANCE},
    "production_readiness": {R.PROJECT_MANAGER, R.SECURITY, R.COMPLIANCE, R.OPERATIONS},
}

# Gates where *every* listed role must approve (others: any one of them).
UNANIMOUS_GATES = {"sdlc", "production_readiness"}

# Data/tool scopes per agent (least privilege). "masked_text" = PII-masked content only.
AGENT_SCOPES: dict[str, set[str]] = {
    "interaction": {"read:masked_text", "write:documents", "read:templates"},
    "extraction": {"read:masked_text", "write:requirements", "llm"},
    "classification": {"read:requirements", "write:requirements", "llm"},
    "clarification": {"read:requirements", "write:questions", "llm"},
    "quality": {"read:requirements", "write:requirements"},
    "conflict": {"read:requirements", "write:conflicts"},
    "compliance": {"read:requirements", "read:kb", "write:compliance", "write:requirements", "llm"},
    "security_privacy": {"read:requirements", "read:kb", "write:requirements"},
    "risk": {"read:requirements", "read:compliance", "write:risks"},
    "sdlc": {"read:requirements", "read:risks", "read:project", "read:kb", "write:sdlc", "llm"},
    "documentation": {"read:requirements", "read:compliance", "read:risks", "read:sdlc", "write:artefacts"},
    "validation": {"read:requirements", "read:compliance", "write:metrics"},
    "approval": {"read:*", "write:approvals"},
}


class PermissionDenied(Exception):
    pass


def check_agent(agent: str, scope: str) -> None:
    scopes = AGENT_SCOPES.get(agent, set())
    if "read:*" in scopes and scope.startswith("read:"):
        return
    if scope not in scopes:
        raise PermissionDenied(f"agent '{agent}' lacks scope '{scope}'")


def can_approve(role: R, gate: str) -> bool:
    return role in GATE_APPROVERS.get(gate, set())
