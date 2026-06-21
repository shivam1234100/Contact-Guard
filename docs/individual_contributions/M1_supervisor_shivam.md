# Individual Contribution — M1 (Tech Lead): Supervisor / Orchestrator

**Member:** Shivam Tiwari
**Component:** Supervisor / Orchestrator + shared state + human-in-the-loop

## What I owned
- The LangGraph `StateGraph` that ties all five agents together
  (`graph/build.py`).
- The shared state contract and all Pydantic schemas, agreed with the team
  (`graph/state.py`).
- Conditional routing logic (`graph/routing.py`).
- The human-in-the-loop approval gate (`interrupt()` + `Command(resume=...)`),
  the `send` node (the only external action), and the `blocked` refusal node.
- Checkpointing (in-memory saver + msgpack allowlist for our schema types).
- The end-to-end runner and CLI (`run.py`) used by the demo and the eval.
- Integration and the live demo driver.

## Design decisions I made & can defend
- **Why LangGraph over a plain function pipeline:** I needed (1) conditional
  routing (blocked vs. fast-track vs. escalate), (2) a *pausable* graph for human
  approval, and (3) checkpointed state to resume after the pause. A linear script
  can't pause-and-resume mid-execution or branch declaratively.
- **One `ContractState` as the single source of truth**, with `operator.add`
  reducers on `audit_log`/`errors`/`compliance`/`approvals` so agents append
  without clobbering each other.
- **HITL as a real interrupt, not a UI hack:** `human_approval` calls
  `interrupt(payload)`; nothing downstream (`send`) can run until a human resumes
  with a decision. This is what makes "no external action without approval" a
  structural guarantee, not a convention.
- **Blocking vs. escalation split:** integrity violations (injection) and
  malformed input route to `blocked` and refuse; risky-but-legitimate contracts
  are escalated to a human. The supervisor encodes that policy in routing.

## How my part connects
Every agent reads from and writes to the state I defined; my routing functions
decide the path; my interrupt is the gate the Outreach agent's package must pass
through before the `send` node acts. The audit log I thread through every node is
the project's built-in trace.

## Q&A I can answer
Routing semantics, why a checkpointer is required for interrupts, how resume
works across Streamlit reruns, and how state reducers prevent lost updates.
