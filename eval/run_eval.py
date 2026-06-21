"""Evaluation harness.

Runs every scenario in ``test_cases.py`` through the full graph and compares the
result against the stored expected labels in ``eval/expected/``. Forces
deterministic MOCK mode so results are reproducible without API keys.

    python -m eval.run_eval        # from the project root
"""
from __future__ import annotations

import os

# Force deterministic mock mode BEFORE importing anything that reads config.
os.environ.setdefault("CONTRACTGUARD_MOCK", "1")

import json
import sys
from pathlib import Path
from typing import List

from eval.test_cases import CASES
from run import run_contract
from tools.contract_parser import read_contract_file

ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = ROOT / "data" / "contracts"
EXPECTED = ROOT / "eval" / "expected"


def check(expected: dict, state: dict, interrupted: bool) -> List[str]:
    """Return a list of failure messages (empty == pass)."""
    fails: List[str] = []
    report = state.get("risk_report")
    overall = report.overall_risk if report else None

    if "route" in expected and state.get("route") != expected["route"]:
        fails.append(f"route={state.get('route')!r} != {expected['route']!r}")
    if "overall" in expected and overall != expected["overall"]:
        fails.append(f"overall={overall!r} != {expected['overall']!r}")
    if "overall_in" in expected and overall not in expected["overall_in"]:
        fails.append(f"overall={overall!r} not in {expected['overall_in']}")
    if "blocked" in expected and bool(state.get("blocked")) != expected["blocked"]:
        fails.append(f"blocked={bool(state.get('blocked'))} != {expected['blocked']}")
    if "interrupt" in expected and interrupted != expected["interrupt"]:
        fails.append(f"interrupt={interrupted} != {expected['interrupt']}")
    if "needs_senior_review" in expected and bool(state.get("needs_senior_review")) != expected["needs_senior_review"]:
        fails.append(
            f"needs_senior_review={bool(state.get('needs_senior_review'))} != {expected['needs_senior_review']}"
        )
    if expected.get("min_redlines"):
        n = len(state.get("redlines", []))
        if n < expected["min_redlines"]:
            fails.append(f"redlines={n} < {expected['min_redlines']}")
    if expected.get("has_missing"):
        miss = report.missing_clauses if report else []
        if not miss:
            fails.append("expected missing clauses, found none")
    if expected.get("injection_flag"):
        flags = state.get("compliance", [])
        if not any(f.kind == "prompt_injection" for f in flags):
            fails.append("expected a prompt_injection flag, found none")
    if expected.get("error"):
        if not state.get("errors"):
            fails.append("expected an error, found none")
    return fails


def main() -> None:
    rows = []
    passed = 0
    for filename, desc, expfile in CASES:
        text = read_contract_file(str(CONTRACTS / filename))
        expected = json.loads((EXPECTED / expfile).read_text())
        state, interrupted, _, _ = run_contract(
            text,
            filename.replace(".txt", ""),
            decision={"decision": "approved", "notes": "eval auto-approve"},
        )
        fails = check(expected, state, interrupted)
        ok = not fails
        passed += ok
        rows.append((ok, desc, state, fails))

    print()
    print("=" * 72)
    print(f"  ContractGuard evaluation — {passed}/{len(CASES)} scenarios passed")
    print("=" * 72)
    for ok, desc, state, fails in rows:
        report = state.get("risk_report")
        risk = report.overall_risk if report else "n/a"
        print(f"\n  [{'PASS' if ok else 'FAIL'}] {desc}")
        print(f"         route={state.get('route')}  risk={risk}  flags={len(state.get('compliance', []))}  redlines={len(state.get('redlines', []))}")
        for f in fails:
            print(f"         ✗ {f}")
    print("\n" + "=" * 72)

    sys.exit(0 if passed == len(CASES) else 1)


if __name__ == "__main__":
    main()
