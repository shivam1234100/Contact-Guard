"""Supervisor / orchestrator — the LangGraph StateGraph that ties the 5 agents
together with conditional routing, a checkpointer, and a human-in-the-loop
interrupt before any external action.

Graph shape (5 agents + supervisor orchestration steps):

    START
      └─> session_start ─> intake ──(blocked?)──> blocked ─> record ─> END
            └─> retrieval ─> analysis ─> guardrail ──(blocked?)──> blocked ─> record ─> END
                                              └─> redline ─> human_approval (interrupt)
                                                     └─(approved)─> send ─> notify ─> record ─> END
                                                     └─(rejected)──────────> notify ─> record ─> END

The orchestration nodes (``session_start``, ``human_approval``, ``send``,
``notify``, ``record``, ``blocked``) are the supervisor's responsibility, not an
agent's — the architecture stays at 5 agents. Owner: M1 (tech lead).
"""
from __future__ import annotations

import datetime as _dt

from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from agents.analysis import analysis_node
from agents.guardrail import guardrail_node
from agents.intake import intake_node
from agents.redline import redline_node
from agents.retrieval import retrieval_node
from graph.routing import (
    route_after_decision,
    route_after_guardrail,
    route_after_intake,
)
from graph.state import Approval, ContractState, DecisionRecord
from tools.email_mock import (
    archive_record,
    export_redlines,
    send_decision_notice,
    send_email,
)


def human_approval_node(state: ContractState) -> dict:
    """HITL gate. Pauses the graph and surfaces the full review package for a
    human to approve / edit / reject before anything is sent."""
    report = state.get("risk_report")
    outreach = state.get("outreach")

    payload = {
        "type": "approval_request",
        "contract": state.get("contract_name"),
        "overall_risk": report.overall_risk if report else "unknown",
        "risk_score": report.risk_score if report else 0,
        "needs_senior_review": state.get("needs_senior_review", False),
        "compliance_flags": [f.model_dump() for f in state.get("compliance", [])],
        "redlines": [r.model_dump() for r in state.get("redlines", [])],
        "outreach": outreach.model_dump() if outreach else None,
    }

    # Execution pauses HERE until the caller resumes with Command(resume=...).
    decision = interrupt(payload)

    if isinstance(decision, str):
        decision = {"decision": decision}
    decision = decision or {}
    verdict = decision.get("decision", "approved")
    if verdict not in ("approved", "rejected", "edited"):
        verdict = "approved"
    notes = decision.get("notes")

    approval = Approval(
        action="send_redline_package",
        decision=verdict,  # type: ignore[arg-type]
        notes=notes,
        timestamp=_dt.datetime.now().isoformat(timespec="seconds"),
    )

    out: dict = {
        "approvals": [approval],
        "audit_log": [
            f"[hitl] reviewer decision: {verdict}" + (f" — {notes}" if notes else "")
        ],
    }

    # Allow the reviewer to edit the outreach body before sending.
    edited = decision.get("edited_outreach")
    if edited and outreach:
        outreach.body = edited
        out["outreach"] = outreach
    return out


def send_node(state: ContractState) -> dict:
    """The only place external actions happen — and only if approved."""
    approvals = state.get("approvals", [])
    verdict = approvals[-1].decision if approvals else "rejected"

    if verdict not in ("approved", "edited"):
        return {"audit_log": ["[send] reviewer rejected — NO external action taken"]}

    logs = []
    outreach = state.get("outreach")
    if outreach:
        rec = send_email(outreach.to, outreach.subject, outreach.body)
        logs.append(f"[send] email -> {rec['to']} (saved {rec['path']})")

    redlines = [r.model_dump() for r in state.get("redlines", [])]
    if redlines:
        exp = export_redlines(state.get("contract_name", "contract"), redlines)
        logs.append(f"[send] {exp['count']} redline(s) exported -> {exp['path']}")

    return {"audit_log": logs or ["[send] approved; nothing to send"]}


def blocked_node(state: ContractState) -> dict:
    """Terminal refusal node: records why and confirms no action was taken."""
    flags = state.get("compliance", [])
    errors = state.get("errors", [])
    reason = state.get("route", "BLOCKED")
    return {
        "audit_log": [
            f"[blocked] pipeline halted ({reason}); "
            f"{len(flags)} compliance flag(s), {len(errors)} error(s); "
            "NO external action taken."
        ]
    }


def session_start_node(state: ContractState) -> dict:
    """Open the review session and stamp who is reviewing (from the UI login)."""
    reviewer = state.get("reviewer") or "system"
    return {"audit_log": [f"[session] review session opened by {reviewer}"]}


