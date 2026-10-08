"""
Embedding model, cached as a singleton.

A HuggingFaceEmbeddings instance loads model weights on first use --
rebuilding it per call (the original project's bug) reloads weights on
every review. This module builds it once and reuses it.
"""

from __future__ import annotations

_embeddings = None

DEFAULT_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


def get_embeddings():
    """Return a cached HuggingFaceEmbeddings instance.

    Imports langchain_huggingface lazily so modules that only need
    `rag.embeddings` for type purposes don't pay the import cost, and so
    a missing optional dependency fails at call time with a clear error
    rather than at module import time.
    """
    global _embeddings
    if _embeddings is None:
        from langchain_huggingface import HuggingFaceEmbeddings

        _embeddings = HuggingFaceEmbeddings(model_name=DEFAULT_MODEL_NAME)
    return _embeddings


def reset_embeddings_cache() -> None:
    """Test/debug hook -- forces the next get_embeddings() call to rebuild."""
    global _embeddings
    _embeddings = None
