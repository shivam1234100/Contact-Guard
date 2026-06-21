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
