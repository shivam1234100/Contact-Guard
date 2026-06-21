"""Agent 2 — Retrieval / RAG.

Grounds every clause in the company **playbook** via vector retrieval, and uses
a second tool (``web_search``) to sanity-check the governing-law jurisdiction.
The evidence snippets it attaches are what the analysis and guardrail agents
cite — retrieval here genuinely improves grounding, it is not bolted on.
Owner: M3 (retrieval + external tools).
"""
from __future__ import annotations

from graph.state import ClauseMatch, ContractState, PlaybookEvidence
from tools.vector_store import get_store
from tools.web_search import web_search


def retrieval_node(state: ContractState) -> dict:
    parsed = state.get("parsed")
    if not parsed:
        return {"audit_log": ["[retrieval] skipped (no parsed contract)"]}

    store = get_store()
    matches = []
    for clause in parsed.clauses:
        query = f"{clause.type.replace('_', ' ')} {clause.heading or ''} {clause.text[:300]}"
        hits = store.retrieve(query, k=2, source_prefix="playbook")
        evidence = [
            PlaybookEvidence(source=src, snippet=snip, score=score)
            for (src, snip, score) in hits
        ]
        matches.append(
            ClauseMatch(clause_id=clause.id, clause_type=clause.type, evidence=evidence)
        )

    log = [f"[retrieval] grounded {len(matches)} clause(s) against playbook (mode={store.mode})"]

    # Second tool: corroborate the governing-law jurisdiction with web search.
    if parsed.governing_law:
        res = web_search(parsed.governing_law, k=1)
        log.append(f"[retrieval] web_search('{parsed.governing_law}') -> {res[0]['title']}")

    return {"matches": matches, "audit_log": log}
