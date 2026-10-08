"""Unified diff generation between original and proposed code."""

from __future__ import annotations

import difflib
from dataclasses import dataclass


@dataclass
class DiffStats:
    lines_added: int
    lines_removed: int
    unified_diff: str


def build_diff(original: str, proposed: str, filename: str = "code.py") -> DiffStats:
    original_lines = original.splitlines(keepends=True)
    proposed_lines = proposed.splitlines(keepends=True)

    diff_lines = list(
        difflib.unified_diff(
            original_lines, proposed_lines,
            fromfile=f"a/{filename}", tofile=f"b/{filename}",
        )
    )

    added = sum(1 for line in diff_lines if line.startswith("+") and not line.startswith("+++"))
    removed = sum(1 for line in diff_lines if line.startswith("-") and not line.startswith("---"))

    return DiffStats(
        lines_added=added,
        lines_removed=removed,
        unified_diff="".join(diff_lines) or "(no textual difference)",
    )
