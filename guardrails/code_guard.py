"""
Code guard -- confirms generated code is actually valid code in the
target language before anything downstream treats it as such.

Phase scope: Python only, reusing the AST validator already built for
static analysis rather than re-implementing parsing here.
"""

from __future__ import annotations

from dataclasses import dataclass

from analyzers.tools.ast_validator import validate_syntax


@dataclass
class CodeGuardResult:
    allowed: bool
    reason: str = ""


def check_generated_code(code: str, language: str) -> CodeGuardResult:
    if language != "python":
        return CodeGuardResult(
            allowed=False,
            reason=f"code_guard only validates Python; got language='{language}'.",
        )

    syntax_findings = validate_syntax(code)
    if syntax_findings:
        return CodeGuardResult(allowed=False, reason=syntax_findings[0].description)

    return CodeGuardResult(allowed=True)
