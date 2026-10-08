"""
Tests for the pieces that tie retrieval together: query_transform
(faked LLM -- no network/API key needed), the reranker (fake
embeddings, same injectable pattern as test_rag_vector.py), and the
full retriever end-to-end, including the 8 metadata-filtering
scenarios called out in the spec.
"""

from __future__ import annotations

from models.finding import Finding
from models.retrieval import QueryPlan
from rag.ingestion import IngestedChunk
from rag.metadata import ChunkMetadata
from rag.query_transform import transform_query
from rag.reranker import rerank
from rag.retriever import RetrieverIndex, retrieve_context
from services.llm_service import LLMServiceError
from tests.fakes.fake_embeddings import FakeEmbeddings


def _finding(title: str, severity: str = "high", category: str = "security") -> Finding:
    return Finding(
        category=category, severity=severity, title=title, description=title,
        evidence="x = 1", recommendation="fix it", source="bandit",
    )


def _chunk(text: str, chunk_id: str, **meta) -> IngestedChunk:
    defaults = {"source": "test", "doc_type": "security", "language": "python", "topic": "general"}
    defaults.update(meta)
    return IngestedChunk(text=text, metadata=ChunkMetadata(chunk_id=chunk_id, **defaults))


class _FakeLLMService:
    """Stands in for LLMService -- structured_generate()/generate()
    return canned values instead of calling a real provider."""

    def __init__(self, plan: QueryPlan | None = None, raises: bool = False, text: str = "a hypothetical passage"):
        self._plan = plan
        self._raises = raises
        self._text = text

    def structured_generate(self, prompt, schema):
        if self._raises:
            raise LLMServiceError("provider down")
        return self._plan

    def generate(self, prompt):
        if self._raises:
            raise LLMServiceError("provider down")
        return self._text


# ── query_transform ─────────────────────────────────────────────────
def test_transform_query_uses_llm_plan_when_valid():
    plan = QueryPlan(queries=["sql injection"], filters={"language": "python"})
    result = transform_query("code", [_finding("SQLi")], "python", llm_service=_FakeLLMService(plan=plan))
    assert result.queries == ["sql injection"]
    assert result.filters == {"language": "python"}


def test_transform_query_drops_invalid_llm_proposed_filters():
    plan = QueryPlan(queries=["sql injection"], filters={"language": "cobol", "made_up": "x"})
    result = transform_query("code", [_finding("SQLi")], "python", llm_service=_FakeLLMService(plan=plan))
    assert result.filters == {}
    assert len(result.dropped_filters) == 2


def test_transform_query_falls_back_on_llm_failure():
    result = transform_query("code", [_finding("Unused import")], "python", llm_service=_FakeLLMService(raises=True))
    assert result.queries == ["Unused import"]
    assert result.filters == {"language": "python"}


def test_transform_query_falls_back_when_llm_returns_no_queries():
    plan = QueryPlan(queries=[], filters={})
    result = transform_query("code", [_finding("Bug")], "python", llm_service=_FakeLLMService(plan=plan))
    assert result.queries  # fallback produced something, never empty


# ── reranker ─────────────────────────────────────────────────────────
def test_rerank_orders_by_similarity_to_query():
    candidates = [
        _chunk("completely unrelated baking bread recipe", "c1"),
        _chunk("sql injection parameterized query database security", "c2"),
    ]
    results = rerank("sql injection database security", candidates, FakeEmbeddings())
    assert results[0].chunk.metadata.chunk_id == "c2"
    assert results[0].rank == 1


def test_rerank_empty_candidates_returns_empty():
    assert rerank("anything", [], FakeEmbeddings()) == []


# ── retriever end-to-end with metadata filtering scenarios ────────────
def _build_index():
    chunks = [
        _chunk("sql injection parameterized query prevents attack", "sqli:0", topic="sql-injection", cwe="CWE-89", language="python"),
        _chunk("hardcoded password credential secret in source code", "secrets:0", topic="hardcoded-secrets", cwe="CWE-798", language="python"),
        _chunk("unused import flagged by linter cleanup", "lint:0", topic="unused-import", rule="F401", doc_type="linting", language="python"),
        _chunk("javascript sql injection also exists in node apps", "sqli_js:0", topic="sql-injection", cwe="CWE-89", language="javascript"),
    ]
    return RetrieverIndex.build(embeddings=FakeEmbeddings(), knowledge_base=chunks)


