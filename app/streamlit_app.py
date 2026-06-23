"""ContractGuard — Streamlit demo UI.

Run from the project root:

    streamlit run app/streamlit_app.py

Flow: sign in as a reviewer → load/paste a contract → the 5 agents run → review the
tabbed report → the human-in-the-loop approval gate (Approve / Edit / Reject) →
the sender is notified and the outcome is archived. The compiled graph + its
checkpoint live in session_state so the resume after approval survives reruns.
"""
from __future__ import annotations

import os
import sys
import traceback
import uuid

# Make the project root importable when launched as app/streamlit_app.py.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
from langgraph.types import Command

from graph.build import build_graph
from llm import llm_mode
from tools.contract_parser import read_contract_file


def _make_state(text: str, name: str, reviewer: str, sender_email: str) -> dict:
    """Build the initial graph state. Defined here (in the always-reloaded app
    file) rather than imported, so the app never depends on a stale helper
    module on the host."""
    return {
        "contract_text": text,
        "contract_name": name,
        "reviewer": reviewer or "reviewer",
        "sender_email": sender_email or "sender@counterparty.example.com",
        "audit_log": [],
        "errors": [],
        "compliance": [],
        "approvals": [],
    }

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONTRACTS_DIR = os.path.join(ROOT, "data", "contracts")

RISK_COLOR = {"low": "🟢", "medium": "🟡", "high": "🟠", "critical": "🔴"}

# Pipeline stepper: label -> the audit-log tag that marks it complete.
STEP_TAGS = [
    ("Session", "[session]"),
    ("Intake", "[intake]"),
    ("Retrieval", "[retrieval]"),
    ("Analysis", "[analysis]"),
    ("Guardrail", "[guardrail]"),
    ("Redline", "[redline]"),
    ("Approval", "[hitl]"),
    ("Notify", "[notify]"),
    ("Record", "[record]"),
]

st.set_page_config(page_title="ContractGuard", page_icon="📝", layout="wide")


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _reset_run():
    for k in ("stage", "graph", "config", "state", "interrupted"):
        st.session_state.pop(k, None)


def _run_until_gate(text: str, name: str, sender_email: str):
    try:
        reviewer = st.session_state.get("reviewer", "reviewer")
        graph = build_graph()
        config = {"configurable": {"thread_id": f"{name}-{uuid.uuid4().hex[:8]}"}}
        graph.invoke(_make_state(text, name, reviewer, sender_email), config)
        snap = graph.get_state(config)
        st.session_state.graph = graph
        st.session_state.config = config
        st.session_state.state = snap.values
        st.session_state.interrupted = bool(snap.next)
        st.session_state.stage = "review" if snap.next else "blocked"
    except Exception:
        st.session_state.error_tb = traceback.format_exc()
        st.session_state.stage = "error"


def _resume(decision: dict):
    try:
        graph = st.session_state.graph
        config = st.session_state.config
        graph.invoke(Command(resume=decision), config)
        st.session_state.state = graph.get_state(config).values
        st.session_state.stage = "done"
    except Exception:
        st.session_state.error_tb = traceback.format_exc()
        st.session_state.stage = "error"


def render_stepper(state: dict, active: str | None = None):
    log = " ".join(state.get("audit_log", []))
    chips = []
    for label, tag in STEP_TAGS:
        if label == active:
            chips.append(f"🔵 **{label}**")
        elif tag in log:
            chips.append(f"✅ {label}")
        else:
            chips.append(f"⚪ {label}")
    st.markdown(" &nbsp;→&nbsp; ".join(chips))
    st.divider()


