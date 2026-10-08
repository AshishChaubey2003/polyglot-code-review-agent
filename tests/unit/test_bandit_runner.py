"""
Phase 2 unit tests: the Bandit wrapper.

Runs the REAL `bandit` CLI against fixture files, same reasoning as the
Ruff tests -- this layer's entire purpose is ground truth a mock can't
verify.
"""

from __future__ import annotations

from analyzers.tools.bandit_runner import run_bandit


def test_clean_code_has_no_bandit_findings(load_fixture):
    code = load_fixture("clean_code.py")
    findings = run_bandit(code)
    assert findings == []


def test_hardcoded_password_is_flagged(load_fixture):
    code = load_fixture("hardcoded_password.py")
    findings = run_bandit(code)

    assert len(findings) >= 1
    assert all(f.category == "security" for f in findings)
    assert any("password" in f.description.lower() for f in findings)


def test_eval_usage_is_flagged_high_severity(load_fixture):
    code = load_fixture("eval_usage.py")
    findings = run_bandit(code)

    assert len(findings) >= 1
    assert any(f.severity in ("high", "medium") for f in findings)
    assert any("eval" in f.description.lower() for f in findings)
