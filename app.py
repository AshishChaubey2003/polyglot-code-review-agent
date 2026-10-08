"""
Polyglot AI Code Review & Repair Agent -- Streamlit UI.

Review mode: analyze -> report. Never modifies code.
Repair mode: analyze -> propose a fix -> guard -> verify -> show diff +
verification -> human Approve/Reject -> apply. Nothing is ever written
or returned as "fixed" without an explicit Approve click.

This UI contains NO orchestration logic of its own -- every button
calls into services/review_service.py, the exact same functions
api/main.py calls, so the two frontends can never behave differently.
"""

from __future__ import annotations

import streamlit as st

from config import is_configured
from human_loop.approval import ApprovalError, get_approval_store
from human_loop.decisions import ApplyFixError, apply_fix
from services.review_service import run_repair, run_review

SUPPORTED_LANGUAGES = ["python", "javascript", "typescript", "java", "go"]
STATIC_ANALYSIS_LANGUAGES = {"python"}

st.set_page_config(page_title="Polyglot AI Code Review & Repair Agent", layout="wide")


def _severity_badge(severity: str) -> str:
    colors = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}
    return f"{colors.get(severity, '⚪')} {severity.upper()}"


def _render_findings(findings) -> None:
    if not findings:
        st.success("No findings.")
        return

    for f in findings:
        with st.expander(f"{_severity_badge(f.severity)} · [{f.category}] {f.title}  (source: {f.source})"):
            st.write(f.description)
            if f.line is not None:
                st.caption(f"Line {f.line}")
            st.markdown(f"**Evidence**\n```\n{f.evidence}\n```")
            st.markdown(f"**Recommendation**\n\n{f.recommendation}")


def _render_verification(verification) -> None:
    for step in verification.steps:
        icon = "✅" if step.passed else "❌"
        st.write(f"{icon} **{step.name}** — {step.detail}")
    overall = "✅ All checks passed" if verification.all_passed else "⚠️ Some checks did not pass"
    st.markdown(f"**{overall}**")


with st.sidebar:
    st.title("⚙️ Settings")
    st.caption("Polyglot AI Code Review & Repair Agent")

    if is_configured():
        st.success("LLM provider configured.")
    else:
        st.error("GROQ_API_KEY is not set — see .env.example.")

    language = st.selectbox("Language", SUPPORTED_LANGUAGES, index=0)
    if language not in STATIC_ANALYSIS_LANGUAGES:
        st.info(
            f"Static analysis (AST/Ruff/Bandit) only supports Python today. "
            f"'{language}' will be reviewed by the LLM agents alone."
        )

    mode = st.radio("Mode", ["Review", "Repair"], help=(
        "Review: analyze and report, never modifies code.\n\n"
        "Repair: additionally proposes a fix. The fix is guarded and "
        "verified but never applied until you explicitly approve it."
    ))

st.title("🔎 Polyglot AI Code Review & Repair Agent")

code = st.text_area("Paste code to review", height=300, placeholder="def example():\n    ...")

run_clicked = st.button("Run Review" if mode == "Review" else "Run Review & Propose Fix", type="primary")

if run_clicked:
    if not code.strip():
        st.warning("Paste some code first.")
    elif mode == "Review":
        with st.spinner("Running static analysis, retrieval, and LLM review agents..."):
            result = run_review(code, language)
        st.session_state["last_review"] = result
        st.session_state.pop("last_approval_id", None)
        st.session_state.pop("last_halt_reason", None)
    else:
        with st.spinner("Reviewing, proposing a fix, and running independent verification..."):
            review_result, approval_record, halted_reason = run_repair(code, language)
        st.session_state["last_review"] = review_result
        if approval_record is not None:
            st.session_state["last_approval_id"] = approval_record.approval_id
            st.session_state.pop("last_halt_reason", None)
        else:
            st.session_state.pop("last_approval_id", None)
            st.session_state["last_halt_reason"] = halted_reason

if "last_review" in st.session_state:
    review = st.session_state["last_review"]
    st.subheader("Summary")
    counts = review.counts_by_severity
    cols = st.columns(4)
    for col, sev in zip(cols, ["critical", "high", "medium", "low"]):
        col.metric(sev.capitalize(), counts[sev])
    st.write(review.summary)

    st.subheader("Findings")
    _render_findings(review.findings)

    if st.session_state.get("last_halt_reason"):
        st.warning(f"No fix could be proposed: {st.session_state['last_halt_reason']}")

    approval_id = st.session_state.get("last_approval_id")
    if approval_id:
        store = get_approval_store()
        record = store.get(approval_id)
        fix = record.proposed_fix

        st.subheader("Proposed Fix")
        st.markdown(f"**Status:** `{fix.approval_status}`")
        st.markdown(f"**Explanation:** {fix.fix.explanation}")

        st.markdown("**Diff**")
        st.code(fix.diff, language="diff")

        st.markdown("**Independent Verification**")
        _render_verification(fix.verification)

        if fix.approval_status == "pending":
            col_approve, col_reject = st.columns(2)
            if col_approve.button("✅ Approve", key=f"approve_{approval_id}"):
                try:
                    store.approve(approval_id)
                    st.rerun()
                except ApprovalError as exc:
                    st.error(str(exc))
            if col_reject.button("❌ Reject", key=f"reject_{approval_id}"):
                try:
                    store.reject(approval_id)
                    st.rerun()
                except ApprovalError as exc:
                    st.error(str(exc))
        elif fix.approval_status == "approved":
            st.success("Fix approved.")
            try:
                applied = apply_fix(store, approval_id)
                st.markdown("**Fixed code**")
                st.code(applied.fixed_code, language=language)
            except ApplyFixError as exc:
                st.error(str(exc))
        elif fix.approval_status == "rejected":
            st.info("Fix rejected — nothing was applied.")
