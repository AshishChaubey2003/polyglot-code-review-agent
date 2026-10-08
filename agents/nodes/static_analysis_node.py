"""Deterministic static analysis -- the "ground truth" layer under the
LLM's reasoning. Python-only for now (analyzers/python_analyzer.py);
other languages get an empty list here and rely on the LLM review
agents alone, which the report node makes explicit rather than silent."""

from __future__ import annotations

from agents.nodes.language_node import SUPPORTED_STATIC_ANALYSIS_LANGUAGES
from agents.state import ReviewState
from analyzers.python_analyzer import PythonAnalyzer

_ANALYZERS = {"python": PythonAnalyzer()}


def run_static_analysis(state: ReviewState) -> dict:
    language = state["language"]
    if language not in SUPPORTED_STATIC_ANALYSIS_LANGUAGES:
        return {"static_findings": []}

    analyzer = _ANALYZERS[language]
    return {"static_findings": analyzer.analyze(state["code"])}
