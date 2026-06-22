# Team Guide — how each member contributes (fork & PR)

ContractGuard is a 5-person capstone. The rubric gives **15% for individual
contribution**, and evaluators look at (a) the repo's commit history and (b) each
person's contribution doc. This guide ensures **every member has a merged pull
request attributed to them** and **their own filled-in contribution doc**.

Workflow: each teammate **forks** the repo, edits **only their own component's
files**, fills in their contribution doc, and opens a **pull request**. Shivam
reviews and merges. After merge, each member shows up under the repo's
**Insights → Contributors**.

---

## 1. Who owns what

Each member edits **only the files in their row** (they don't overlap, so no merge
conflicts). Mapping matches `README.md` → Architecture and the
`docs/individual_contributions/` docs.

| Member | Role / contribution doc | Files you own (edit only these) |
|---|---|---|
| **M1 — Shivam** | Supervisor — `M1_supervisor_shivam.md` | `graph/build.py`, `graph/state.py`, `graph/routing.py`, `run.py` |
| **M2** | Intake & Redline/Outreach — `M2_intake_outreach.md` | `agents/intake.py`, `agents/redline.py`, `tools/contract_parser.py`, `tools/email_mock.py` |
| **M3** | Retrieval / RAG — `M3_retrieval_rag.md` | `agents/retrieval.py`, `tools/vector_store.py`, `tools/web_search.py`, `data/playbook.md` |
| **M4** | Risk Analysis & Eval — `M4_analysis_eval.md` | `agents/analysis.py`, `eval/run_eval.py`, `eval/test_cases.py`, `data/contracts/`, `eval/expected/` |
| **M5** | Compliance / Guardrail — `M5_guardrail_safety.md` | `agents/guardrail.py`, `data/policy.md` |

---

## 2. A safe, real code edit you can make (won't break the eval)

Pick something from your row — these are genuine improvements, additive, and keep
the evaluation green:

- **M2** — add a `STANDARD_TEXT` entry for a clause type that doesn't have one yet
  (e.g. `payment`, `ip_ownership`, `dispute_resolution`) in `agents/redline.py`;
  and/or improve the party/effective-date regex in `tools/contract_parser.py`.
- **M3** — add a new `## Section` to `data/playbook.md` and a new canned topic to
  the `_CANNED` dict in `tools/web_search.py` (e.g. an `indemnification` reference).
- **M4** — add a **7th evaluation scenario**: a new contract in `data/contracts/`,
  its expected labels in `eval/expected/<name>.json`, and a row in
  `eval/test_cases.py`. (Optionally a new heuristic in `agents/analysis.py`.) The
  eval becomes **7/7**.
- **M5** — add a new pattern to `INJECTION_PATTERNS` in `agents/guardrail.py`, and a
  new `## Policy` section in `data/policy.md` with a matching check.
- **M1 (Shivam)** — already has commits; optional small supervisor enhancement.

**In the same PR, also do your contribution doc:**
1. Rename your doc to include your name (keep the `Mx` prefix), e.g.
   `git mv docs/individual_contributions/M3_retrieval_rag.md docs/individual_contributions/M3_retrieval_rag_aarav.md`
2. Open it, replace `<Member N name>` with your real name, and write what you
   actually did (the file already lists what your component is).

---

## 3. Step-by-step: fork → edit → pull request

You need your **own GitHub account**.

1. Go to **https://github.com/shivam1234100/Contact-Guard** and click **Fork**
   (top-right). This creates a copy under your account.

2. Clone *your fork* and set your identity (critical — this is what attributes the
   commit to you):
   ```bash
   git clone https://github.com/<your-username>/Contact-Guard.git
   cd Contact-Guard
   git config user.name "Your Name"
   git config user.email "the-email-on-your-github-account@example.com"
   git checkout -b m3-retrieval-yourname     # name the branch after your part
   ```

3. Make your edits — **only your own files** (table above) + your renamed/filled doc.

4. Run the evaluation to be sure you didn't break anything:
   ```bash
   python3.11 -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   python -m eval.run_eval        # expect 6/6  (7/7 if you're M4 and added a case)
   ```

5. Commit and push to your fork:
   ```bash
   git add -A
   git commit -m "M3: add playbook section + web_search topic; fill contribution doc"
   git push origin m3-retrieval-yourname
   ```

6. Open **https://github.com/<your-username>/Contact-Guard** — GitHub shows a
   **"Compare & pull request"** button. Click it; the base is
   `shivam1234100/Contact-Guard` branch `main`. Add a short description, **Create
   pull request**.

7. **Shivam** reviews and clicks **Merge** (use *Create a merge commit* or *Squash
   and merge* — both keep you as the commit author). Done — you now appear under
   the repo's **Insights → Contributors**.

---

## 4. Checklist (per member)
- [ ] Forked the repo to my own GitHub account
- [ ] Set `git config user.email` to my GitHub email (so the commit is mine)
- [ ] Edited only my own files + made one real improvement
- [ ] Renamed my contribution doc to `Mx_role_<myname>.md` and filled in my name + work
- [ ] `python -m eval.run_eval` passes
- [ ] Opened a PR into `shivam1234100/Contact-Guard:main`
- [ ] (Shivam) merged it; I show up under Contributors
- [ ] Submitted the Google Form (repo link + my contribution doc)

## Tips / gotchas
- **Attribution depends on your git email** matching your GitHub account — double-check step 2.
- **Stay in your own files** to avoid merge conflicts with teammates.
- Shivam should **merge PRs one at a time and confirm the eval stays green** before the next.
- This doesn't affect the live app — Streamlit redeploys automatically when `main` updates.
