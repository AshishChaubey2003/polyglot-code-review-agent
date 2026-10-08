"""
Output guardrail -- validates what comes back from the LLM before it is
used anywhere downstream.

Most structural validation already happens for free: `LLMService.
structured_generate()` returns a Pydantic-validated object or raises.
This module adds the checks Pydantic's type system can't express on its
own: that a fix doesn't echo back a secret from the input, and that a
"code" field actually looks like code rather than conversational prose.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from guardrails.secret_guard import find_secrets
from models.fix import CodeFix

# A handful of conversational openers that indicate the model answered
# in prose where a code-only contract was specified.
_PROSE_MARKERS = ("sure!", "here is", "here's", "certainly", "i'll fix", "i will fix")


@dataclass
class OutputGuardResult:
    allowed: bool
    reasons: list[str] = field(default_factory=list)


def check_fix_output(fix: CodeFix, original_code: str) -> OutputGuardResult:
    """Validate a proposed fix before it reaches verification."""
    reasons: list[str] = []

    body = fix.fixed_code.strip()
    if not body:
        return OutputGuardResult(allowed=False, reasons=["Fix contains no code."])

    lowered_start = body.lower()[:40]
    if any(lowered_start.startswith(marker) for marker in _PROSE_MARKERS):
        return OutputGuardResult(
            allowed=False,
            reasons=["Fix output looks like conversational prose, not code."],
        )

    original_secrets = {s.masked for s in find_secrets(original_code)}
    fix_secrets = find_secrets(fix.fixed_code)
    leaked = [s for s in fix_secrets if s.masked in original_secrets]
    if leaked:
        reasons.append(
            f"Fix appears to reproduce {len(leaked)} secret(s) from the original code verbatim."
        )
        return OutputGuardResult(allowed=False, reasons=reasons)

    return OutputGuardResult(allowed=True, reasons=reasons)
