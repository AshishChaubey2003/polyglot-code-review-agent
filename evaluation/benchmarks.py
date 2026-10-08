"""
Retrieval benchmark: basic FAISS-only vs. hybrid (FAISS+BM25 fused by
RRF) vs. hybrid+rerank, measured as "does the expected document appear
in the top-k" over a handful of hand-labeled queries against the
bundled knowledge base.

Same caveat as evaluation/metrics.py: this knowledge base has five
documents and this benchmark has five queries. The numbers below are
useful for noticing "hybrid retrieval regressed and now does worse
than vector-only", never for claiming one retrieval strategy is
statistically better than another -- that would need a much larger,
independently-labeled query set.
"""

from __future__ import annotations

from dataclasses import dataclass

from rag.ingestion import load_knowledge_base
from rag.reranker import rerank
from rag.retriever import RetrieverIndex
from rag.rrf import reciprocal_rank_fusion

CAVEAT = (
    "Benchmarked over 5 queries against a 5-document knowledge base -- "
    "far too small to be statistically significant. This compares "
    "retrieval STRATEGIES against each other on a fixed, tiny corpus "
    "for regression visibility, not an absolute quality claim."
)

_LABELED_QUERIES: list[tuple[str, str]] = [
    ("SQL injection parameterized query", "sql_injection"),
    ("hardcoded password in source code", "hardcoded_secrets"),
    ("eval exec arbitrary code execution", "eval_exec"),
    ("unused import flagged by linter", "unused_imports"),
    ("undefined name used before assignment", "undefined_names"),
]


@dataclass
class StrategyResult:
    name: str
    hits: int
    total: int

    @property
    def hit_rate(self) -> float:
        return self.hits / self.total if self.total else 0.0


def _is_hit(results, expected_source: str, k: int = 3) -> bool:
    return any(r.chunk.metadata.source == expected_source for r in results[:k])


def run_benchmark(embeddings) -> list[StrategyResult]:
    """`embeddings` must be supplied by the caller (injectable, same as
    everywhere else in rag/) -- this never downloads a model itself."""
    chunks = load_knowledge_base()
    index = RetrieverIndex.build(embeddings=embeddings, knowledge_base=chunks)

    vector_only_hits = 0
    hybrid_hits = 0
    hybrid_rerank_hits = 0

    for query, expected_source in _LABELED_QUERIES:
        vector_results = index.vector_store.search(query, k=5)
        if _is_hit(vector_results, expected_source):
            vector_only_hits += 1

        bm25_results = index.bm25.search(query, k=5)
        by_id = {c.metadata.chunk_id: c for c in chunks}
        fused_ids = sorted(
            reciprocal_rank_fusion([
                [r.chunk.metadata.chunk_id for r in vector_results],
                [r.chunk.metadata.chunk_id for r in bm25_results],
            ]).items(),
            key=lambda pair: pair[1], reverse=True,
        )
        fused_chunks = [by_id[cid] for cid, _ in fused_ids if cid in by_id]
        if any(c.metadata.source == expected_source for c in fused_chunks[:3]):
            hybrid_hits += 1

        reranked = rerank(query, fused_chunks[:10], embeddings)
        if any(r.chunk.metadata.source == expected_source for r in reranked[:3]):
            hybrid_rerank_hits += 1

    total = len(_LABELED_QUERIES)
    return [
        StrategyResult("vector_only", vector_only_hits, total),
        StrategyResult("hybrid_rrf", hybrid_hits, total),
        StrategyResult("hybrid_rrf_rerank", hybrid_rerank_hits, total),
    ]
