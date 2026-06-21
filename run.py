"""Command-line driver for ContractGuard.

    python run.py data/contracts/risky_saas.txt          # approve at the gate
    python run.py data/contracts/risky_saas.txt --reject  # reject at the gate

Programmatic entry point ``run_contract`` is reused by the Streamlit app and the
evaluation harness. It runs the graph, detects the human-approval interrupt, and
resumes with the supplied decision.
"""
from __future__ import annotations

import argparse
import os
import uuid

from langgraph.types import Command

from graph.build import build_graph
from tools.contract_parser import read_contract_file


def initial_state(text: str, name: str) -> dict:
    return {
        "contract_text": text,
        "contract_name": name,
        "audit_log": [],
        "errors": [],
        "compliance": [],
        "approvals": [],
    }


def run_contract(text, name, decision=None, graph=None, thread_id=None):
    """Run a contract end-to-end.

    Returns ``(final_state, interrupted, graph, config)``. If the graph pauses at
    the human-approval gate, it resumes with ``decision`` (default: auto-approve).
    """
    graph = graph or build_graph()
    thread_id = thread_id or f"{name}-{uuid.uuid4().hex[:8]}"
    config = {"configurable": {"thread_id": thread_id}}

    result = graph.invoke(initial_state(text, name), config)
    interrupted = bool(graph.get_state(config).next) or "__interrupt__" in result

    if interrupted:
        decision = decision or {"decision": "approved", "notes": "auto-approved"}
        result = graph.invoke(Command(resume=decision), config)

    return result, interrupted, graph, config


# --------------------------------------------------------------------------- #
# Pretty printing
# --------------------------------------------------------------------------- #
def _line(char="─", n=70):
    return char * n


def print_report(state: dict, interrupted: bool) -> None:
    from llm import llm_mode

    print(_line("="))
    print(f"  ContractGuard report — '{state.get('contract_name')}'  (LLM mode: {llm_mode()})")
    print(_line("="))

    report = state.get("risk_report")
    if report:
        print(f"\nOverall risk : {report.overall_risk.upper()}  (score {report.risk_score}/100)")
        print(f"Route        : {state.get('route')}")
        print(f"Summary      : {report.summary}")
        print("\nPer-clause analysis:")
        for cr in report.clause_risks:
            print(f"  • [{cr.risk.upper():8}] {cr.clause_type:22} {cr.recommendation:8} — {cr.deviation}")
        if report.missing_clauses:
            print(f"\nMissing critical clauses: {', '.join(report.missing_clauses)}")

    flags = state.get("compliance", [])
    if flags:
        print("\nCompliance flags:")
        for f in flags:
            tag = "BLOCKING" if f.blocking else "flag"
            print(f"  • ({tag}) [{f.kind}] {f.message}  <{f.policy_ref}>")

    redlines = state.get("redlines", [])
    if redlines:
        print(f"\nProposed redlines: {len(redlines)}")
        for r in redlines:
            print(f"  • {r.clause_type}: {r.reason}")

    print(f"\nInterrupted for human approval: {interrupted}")
    print("\nAudit log:")
    for entry in state.get("audit_log", []):
        print(f"  {entry}")
    print(_line("="))


def main():
    ap = argparse.ArgumentParser(description="Run a contract through ContractGuard.")
    ap.add_argument("path", help="path to a contract file (.txt / .md / .pdf)")
    ap.add_argument("--name", help="display name (defaults to filename)")
    ap.add_argument("--reject", action="store_true", help="reject at the approval gate")
    args = ap.parse_args()

    text = read_contract_file(args.path)
    name = args.name or os.path.splitext(os.path.basename(args.path))[0]
    decision = (
        {"decision": "rejected", "notes": "CLI --reject"}
        if args.reject
        else {"decision": "approved", "notes": "CLI approved"}
    )

    final, interrupted, _, _ = run_contract(text, name, decision=decision)
    print_report(final, interrupted)


if __name__ == "__main__":
    main()
