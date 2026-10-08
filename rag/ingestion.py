"""
Knowledge-base ingestion.

The bundled knowledge base (`data/documents/*.md`) is small and
hand-written -- six short reference documents covering the exact
finding types the static analyzers produce (SQL injection, hardcoded
secrets, eval/exec, unused imports, undefined names) plus PEP8 basics.
This is intentionally NOT a scrape of the full OWASP/CWE sites; it is
enough real, accurate content to prove the retrieval pipeline (chunking,
embedding, BM25, RRF, metadata filtering, reranking) actually works end
to end, and it is the right shape to extend with more documents later.

Metadata per document is assigned from the manifest below rather than
auto-extracted, which keeps it accurate and avoids relying on an LLM to
correctly tag every chunk of a six-document corpus.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from config import KNOWLEDGE_BASE_DIR, logger
from rag.chunking import chunk_markdown
from rag.metadata import ChunkMetadata

_MANIFEST: dict[str, dict] = {
    "sql_injection.md": {"doc_type": "security", "language": "python", "topic": "sql-injection", "cwe": "CWE-89"},
    "hardcoded_secrets.md": {"doc_type": "security", "language": "python", "topic": "hardcoded-secrets", "cwe": "CWE-798"},
    "eval_exec.md": {"doc_type": "security", "language": "python", "topic": "eval-exec", "cwe": "CWE-95", "rule": "B307"},
    "unused_imports.md": {"doc_type": "linting", "language": "python", "topic": "unused-import", "rule": "F401"},
    "undefined_names.md": {"doc_type": "linting", "language": "python", "topic": "undefined-name", "rule": "F821"},
}


@dataclass
class IngestedChunk:
    text: str
    metadata: ChunkMetadata


def load_knowledge_base(base_dir: str | Path = KNOWLEDGE_BASE_DIR) -> list[IngestedChunk]:
    """Read, chunk, and tag every document in the manifest.

    A document present on disk but missing from the manifest is skipped
    with a warning rather than ingested with guessed metadata -- better
    to notice a document was forgotten than to tag it wrong.
    """
    base_path = Path(base_dir)
    chunks: list[IngestedChunk] = []

    for filename, meta in _MANIFEST.items():
        file_path = base_path / filename
        if not file_path.exists():
            logger.warning("Knowledge base document not found: %s", file_path)
            continue

        text = file_path.read_text(encoding="utf-8")
        for piece in chunk_markdown(text):
            chunks.append(
                IngestedChunk(
                    text=piece.text,
                    metadata=ChunkMetadata(
                        source=filename.removesuffix(".md"),
                        doc_type=meta["doc_type"],
                        language=meta["language"],
                        topic=meta["topic"],
                        chunk_id=f"{filename}:{piece.index}",
                        cwe=meta.get("cwe"),
                        rule=meta.get("rule"),
                    ),
                )
            )

    unmanifested = [
        p.name for p in base_path.glob("*.md") if p.name not in _MANIFEST
    ] if base_path.exists() else []
    if unmanifested:
        logger.warning("Documents present but not in the ingestion manifest, skipped: %s", unmanifested)

    return chunks