def report_tabs(state: dict, editable: bool = False):
    """Render the report in tabs. Returns the (possibly edited) email body."""
    report = state.get("risk_report")
    edited_body = None
    t_risk, t_comp, t_red, t_email = st.tabs(
        ["📊 Risk analysis", "🛡️ Compliance", "✏️ Redlines", "✉️ Email"]
    )

    with t_risk:
        if report:
            c1, c2, c3 = st.columns(3)
            c1.metric("Overall risk", f"{RISK_COLOR.get(report.overall_risk,'')} {report.overall_risk.upper()}")
            c2.metric("Risk score", f"{report.risk_score}/100")
            c3.metric("Route", state.get("route", "—"))
            st.caption(report.summary)
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
                st.warning(
                    "Missing critical clauses: "
                    + ", ".join(c.replace("_", " ") for c in report.missing_clauses)
                )
            with st.expander("🔎 RAG grounding (playbook evidence per clause)"):
                for m in state.get("matches", []):
                    if m.evidence:
                        st.markdown(f"**clause {m.clause_id}** ({m.clause_type.replace('_',' ')})")
                        for e in m.evidence:
                            st.caption(f"`{e.source}` (score {e.score}) — {e.snippet[:160]}…")
        else:
            st.info("No risk report (pipeline did not reach analysis).")

    with t_comp:
        flags = state.get("compliance", [])
        if flags:
            for f in flags:
                badge = "🚫 BLOCKING" if f.blocking else "⚠️"
                st.markdown(
                    f"{badge} **{f.kind}** — {f.message}  \n<small>policy: `{f.policy_ref}`</small>",
                    unsafe_allow_html=True,
                )
        else:
            st.success("No compliance flags raised.")

    with t_red:
        redlines = state.get("redlines", [])
        if redlines:
            st.caption(f"{len(redlines)} proposed redline(s)")
            for r in redlines:
                with st.expander(f"{r.clause_type.replace('_',' ')} — {r.reason}"):
                    st.markdown("**Current:**")
                    st.code(r.original, language=None)
                    st.markdown("**Proposed:**")
                    st.code(r.proposed, language=None)
        else:
            st.info("No redlines proposed.")

    with t_email:
        outreach = state.get("outreach")
        if outreach:
            st.text(f"To: {outreach.to}\nSubject: {outreach.subject}")
            if editable:
                edited_body = st.text_area("Email body (editable)", value=outreach.body, height=240)
            else:
                st.code(outreach.body, language=None)
            with st.expander("Internal summary memo"):
                st.text(outreach.summary_memo)
        else:
            st.info("No outreach drafted.")
    return edited_body


# --------------------------------------------------------------------------- #
# Stage 0 — login
# --------------------------------------------------------------------------- #
if "reviewer" not in st.session_state:
    st.title("📝 ContractGuard")
    st.caption("Multi-agent contract-review copilot · LangGraph")
    st.subheader("Reviewer sign-in")
    with st.form("login"):
        name = st.text_input("Your name")
        role = st.selectbox("Role", ["Reviewer", "Senior Counsel", "Compliance Officer"])
        st.text_input("Password", type="password", help="Demo only — any value works")
        submitted = st.form_submit_button("Sign in", type="primary")
    if submitted and name.strip():
        st.session_state.reviewer = f"{name.strip()} ({role})"
        st.session_state.stage = "input"
        st.rerun()
    elif submitted:
        st.warning("Enter your name to sign in.")
    st.stop()


# --------------------------------------------------------------------------- #
# Sidebar
# --------------------------------------------------------------------------- #
with st.sidebar:
    st.title("📝 ContractGuard")
    st.caption("Multi-agent contract-review copilot · LangGraph")
    st.success(f"👤 {st.session_state.reviewer}")
    mode = llm_mode()
    st.info(f"LLM mode: **{mode}**" + ("  _(deterministic)_" if mode == "mock" else ""))
    st.markdown(
        "**5 agents**\n\n"
        "1. Intake / Parse\n"
        "2. Retrieval (RAG)\n"
        "3. Risk Analysis\n"
        "4. Compliance / Guardrail\n"
        "5. Redline / Outreach\n\n"
        "**+ Supervisor steps:** session · routing · HITL · notify · record"
    )
    if st.button("↺ New review", use_container_width=True):
        _reset_run()
        st.session_state.stage = "input"
        st.rerun()
    if st.button("⎋ Sign out", use_container_width=True):
        _reset_run()
        st.session_state.pop("reviewer", None)
        st.rerun()


stage = st.session_state.get("stage", "input")

# --------------------------------------------------------------------------- #
# Stage: input
# --------------------------------------------------------------------------- #
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
    sender_email = st.text_input(
        "📧 Sender's email",
        value="sender@counterparty.example.com",
        help="The status notification (approved / rejected / flagged) is emailed here.",
    )
    if st.button("▶ Run review", type="primary"):
        if not text.strip():
            st.warning("Paste or load a contract first.")
        elif "@" not in (sender_email or ""):
            st.warning("Enter a valid sender email for the status notification.")
        else:
            with st.spinner("Running 5 agents…"):
                _run_until_gate(text, name, sender_email.strip())
            st.rerun()


