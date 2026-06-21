"""ContractGuard — Streamlit demo UI.

Run from the project root:

    streamlit run app/streamlit_app.py

Shows the full pipeline and, crucially, the human-in-the-loop approval gate: the
graph pauses before any external action and the reviewer must Approve / Edit /
Reject. State (the compiled graph + its checkpoint) is held in session so the
resume after approval works across Streamlit reruns.
"""
from __future__ import annotations

import os
import sys
import uuid

# Make the project root importable when launched as app/streamlit_app.py.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
from langgraph.types import Command

from graph.build import build_graph
from llm import llm_mode
from run import initial_state
from tools.contract_parser import read_contract_file

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONTRACTS_DIR = os.path.join(ROOT, "data", "contracts")

RISK_COLOR = {"low": "🟢", "medium": "🟡", "high": "🟠", "critical": "🔴"}

st.set_page_config(page_title="ContractGuard", page_icon="📝", layout="wide")


def _reset():
    for k in ("stage", "graph", "config", "state", "interrupted"):
        st.session_state.pop(k, None)


def _run_until_gate(text: str, name: str):
    graph = build_graph()
    config = {"configurable": {"thread_id": f"{name}-{uuid.uuid4().hex[:8]}"}}
    graph.invoke(initial_state(text, name), config)
    snap = graph.get_state(config)
    interrupted = bool(snap.next)
    st.session_state.graph = graph
    st.session_state.config = config
    st.session_state.state = snap.values
    st.session_state.interrupted = interrupted
    st.session_state.stage = "review" if interrupted else "blocked"


def _resume(decision: dict):
    graph = st.session_state.graph
    config = st.session_state.config
    graph.invoke(Command(resume=decision), config)
    st.session_state.state = graph.get_state(config).values
    st.session_state.stage = "done"


# --------------------------------------------------------------------------- #
# Sidebar
# --------------------------------------------------------------------------- #
with st.sidebar:
    st.title("📝 ContractGuard")
    st.caption("Multi-agent contract-review copilot · LangGraph")
    mode = llm_mode()
    st.info(f"LLM mode: **{mode}**" + ("  _(deterministic)_" if mode == "mock" else ""))
    st.markdown(
        "**Agents**\n\n"
        "1. Intake / Parse\n"
        "2. Retrieval (RAG)\n"
        "3. Risk Analysis\n"
        "4. Compliance / Guardrail\n"
        "5. Redline / Outreach\n\n"
        "+ Supervisor (routing + HITL)"
    )
    if st.button("↺ Start over", use_container_width=True):
        _reset()
        st.rerun()


# --------------------------------------------------------------------------- #
# Stage: input
# --------------------------------------------------------------------------- #
stage = st.session_state.get("stage", "input")

if stage == "input":
    st.header("Review a contract")
    samples = sorted(f for f in os.listdir(CONTRACTS_DIR) if f.endswith((".txt", ".md")))
    col1, col2 = st.columns([1, 2])
    with col1:
        choice = st.selectbox("Load a sample", ["(paste your own below)"] + samples)
        uploaded = st.file_uploader("…or upload .txt / .pdf", type=["txt", "md", "pdf"])
    default_text = ""
    name = "pasted_contract"
    if uploaded is not None:
        if uploaded.name.lower().endswith(".pdf"):
            tmp = os.path.join(ROOT, "outbox", uploaded.name)
            with open(tmp, "wb") as fh:
                fh.write(uploaded.getbuffer())
            default_text = read_contract_file(tmp)
        else:
            default_text = uploaded.getvalue().decode("utf-8", errors="ignore")
        name = os.path.splitext(uploaded.name)[0]
    elif choice != "(paste your own below)":
        default_text = read_contract_file(os.path.join(CONTRACTS_DIR, choice))
        name = os.path.splitext(choice)[0]

    text = st.text_area("Contract text", value=default_text, height=320)
    if st.button("▶ Run review", type="primary"):
        if text.strip():
            with st.spinner("Running 5 agents…"):
                _run_until_gate(text, name)
            st.rerun()
        else:
            st.warning("Paste or load a contract first.")


