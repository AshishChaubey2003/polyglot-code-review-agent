"""Schema for LLM-proposed retrieval queries.

query_transform.py asks the LLM for this shape via
LLMService.structured_generate(). The `filters` it proposes are NOT
trusted as-is -- rag/metadata.validate_filters() checks every key and
value against an explicit allow-list before anything is filtered on
them. This model only guarantees shape, not permission.
"""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, Field


class QueryPlan(BaseModel):
    """What the LLM proposes to retrieve relevant knowledge-base context."""

    queries: list[str] = Field(
        description="1-3 short search queries capturing the distinct issues to look up."
    )
    filters: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "Optional metadata filters, e.g. {'language': 'python', 'topic': 'sql-injection'}. "
            "Leave empty if unsure -- an unfiltered search is safer than a wrong filter."
        ),
    )


@dataclass
class RetrievedContext:
    """One piece of retrieved knowledge-base context, with full
    provenance -- per the spec's requirement that a retrieval result
    expose where it came from, not just its text."""

    text: str
    source: str
    metadata: dict
    retrieval_method: str  # "vector" | "bm25" | "hyde" | "fused"
    rank: int
    rrf_score: float
    rerank_score: float | None = None
