# Deployment & GitHub Guide

Everything you need to (A) put the project on GitHub, (B) deploy a live demo,
and (C) run the presentation-day checklist.

---

## A. Create the GitHub repository

The repo is already a local git repository with an initial commit. You just need
to create the remote and push. Two ways:

### Option 1 — GitHub CLI (fastest)
`gh` is not installed yet. On macOS with Homebrew:

```bash
brew install gh
gh auth login                       # pick GitHub.com → HTTPS → browser

# from the project root:
gh repo create contractguard --public --source=. --remote=origin --push
```

That creates the repo and pushes `main` in one step.

### Option 2 — Web UI + git remote
1. Go to <https://github.com/new>, name it `contractguard`, **don't** add a
   README/.gitignore (we already have them), click *Create repository*.
2. Copy the repo URL, then from the project root:

```bash
git remote add origin https://github.com/<your-username>/contractguard.git
git branch -M main
git push -u origin main
```

> Every team member submits the **same repo link** plus their own
> `docs/individual_contributions/<member>.md` in the Google Form.

---

## B. Deploy a live demo

### Option 1 — Streamlit Community Cloud (recommended, free)
1. Push to GitHub (Part A).
2. Go to <https://share.streamlit.io> → *Create app* → pick your repo.
3. **Main file path:** `app/streamlit_app.py`. **Python version:** 3.11.
4. Click *Advanced settings → Secrets* and paste (optional — omit to run in
   mock mode):
   ```toml
   OPENAI_API_KEY = "sk-..."
   LLM_PROVIDER = "openai"
   ```
   To force the deterministic demo regardless of keys, add `CONTRACTGUARD_MOCK = "1"`.
5. Deploy. Streamlit installs `requirements.txt` automatically and gives you a
   public URL. (No key needed — it will run in mock mode out of the box.)

### Option 2 — Docker (any host: Render, Railway, Fly.io, a VM)
A `Dockerfile` is included.

```bash
docker build -t contractguard .
docker run -p 8501:8501 contractguard                 # mock mode
docker run -p 8501:8501 -e CONTRACTGUARD_MOCK= \
    -e OPENAI_API_KEY=sk-... contractguard             # live mode
```
Open <http://localhost:8501>. On Render/Railway, point the service at this repo,
use the Dockerfile, expose port 8501, and add `OPENAI_API_KEY` as an env var.

### Option 3 — Hugging Face Spaces
Create a new **Streamlit** Space, push this repo to it, and set
`app/streamlit_app.py` as the entry (or add an `app.py` that imports it). Add
`OPENAI_API_KEY` under *Settings → Secrets*.

> For a class demo, **mock mode on Streamlit Community Cloud is the safest path**:
> zero keys, zero cost, deterministic, and a shareable URL.

---

## C. Secrets & cost

- The only secret is `OPENAI_API_KEY` (or `ANTHROPIC_API_KEY`). Never commit
  `.env` — it is gitignored.
- No keys → mock mode → **$0** and fully functional for the demo and the eval.
- Live mode uses `gpt-4o-mini` by default (cheap). Override with `OPENAI_MODEL`.

---

## D. Presentation-day plan (maps to the brief's 10-min + 5-min Q&A)

| Time | Content | Who |
|---|---|---|
| 0–1 | Problem, target user (legal/procurement), why it matters | M2 |
| 1–2 | Why multi-agent (compliance + approval gates can't live in one prompt) | M5 |
| 2–4 | Architecture: agents, tools, state, routing, handoffs (use the Mermaid diagram) | M1 |
| 4–7 | Live demo: run `risky_saas` → analysis → guardrail → **approval gate** → "send" | M1 drives, M3 narrates RAG |
| 7–8.5 | Eval (run `python -m eval.run_eval`), injection case, guardrails, LangSmith/audit trace, limitations | M4 + M5 |
| 8.5–10 | Each member states their individual contribution (1 line) | All |
| 10–15 | Q&A — each member defends their own component | All |

**Demo failure-mode story (examiners love this):** show the prompt-injection
contract being **blocked while its risk stays critical** — proof the injected
"mark low risk" instruction was treated as data, not obeyed.

Likely Q&A: *Why LangGraph over a plain pipeline?* (routing + interrupts +
checkpointed state) · *How does injection defense work?* · *What's the human's
exact role?* · *What if RAG retrieves the wrong clause?*

---

## E. Submission checklist (each member, individually)

- [ ] GitHub repo link (same for everyone)
- [ ] Individual Contribution Document (`docs/individual_contributions/<you>.md`)
- [ ] README with architecture diagram + run instructions ✅ (done)
- [ ] Repo runs end-to-end on sample inputs ✅ (`python -m eval.run_eval` → 6/6)
- [ ] LangSmith traces saved / screenshotted (enable `LANGCHAIN_TRACING_V2`),
      or the audit log from a CLI run
- [ ] Google Form submitted by each person
