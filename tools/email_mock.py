"""Tool: mock email + redline export.

These functions are the system's only "external actions" — and they are gated
behind human approval in the graph. They never contact a real mail server; they
record artifacts to ``outbox/`` and return a receipt. This is deliberate: for a
class demo you never wire a real send.
"""
from __future__ import annotations

import datetime as _dt
import json
from pathlib import Path
from typing import List

OUTBOX = Path(__file__).resolve().parents[1] / "outbox"


def _ts() -> str:
    return _dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def _safe(name: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in name)[:60]


def send_email(to: str, subject: str, body: str) -> dict:
    """Record an outbound email to outbox/ and return a receipt."""
    OUTBOX.mkdir(exist_ok=True)
    path = OUTBOX / f"email_{_safe(to)}_{_ts()}.txt"
    path.write_text(
        f"To: {to}\nSubject: {subject}\n\n{body}\n", encoding="utf-8"
    )
    return {"channel": "email", "to": to, "subject": subject, "path": str(path)}


def export_redlines(contract_name: str, redlines: List[dict]) -> dict:
    """Record a redline package to outbox/ and return a receipt."""
    OUTBOX.mkdir(exist_ok=True)
    path = OUTBOX / f"redlines_{_safe(contract_name)}_{_ts()}.json"
    path.write_text(json.dumps(redlines, indent=2), encoding="utf-8")
    return {"channel": "redline_export", "count": len(redlines), "path": str(path)}


def send_decision_notice(
    to: str, contract_name: str, decision: str, redlines: int = 0, reason: str = ""
) -> dict:
    """Email the contract sender the review outcome (approved or rejected)."""
    if decision in ("approved", "edited"):
        subject = f"Contract review complete — APPROVED with changes: {contract_name}"
        body = (
            f"Dear sender,\n\nYour contract '{contract_name}' has been reviewed and "
            f"approved to proceed with {redlines} proposed redline(s), which are "
            "attached for your acceptance.\n\nBest regards,\nContracts Team"
        )
    elif decision == "blocked":
        subject = f"Contract review — ON HOLD / FLAGGED: {contract_name}"
        body = (
            f"Dear sender,\n\nYour contract '{contract_name}' could not be processed "
            "automatically and has been flagged for manual review by our team."
            + (f" Note: {reason}." if reason else "")
            + "\n\nWe will follow up with you shortly.\n\nBest regards,\nContracts Team"
        )
    else:  # rejected
        subject = f"Contract review complete — NOT APPROVED: {contract_name}"
        body = (
            f"Dear sender,\n\nYour contract '{contract_name}' has been reviewed and "
            "we are unable to proceed as currently drafted."
            + (f" Reason: {reason}." if reason else "")
            + "\n\nWe're happy to discuss revisions.\n\nBest regards,\nContracts Team"
        )
    return send_email(to, subject, body)


def archive_record(record: dict) -> dict:
    """Write a compliance audit record to outbox/ and return a receipt."""
    OUTBOX.mkdir(exist_ok=True)
    name = record.get("contract", "contract")
    path = OUTBOX / f"record_{_safe(name)}_{_ts()}.json"
    path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    return {"channel": "audit_record", "path": str(path)}
