"""Conditional-edge decision functions for the StateGraph.

These are the supervisor's branching logic — pure functions of state, kept
separate from node implementations so the routing is easy to read and test.
"""
from __future__ import annotations

from graph.state import ContractState


def route_after_intake(state: ContractState) -> str:
    """Malformed/empty contracts short-circuit straight to the blocked node."""
    return "blocked" if state.get("blocked") else "retrieval"


def route_after_guardrail(state: ContractState) -> str:
    """Integrity violations (prompt injection) refuse; everything else proceeds
    to redline drafting + the human-approval gate."""
    return "blocked" if state.get("blocked") else "redline"


def route_after_decision(state: ContractState) -> str:
    """After the human approval gate: an approval (or edited approval) proceeds to
    the mock send; a rejection skips sending and goes straight to notifying the
    sender. Either way the sender is notified and the outcome is recorded."""
    approvals = state.get("approvals", [])
    verdict = approvals[-1].decision if approvals else "rejected"
    return "send" if verdict in ("approved", "edited") else "notify"
