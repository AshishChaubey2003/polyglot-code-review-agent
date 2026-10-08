"""
PythonAnalyzer -- the first, and so far only, LanguageAnalyzer.

AST validation runs first. If the code does not parse, Ruff and Bandit
are skipped entirely: both would otherwise either error out or report
confusing secondary findings on code that is already known broken, and
the one finding that matters -- "this doesn't parse" -- would be buried.
"""

from __future__ import annotations

from analyzers.base import LanguageAnalyzer
from analyzers.tools.ast_validator import validate_syntax
from analyzers.tools.bandit_runner import run_bandit
from analyzers.tools.ruff_runner import run_ruff
from models.finding import Finding


class PythonAnalyzer(LanguageAnalyzer):
    language = "python"

    def analyze(self, code: str) -> list[Finding]:
        syntax_findings = validate_syntax(code)
        if syntax_findings:
            return syntax_findings

        findings: list[Finding] = []
        findings.extend(run_ruff(code))
        findings.extend(run_bandit(code))
        return findings
