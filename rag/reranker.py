"""
Reranking: re-score an already-retrieved candidate set against the
original query using embedding cosine similarity. This runs on a small
candidate list (tens of chunks), not the whole corpus, so it is cheap
even though it recomputes similarity directly rather than trusting the
RRF-fused order alone.

Embeddings are injectable here too (same pattern as vector_store.py)
so this is testable without a model download. An optional cross-encoder
path is left as a documented extension point, not implemented, since a
cross-encoder model is a second heavy model download this environment
cannot validate with real network access.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from rag.ingestion import IngestedChunk


@dataclass
class RerankedResult:
    chunk: IngestedChunk
    score: float
    rank: int


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    a_arr, b_arr = np.array(a), np.array(b)
    denom = np.linalg.norm(a_arr) * np.linalg.norm(b_arr)
    if denom == 0:
        return 0.0
    return float(np.dot(a_arr, b_arr) / denom)


def rerank(query: str, candidates: list[IngestedChunk], embeddings) -> list[RerankedResult]:
    """`embeddings` is any object with `.embed_query(text) -> list[float]`
    and `.embed_documents(texts) -> list[list[float]]`, matching
    LangChain's Embeddings interface -- the same injectable contract
    vector_store.py uses, so tests can pass a fake, numerically-real
    embedding function instead of downloading a model.

    Returns candidates re-sorted by cosine similarity to the query,
    best first. Never raises on an empty candidate list."""
    if not candidates:
        return []

    # Documents first: with the injectable fake embeddings, this is what
    # builds/grows the vocabulary that embed_query() then maps onto, the
    # same order VectorStore uses (index built from docs, then queried).
    doc_vecs = embeddings.embed_documents([c.text for c in candidates])
    query_vec = embeddings.embed_query(query)

    scored = [
        (chunk, _cosine_similarity(query_vec, doc_vec))
        for chunk, doc_vec in zip(candidates, doc_vecs)
    ]
    scored.sort(key=lambda pair: pair[1], reverse=True)

    return [
        RerankedResult(chunk=chunk, score=score, rank=rank)
        for rank, (chunk, score) in enumerate(scored, start=1)
    ]
