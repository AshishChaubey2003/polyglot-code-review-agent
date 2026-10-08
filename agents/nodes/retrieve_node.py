"""Retrieval node -- wraps rag.retriever.retrieve_context(). The
RetrieverIndex is built once at module import (knowledge base is
small and static) and reused across requests, not rebuilt per call."""

from __future__ import annotations

from agents.state import ReviewState
from rag.retriever import RetrieverIndex, retrieve_context

_INDEX: RetrieverIndex | None = None


def _get_index() -> RetrieverIndex:
    global _INDEX
    if _INDEX is None:
        _INDEX = RetrieverIndex.build()
    return _INDEX


def run_retrieval(state: ReviewState) -> dict:
    try:
        index = _get_index()
        results = retrieve_context(
            state["code"], state.get("static_findings", []), state["language"], index,
        )
    except Exception:  # noqa: BLE001 -- retrieval is an enhancement, never fatal to the review
        results = []
    return {"retrieved_context": results}
