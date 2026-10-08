"""
FAISS integration tests using an injected FakeEmbeddings (see
tests/fakes/fake_embeddings.py) -- real FAISS index-build and
similarity-search code paths, run with a fake-but-numerically-real
embedding function instead of a downloaded HuggingFace model.

huggingface.co is blocked by this sandbox's outbound proxy policy
(confirmed via a 403 on CONNECT, not a timeout), so the real
sentence-transformers model cannot be downloaded here. VectorStore's
`embeddings` parameter exists specifically so this integration path can
still be tested for real -- only the embedding *model* is faked, FAISS
itself is the real library.
"""

from __future__ import annotations

from rag.ingestion import IngestedChunk
from rag.metadata import ChunkMetadata
from rag.vector_store import VectorStore
from tests.fakes.fake_embeddings import FakeEmbeddings


def _chunk(text: str, chunk_id: str, topic: str = "general") -> IngestedChunk:
    return IngestedChunk(
        text=text,
        metadata=ChunkMetadata(
            source="test", doc_type="security", language="python",
            topic=topic, chunk_id=chunk_id,
        ),
    )


def test_empty_chunk_list_returns_no_results():
    store = VectorStore([], embeddings=FakeEmbeddings())
    assert store.search("anything") == []


def test_search_returns_results_with_increasing_rank():
    chunks = [
        _chunk("sql injection parameterized query database", "c1"),
        _chunk("hardcoded password secret credential", "c2"),
        _chunk("unused import lint warning", "c3"),
    ]
    store = VectorStore(chunks, embeddings=FakeEmbeddings())

    results = store.search("sql injection database query", k=3)
    assert [r.rank for r in results] == [1, 2, 3]
    # the SQL-injection chunk shares the most vocabulary with the query
    assert results[0].chunk.metadata.chunk_id == "c1"


def test_search_scores_are_higher_for_more_similar_documents():
    chunks = [
        _chunk("sql injection parameterized query database security", "c1"),
        _chunk("completely unrelated topic about baking bread", "c2"),
    ]
    store = VectorStore(chunks, embeddings=FakeEmbeddings())

    results = store.search("sql injection database security", k=2)
    scores = {r.chunk.metadata.chunk_id: r.score for r in results}
    assert scores["c1"] > scores["c2"]


def test_search_respects_k():
    chunks = [_chunk(f"document number {i} about security topic", f"c{i}") for i in range(5)]
    store = VectorStore(chunks, embeddings=FakeEmbeddings())

    results = store.search("security topic", k=2)
    assert len(results) == 2
