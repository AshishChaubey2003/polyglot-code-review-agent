"""
Metadata schema and filter validation for the knowledge base.

The core rule from the spec: an LLM may PROPOSE metadata filters (via
query_transform.py), but a proposal is not permission -- every key and
every value is checked against an explicit allow-list here before it is
ever handed to FAISS or BM25. An unknown key or an unknown value is
dropped, not silently passed through and not a hard failure either.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# The only metadata keys a filter may reference. Anything else is
# dropped by validate_filters(), never raises.
ALLOWED_KEYS = {"source", "doc_type", "language", "topic", "cwe", "rule", "section"}

# Per-key allow-lists. A key present here with a non-empty set only
# accepts those exact values; a key absent from this dict is validated
# for shape only (must be a non-empty string).
ALLOWED_VALUES: dict[str, set[str]] = {
    "language": {"python", "javascript", "typescript", "java", "go"},
    "doc_type": {"security", "linting", "style", "quality"},
}


@dataclass
class ChunkMetadata:
    source: str
    doc_type: str
    language: str
    topic: str
    chunk_id: str
    cwe: str | None = None
    rule: str | None = None
    section: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if v is not None}


@dataclass
class FilterValidationResult:
    filters: dict[str, str]
    dropped: list[str] = field(default_factory=list)


def validate_filters(raw_filters: dict[str, Any]) -> FilterValidationResult:
    """Validate an LLM-proposed filter dict against the allow-lists.

    Never raises. Every rejected key/value is recorded in `.dropped`
    with a human-readable reason, for observability -- "the LLM proposed
    X and it was dropped" is a fact worth keeping, not hiding.
    """
    clean: dict[str, str] = {}
    dropped: list[str] = []

    for key, value in (raw_filters or {}).items():
        if key not in ALLOWED_KEYS:
            dropped.append(f"'{key}' is not an allowed filter key")
            continue

        if not isinstance(value, str) or not value.strip():
            dropped.append(f"'{key}' value is not a non-empty string: {value!r}")
            continue

        allowed_values = ALLOWED_VALUES.get(key)
        if allowed_values is not None and value not in allowed_values:
            dropped.append(f"'{key}'='{value}' is not in the allowed value set for '{key}'")
            continue

        clean[key] = value

    return FilterValidationResult(filters=clean, dropped=dropped)
