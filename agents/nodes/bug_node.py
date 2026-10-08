"""LLM bug-review agent -- one of three parallel branches fanning out
from static analysis, fanning back in at the aggregate node."""

from __future__ import annotations

from agents.nodes._llm_review import run_llm_review
from agents.state import ReviewState


def run_bug_review(state: ReviewState) -> dict:
    findings = run_llm_review(
        code=state["code"],
        language=state["language"],
        category="bug",
        focus="logic and correctness",
        existing_findings=state.get("static_findings", []),
        retrieved_context=state.get("retrieved_context", []),
    )
    return {"findings": findings}
