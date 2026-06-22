# ContractGuard — Architecture

## 1. Design goals

1. **Genuinely specialized agents.** Each node does one cognitive job with its
   own prompt/tools/failure modes. No single mega-prompt.
2. **Controllable & auditable.** A routing supervisor decides the path; every
   step appends to a shared `audit_log`.
3. **Safe by construction.** Risky text is *refused*; risky-but-legitimate text
   is *escalated to a human*. No external action without approval.
4. **Always demo-able.** A deterministic mock mode guarantees the graph runs
   end-to-end with no keys, so a flaky network never breaks the demo.

## 2. The graph

A LangGraph `StateGraph[ContractState]` compiled with an in-memory checkpointer
(required for interrupts). Nodes:

```
START → session_start → intake ─(blocked?)→ blocked → record → END
              └→ retrieval → analysis → guardrail ─(blocked?)→ blocked → record → END
                              └→ redline → human_approval ⏸
                                     ├─(approved)→ send → notify → record → END
                                     └─(rejected)──────→ notify → record → END
```

Every outcome emails the contract sender (the address entered in the UI): the
`notify` step handles approved/rejected, and the `blocked` node sends the
flagged/on-hold notice itself — so approved, rejected, *and* blocked all close the
loop with the sender.

The **5 agents** are `intake`, `retrieval`, `analysis`, `guardrail`, `redline`.
The other nodes are **supervisor / orchestration steps** (the architecture is
still 5 agents):

- **`session_start`** opens the review session and stamps the signed-in reviewer.
- **Conditional edges** (`graph/routing.py`):
  - `route_after_intake`: malformed/empty input → `blocked`, else `retrieval`.
  - `route_after_guardrail`: integrity violation (injection) → `blocked`, else `redline`.
  - `route_after_decision`: approved/edited → `send`, rejected → `notify`.
- **`human_approval`** calls `interrupt(payload)`; execution pauses and the
  caller resumes with `Command(resume=decision)`. This is the mandatory HITL.
- **`send`** performs the external action (mock send of the redline package), only
  if the recorded approval is `approved`/`edited`.
- **`notify`** emails the contract sender the outcome on BOTH approve and reject.
- **`record`** archives a `DecisionRecord` audit entry for every outcome
  (approved / rejected / blocked).
- **`blocked`** is a refusal node that records *why* and confirms no action taken.

## 3. Shared state & structured outputs

`ContractState` (a `TypedDict`) is the single source of truth. The pipeline
transforms it stage by stage, and **every handoff is a Pydantic model**:

| Stage | Produces | Schema |
|---|---|---|
| Intake | parsed contract | `ParsedContract { parties, governing_law, clauses[] }` |
| Retrieval | grounding evidence | `ClauseMatch { evidence: PlaybookEvidence[] }` |
| Analysis | risk report | `ContractRiskReport { overall_risk, risk_score, clause_risks[], missing_clauses[] }` |
| Guardrail | compliance flags | `ComplianceFlag { kind, severity, blocking, policy_ref }` |
| Redline | edits + outreach | `Redline[]`, `OutreachDraft` |
| Human | decision | `Approval { decision, notes, timestamp }` |

`audit_log`, `errors`, `compliance`, and `approvals` use `operator.add` reducers
so multiple nodes append without clobbering. Everything else is last-write-wins.

Pydantic objects are stored in the checkpoint, so `graph/build.py` registers them
with the serializer's `allowed_msgpack_modules` allowlist (forward-compatible,
no deprecation warnings).

## 4. The two LLM paths

`llm.py` exposes `structured(system, user, schema)`, which returns a validated
Pydantic object via the provider's `with_structured_output`. In **mock mode** it
raises, and each agent falls back to a transparent heuristic. This means:

- **Live mode** (`OPENAI_API_KEY` set): the analysis agent uses the LLM per
  clause, grounded in retrieved playbook text, with the heuristic as a safety net.
- **Mock mode**: deterministic heuristics + TF-IDF retrieval → reproducible
  evaluation and a demo that never depends on the network.

Parsing (intake) and sending (outreach) are deterministic by design — they are
I/O, not reasoning — which keeps the boundaries clean and debuggable.

## 5. RAG

`tools/vector_store.py` chunks `playbook.md` and `policy.md` on `##` headings,
giving each chunk a stable citation id (e.g. `policy.md#liability_policy`). The
analysis agent retrieves playbook chunks to ground clause risk; the guardrail
agent retrieves policy chunks to ground each compliance flag. Retrieval uses
OpenAI embeddings in live mode and TF-IDF cosine in mock mode — same interface.

## 6. Guardrails in depth

- **Prompt-injection defense.** The guardrail scans the *raw* clause text for
  instruction-like patterns. Because the analysis is independent and
  evidence-based, an injected "mark this low risk" does **not** change the score;
  the guardrail additionally raises a *blocking* flag and routes to `blocked`.
  (Eval case 5 asserts the risk stays high while the contract is refused.)
- **Policy refusal.** Unlimited liability, personal-data processing without a
  DPA, and >12-month auto-renewal each raise a policy flag citing `policy.md`.
- **Missing protections.** Absent critical clauses (liability, confidentiality,
  governing law) are flagged and proposed as redlines to *add*.
- **HITL.** Nothing is sent without `interrupt()` + human resume.

## 7. Failure handling

- Empty/short input → `ValueError` in the parser → caught by intake → `blocked`
  with an `errors[]` entry. The graph never throws.
- Live LLM error in analysis → per-clause heuristic fallback (logged).
- web_search miss → returns an "unverified" result rather than failing.