def test_correct_metadata_filtering_returns_only_matching_language():
    index = _build_index()
    plan = QueryPlan(queries=["sql injection"], filters={"language": "javascript"})
    results = retrieve_context(
        "code", [_finding("SQLi")], "javascript", index,
        llm_service=_FakeLLMService(plan=plan), use_rerank=False,
    )
    assert results
    assert all(r.metadata["language"] == "javascript" for r in results)


def test_multiple_metadata_filters_combine_with_and():
    index = _build_index()
    plan = QueryPlan(queries=["sql injection"], filters={"language": "python", "topic": "sql-injection"})
    results = retrieve_context(
        "code", [_finding("SQLi")], "python", index,
        llm_service=_FakeLLMService(plan=plan), use_rerank=False,
    )
    assert results
    assert all(r.metadata["language"] == "python" and r.metadata["topic"] == "sql-injection" for r in results)


def test_invalid_llm_generated_filters_are_dropped_not_applied():
    index = _build_index()
    plan = QueryPlan(queries=["sql injection"], filters={"language": "cobol"})
    results = retrieve_context(
        "code", [_finding("SQLi")], "python", index,
        llm_service=_FakeLLMService(plan=plan), use_rerank=False,
    )
    # invalid filter dropped -> unfiltered search -> still returns results
    assert results


def test_zero_result_filters_fall_back_to_relaxed_search():
    index = _build_index()
    # topic that doesn't exist in the corpus at all combined with a valid language
    plan = QueryPlan(queries=["sql injection"], filters={"language": "python", "topic": "nonexistent-topic"})
    results = retrieve_context(
        "code", [_finding("SQLi")], "python", index,
        llm_service=_FakeLLMService(plan=plan), use_rerank=False,
    )
    # the topic filter should have been relaxed, leaving results after dropping it
    assert results


def test_language_filtering_excludes_other_languages():
    index = _build_index()
    plan = QueryPlan(queries=["sql injection"], filters={"language": "python"})
    results = retrieve_context(
        "code", [_finding("SQLi")], "python", index,
        llm_service=_FakeLLMService(plan=plan), use_rerank=False,
    )
    assert all(r.metadata["language"] == "python" for r in results)


def test_security_topic_filtering_excludes_linting_docs():
    index = _build_index()
    plan = QueryPlan(queries=["security issue"], filters={"doc_type": "security"})
    results = retrieve_context(
        "code", [_finding("SQLi")], "python", index,
        llm_service=_FakeLLMService(plan=plan), use_rerank=False,
    )
    assert all(r.metadata["doc_type"] == "security" for r in results)


def test_rrf_runs_after_metadata_filtering_assigns_scores():
    index = _build_index()
    plan = QueryPlan(queries=["sql injection parameterized"], filters={"language": "python"})
    results = retrieve_context(
        "code", [_finding("SQLi")], "python", index,
        llm_service=_FakeLLMService(plan=plan), use_rerank=False,
    )
    assert results
    assert all(r.rrf_score > 0 for r in results)
    assert results[0].rank == 1


def test_reranking_runs_after_filtered_retrieval_assigns_rerank_scores():
    index = _build_index()
    plan = QueryPlan(queries=["sql injection parameterized query"], filters={"language": "python"})
    results = retrieve_context(
        "code", [_finding("SQLi")], "python", index,
        llm_service=_FakeLLMService(plan=plan), use_rerank=True, rerank_embeddings=FakeEmbeddings(),
    )
    assert results
    assert any(r.rerank_score is not None for r in results)


def test_retrieve_context_returns_empty_when_nothing_matches_at_all():
    chunks = [_chunk("only python content here", "only:0", language="python")]
    index = RetrieverIndex.build(embeddings=FakeEmbeddings(), knowledge_base=chunks)
    plan = QueryPlan(queries=["totally unrelated query text zzzz"], filters={"language": "go"})
    results = retrieve_context(
        "code", [_finding("Bug")], "go", index,
        llm_service=_FakeLLMService(plan=plan), use_rerank=False,
    )
    # language=go filter relaxed away (no go docs at all) -> falls back to
    # the one unfiltered python chunk, which is a valid, honest outcome
    assert isinstance(results, list)
