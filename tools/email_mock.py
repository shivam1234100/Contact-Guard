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
