"""Shared graph state and all structured-output schemas for ContractGuard.

This single file is the contract between agents. Every handoff is a validated
Pydantic model, and the whole pipeline reads/writes one ``ContractState``
object — the "single source of truth" that flows through the StateGraph.

    raw text -> ParsedContract -> ClauseMatch[] -> ContractRiskReport
             -> ComplianceFlag[] -> Redline[] + OutreachDraft -> Approval[]
"""
from __future__ import annotations

import operator
from typing import Annotated, List, Literal, Optional, TypedDict

from pydantic import BaseModel, Field

# --------------------------------------------------------------------------- #
# Vocabularies
# --------------------------------------------------------------------------- #
RiskLevel = Literal["low", "medium", "high", "critical"]
Recommendation = Literal["accept", "redline", "reject", "escalate"]
ClauseType = Literal[
    "limitation_of_liability",
    "indemnification",
    "confidentiality",
    "termination",
    "auto_renewal",
    "governing_law",
    "data_protection",
    "payment",
    "warranty",
    "ip_ownership",
    "dispute_resolution",
    "other",
]

# Clauses a B2B contract should always contain. Missing ones are flagged.
CRITICAL_CLAUSES: List[ClauseType] = [
    "limitation_of_liability",
    "confidentiality",
    "governing_law",
]


# --------------------------------------------------------------------------- #
# Stage 1 — Intake / parsing
# --------------------------------------------------------------------------- #
class Clause(BaseModel):
    id: int
    type: ClauseType = "other"
    heading: Optional[str] = None
    text: str


class ParsedContract(BaseModel):
    title: Optional[str] = None
    parties: List[str] = Field(default_factory=list)
    effective_date: Optional[str] = None
    governing_law: Optional[str] = None
    term: Optional[str] = None
    clauses: List[Clause] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Stage 2 — Retrieval (RAG grounding against the playbook)
# --------------------------------------------------------------------------- #
class PlaybookEvidence(BaseModel):
    source: str  # e.g. "playbook.md#limitation_of_liability"
    snippet: str
    score: float


class ClauseMatch(BaseModel):
    clause_id: int
    clause_type: ClauseType
    evidence: List[PlaybookEvidence] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Stage 3 — Risk analysis (the evaluative core)
# --------------------------------------------------------------------------- #
class ClauseRisk(BaseModel):
    clause_id: int
    clause_type: ClauseType
    risk: RiskLevel
    deviation: str  # how the clause deviates from the playbook standard
    recommendation: Recommendation
    rationale: str
    evidence_refs: List[str] = Field(default_factory=list)


class ContractRiskReport(BaseModel):
    overall_risk: RiskLevel
    risk_score: int = Field(ge=0, le=100)
    clause_risks: List[ClauseRisk] = Field(default_factory=list)
    missing_clauses: List[ClauseType] = Field(default_factory=list)
    summary: str = ""


# --------------------------------------------------------------------------- #
# Stage 4 — Compliance / guardrail
# --------------------------------------------------------------------------- #
class ComplianceFlag(BaseModel):
    kind: Literal[
        "policy_violation",
        "prompt_injection",
        "missing_protection",
        "bias",
        "other",
    ]
    severity: RiskLevel
    clause_id: Optional[int] = None
    message: str
    policy_ref: Optional[str] = None
    blocking: bool = False


# --------------------------------------------------------------------------- #
# Stage 5 — Redline / outreach (the action that needs human approval)
# --------------------------------------------------------------------------- #
class Redline(BaseModel):
    clause_id: int
    clause_type: ClauseType
    original: str
    proposed: str
    reason: str


class OutreachDraft(BaseModel):
    to: str
    subject: str
    body: str
    summary_memo: str


# --------------------------------------------------------------------------- #
# Human-in-the-loop decisions
# --------------------------------------------------------------------------- #
class Approval(BaseModel):
    action: str
    decision: Literal["approved", "rejected", "edited"]
    actor: str = "human_reviewer"
    notes: Optional[str] = None
    timestamp: str


# --------------------------------------------------------------------------- #
# Audit record (written by the supervisor's `record` step)
# --------------------------------------------------------------------------- #
class DecisionRecord(BaseModel):
    contract: str
    decision: Literal["approved", "edited", "rejected", "blocked"]
    reviewer: str = "system"
    overall_risk: Optional[RiskLevel] = None
    route: Optional[str] = None
    redlines: int = 0
    timestamp: str
    audit_steps: int = 0


# --------------------------------------------------------------------------- #
# The single shared state object
# --------------------------------------------------------------------------- #
class ContractState(TypedDict, total=False):
    """One object threaded through every node.

    ``audit_log``, ``errors`` and ``compliance`` use ``operator.add`` reducers
    so multiple nodes can append to them and LangGraph merges the deltas.
    """

    # --- inputs ---
    contract_text: str
    contract_name: str
    reviewer: str  # who is running the review (from the UI login); defaults set by callers
    sender_email: str  # where the status notification is emailed (the contract sender)

    # --- pipeline artifacts ---
    parsed: Optional[ParsedContract]
    matches: List[ClauseMatch]
    risk_report: Optional[ContractRiskReport]
    compliance: Annotated[List[ComplianceFlag], operator.add]
    redlines: List[Redline]
    outreach: Optional[OutreachDraft]
    approvals: Annotated[List[Approval], operator.add]

    # --- control / routing ---
    route: str  # human-readable route label, e.g. "REVIEW_REDLINE", "BLOCKED_INJECTION"
    needs_senior_review: bool
    blocked: bool
    record_path: Optional[str]  # where the audit record was archived

    # --- observability ---
    audit_log: Annotated[List[str], operator.add]
    errors: Annotated[List[str], operator.add]
