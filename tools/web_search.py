"""Tool: web search (mock).

Lets the retrieval agent sanity-check an external legal reference (e.g. a
governing-law jurisdiction or a regulation named in the contract). For a class
demo we never hit the open internet — this returns deterministic canned results
so traces are reproducible. Swap ``_search`` for a real Tavily/SerpAPI/DDG call
to go live; the interface is unchanged.
"""
from __future__ import annotations

from typing import Dict, List

# A tiny "knowledge of the world" lookup keyed by topic substrings.
_CANNED: Dict[str, List[dict]] = {
    "gdpr": [
        {
            "title": "Art. 28 GDPR — Processor",
            "snippet": (
                "Processing by a processor shall be governed by a contract (a Data "
                "Processing Agreement) that sets out the subject-matter, duration, "
                "nature and purpose of the processing."
            ),
            "url": "https://gdpr-info.eu/art-28-gdpr/",
        }
    ],
    "dpdp": [
        {
            "title": "Digital Personal Data Protection Act, 2023 (India)",
            "snippet": (
                "A Data Fiduciary may engage a Data Processor only under a valid "
                "contract; obligations of security and breach notification apply."
            ),
            "url": "https://www.meity.gov.in/data-protection-framework",
        }
    ],
    "delaware": [
        {
            "title": "Delaware General Corporation Law",
            "snippet": (
                "Delaware is a common, well-understood governing-law choice for US "
                "commercial contracts; courts are experienced in contract disputes."
            ),
            "url": "https://corp.delaware.gov/",
        }
    ],
    "arbitration": [
        {
            "title": "Arbitration clauses — enforceability",
            "snippet": (
                "Binding arbitration limits the right to litigate; seat and rules "
                "(e.g. ICC, SIAC) materially affect cost and neutrality."
            ),
            "url": "https://www.newyorkconvention.org/",
        }
    ],
}


def web_search(query: str, k: int = 2) -> List[dict]:
    """Return up to ``k`` canned results whose topic appears in ``query``."""
    q = query.lower()
    results: List[dict] = []
    for topic, hits in _CANNED.items():
        if topic in q:
            results.extend(hits)
    if not results:
        results = [
            {
                "title": "No authoritative source found",
                "snippet": f"No canned reference matched '{query}'. Treat as unverified.",
                "url": "",
            }
        ]
    return results[:k]
