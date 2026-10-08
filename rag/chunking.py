"""
Chunking strategies.

`chunk_markdown` is structure-aware for the knowledge-base documents
(splits on section boundaries first, falls back to size-based splitting
only within an oversized section) -- it never cuts a sentence in half
if a paragraph boundary is available nearby.

`chunk_python_code` is AST-aware: it splits on function/class
boundaries rather than raw character count, so a chunk is never half a
function. This exists for a future "index the user's own codebase"
feature; the bundled knowledge base is markdown, so today only
`chunk_markdown` runs in the ingestion pipeline.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass

DEFAULT_CHUNK_SIZE = 500
DEFAULT_CHUNK_OVERLAP = 50


@dataclass
class Chunk:
    text: str
    index: int


def chunk_markdown(
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[Chunk]:
    """Split on blank-line (paragraph/section) boundaries first, then
    pack paragraphs into ~chunk_size windows without splitting a
    paragraph unless it alone exceeds chunk_size."""
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if not paragraphs:
        return []

    chunks: list[str] = []
    current = ""

    for para in paragraphs:
        if len(para) > chunk_size:
            # Oversized paragraph: fall back to character windows with overlap.
            if current:
                chunks.append(current)
                current = ""
            start = 0
            while start < len(para):
                end = start + chunk_size
                chunks.append(para[start:end])
                start = end - overlap if end - overlap > start else end
            continue

        candidate = f"{current}\n\n{para}" if current else para
        if len(candidate) <= chunk_size:
            current = candidate
        else:
            chunks.append(current)
            current = para

    if current:
        chunks.append(current)

    return [Chunk(text=c, index=i) for i, c in enumerate(chunks)]


def chunk_python_code(code: str) -> list[Chunk]:
    """Split Python source on top-level function/class boundaries.

    Falls back to a single whole-file chunk if the code does not parse
    -- chunking should never raise on code that is merely invalid, that
    is static analysis's job, not this one's.
    """
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return [Chunk(text=code, index=0)]

    lines = code.splitlines(keepends=True)
    top_level = [
        node for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    ]

    if not top_level:
        return [Chunk(text=code, index=0)] if code.strip() else []

    chunks: list[Chunk] = []
    for i, node in enumerate(top_level):
        start = node.lineno - 1
        end = node.end_lineno if node.end_lineno is not None else len(lines)
        chunks.append(Chunk(text="".join(lines[start:end]), index=i))

    return chunks
