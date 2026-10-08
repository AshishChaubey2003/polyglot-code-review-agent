"""
A fake embedding model with LangChain's Embeddings interface
(`embed_documents`, `embed_query`), used everywhere real network access
to HuggingFace is unavailable (confirmed blocked in this sandbox).

It is not a random stub: it builds a real bag-of-words vector over a
fixed vocabulary, so cosine similarity between two embeddings genuinely
reflects word overlap. This lets tests assert real things ("the SQL
injection query is closer to the SQL injection document than to the
unused-import document") rather than just "a number came back".
"""

from __future__ import annotations

import re

from langchain_core.embeddings import Embeddings

_TOKEN_RE = re.compile(r"[a-z0-9_]+")


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


class FakeEmbeddings(Embeddings):
    """Deterministic bag-of-words embeddings. Builds its vocabulary
    lazily from whatever text it has seen, so vector length grows as
    needed -- callers just need `embed_documents` called with the full
    corpus before comparing against query vectors of consistent length,
    which `embed_query`/`embed_documents` handle by sharing one
    growing vocabulary across calls."""

    def __init__(self) -> None:
        self._vocab: dict[str, int] = {}

    def _vector_for(self, text: str, grow_vocab: bool) -> list[float]:
        counts: dict[int, int] = {}
        for token in _tokenize(text):
            if grow_vocab:
                idx = self._vocab.setdefault(token, len(self._vocab))
            else:
                idx = self._vocab.get(token)
                if idx is None:
                    continue  # unknown word at query time: ignored, not a new dimension
            counts[idx] = counts.get(idx, 0) + 1
        vector = [0.0] * len(self._vocab)
        for idx, count in counts.items():
            vector[idx] = float(count)
        return vector

    def _pad(self, vectors: list[list[float]]) -> list[list[float]]:
        width = len(self._vocab)
        return [v + [0.0] * (width - len(v)) for v in vectors]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        # Builds the vocabulary. Called once by FAISS.from_documents(),
        # so the index's vector dimension is fixed from here on.
        vectors = [self._vector_for(t, grow_vocab=True) for t in texts]
        return self._pad(vectors)

    def embed_query(self, text: str) -> list[float]:
        # Never grows the vocabulary -- keeps dimension consistent with
        # whatever embed_documents() already fixed for the index.
        return self._vector_for(text, grow_vocab=False)
