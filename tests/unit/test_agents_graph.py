"""
End-to-end graph tests. No real LLM calls: `LLMService.structured_generate`
and `.generate` are monkeypatched at the class level (every node builds
its own LLMService() instance internally, so patching the class is what
makes every node's calls deterministic without a GROQ_API_KEY).
"""

from __future__ import annotations

import pytest

from agents.graph import build_graph
from models.finding import Finding, FindingList
from models.fix import CodeFix
from models.retrieval import QueryPlan
from services.llm_service import LLMService


@pytest.fixture(autouse=True)
def _no_real_llm_or_retrieval(monkeypatch):
    """Every test in this file runs with the LLM faked out and
    retrieval short-circuited to an empty list -- these tests exercise
    the GRAPH'S WIRING (routing, fan-out/fan-in, state merging), not
    the RAG pipeline or a real model, which are already covered by
    their own test files."""

    def fake_structured_generate(self, prompt, schema):
        if schema is QueryPlan:
            return QueryPlan(queries=["irrelevant query"], filters={})
        if schema is FindingList:
            return FindingList(findings=[])
        if schema is CodeFix:
            return CodeFix(fixed_code="print('fixed')\n", explanation="fixed it", changed_lines=[1])
        raise AssertionError(f"Unexpected schema requested: {schema}")

    monkeypatch.setattr(LLMService, "structured_generate", fake_structured_generate)
    monkeypatch.setattr(LLMService, "generate", lambda self, prompt: "a hypothetical passage")

    # agents.graph imports run_retrieval by name (`from ... import
    # run_retrieval`) and looks it up in its own module globals each
    # time build_graph() runs, so patching the name there -- not on
    # retrieve_node itself -- is what actually intercepts it.
    import agents.graph as graph_module
    monkeypatch.setattr(graph_module, "run_retrieval", lambda state: {"retrieved_context": []})


def test_review_mode_clean_code_produces_a_report():
    graph = build_graph()
    result = graph.invoke({"code": "x = 1\n", "language": "python", "mode": "review"})

    assert result["input_allowed"] is True
    assert "all_findings" in result
    assert "summary" in result
    assert result["summary"]


def test_review_mode_blocked_input_short_circuits_to_report():
    graph = build_graph()
    result = graph.invoke({"code": "", "language": "python", "mode": "review"})

    assert result["input_allowed"] is False
    assert "blocked" in result["summary"].lower()
    assert result.get("all_findings", []) == []


def test_review_mode_surfaces_static_findings():
    graph = build_graph()
    vulnerable_code = "import os\npassword = 'hardcoded12345'\n"
    result = graph.invoke({"code": vulnerable_code, "language": "python", "mode": "review"})

    titles = [f.title for f in result["all_findings"]]
    assert any("password" in t.lower() or "secret" in t.lower() or "hardcod" in t.lower() for t in titles) or result["all_findings"]


def test_repair_mode_produces_a_proposed_fix_with_verification():
    graph = build_graph()
    result = graph.invoke({"code": "eval(input())\n", "language": "python", "mode": "repair"})

    proposed = result.get("proposed_fix")
    assert proposed is not None
    assert proposed.approval_status == "pending"
    assert proposed.fix.fixed_code == "print('fixed')\n"
    assert len(proposed.verification.steps) == 4


def test_repair_mode_halts_when_fix_fails_a_guard(monkeypatch):
    def empty_fix_generate(self, prompt, schema):
        if schema is QueryPlan:
            return QueryPlan(queries=["q"], filters={})
        if schema is FindingList:
            return FindingList(findings=[])
        if schema is CodeFix:
            return CodeFix(fixed_code="", explanation="oops", changed_lines=[1])
        raise AssertionError

    monkeypatch.setattr(LLMService, "structured_generate", empty_fix_generate)

    graph = build_graph()
    result = graph.invoke({"code": "x = 1\n", "language": "python", "mode": "repair"})

    assert result.get("proposed_fix") is None
    assert "halted_reason" in result
    assert "output guard" in result["halted_reason"].lower()


def test_parallel_review_findings_from_all_three_agents_are_merged(monkeypatch):
    def three_agent_generate(self, prompt, schema):
        if schema is QueryPlan:
            return QueryPlan(queries=["q"], filters={})
        if schema is FindingList:
            if "bug" in prompt:
                category = "bug"
            elif "security" in prompt:
                category = "security"
            else:
                category = "quality"
            return FindingList(findings=[
                Finding(category=category, severity="low", title=f"{category} issue",
                        description="d", evidence="e", recommendation="r", source="llm")
            ])
        raise AssertionError

    monkeypatch.setattr(LLMService, "structured_generate", three_agent_generate)

    graph = build_graph()
    result = graph.invoke({"code": "x = 1\n", "language": "python", "mode": "review"})

    categories = {f.category for f in result["all_findings"] if f.source == "llm"}
    assert categories == {"bug", "security", "quality"}
