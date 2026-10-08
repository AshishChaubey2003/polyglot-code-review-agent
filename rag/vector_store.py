"""
FAISS vector store wrapper.

Builds an index from the ingested knowledge-base chunks and exposes a
similarity search that returns the same `IngestedChunk` objects the
index was built from, so a result carries its metadata, not just text.
"""

from __future__ import annotations

from dataclasses import dataclass

from rag.embeddings import get_embeddings
from rag.ingestion import IngestedChunk


@dataclass
class VectorResult:
    chunk: IngestedChunk
    score: float
    rank: int


class VectorStore:
    """`embeddings` is injectable (any object with `.embed_documents()`
    and `.embed_query()`, matching LangChain's Embeddings interface) so
    this can be tested without downloading a real model. Production
    code omits it and gets the real HuggingFace embeddings via
    `get_embeddings()`."""

    def __init__(self, chunks: list[IngestedChunk], embeddings=None) -> None:
        self.chunks = chunks
        self._index = None
        if chunks:
            self._build(embeddings or get_embeddings())

    def _build(self, embeddings) -> None:
        from langchain_community.vectorstores import FAISS
        from langchain_core.documents import Document

        docs = [
            Document(page_content=c.text, metadata={**c.metadata.to_dict(), "_idx": i})
            for i, c in enumerate(self.chunks)
        ]
        self._index = FAISS.from_documents(docs, embeddings)

    def search(self, query: str, k: int = 10) -> list[VectorResult]:
        if self._index is None:
            return []

        results = self._index.similarity_search_with_score(query, k=k)
        out: list[VectorResult] = []
        for rank, (doc, distance) in enumerate(results, start=1):
            idx = doc.metadata["_idx"]
            # FAISS returns L2 distance (lower = closer); invert to a
            # similarity-style score so higher is better, consistent
            # with BM25's scoring direction.
            similarity = 1.0 / (1.0 + distance)
            out.append(VectorResult(chunk=self.chunks[idx], score=similarity, rank=rank))
        return out
