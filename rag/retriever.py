"""
Retrieval orchestrator: ties query transformation, FAISS (vector), BM25
(lexical), optional HyDE, metadata filtering, RRF fusion, and reranking
into one `retrieve_context()` call.

Zero-result fallback chain (per spec -- a wrong filter should narrow
results, never silently return nothing with no explanation):
  1. Try with the LLM-proposed (validated) filters.
  2. If empty, drop the most specific filter (topic, then cwe/rule).
  3. If still empty, drop all filters and search unfiltered.
  4. If still empty, return [] -- genuinely nothing matched.
Every step taken is logged so a caller can see which fallback fired.
"""

from __future__ import annotations

from dataclasses import dataclass

from config import logger
from models.retrieval import RetrievedContext
from rag.bm25 import BM25Index
from rag.hyde import hyde_candidate_ids
from rag.ingestion import IngestedChunk, load_knowledge_base
from rag.query_transform import transform_query
from rag.reranker import rerank
from rag.rrf import reciprocal_rank_fusion
from rag.vector_store import VectorStore
from services.llm_service import LLMService

_RELAX_ORDER = ["section", "rule", "cwe", "topic", "doc_type", "language", "source"]


def _apply_filters(chunks: list[IngestedChunk], filters: dict[str, str]) -> list[IngestedChunk]:
    if not filters:
        return chunks
    return [
        c for c in chunks
        if all(getattr(c.metadata, key, None) == value for key, value in filters.items())
    ]


def _filtered_chunks_with_fallback(
    chunks: list[IngestedChunk], filters: dict[str, str]
) -> tuple[list[IngestedChunk], dict[str, str]]:
    """Returns (matching_chunks, filters_actually_used), relaxing one
    filter key at a time until something matches or filters run out."""
    current = dict(filters)
    matched = _apply_filters(chunks, current)
    if matched or not current:
        return matched, current

    for key in _RELAX_ORDER:
        if key in current:
            logger.info("Retrieval: no matches with filters=%s, relaxing '%s'", current, key)
            current = {k: v for k, v in current.items() if k != key}
            matched = _apply_filters(chunks, current)
            if matched or not current:
                return matched, current

    return matched, current


@dataclass
class RetrieverIndex:
    """Bundles the knowledge base's chunks with its two search indexes
    so they're built once and reused across calls, not rebuilt per
    query."""

    chunks: list[IngestedChunk]
    bm25: BM25Index
    vector_store: VectorStore
    embeddings: object = None

    @classmethod
    def build(cls, embeddings=None, knowledge_base: list[IngestedChunk] | None = None) -> "RetrieverIndex":
        chunks = knowledge_base if knowledge_base is not None else load_knowledge_base()
        return cls(
            chunks=chunks,
            bm25=BM25Index(chunks),
            vector_store=VectorStore(chunks, embeddings=embeddings),
            embeddings=embeddings,
        )


def retrieve_context(
    code: str,
    findings: list,
    language: str,
    index: RetrieverIndex,
    llm_service: LLMService | None = None,
    use_hyde: bool = False,
    use_rerank: bool = True,
    rerank_embeddings=None,
    top_k: int = 5,
) -> list[RetrievedContext]:
    """Full hybrid retrieval pipeline. Returns up to `top_k` results,
    each carrying its provenance (which method(s) surfaced it, its
    fused RRF score, and its rerank score if reranking ran)."""
    service = llm_service or LLMService()
    plan = transform_query(code, findings, language, llm_service=service)

    candidate_chunks, used_filters = _filtered_chunks_with_fallback(index.chunks, plan.filters)
    if not candidate_chunks:
        logger.info("Retrieval: no chunks matched even after relaxing all filters.")
        return []

    by_id = {c.metadata.chunk_id: c for c in candidate_chunks}
    scoped_bm25 = BM25Index(candidate_chunks) if used_filters else index.bm25
    scoped_vectors = (
        VectorStore(candidate_chunks, embeddings=index.embeddings) if used_filters else index.vector_store
    )

    ranked_lists: list[list[str]] = []
    for query in plan.queries:
        vector_hits = scoped_vectors.search(query, k=top_k * 2)
        ranked_lists.append([r.chunk.metadata.chunk_id for r in vector_hits if r.chunk.metadata.chunk_id in by_id])

        bm25_hits = scoped_bm25.search(query, k=top_k * 2)
        ranked_lists.append([r.chunk.metadata.chunk_id for r in bm25_hits if r.chunk.metadata.chunk_id in by_id])

        if use_hyde:
            hyde_ids = hyde_candidate_ids(query, candidate_chunks, scoped_vectors, k=top_k * 2, llm_service=service)
            ranked_lists.append([cid for cid in hyde_ids if cid in by_id])

    fused_scores = reciprocal_rank_fusion([lst for lst in ranked_lists if lst])
    if not fused_scores:
        return []

    fused_order = sorted(fused_scores, key=lambda cid: fused_scores[cid], reverse=True)[: top_k * 2]
    top_chunks = [by_id[cid] for cid in fused_order]

    rerank_scores: dict[str, float] = {}
    if use_rerank:
        try:
            embeddings = rerank_embeddings or index.embeddings
            if embeddings is None:
                from rag.embeddings import get_embeddings
                embeddings = get_embeddings()
            reranked = rerank(plan.queries[0], top_chunks, embeddings)
            for r in reranked:
                rerank_scores[r.chunk.metadata.chunk_id] = r.score
            top_chunks.sort(key=lambda c: rerank_scores.get(c.metadata.chunk_id, 0.0), reverse=True)
        except Exception as exc:  # noqa: BLE001 -- reranking is an enhancement, never fatal
            logger.warning("Reranking failed, falling back to RRF order: %s", exc)

    results = []
    for rank, chunk in enumerate(top_chunks[:top_k], start=1):
        cid = chunk.metadata.chunk_id
        results.append(
            RetrievedContext(
                text=chunk.text,
                source=chunk.metadata.source,
                metadata=chunk.metadata.to_dict(),
                retrieval_method="fused" if len(ranked_lists) > 1 else "vector",
                rank=rank,
                rrf_score=fused_scores.get(cid, 0.0),
                rerank_score=rerank_scores.get(cid),
            )
        )
    return results
