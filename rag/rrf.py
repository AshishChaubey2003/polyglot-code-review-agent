"""
Reciprocal Rank Fusion.

    RRF(d) = sum over every ranked list containing d of 1 / (k + rank(d))

Combines any number of ranked result lists (vector, BM25, HyDE, ...)
into one fused ranking, without hand-tuned per-source weights. Generic
over a document id -- callers decide what identifies "the same chunk"
across different result lists (here, `chunk_id`).
"""

from __future__ import annotations

DEFAULT_K = 60


def reciprocal_rank_fusion(
    ranked_lists: list[list[str]],
    k: int = DEFAULT_K,
) -> dict[str, float]:
    """`ranked_lists`: each inner list is document ids in rank order
    (best first) from one retrieval source. Returns {doc_id: rrf_score},
    not sorted -- callers sort by score descending themselves."""
    scores: dict[str, float] = {}

    for ranked_ids in ranked_lists:
        for position, doc_id in enumerate(ranked_ids, start=1):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + position)

    return scores


def fuse_and_rank(ranked_lists: list[list[str]], k: int = DEFAULT_K) -> list[str]:
    """Convenience wrapper: fuse, then return doc ids sorted best-first."""
    scores = reciprocal_rank_fusion(ranked_lists, k=k)
    return sorted(scores, key=lambda doc_id: scores[doc_id], reverse=True)
