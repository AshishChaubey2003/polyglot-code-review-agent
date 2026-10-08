"""Phase 5/6 unit tests: the parts of RAG that need no network --
chunking, metadata validation, ingestion, BM25, and RRF. All real, no
mocks. Embedding/FAISS tests live in test_rag_vector.py since they need
a model download."""

from __future__ import annotations

from rag.bm25 import BM25Index
from rag.chunking import chunk_markdown, chunk_python_code
from rag.ingestion import load_knowledge_base
from rag.metadata import validate_filters
from rag.rrf import fuse_and_rank, reciprocal_rank_fusion


# ── chunking ─────────────────────────────────────────────────────────
def test_chunk_markdown_splits_on_paragraphs():
    text = "para one.\n\npara two.\n\npara three."
    chunks = chunk_markdown(text, chunk_size=1000)
    assert len(chunks) == 1  # all fit in one chunk at this size
    assert "para one" in chunks[0].text


def test_chunk_markdown_respects_small_chunk_size():
    text = "first paragraph here.\n\nsecond paragraph here.\n\nthird paragraph here."
    chunks = chunk_markdown(text, chunk_size=30)
    assert len(chunks) > 1
    assert all(len(c.text) <= 60 for c in chunks)  # allows some slack for one long paragraph


def test_chunk_python_code_splits_on_function_boundaries():
    code = "def a():\n    return 1\n\n\ndef b():\n    return 2\n"
    chunks = chunk_python_code(code)
    assert len(chunks) == 2
    assert "def a" in chunks[0].text
    assert "def b" in chunks[1].text


def test_chunk_python_code_falls_back_on_syntax_error():
    chunks = chunk_python_code("def a(:\n")
    assert len(chunks) == 1


# ── metadata ─────────────────────────────────────────────────────────
def test_valid_filters_pass_through():
    result = validate_filters({"language": "python", "topic": "sql-injection"})
    assert result.filters == {"language": "python", "topic": "sql-injection"}
    assert result.dropped == []


def test_unknown_key_is_dropped_not_raised():
    result = validate_filters({"language": "python", "made_up_key": "x"})
    assert "language" in result.filters
    assert "made_up_key" not in result.filters
    assert len(result.dropped) == 1


def test_invalid_language_value_is_dropped():
    result = validate_filters({"language": "cobol"})
    assert result.filters == {}
    assert result.dropped


def test_empty_filters_are_fine():
    result = validate_filters({})
    assert result.filters == {}
    assert result.dropped == []


# ── ingestion ────────────────────────────────────────────────────────
def test_knowledge_base_loads_all_manifested_documents():
    chunks = load_knowledge_base()
    sources = {c.metadata.source for c in chunks}
    assert sources == {
        "sql_injection", "hardcoded_secrets", "eval_exec",
        "unused_imports", "undefined_names",
    }


def test_every_chunk_has_a_chunk_id():
    chunks = load_knowledge_base()
    ids = [c.metadata.chunk_id for c in chunks]
    assert len(ids) == len(set(ids))  # all unique


# ── BM25 ─────────────────────────────────────────────────────────────
def test_bm25_finds_exact_term_match():
    chunks = load_knowledge_base()
    index = BM25Index(chunks)

    results = index.search("CWE-89 SQL injection parameterized query", k=5)
    assert results
    assert any(r.chunk.metadata.source == "sql_injection" for r in results)


def test_bm25_empty_corpus_returns_nothing():
    index = BM25Index([])
    assert index.search("anything") == []


def test_bm25_ranks_are_sequential():
    chunks = load_knowledge_base()
    index = BM25Index(chunks)
    results = index.search("eval exec unsafe", k=5)
    ranks = [r.rank for r in results]
    assert ranks == sorted(ranks)


# ── RRF ──────────────────────────────────────────────────────────────
def test_rrf_favors_documents_ranked_highly_in_multiple_lists():
    list_a = ["doc1", "doc2", "doc3"]
    list_b = ["doc2", "doc1", "doc4"]

    scores = reciprocal_rank_fusion([list_a, list_b])
    # doc1 and doc2 both appear near the top of both lists -- they should
    # outscore doc3/doc4, which each appear low in only one list.
    assert scores["doc1"] > scores["doc3"]
    assert scores["doc2"] > scores["doc4"]


def test_rrf_matches_hand_computed_example():
    # k=60 by default. doc_a: rank 1 in list A, rank 2 in list B.
    list_a = ["doc_a", "doc_b"]
    list_b = ["doc_b", "doc_a"]

    scores = reciprocal_rank_fusion([list_a, list_b], k=60)
    expected_a = 1 / 61 + 1 / 62  # rank1 in A, rank2 in B
    expected_b = 1 / 62 + 1 / 61  # rank2 in A, rank1 in B

    assert abs(scores["doc_a"] - expected_a) < 1e-9
    assert abs(scores["doc_b"] - expected_b) < 1e-9
    assert scores["doc_a"] == scores["doc_b"]  # symmetric placement


def test_fuse_and_rank_returns_sorted_ids():
    ranked = fuse_and_rank([["x", "y", "z"], ["y", "z", "x"]])
    assert set(ranked) == {"x", "y", "z"}
    # y is rank 1 in list B and rank 2 in list A -- should rank at least as well as z
    assert ranked.index("y") <= ranked.index("z")
