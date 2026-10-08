"""Terminal node for review mode: builds the ReviewResult the UI/API
return. If the input guard blocked the request, this short-circuits to
a report that carries zero findings and the block reason, rather than
pretending a review happened."""

from __future__ import annotations

from agents.state import ReviewState
from models.review import ReviewResult


def build_report(state: ReviewState) -> dict:
    if not state.get("input_allowed", True):
        reasons = "; ".join(state.get("input_block_reasons", []))
        return {
            "summary": f"Review blocked by input guard: {reasons}",
            "all_findings": [],
        }
    return {}


def to_review_result(state: ReviewState) -> ReviewResult:
    """Not a graph node -- a convenience the app/API layer calls after
    the graph finishes, to get the typed result object."""
    return ReviewResult(
        findings=state.get("all_findings", []),
        summary=state.get("summary", ""),
        language=state.get("language", "python"),
        mode=state.get("mode", "review"),
    )
