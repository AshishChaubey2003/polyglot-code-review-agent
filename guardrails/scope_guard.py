"""
Scope guard -- a fix should touch what the finding says it touches, not
rewrite the file around it.

This is a size/shape heuristic, not a semantic one: it flags a diff that
is implausibly large relative to the number of lines actually implicated
by the findings being fixed. It does not understand WHY a change was
made, only whether its size is consistent with "fix these findings."
"""

from __future__ import annotations

from dataclasses import dataclass

# A changed-line count more than this multiple of the implicated lines
# (with a floor, so a 1-line fix for a 1-line finding doesn't trip this)
# is flagged for review rather than silently accepted.
_MAX_EXPANSION_FACTOR = 4
_MIN_LINE_ALLOWANCE = 5


@dataclass
class ScopeGuardResult:
    allowed: bool
    reason: str = ""


def check_fix_scope(changed_lines: list[int], finding_lines: list[int]) -> ScopeGuardResult:
    """changed_lines: lines the fix actually touched (from CodeFix.changed_lines).
    finding_lines: lines the findings being addressed were reported on."""
    implicated = {ln for ln in finding_lines if ln is not None}
    touched = set(changed_lines)

    if not touched:
        return ScopeGuardResult(allowed=False, reason="Fix reports no changed lines.")

    allowance = max(_MIN_LINE_ALLOWANCE, len(implicated) * _MAX_EXPANSION_FACTOR)
    if len(touched) > allowance:
        return ScopeGuardResult(
            allowed=False,
            reason=(
                f"Fix touches {len(touched)} lines but only {len(implicated)} were "
                f"implicated by the findings being addressed (allowance: {allowance}). "
                "This looks like more than a targeted fix -- review manually."
            ),
        )

    return ScopeGuardResult(allowed=True)
