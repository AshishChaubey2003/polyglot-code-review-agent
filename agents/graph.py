"""
The review/repair LangGraph.

Review mode:
    input_guard -> [blocked? -> report] -> language -> static_analysis
    -> retrieve -> {bug, security, quality} (parallel) -> aggregate -> report -> END

Repair mode runs the same review pipeline first (a fix needs to know
what to fix), then extends it:
    ... -> aggregate -> generate_fix -> verify_fix -> END

Human approval and applying the fix happen OUTSIDE this graph, in
human_loop/approval.py and the app/API layer -- the graph only ever
produces a ProposedFix with its verification evidence attached, it
never auto-applies anything.
"""

from __future__ import annotations

from langgraph.graph import END, StateGraph

from agents.nodes.aggregate_node import run_aggregate
from agents.nodes.bug_node import run_bug_review
from agents.nodes.fix_node import run_generate_fix
from agents.nodes.input_node import run_input_guard
from agents.nodes.language_node import detect_language
from agents.nodes.quality_node import run_quality_review
from agents.nodes.report_node import build_report
from agents.nodes.retrieve_node import run_retrieval
from agents.nodes.security_node import run_security_review
from agents.nodes.static_analysis_node import run_static_analysis
from agents.nodes.verify_node import run_verify_fix
from agents.state import ReviewState


def _input_was_blocked(state: ReviewState) -> str:
    return "blocked" if not state.get("input_allowed", True) else "allowed"


def _review_or_repair(state: ReviewState) -> str:
    return "repair" if state.get("mode") == "repair" else "review"


def build_graph(compile_graph: bool = True):
    graph = StateGraph(ReviewState)

    graph.add_node("input_guard", run_input_guard)
    graph.add_node("language", detect_language)
    graph.add_node("static_analysis", run_static_analysis)
    graph.add_node("retrieve", run_retrieval)
    graph.add_node("bug_review", run_bug_review)
    graph.add_node("security_review", run_security_review)
    graph.add_node("quality_review", run_quality_review)
    graph.add_node("aggregate", run_aggregate)
    graph.add_node("report", build_report)
    graph.add_node("generate_fix", run_generate_fix)
    graph.add_node("verify_fix", run_verify_fix)

    graph.set_entry_point("input_guard")

    graph.add_conditional_edges(
        "input_guard", _input_was_blocked, {"blocked": "report", "allowed": "language"},
    )
    graph.add_edge("language", "static_analysis")
    graph.add_edge("static_analysis", "retrieve")

    # fan-out
    graph.add_edge("retrieve", "bug_review")
    graph.add_edge("retrieve", "security_review")
    graph.add_edge("retrieve", "quality_review")

    # fan-in
    graph.add_edge("bug_review", "aggregate")
    graph.add_edge("security_review", "aggregate")
    graph.add_edge("quality_review", "aggregate")

    graph.add_conditional_edges(
        "aggregate", _review_or_repair, {"review": "report", "repair": "generate_fix"},
    )
    graph.add_edge("generate_fix", "verify_fix")
    graph.add_edge("verify_fix", "report")
    graph.add_edge("report", END)

    return graph.compile() if compile_graph else graph


_COMPILED = None


def get_graph():
    global _COMPILED
    if _COMPILED is None:
        _COMPILED = build_graph()
    return _COMPILED
