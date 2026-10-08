"""
BM25 lexical index.

Searches the original chunk text for exact-term matches -- a CWE id, a
Ruff code, a function name -- which a semantic embedding can miss. This
is deliberately a separate, simple index over the SAME chunks FAISS
indexes, not an attempt to make BM25 do semantic search.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from rank_bm25 import BM25Okapi

from rag.ingestion import IngestedChunk

_TOKEN_RE = re.compile(r"[A-Za-z0-9_\-]+")


def _tokenize(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text)]


@dataclass
class BM25Result:
    chunk: IngestedChunk
    score: float
    rank: int  # 1-based rank within this result set


class BM25Index:
    """Wraps rank_bm25.BM25Okapi with the chunk objects it was built from,
    so a search result carries its metadata, not just a bare score."""

    def __init__(self, chunks: list[IngestedChunk]) -> None:
        self.chunks = chunks
        self._tokenized_corpus = [_tokenize(c.text) for c in chunks]
        self._bm25 = BM25Okapi(self._tokenized_corpus) if chunks else None

    def search(self, query: str, k: int = 10) -> list[BM25Result]:
        if self._bm25 is None or not self.chunks:
            return []

        scores = self._bm25.get_scores(_tokenize(query))
        ranked_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]

        return [
            BM25Result(chunk=self.chunks[idx], score=float(scores[idx]), rank=rank)
            for rank, idx in enumerate(ranked_indices, start=1)
            if scores[idx] > 0  # a zero score means no term overlap at all -- not a real match
        ]
