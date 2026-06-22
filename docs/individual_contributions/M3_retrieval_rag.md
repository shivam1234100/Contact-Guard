# Individual Contribution — M3 (Retrieval): RAG / Matching

**Member:** <Member 3 name>
**Component:** Retrieval agent + vector store + embeddings + web-search tool

## What I owned
- **Retrieval agent** (`agents/retrieval.py`): for every clause, retrieves the
  most relevant playbook passages and attaches them as `PlaybookEvidence`.
- **Vector store** (`tools/vector_store.py`): chunks `playbook.md` and
  `policy.md` on `##` headings into citable passages, with two backends behind
  one interface — OpenAI embeddings + cosine in live mode, TF-IDF cosine in mock
  mode.
- **web_search tool** (`tools/web_search.py`): a second integration that
  sanity-checks the governing-law jurisdiction / named regulations.
- The knowledge content the system grounds on (co-authored `data/playbook.md`).

## Design decisions I made & can defend
- **RAG is justified, not bolted on.** Risk and compliance decisions must be
  grounded in *our actual* playbook/policy text; retrieval is what supplies that
  evidence and the citation ids (e.g. `policy.md#liability_policy`).
- **One interface, two backends.** Real embeddings when a key exists; a
  deterministic TF-IDF fallback otherwise. Same `retrieve()` signature, so the
  rest of the system is agnostic and the demo always works.
- **Heading-based chunking** gives stable, human-readable citations that map 1:1
  to clause topics — better than arbitrary fixed-size chunks for this domain.
- **A real second tool:** web_search corroborates external references, satisfying
  the "≥2 meaningful tools" requirement with a genuine use, not a stub.

## How my part connects
The evidence I attach is what the Analysis agent cites for each risk judgement
and what the Guardrail agent cites for each policy flag. Without my grounding
layer, those agents would be guessing.

## Q&A I can answer
Embedding vs. TF-IDF trade-offs, how chunking/citation works, what happens if
retrieval returns a weak match, and how to swap in a real search API.
