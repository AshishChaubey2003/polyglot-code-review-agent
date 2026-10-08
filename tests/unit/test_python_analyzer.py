"""
Phase 2 integration-ish unit tests: PythonAnalyzer end-to-end.

Confirms the "stop at the first broken gate" behavior: a syntax error
skips Ruff and Bandit entirely rather than running them on code already
known to be broken.
"""

from __future__ import annotations

from analyzers.python_analyzer import PythonAnalyzer


def test_clean_code_produces_no_findings(load_fixture):
    analyzer = PythonAnalyzer()
    findings = analyzer.analyze(load_fixture("clean_code.py"))
    assert findings == []


def test_syntax_error_short_circuits_before_ruff_and_bandit(load_fixture):
    analyzer = PythonAnalyzer()
    findings = analyzer.analyze(load_fixture("syntax_error.py"))

    assert len(findings) == 1
    assert findings[0].source == "ast"
    assert findings[0].severity == "critical"


def test_security_issue_surfaces_through_the_full_analyzer(load_fixture):
    analyzer = PythonAnalyzer()
    findings = analyzer.analyze(load_fixture("hardcoded_password.py"))

    assert any(f.source == "bandit" and f.category == "security" for f in findings)


def test_analyzer_declares_its_language():
    assert PythonAnalyzer().language == "python"
