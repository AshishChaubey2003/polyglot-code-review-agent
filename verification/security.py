"""Security verification step -- wraps the real Bandit runner.

Unlike lint, this one is strict: a fix must not introduce ANY new
Bandit finding, since the whole point of repair mode is often to FIX a
security issue, not trade it for a different one.
"""

from __future__ import annotations

from analyzers.tools.bandit_runner import run_bandit
from models.fix import VerificationStepResult


def verify_security(fixed_code: str, original_finding_titles: set[str] | None = None) -> VerificationStepResult:
    original_finding_titles = original_finding_titles or set()
    findings = run_bandit(fixed_code)
    new_findings = [f for f in findings if f.title not in original_finding_titles]

    if new_findings:
        titles = ", ".join(f.title for f in new_findings[:3])
        return VerificationStepResult(
            name="security", passed=False,
            detail=f"Fix introduces {len(new_findings)} new security finding(s): {titles}",
        )
    return VerificationStepResult(name="security", passed=True, detail="No new security findings.")
