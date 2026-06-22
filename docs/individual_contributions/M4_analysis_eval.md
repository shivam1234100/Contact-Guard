# Individual Contribution — M4 (Evaluation): Risk Analysis + Eval Harness

**Member:** <Member 4 name>
**Component:** Risk Analysis agent + evaluation harness + 6 test cases

## What I owned
- **Risk Analysis agent** (`agents/analysis.py`): the evaluative core. Per-clause
  risk level, deviation from the playbook, recommendation, and rationale →
  aggregated `ContractRiskReport` with an overall score and missing-clause list.
- **Evaluation harness** (`eval/run_eval.py`, `eval/test_cases.py`) and the
  stored expected labels (`eval/expected/*.json`).
- The 6 sample contracts that drive the eval (`data/contracts/`).

## Design decisions I made & can defend
- **LLM judgement, deterministic aggregation.** Per-clause risk can come from the
  LLM (with playbook evidence) in live mode, but the *aggregation* (score →
  overall risk → route) is deterministic. That keeps routing and evaluation
  reproducible regardless of provider.
- **Heuristic fallback that's transparent.** In mock mode each clause type has an
  explicit, defensible rule (e.g. "unlimited" → critical). This is what lets the
  whole project run and be graded with no keys.
- **Evidence-only.** Recommendations cite retrieved playbook refs; the agent
  doesn't invent obligations.
- **Eval covers behaviour, not just happy path:** clean, risky, borderline,
  missing-clauses, prompt-injection, and malformed — including the failure-mode
  cases examiners look for. Each is compared against a stored expected label.

## How my part connects
I consume the parsed contract + retrieval evidence and produce the report that
drives the supervisor's routing, the guardrail's policy checks, and the
redlines. My harness runs the *entire* graph for every case, so it validates the
whole team's work, not just my node.

## Q&A I can answer
How the risk score maps to routing thresholds, why aggregation is deterministic,
how the injection case proves the score isn't manipulated, and how to add a 7th
test case.
