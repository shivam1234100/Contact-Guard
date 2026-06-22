"""Supervisor / orchestrator — the LangGraph StateGraph that ties the 5 agents
together with conditional routing, a checkpointer, and a human-in-the-loop
interrupt before any external action.

Graph shape:

    START
      └─> intake ──(blocked?)──> blocked ─> END
            └─> retrieval ─> analysis ─> guardrail ──(blocked?)──> blocked ─> END
                                              └─> redline ─> human_approval (interrupt)
                                                                  └─> send ─> END

The three orchestration nodes (``human_approval``, ``send``, ``blocked``) live
here because they are the supervisor's responsibility, not an agent's.
Owner: M1 (tech lead).
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
from graph.routing import route_after_guardrail, route_after_intake
from graph.state import Approval, ContractState
from tools.email_mock import export_redlines, send_email


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
    )
]


def default_checkpointer() -> MemorySaver:
    serde = JsonPlusSerializer(allowed_msgpack_modules=_ALLOWED_STATE_TYPES)
    return MemorySaver(serde=serde)


def _new_builder() -> StateGraph:
    """Construct the (uncompiled) StateGraph: nodes, edges, conditional routing."""
    builder = StateGraph(ContractState)

    builder.add_node("intake", intake_node)
    builder.add_node("retrieval", retrieval_node)
    builder.add_node("analysis", analysis_node)
    builder.add_node("guardrail", guardrail_node)
    builder.add_node("redline", redline_node)
    builder.add_node("human_approval", human_approval_node)
    builder.add_node("send", send_node)
    builder.add_node("blocked", blocked_node)

    builder.add_edge(START, "intake")
    builder.add_conditional_edges(
        "intake", route_after_intake, {"blocked": "blocked", "retrieval": "retrieval"}
    )
    builder.add_edge("retrieval", "analysis")
    builder.add_edge("analysis", "guardrail")
    builder.add_conditional_edges(
        "guardrail", route_after_guardrail, {"blocked": "blocked", "redline": "redline"}
    )
    builder.add_edge("redline", "human_approval")
    builder.add_edge("human_approval", "send")
    builder.add_edge("send", END)
    builder.add_edge("blocked", END)
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
