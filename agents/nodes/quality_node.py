"""LLM quality-review agent -- parallel branch alongside bug/security."""

from __future__ import annotations

from agents.nodes._llm_review import run_llm_review
from agents.state import ReviewState


def run_quality_review(state: ReviewState) -> dict:
    findings = run_llm_review(
        code=state["code"],
        language=state["language"],
        category="quality",
        focus="code quality and maintainability",
        existing_findings=state.get("static_findings", []),
        retrieved_context=state.get("retrieved_context", []),
    )
    return {"findings": findings}
