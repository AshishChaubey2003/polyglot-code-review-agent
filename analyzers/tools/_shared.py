"""
Shared helpers for tool wrappers (ruff_runner, bandit_runner).

Leading underscore: internal to analyzers.tools, not part of the public
LanguageAnalyzer interface.
"""

from __future__ import annotations

from models.finding import Finding, Source


def tool_unavailable_finding(
    tool_name: str,
    source: Source,
    detail: str = "is not installed or not on PATH",
) -> Finding:
    """A tool that could not run becomes a low-severity quality finding,
    never a crash and never a silently empty result the caller can't
    distinguish from 'this code is clean'."""
    return Finding(
        category="quality",
        severity="low",
        title=f"{tool_name} unavailable",
        description=f"{tool_name} {detail}; static findings from this tool were skipped.",
        line=None,
        evidence=f"{tool_name} {detail}",
        recommendation=f"Install {tool_name} to enable this analysis.",
        source=source,
    )


def tool_timeout_finding(tool_name: str, source: Source, timeout_seconds: int) -> Finding:
    return Finding(
        category="quality",
        severity="low",
        title=f"{tool_name} timed out",
        description=(
            f"{tool_name} did not finish within {timeout_seconds}s; "
            "findings from this tool were skipped."
        ),
        line=None,
        evidence="timeout",
        recommendation="Review the file manually; it may be unusually large.",
        source=source,
    )