# --------------------------------------------------------------------------- #
# Stage: review (human approval gate)
# --------------------------------------------------------------------------- #
if stage == "review":
    state = st.session_state.state
    st.header(f"Review package — {state.get('contract_name')}")
    render_stepper(state, active="Approval")
    if state.get("needs_senior_review"):
        st.error("⚖️ Senior-counsel review required (high/critical risk).")

    edited_body = report_tabs(state, editable=True)
    outreach = state.get("outreach")

    st.divider()
    st.markdown("### 🔐 Human approval gate")
    st.caption("Nothing is sent until you approve. This is the mandatory HITL checkpoint.")
    a, b, c = st.columns(3)
    if a.button("✅ Approve & send", type="primary", use_container_width=True):
        dec = {"decision": "approved", "notes": f"approved by {st.session_state.reviewer}"}
        if outreach and edited_body and edited_body != outreach.body:
            dec = {"decision": "edited", "notes": "edited via UI", "edited_outreach": edited_body}
        _resume(dec)
        st.rerun()
    if b.button("✏️ Approve edits & send", use_container_width=True):
        _resume(
            {
                "decision": "edited",
                "notes": "edited via UI",
                "edited_outreach": edited_body or (outreach.body if outreach else ""),
            }
        )
        st.rerun()
    if c.button("❌ Reject", use_container_width=True):
        _resume({"decision": "rejected", "notes": f"rejected by {st.session_state.reviewer}"})
        st.rerun()


# --------------------------------------------------------------------------- #
# Stage: blocked (refusal — no human gate reached)
# --------------------------------------------------------------------------- #
if stage == "blocked":
    state = st.session_state.state
    st.header(f"Blocked — {state.get('contract_name')}")
    render_stepper(state)
    st.error(f"🚫 Pipeline refused to proceed · route = **{state.get('route')}**. No external action taken.")
    st.info(
        f"📨 Sender notified at **{state.get('sender_email', 'sender@counterparty.example.com')}** "
        "— status: flagged / on hold for manual review."
    )
    if state.get("errors"):
        for e in state["errors"]:
            st.code(e)
    report_tabs(state, editable=False)
    if state.get("record_path"):
        st.caption(f"🗄️ Audit record archived: `{state['record_path']}`")
    with st.expander("📜 Audit log", expanded=True):
        for entry in state.get("audit_log", []):
            st.text(entry)


# --------------------------------------------------------------------------- #
# Stage: done (decision + notification)
# --------------------------------------------------------------------------- #
if stage == "done":
    state = st.session_state.state
    approvals = state.get("approvals", [])
    verdict = approvals[-1].decision if approvals else "unknown"
    name = state.get("contract_name")
    st.header(f"Decision recorded — {name}")
    render_stepper(state)

    if verdict in ("approved", "edited"):
        st.success(f"✅ **{verdict.upper()}** by {st.session_state.reviewer} — redlines + outreach recorded to `outbox/`.")
        subject = "Contract review complete — APPROVED with changes"
        body = (
            f"Your contract '{name}' has been reviewed and approved to proceed with "
            f"{len(state.get('redlines', []))} proposed redline(s), attached for acceptance."
        )
    else:
        st.warning(f"❌ **{verdict.upper()}** by {st.session_state.reviewer} — no external action was taken.")
        subject = "Contract review complete — NOT APPROVED"
        body = f"Your contract '{name}' was reviewed and we are unable to proceed as currently drafted."

    st.subheader("📨 Decision notification sent to the sender")
    to_addr = state.get("sender_email", "sender@counterparty.example.com")
    st.text(f"To: {to_addr}\nSubject: {subject}\n\n{body}")

    if state.get("record_path"):
        st.subheader("🗄️ Compliance audit record")
        st.caption(f"Archived to `{state['record_path']}`")

    with st.expander("📋 Full report"):
        report_tabs(state, editable=False)
    with st.expander("📜 Full audit log", expanded=True):
        for entry in state.get("audit_log", []):
            st.text(entry)


# --------------------------------------------------------------------------- #
# Stage: error (surface the real, non-redacted error for debugging)
# --------------------------------------------------------------------------- #
if stage == "error":
    st.header("⚠️ Pipeline error")
    try:
        from importlib.metadata import version
        st.caption(
            f"langgraph={version('langgraph')} · "
            f"langgraph-checkpoint={version('langgraph-checkpoint')} · "
            f"langchain-core={version('langchain-core')} · "
            f"pydantic={version('pydantic')} · python={sys.version.split()[0]}"
        )
    except Exception:
        pass
    st.error("The run failed. Full traceback (please screenshot this):")
    st.code(st.session_state.get("error_tb", "(no traceback captured)"))
    if st.button("← Back", type="primary"):
        st.session_state.stage = "input"
        st.rerun()