def notify_node(state: ContractState) -> dict:
    """Email the contract sender the outcome — on approval, rejection, OR block.

    The recipient is the sender email entered in the UI (falls back to a default)."""
    to = state.get("sender_email") or "sender@counterparty.example.com"
    name = state.get("contract_name", "contract")

    if state.get("blocked"):
        verdict = "blocked"
    else:
        approvals = state.get("approvals", [])
        verdict = approvals[-1].decision if approvals else "rejected"

    report = state.get("risk_report")
    reason = report.summary if (verdict in ("rejected", "blocked") and report) else ""
    rec = send_decision_notice(
        to,
        name,
        verdict,
        redlines=len(state.get("redlines", [])),
        reason=reason,
    )
    return {
        "audit_log": [f"[notify] sender emailed: {verdict} -> {rec['to']} (saved {rec['path']})"]
    }


def record_node(state: ContractState) -> dict:
    """Archive a compliance audit record of the final outcome (approved/rejected/blocked)."""
    approvals = state.get("approvals", [])
    if state.get("blocked"):
        decision = "blocked"
    elif approvals:
        decision = approvals[-1].decision
    else:
        decision = "rejected"
    report = state.get("risk_report")
    record = DecisionRecord(
        contract=state.get("contract_name", "contract"),
        decision=decision,  # type: ignore[arg-type]
        reviewer=state.get("reviewer") or "system",
        overall_risk=report.overall_risk if report else None,
        route=state.get("route"),
        redlines=len(state.get("redlines", [])),
        timestamp=_dt.datetime.now().isoformat(timespec="seconds"),
        audit_steps=len(state.get("audit_log", [])),
    )
    receipt = archive_record(record.model_dump())
    return {
        "record_path": receipt["path"],
        "audit_log": [f"[record] decision '{decision}' archived -> {receipt['path']}"],
    }


# Pydantic schemas we knowingly store in checkpointed state. Registering them
# explicitly keeps the checkpoint serializer quiet and forward-compatible
# (instead of relying on langgraph's permissive "allow everything" default).
_ALLOWED_STATE_TYPES = [
    ("graph.state", name)
    for name in (
        "ParsedContract",
        "Clause",
        "ClauseMatch",
        "PlaybookEvidence",
        "ClauseRisk",
        "ContractRiskReport",
        "ComplianceFlag",
        "Redline",
        "OutreachDraft",
        "Approval",
        "DecisionRecord",
    )
]


def default_checkpointer() -> MemorySaver:
    serde = JsonPlusSerializer(allowed_msgpack_modules=_ALLOWED_STATE_TYPES)
    return MemorySaver(serde=serde)


def _new_builder() -> StateGraph:
    """Construct the (uncompiled) StateGraph: nodes, edges, conditional routing."""
    builder = StateGraph(ContractState)

    builder.add_node("session_start", session_start_node)
    builder.add_node("intake", intake_node)
    builder.add_node("retrieval", retrieval_node)
    builder.add_node("analysis", analysis_node)
    builder.add_node("guardrail", guardrail_node)
    builder.add_node("redline", redline_node)
    builder.add_node("human_approval", human_approval_node)
    builder.add_node("send", send_node)
    builder.add_node("notify", notify_node)
    builder.add_node("record", record_node)
    builder.add_node("blocked", blocked_node)

    builder.add_edge(START, "session_start")
    builder.add_edge("session_start", "intake")
    builder.add_conditional_edges(
        "intake", route_after_intake, {"blocked": "blocked", "retrieval": "retrieval"}
    )
    builder.add_edge("retrieval", "analysis")
    builder.add_edge("analysis", "guardrail")
    builder.add_conditional_edges(
        "guardrail", route_after_guardrail, {"blocked": "blocked", "redline": "redline"}
    )
    builder.add_edge("redline", "human_approval")
    builder.add_conditional_edges(
        "human_approval", route_after_decision, {"send": "send", "notify": "notify"}
    )
    builder.add_edge("send", "notify")
    builder.add_edge("blocked", "notify")
    builder.add_edge("notify", "record")
    builder.add_edge("record", END)
    return builder


def build_graph(checkpointer=None):
    """Compile the graph for local use (CLI, Streamlit, eval).

    A checkpointer is required for interrupts; defaults to an in-memory one.
    """
    return _new_builder().compile(
        checkpointer=checkpointer if checkpointer is not None else default_checkpointer()
    )


def make_graph():
    """Entry point for **LangGraph Platform** / ``langgraph dev`` (see langgraph.json).

    The platform supplies its own durable persistence, so we compile WITHOUT a
    checkpointer here — passing one would conflict with the platform-managed store.
    """
    return _new_builder().compile()
