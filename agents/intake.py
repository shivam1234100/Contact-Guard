"""Agent 1 — Intake / Parse.

Turns the raw uploaded contract into a structured ``ParsedContract``. Parsing is
deterministic (an I/O concern), and malformed input fails *gracefully*: instead
of crashing the graph, it sets ``blocked`` + an error and lets the supervisor
route straight to the blocked node. Owner: M2 (I/O boundary).
"""
from __future__ import annotations

from graph.state import ContractState
from tools.contract_parser import parse_contract


def intake_node(state: ContractState) -> dict:
    name = state.get("contract_name", "contract")
    text = state.get("contract_text", "")

    try:
        parsed = parse_contract(text, name)
    except ValueError as exc:
        return {
            "route": "BLOCKED_INTAKE",
            "blocked": True,
            "errors": [f"intake: {exc}"],
            "audit_log": [f"[intake] FAILED to parse '{name}': {exc}"],
        }

    return {
        "parsed": parsed,
        "audit_log": [
            f"[intake] parsed '{name}': {len(parsed.clauses)} clause(s); "
            f"parties={parsed.parties or 'unknown'}; "
            f"law={parsed.governing_law or 'unspecified'}"
        ],
    }
