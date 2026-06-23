"""Agent 5 — Redline / Outreach.

Drafts the *proposed* changes: a redline for every clause the analysis wants to
fix, plus a counterparty negotiation email and an internal summary memo. It
prepares the package only — it never sends. Sending happens in a separate node,
and only after a human approves at the interrupt gate.
"""
from __future__ import annotations

from typing import List

from graph.state import (
    ContractState,
    OutreachDraft,
    Redline,
)

# Playbook "standard position" replacement text, used to draft redlines.
STANDARD_TEXT = {
    "limitation_of_liability": (
        "Each party's aggregate liability under this Agreement shall not exceed the "
        "total fees paid or payable in the twelve (12) months preceding the claim. "
        "Neither party shall be liable for indirect, incidental, or consequential damages."
    ),
    "indemnification": (
        "Each party shall indemnify the other against third-party claims arising from "
        "its breach of confidentiality or infringement of intellectual property. "
        "Indemnification obligations are mutual and subject to the liability cap."
    ),
    "auto_renewal": (
        "This Agreement renews for successive twelve (12) month terms unless either "
        "party gives sixty (60) days' written notice of non-renewal. No renewal term "
        "shall exceed twelve (12) months."
    ),
    "data_protection": (
        "The parties shall enter into a Data Processing Agreement compliant with GDPR "
        "Art. 28 and the India DPDP Act, 2023 governing any processing of personal data."
    ),
    "termination": (
        "Either party may terminate for material breach on thirty (30) days' written "
        "notice if uncured, and for convenience on sixty (60) days' written notice."
    ),
    "confidentiality": (
        "Each party shall protect the other's Confidential Information using no less "
        "than reasonable care, for three (3) years following disclosure."
    ),
}

_FIXABLE = {"redline", "reject", "escalate"}


def _short(text: str, n: int = 240) -> str:
    text = " ".join(text.split())
    return text if len(text) <= n else text[: n - 1] + "…"


def redline_node(state: ContractState) -> dict:
    parsed = state.get("parsed")
    report = state.get("risk_report")
    if not parsed or not report:
        return {"audit_log": ["[redline] skipped (nothing to draft)"]}

    clause_by_id = {c.id: c for c in parsed.clauses}
    redlines: List[Redline] = []

    # Redlines for clauses the analysis wants changed.
    for cr in report.clause_risks:
        if cr.recommendation in _FIXABLE:
            clause = clause_by_id.get(cr.clause_id)
            original = _short(clause.text) if clause else "(clause text unavailable)"
            proposed = STANDARD_TEXT.get(
                cr.clause_type, "Revise to align with the company playbook standard position."
            )
            redlines.append(
                Redline(
                    clause_id=cr.clause_id,
                    clause_type=cr.clause_type,
                    original=original,
                    proposed=proposed,
                    reason=cr.deviation,
                )
            )

    # Redlines that ADD missing critical clauses.
    for ct in report.missing_clauses:
        redlines.append(
            Redline(
                clause_id=0,
                clause_type=ct,
                original="(clause absent from contract)",
                proposed=STANDARD_TEXT.get(ct, f"Add a standard '{ct.replace('_', ' ')}' clause."),
                reason=f"Critical '{ct.replace('_', ' ')}' clause is missing.",
            )
        )

    # Build the outreach package.
    counterparty = parsed.parties[1] if len(parsed.parties) > 1 else "Counterparty"
    to = "legal@counterparty.example.com"
    subject = f"Redline & comments — {parsed.title or state.get('contract_name', 'contract')}"

    issue_lines = "\n".join(
        f"  {i}. [{r.clause_type.replace('_', ' ')}] {r.reason}"
        for i, r in enumerate(redlines, start=1)
    ) or "  (no changes requested)"

    body = (
        f"Dear {counterparty},\n\n"
        f"Thank you for the draft. Our review (overall risk: {report.overall_risk.upper()}) "
        f"identified {len(redlines)} item(s) we would like to address before signature:\n\n"
        f"{issue_lines}\n\n"
        "Proposed redlines are attached. We're happy to discuss on a call.\n\n"
        "Best regards,\nContracts Team"
    )

    top_issues = "\n".join(
        f"  - [{cr.risk.upper()}] {cr.clause_type.replace('_', ' ')}: {cr.deviation}"
        for cr in report.clause_risks
        if cr.risk in ("high", "critical")
    ) or "  - None"

    summary_memo = (
        f"CONTRACT REVIEW SUMMARY — {parsed.title or state.get('contract_name', 'contract')}\n"
        f"Overall risk: {report.overall_risk.upper()} (score {report.risk_score}/100)\n"
        f"Recommendation: {'PROCEED with redlines' if report.overall_risk != 'low' else 'ACCEPTABLE'}\n\n"
        f"Top issues:\n{top_issues}\n\n"
        f"Missing critical clauses: "
        f"{', '.join(c.replace('_', ' ') for c in report.missing_clauses) or 'none'}\n"
        f"Proposed redlines: {len(redlines)}"
    )

    outreach = OutreachDraft(to=to, subject=subject, body=body, summary_memo=summary_memo)

    return {
        "redlines": redlines,
        "outreach": outreach,
        "audit_log": [
            f"[redline] drafted {len(redlines)} redline(s) + outreach package (awaiting approval)"
        ],
    }
