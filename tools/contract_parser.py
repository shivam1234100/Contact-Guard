"""Tool: contract parser.

Turns raw contract text (or a PDF/txt file) into a structured ``ParsedContract``
with individually typed clauses. This is intentionally deterministic — parsing
is an I/O concern, not a reasoning one — which also makes the pipeline robust in
mock mode. Empty / junk input raises ``ValueError`` so the intake node can fail
gracefully (eval case: malformed input).
"""
from __future__ import annotations

import re
from typing import List, Optional

from graph.state import Clause, ClauseType, ParsedContract

# Keyword signatures used to label each clause with a ClauseType.
CLAUSE_KEYWORDS = {
    "limitation_of_liability": [
        "limitation of liability",
        "limit of liability",
        "aggregate liability",
        "liable",
        "liability",
        "consequential damages",
    ],
    "indemnification": ["indemnif", "hold harmless", "defend and"],
    "confidentiality": [
        "confidential",
        "non-disclosure",
        "proprietary information",
    ],
    "auto_renewal": [
        "automatically renew",
        "auto-renew",
        "auto renew",
        "renewal term",
        "evergreen",
    ],
    "termination": ["terminate", "termination", "right to terminate"],
    "governing_law": ["governing law", "governed by the laws", "governed by and"],
    "data_protection": [
        "personal data",
        "data protection",
        "data processing",
        "gdpr",
        "dpdp",
        "processor",
    ],
    "payment": ["payment terms", "fees", "invoice", "net 30", "net 45"],
    "warranty": ["warrant", "warranty", "as is", "as-is"],
    "ip_ownership": [
        "intellectual property",
        "ip ownership",
        "work product",
        "ownership of",
    ],
    "dispute_resolution": [
        "arbitration",
        "dispute resolution",
        "jurisdiction",
        "venue",
    ],
}

# Lines that begin a new clause: "1.", "1.2", "Section 3", "ARTICLE IV", or an
# ALL-CAPS / Title-Case heading possibly ending in a colon.
_HEADING_RE = re.compile(
    r"^\s*(?:"
    r"(?P<num>\d+(?:\.\d+)*)[.)]?\s+"  # 1.  1.2)
    r"|(?P<sec>(?:section|article|clause)\s+[\w.]+)\b[:.\s-]*"  # Section 3
    r")(?P<title>.*)$",
    re.IGNORECASE,
)


def classify_clause(text: str) -> ClauseType:
    """Best-effort clause typing by keyword frequency."""
    low = text.lower()
    best: Optional[ClauseType] = None
    best_hits = 0
    for ctype, kws in CLAUSE_KEYWORDS.items():
        hits = sum(low.count(kw) for kw in kws)
        if hits > best_hits:
            best_hits, best = hits, ctype  # type: ignore[assignment]
    return best or "other"


def _split_clauses(body: str) -> List[tuple]:
    """Return a list of (heading, text) tuples."""
    lines = body.splitlines()
    chunks: List[tuple] = []
    cur_head: Optional[str] = None
    cur_lines: List[str] = []

    def flush():
        text = "\n".join(cur_lines).strip()
        if text:
            chunks.append((cur_head, text))

    for line in lines:
        m = _HEADING_RE.match(line)
        if m and (m.group("num") or m.group("sec")):
            # New clause boundary.
            flush()
            label = (m.group("sec") or m.group("num") or "").strip()
            title = (m.group("title") or "").strip()
            cur_head = (f"{label} {title}").strip() or label
            cur_lines = [title] if title else []
        else:
            cur_lines.append(line)
    flush()

    # Fallback: if numbering didn't split it, use blank-line paragraphs.
    if len(chunks) < 2:
        paras = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
        chunks = [(None, p) for p in paras]
    return chunks


def _extract_parties(text: str) -> List[str]:
    parties: List[str] = []
    m = re.search(
        r"by and between\s+(.+?)\s+and\s+(.+?)(?:[.,(]|\n|$)",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    if m:
        parties = [m.group(1).strip(" \n\"'"), m.group(2).strip(" \n\"'")]
    return [p for p in parties if p][:2]


def _extract_field(text: str, pattern: str) -> Optional[str]:
    m = re.search(pattern, text, re.IGNORECASE)
    return m.group(1).strip(" .\n") if m else None


def parse_contract(text: str, name: str = "contract") -> ParsedContract:
    """Parse raw contract text into a ``ParsedContract``.

    Raises ``ValueError`` if the input is empty or too short to be a contract.
    """
    if not text or not text.strip():
        raise ValueError("empty contract: no text to parse")
    if len(text.strip()) < 40:
        raise ValueError("contract too short / malformed (<40 chars)")

    title = text.strip().splitlines()[0].strip()[:120] or name

    parties = _extract_parties(text)
    effective_date = _extract_field(
        text, r"effective (?:as of|date)[:\s]+([A-Za-z0-9 ,]+?)(?:\.|\n|by and)"
    )
    governing_law = _extract_field(
        text, r"governed by(?: and construed in accordance with)? the laws of\s+([A-Za-z ,]+)"
    )
    term = _extract_field(text, r"term of\s+([\w ]+?)(?:\.|,|\n)")

    clauses: List[Clause] = []
    for i, (heading, body) in enumerate(_split_clauses(text), start=1):
        clauses.append(
            Clause(
                id=i,
                type=classify_clause((heading or "") + " " + body),
                heading=heading,
                text=body,
            )
        )

    return ParsedContract(
        title=title,
        parties=parties,
        effective_date=effective_date,
        governing_law=governing_law,
        term=term,
        clauses=clauses,
    )


def read_contract_file(path: str) -> str:
    """Read a .txt/.md/.pdf contract file into raw text."""
    if path.lower().endswith(".pdf"):
        from pypdf import PdfReader

        reader = PdfReader(path)
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    with open(path, "r", encoding="utf-8", errors="ignore") as fh:
        return fh.read()
