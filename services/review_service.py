"""
Shared orchestration layer. Both app.py (Streamlit) and api/main.py
(FastAPI) call these two functions instead of touching agents.graph
directly -- one place owns "how a review/repair request actually
runs," so the two frontends can never drift out of sync with each
other's behavior.
"""

from __future__ import annotations

from agents.graph import get_graph
from agents.nodes.report_node import to_review_result
from human_loop.approval import ApprovalRecord, get_approval_store
from models.review import ReviewResult


def run_review(code: str, language: str = "python") -> ReviewResult:
    """Review mode: analyze, never modify."""
    graph = get_graph()
    final_state = graph.invoke({"code": code, "language": language, "mode": "review"})
    return to_review_result(final_state)


def run_repair(code: str, language: str = "python") -> tuple[ReviewResult, ApprovalRecord | None, str | None]:
    """Repair mode: runs the same review pipeline, then proposes a fix
    and submits it for human approval. Returns (review_result,
    approval_record_or_None, halted_reason_or_None) -- exactly one of
    the last two is set: a halted_reason means no fix could be safely
    proposed (a guard rejected it, or generation failed), in which case
    there is nothing to approve."""
    graph = get_graph()
    final_state = graph.invoke({"code": code, "language": language, "mode": "repair"})
    review_result = to_review_result(final_state)

    proposed_fix = final_state.get("proposed_fix")
    halted_reason = final_state.get("halted_reason")

    if proposed_fix is None:
        return review_result, None, halted_reason or "No fix could be proposed."

    record = get_approval_store().submit(proposed_fix)
    return review_result, record, None
