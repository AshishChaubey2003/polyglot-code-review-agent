"""Syntax verification step -- thin wrapper over the Phase 2 AST validator
so verification/* has one consistent VerificationStepResult interface."""

from __future__ import annotations

from analyzers.tools.ast_validator import validate_syntax
from models.fix import VerificationStepResult


def verify_syntax(code: str) -> VerificationStepResult:
    findings = validate_syntax(code)
    if findings:
        return VerificationStepResult(name="syntax", passed=False, detail=findings[0].description)
    return VerificationStepResult(name="syntax", passed=True, detail="Parses cleanly.")
