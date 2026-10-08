"""Entry node: runs the input guard. Blocking issues halt the graph
immediately (handled by graph.py's conditional edge); flagged-but-not-
blocking issues (an injection phrase, a detected secret) are recorded
and surfaced in the final report but do not stop the review."""

from __future__ import annotations

from agents.state import ReviewState
from guardrails.input_guard import check_input


def run_input_guard(state: ReviewState) -> dict:
    result = check_input(state["code"])
    return {
        "input_allowed": result.allowed,
        "input_block_reasons": list(result.reasons),
    }
