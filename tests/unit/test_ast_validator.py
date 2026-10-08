"""Phase 2 unit tests: AST validation and structural summary."""

from __future__ import annotations

from analyzers.tools.ast_validator import structural_summary, validate_syntax


def test_clean_code_has_no_syntax_findings(load_fixture):
    code = load_fixture("clean_code.py")
    assert validate_syntax(code) == []


def test_syntax_error_produces_one_critical_finding(load_fixture):
    code = load_fixture("syntax_error.py")
    findings = validate_syntax(code)

    assert len(findings) == 1
    assert findings[0].severity == "critical"
    assert findings[0].source == "ast"
    assert findings[0].line is not None


def test_structural_summary_counts_functions_and_classes():
    code = "class Foo:\n    def bar(self):\n        pass\n\ndef baz():\n    pass\n"
    summary = structural_summary(code)

    assert summary == {"functions": 2, "classes": 1, "parsed": True}


def test_structural_summary_on_unparseable_code_returns_unparsed(load_fixture):
    code = load_fixture("syntax_error.py")
    summary = structural_summary(code)

    assert summary["parsed"] is False
    assert summary["functions"] == 0
