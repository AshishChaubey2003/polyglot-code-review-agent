"""Lint verification step -- wraps the real Ruff runner.

A fix is not required to be perfectly lint-clean (the original code
might not have been either), only to not introduce NEW bug-category
findings that weren't there before.
"""

from __future__ import annotations

from analyzers.tools.ruff_runner import run_ruff
from models.fix import VerificationStepResult


def verify_lint(fixed_code: str, original_bug_titles: set[str] | None = None) -> VerificationStepResult:
    original_bug_titles = original_bug_titles or set()
    findings = run_ruff(fixed_code)
    new_bugs = [f for f in findings if f.category == "bug" and f.title not in original_bug_titles]

    if new_bugs:
        titles = ", ".join(f.title for f in new_bugs[:3])
        return VerificationStepResult(
            name="lint", passed=False,
            detail=f"Fix introduces {len(new_bugs)} new bug-category finding(s): {titles}",
        )
    return VerificationStepResult(name="lint", passed=True, detail="No new bug-category findings.")
