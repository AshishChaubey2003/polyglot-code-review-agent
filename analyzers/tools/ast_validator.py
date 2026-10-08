"""
AST-based structural validation for Python.

Two responsibilities only -- this does not duplicate Ruff's job:
  1. Confirm the code parses at all. A SyntaxError here is the one
     finding every other analyzer depends on being absent, so it runs
     first and, if it fires, Ruff/Bandit are skipped entirely.
  2. Cheap structural facts (function/class counts) that later phases
     (code-aware chunking, the scope guard on repairs) will need and
     that are free to compute here rather than re-parsing elsewhere.
"""

from __future__ import annotations

import ast

from models.finding import Finding


def validate_syntax(code: str) -> list[Finding]:
    """Return a single critical Finding if the code does not parse,
    otherwise an empty list."""
    try:
        ast.parse(code)
        return []
    except SyntaxError as exc:
        return [
            Finding(
                category="bug",
                severity="critical",
                title="Code does not parse",
                description=f"SyntaxError: {exc.msg}",
                line=exc.lineno,
                evidence=(exc.text or "").strip() or "(no source line available)",
                recommendation="Fix the syntax error before any further analysis is possible.",
                source="ast",
            )
        ]


def structural_summary(code: str) -> dict:
    """Best-effort function/class counts for later phases.

    Returns parsed=False rather than raising if the code does not parse
    -- callers should run validate_syntax() first and only call this on
    code already known to parse.
    """
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return {"functions": 0, "classes": 0, "parsed": False}

    functions = sum(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) for node in ast.walk(tree)
    )
    classes = sum(isinstance(node, ast.ClassDef) for node in ast.walk(tree))
    return {"functions": functions, "classes": classes, "parsed": True}