# --------------------------------------------------------------------------- #
# Shared report renderer
# --------------------------------------------------------------------------- #
def render_report(state: dict):
    report = state.get("risk_report")
    if report:
        c1, c2, c3 = st.columns(3)
        c1.metric("Overall risk", f"{RISK_COLOR.get(report.overall_risk,'')} {report.overall_risk.upper()}")
        c2.metric("Risk score", f"{report.risk_score}/100")
        c3.metric("Route", state.get("route", "—"))
        st.caption(report.summary)

        st.subheader("Per-clause analysis")
        st.dataframe(
            [
                {
                    "clause": cr.clause_type.replace("_", " "),
                    "risk": cr.risk.upper(),
                    "recommendation": cr.recommendation,
                    "deviation": cr.deviation,
                }
                for cr in report.clause_risks
            ],
            use_container_width=True,
            hide_index=True,
        )
        if report.missing_clauses:
            st.warning("Missing critical clauses: " + ", ".join(c.replace("_", " ") for c in report.missing_clauses))

    flags = state.get("compliance", [])
    if flags:
        st.subheader("Compliance flags")
        for f in flags:
            badge = "🚫 BLOCKING" if f.blocking else "⚠️"
            st.markdown(f"{badge} **{f.kind}** — {f.message}  \n<small>policy: `{f.policy_ref}`</small>", unsafe_allow_html=True)

    with st.expander("🔎 RAG grounding (playbook evidence per clause)"):
        for m in state.get("matches", []):
            if m.evidence:
                st.markdown(f"**clause {m.clause_id}** ({m.clause_type.replace('_',' ')})")
                for e in m.evidence:
                    st.caption(f"`{e.source}` (score {e.score}) — {e.snippet[:160]}…")


# --------------------------------------------------------------------------- #
# Stage: review (human approval gate)
# --------------------------------------------------------------------------- #
if stage == "review":
    state = st.session_state.state
    st.header(f"Review package — {state.get('contract_name')}")
    if state.get("needs_senior_review"):
        st.error("⚖️ Senior-counsel review required (high/critical risk).")
    render_report(state)

    redlines = state.get("redlines", [])
    if redlines:
        st.subheader(f"Proposed redlines ({len(redlines)})")
        for r in redlines:
            with st.expander(f"{r.clause_type.replace('_',' ')} — {r.reason}"):
                st.markdown("**Current:**")
                st.code(r.original, language=None)
                st.markdown("**Proposed:**")
                st.code(r.proposed, language=None)

    outreach = state.get("outreach")
    edited_body = None
    if outreach:
        st.subheader("Outreach (awaiting your approval to send)")
        st.text(f"To: {outreach.to}\nSubject: {outreach.subject}")
        edited_body = st.text_area("Email body (editable)", value=outreach.body, height=220)
        with st.expander("Internal summary memo"):
            st.text(outreach.summary_memo)

    st.divider()
    st.markdown("### 🔐 Human approval gate")
    st.caption("Nothing is sent until you approve. This is the mandatory HITL checkpoint.")
    a, b, c = st.columns(3)
    if a.button("✅ Approve & send", type="primary", use_container_width=True):
        dec = {"decision": "approved", "notes": "approved via UI"}
        if outreach and edited_body and edited_body != outreach.body:
            dec = {"decision": "edited", "notes": "edited via UI", "edited_outreach": edited_body}
        _resume(dec)
        st.rerun()
    if b.button("✏️ Approve edits & send", use_container_width=True):
        _resume({"decision": "edited", "notes": "edited via UI", "edited_outreach": edited_body or (outreach.body if outreach else "")})
        st.rerun()
    if c.button("❌ Reject", use_container_width=True):
        _resume({"decision": "rejected", "notes": "rejected via UI"})
        st.rerun()


# --------------------------------------------------------------------------- #
# Stage: blocked (refusal — no human gate reached)
# --------------------------------------------------------------------------- #
if stage == "blocked":
    state = st.session_state.state
    st.header(f"Blocked — {state.get('contract_name')}")
    st.error(f"🚫 Pipeline refused to proceed · route = **{state.get('route')}**. No external action taken.")
    if state.get("errors"):
        for e in state["errors"]:
            st.code(e)
    render_report(state)
    with st.expander("📜 Audit log", expanded=True):
        for entry in state.get("audit_log", []):
            st.text(entry)


# --------------------------------------------------------------------------- #
# Stage: done
# --------------------------------------------------------------------------- #
if stage == "done":
    state = st.session_state.state
    approvals = state.get("approvals", [])
    verdict = approvals[-1].decision if approvals else "unknown"
    st.header(f"Done — {state.get('contract_name')}")
    if verdict in ("approved", "edited"):
        st.success(f"✅ Reviewer **{verdict}** the package — outreach + redlines recorded to `outbox/`.")
    else:
        st.warning(f"❌ Reviewer **{verdict}** — no external action was taken.")
    render_report(state)
    with st.expander("📜 Full audit log", expanded=True):
        for entry in state.get("audit_log", []):
            st.text(entry)
