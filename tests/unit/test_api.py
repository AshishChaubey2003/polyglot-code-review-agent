from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.main import app
from models.finding import FindingList
from models.fix import CodeFix
from models.retrieval import QueryPlan
from services.llm_service import LLMService


@pytest.fixture(autouse=True)
def _no_real_llm_or_retrieval(monkeypatch):
    def fake_structured_generate(self, prompt, schema):
        if schema is QueryPlan:
            return QueryPlan(queries=["q"], filters={})
        if schema is FindingList:
            return FindingList(findings=[])
        if schema is CodeFix:
            return CodeFix(fixed_code="print('fixed')\n", explanation="fixed", changed_lines=[1])
        raise AssertionError(schema)

    monkeypatch.setattr(LLMService, "structured_generate", fake_structured_generate)
    monkeypatch.setattr(LLMService, "generate", lambda self, prompt: "passage")

    import agents.graph as graph_module
    monkeypatch.setattr(graph_module, "run_retrieval", lambda state: {"retrieved_context": []})

    # agents.graph caches a compiled graph module-globally; clear it so
    # each test rebuilds against this test's monkeypatched run_retrieval.
    graph_module._COMPILED = None


client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert "llm_configured" in response.json()


def test_review_endpoint_returns_findings_shape():
    response = client.post("/review", json={"code": "x = 1\n", "language": "python"})
    assert response.status_code == 200
    body = response.json()
    assert "findings" in body
    assert "summary" in body


def test_repair_endpoint_returns_an_approval_id():
    response = client.post("/repair", json={"code": "eval(input())\n", "language": "python"})
    assert response.status_code == 200
    body = response.json()
    assert body["proposed_fix"] is not None
    assert "approval_id" in body


def test_full_repair_approve_apply_flow():
    repair_response = client.post("/repair", json={"code": "x = 1\n", "language": "python"})
    approval_id = repair_response.json()["approval_id"]

    verify_response = client.post("/verify", params={"approval_id": approval_id})
    assert verify_response.status_code == 200

    approve_response = client.post("/approve", json={"approval_id": approval_id})
    assert approve_response.status_code == 200
    assert approve_response.json()["status"] == "approved"

    apply_response = client.post("/apply", json={"approval_id": approval_id})
    assert apply_response.status_code == 200
    assert apply_response.json()["fixed_code"] == "print('fixed')\n"


def test_apply_before_approve_fails():
    repair_response = client.post("/repair", json={"code": "y = 2\n", "language": "python"})
    approval_id = repair_response.json()["approval_id"]

    apply_response = client.post("/apply", json={"approval_id": approval_id})
    assert apply_response.status_code == 400


def test_approve_unknown_id_returns_400():
    response = client.post("/approve", json={"approval_id": "not-real"})
    assert response.status_code == 400
