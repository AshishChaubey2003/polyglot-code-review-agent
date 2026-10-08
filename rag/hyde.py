"""
HyDE (Hypothetical Document Embeddings) -- optional extra retrieval
signal. Ask the LLM to write a short hypothetical reference passage
that *would* answer the query, embed that passage, and search with it
alongside the real query. The hypothetical text is never shown to the
user and never stored as a real document -- it only produces one more
ranked id list that gets fused via RRF with everything else. If the
LLM call fails, HyDE simply contributes nothing; it never replaces or
blocks the original query-based retrieval.
"""

from __future__ import annotations

from config import logger
from rag.ingestion import IngestedChunk
from rag.vector_store import VectorStore
from services.llm_service import LLMService, LLMServiceError

_PROMPT_TEMPLATE = """\
Write a short (2-4 sentence) technical reference passage that would be a \
perfect answer to this search query about a code issue. Do not mention \
the query itself -- just write the passage as if it were an excerpt from \
a secure-coding reference document.

Query: {query}
"""


def generate_hypothetical_document(query: str, llm_service: LLMService | None = None) -> str | None:
    """Returns a hypothetical passage, or None if the LLM call failed."""
    service = llm_service or LLMService()
    try:
        return service.generate(_PROMPT_TEMPLATE.format(query=query)).strip() or None
    except LLMServiceError as exc:
        logger.warning("HyDE generation failed, skipping this signal: %s", exc)
        return None


def hyde_candidate_ids(
    query: str,
    chunks: list[IngestedChunk],
    vector_store: VectorStore,
    k: int = 10,
    llm_service: LLMService | None = None,
) -> list[str]:
    """Returns a ranked list of chunk_ids from searching the vector
    store with a HyDE-generated hypothetical document instead of the
    raw query. Returns [] (contributes nothing) on any failure --
    callers fuse this with other ranked lists via RRF, so an empty
    list here just means HyDE added no signal this time."""
    hypothetical = generate_hypothetical_document(query, llm_service=llm_service)
    if not hypothetical:
        return []

    results = vector_store.search(hypothetical, k=k)
    return [r.chunk.metadata.chunk_id for r in results]
