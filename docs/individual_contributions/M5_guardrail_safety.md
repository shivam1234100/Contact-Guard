# Individual Contribution — M5 (Safety): Compliance / Guardrail

**Member:** <Member 5 name>
**Component:** Compliance/Guardrail agent + policy RAG + injection defense

## What I owned
- **Guardrail agent** (`agents/guardrail.py`): prompt-injection defense,
  policy-grounded compliance checks, and missing-protection flags.
- The **compliance policy** the agent enforces (`data/policy.md`), grounded via
  RAG so every flag carries a citation.
- The safety write-up and the "why multi-agent" argument for the deck.

## Design decisions I made & can defend
- **Contract text is data, never instructions.** I scan raw clause text for
  injection patterns ("ignore previous instructions", "mark low risk",
  "approve automatically"). A hit raises a **blocking** flag and routes to
  `blocked`. Critically, because Analysis is independent and evidence-based, the
  injected text does **not** change the risk score — eval case 5 asserts the risk
  stays critical while the contract is refused.
- **Refuse vs. escalate.** Only integrity violations block. Genuinely risky but
  legitimate terms (unlimited liability, missing DPA, long auto-renewal) are
  *flagged and escalated to a human*, not silently rejected — the human decides.
- **Every flag is grounded.** I retrieve the relevant `policy.md` section and
  attach it as `policy_ref`, so a reviewer can audit *why* something was flagged.
- **Defense in depth:** Pydantic schema validation on handoffs + policy checks +
  injection scan + mandatory human approval downstream.

## How my part connects
I sit between Analysis and the Outreach/HITL gate. My routing decision
(`route_after_guardrail`) is what stops an injected or non-compliant contract
from ever reaching the send path, and my flags are surfaced to the human at the
approval gate.

## Q&A I can answer
How injection detection works and its limits, why blocking is reserved for
integrity violations, how policy grounding produces citations, and how this
layer would extend to bias/PII checks.
