"""Core domain models shared by every agent."""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class StakeholderRole(str, Enum):
    CUSTOMER = "customer"
    BUSINESS_ANALYST = "business_analyst"
    PRODUCT_OWNER = "product_owner"
    ARCHITECT = "architect"
    DEVELOPER = "developer"
    SECURITY = "security"
    COMPLIANCE = "compliance"
    LEGAL = "legal"
    RISK = "risk"
    OPERATIONS = "operations"
    AUDITOR = "auditor"
    PROJECT_MANAGER = "project_manager"


class SourceType(str, Enum):
    CONVERSATION = "conversation"
    TRANSCRIPT = "transcript"
    QUESTIONNAIRE = "questionnaire"
    EMAIL = "email"
    MEETING_NOTES = "meeting_notes"
    REQUIREMENT_DOC = "requirement_doc"
    POLICY = "policy"
    REGULATION = "regulation"
    API_SPEC = "api_spec"
    LEGACY_DOC = "legacy_doc"
    INCIDENT_REPORT = "incident_report"
    AUDIT_FINDING = "audit_finding"


class Category(str, Enum):
    BUSINESS = "business"
    STAKEHOLDER = "stakeholder"
    FUNCTIONAL = "functional"
    SECURITY = "security"
    PRIVACY = "privacy"
    REGULATORY = "regulatory"
    PERFORMANCE = "performance"
    AVAILABILITY = "availability"
    USABILITY = "usability"
    DATA = "data_management"
    INTEGRATION = "integration"
    AUDIT = "audit_reporting"
    OPERATIONAL = "operational"


NON_FUNCTIONAL = {
    Category.SECURITY, Category.PRIVACY, Category.PERFORMANCE, Category.AVAILABILITY,
    Category.USABILITY, Category.OPERATIONAL,
}


class Priority(str, Enum):
    MUST = "must"
    SHOULD = "should"
    COULD = "could"
    WONT = "wont"


class Level(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ApprovalStatus(str, Enum):
    DRAFT = "draft"
    NEEDS_CLARIFICATION = "needs_clarification"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    MODIFIED = "modified"
    REGENERATE = "regenerate"


class SourceDocument(BaseModel):
    id: str
    title: str
    type: SourceType
    stakeholder: str = ""
    role: StakeholderRole | None = None
    text: str
    masked_text: str = ""
    pii_findings: list[dict[str, Any]] = Field(default_factory=list)
    injection_flags: list[str] = Field(default_factory=list)
    quarantined: bool = False


class Evidence(BaseModel):
    """A pointer back to where a statement came from."""
    doc_id: str
    excerpt: str
    stakeholder: str = ""


class Citation(BaseModel):
    kb_id: str
    title: str
    source: str
    jurisdiction: str
    version: str
    excerpt: str = ""
    score: float = 0.0


class QualityIssue(BaseModel):
    type: str  # ambiguity | incompleteness | untestable | duplicate | ...
    detail: str
    severity: Level = Level.MEDIUM
    suggestion: str = ""


class Requirement(BaseModel):
    id: str
    statement: str
    categories: list[Category] = Field(default_factory=list)
    kind: str = "functional"  # functional | non_functional | business | constraint
    source_stakeholder: str = ""
    source_role: StakeholderRole | None = None
    evidence: list[Evidence] = Field(default_factory=list)
    business_justification: str = ""
    priority: Priority = Priority.SHOULD
    dependencies: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    regulations: list[Citation] = Field(default_factory=list)
    controls: list[str] = Field(default_factory=list)
    risk_level: Level = Level.LOW
    confidence: float = 0.5
    quality_issues: list[QualityIssue] = Field(default_factory=list)
    status: ApprovalStatus = ApprovalStatus.DRAFT
    origin: str = "extracted"  # extracted | derived_control | clarified | human
    history: list[dict[str, Any]] = Field(default_factory=list)


class ClarificationQuestion(BaseModel):
    id: str
    requirement_id: str | None = None
    target_role: StakeholderRole | None = None
    question: str
    reason: str
    answer: str | None = None


class Conflict(BaseModel):
    id: str
    requirement_ids: list[str]
    type: str  # contradiction | duplicate | overlap
    detail: str
    severity: Level = Level.MEDIUM
    resolution: str | None = None


class ComplianceMapping(BaseModel):
    requirement_id: str
    control_id: str
    control: str
    citations: list[Citation]
    obligation: str
    jurisdiction: str
    gap: bool = False
    needs_legal_review: bool = False
    confidence: float = 0.0


class ControlCoverage(BaseModel):
    control_id: str
    title: str
    mandatory: bool
    covered_by: list[str] = Field(default_factory=list)
    status: str = "gap"  # covered | partial | gap
    derived_requirement: str | None = None


class Risk(BaseModel):
    id: str
    title: str
    category: str  # business | technical | compliance | security | privacy | operational
    description: str
    likelihood: int  # 1..5
    impact: int  # 1..5
    level: Level
    mitigation: str
    owner: StakeholderRole
    linked_requirements: list[str] = Field(default_factory=list)


class SDLCFactor(BaseModel):
    name: str
    score: int  # 1..5
    rationale: str


class SDLCOption(BaseModel):
    model: str
    score: float  # 0..100
    reasons: list[str] = Field(default_factory=list)


class SDLCPhase(BaseModel):
    name: str
    activities: list[str]
    roles: list[str]
    deliverables: list[str]
    security_activities: list[str]
    testing: list[str]
    compliance_checkpoints: list[str]
    approval_gate: str
    entry_criteria: list[str]
    exit_criteria: list[str]
    traceability: list[str]


class SDLCRecommendation(BaseModel):
    factors: list[SDLCFactor]
    ranked: list[SDLCOption]
    selected: str
    explanation: str
    workflow: list[SDLCPhase] = Field(default_factory=list)
    status: ApprovalStatus = ApprovalStatus.PENDING_APPROVAL


class ApprovalItem(BaseModel):
    id: str
    gate: str  # baseline | regulatory_interpretation | high_risk_security | conflict | sdlc | change | architecture
    subject_id: str
    summary: str
    required_roles: list[StakeholderRole]
    decisions: list[dict[str, Any]] = Field(default_factory=list)
    status: ApprovalStatus = ApprovalStatus.PENDING_APPROVAL


class ProjectContext(BaseModel):
    name: str
    domain: str = "kyc_onboarding"
    jurisdictions: list[str] = Field(default_factory=lambda: ["GLOBAL"])
    description: str = ""
    channels: list[str] = Field(default_factory=list)
    customer_types: list[str] = Field(default_factory=list)
    legacy_systems: list[str] = Field(default_factory=list)
    timeline_months: int | None = None
    team_size: int | None = None
    budget_flexibility: str = "medium"  # low | medium | high


class ProjectState(BaseModel):
    """The shared context the coordinator passes between agents."""
    project: ProjectContext
    documents: list[SourceDocument] = Field(default_factory=list)
    requirements: list[Requirement] = Field(default_factory=list)
    questions: list[ClarificationQuestion] = Field(default_factory=list)
    conflicts: list[Conflict] = Field(default_factory=list)
    compliance: list[ComplianceMapping] = Field(default_factory=list)
    coverage: list[ControlCoverage] = Field(default_factory=list)
    risks: list[Risk] = Field(default_factory=list)
    sdlc: SDLCRecommendation | None = None
    approvals: list[ApprovalItem] = Field(default_factory=list)
    open_issues: list[str] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=utcnow)

    def req(self, rid: str) -> Requirement | None:
        return next((r for r in self.requirements if r.id == rid), None)
