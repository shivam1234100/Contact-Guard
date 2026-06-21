# Individual Contribution — M2 (I/O Boundary): Intake & Redline/Outreach

**Member:** <Member 2 name>
**Component:** Intake/Parse agent + Redline/Outreach agent + Pydantic schemas + mock action tools

## What I owned
- **Intake agent** (`agents/intake.py`) and the deterministic contract parser
  (`tools/contract_parser.py`): raw text/PDF → `ParsedContract` with typed
  clauses, party extraction, governing-law detection.
- **Redline/Outreach agent** (`agents/redline.py`): drafts a redline per risky
  clause (grounded in the playbook standard text), proposes redlines that *add*
  missing critical clauses, and produces the counterparty email + internal memo.
- The **mock action tools** (`tools/email_mock.py`) that record "sent" emails and
  exported redlines to `outbox/` — the system's only external actions.
- Co-authored the Pydantic schemas in `graph/state.py` (the data-in / data-out
  contract).

## Design decisions I made & can defend
- **Parsing is deterministic on purpose.** Intake is I/O, not reasoning, so a
  regex/heuristic splitter is more robust and debuggable than an LLM here, and it
  makes the whole pipeline run with no keys.
- **Graceful failure on malformed input:** the parser raises `ValueError` on
  empty/junk input; intake catches it and signals `blocked` so the graph never
  crashes (eval case 6).
- **The Outreach agent prepares, it never sends.** Sending is a separate node
  behind the human gate — I draft the package, the human approves, the supervisor
  sends. This cleanly separates "compose" from "act".
- **Redlines are grounded:** proposed text mirrors the playbook's standard
  position, so a reviewer sees a concrete fix, not just a complaint.

## How my part connects
I own both ends of the data flow: I turn the upload into the structured object
every other agent consumes, and I turn the analysis into the human-readable
package that leaves the system once approved.

## Q&A I can answer
How clause typing works, how malformed input is contained, why send is gated,
and how the outreach package is assembled from the risk report.
