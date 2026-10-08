"""Phase 7 unit tests: verification steps.

syntax/lint/security run real Ruff/Bandit (same approach as Phase 2 --
these tools ARE the thing being tested). diff is pure Python. behavior
exercises both the disabled-by-default path (no subprocess) and the
enabled path (real subprocess, real pytest) explicitly.
"""

from __future__ import annotations

from verification.diff import build_diff
from verification.lint import verify_lint
from verification.security import verify_security
from verification.syntax import verify_syntax
from verification.tests import verify_behavior


# ── syntax ───────────────────────────────────────────────────────────
def test_verify_syntax_passes_on_valid_code():
    result = verify_syntax("def f():\n    return 1\n")
    assert result.passed is True


def test_verify_syntax_fails_on_invalid_code():
    result = verify_syntax("def f(:\n    return 1\n")
    assert result.passed is False


# ── lint ─────────────────────────────────────────────────────────────
def test_verify_lint_passes_when_no_new_bugs():
    result = verify_lint("def f():\n    return 1\n")
    assert result.passed is True


def test_verify_lint_fails_on_new_undefined_name():
    result = verify_lint("def f():\n    return undefined_variable\n")
    assert result.passed is False


# ── security ─────────────────────────────────────────────────────────
def test_verify_security_passes_on_clean_code():
    result = verify_security("def f():\n    return 1\n")
    assert result.passed is True


def test_verify_security_fails_on_new_eval():
    result = verify_security("def f(x):\n    return eval(x)\n")
    assert result.passed is False


def test_verify_security_ignores_preexisting_findings():
    """A fix shouldn't be penalized for a security issue that was
    already present and the fix didn't introduce or touch."""
    code = "def f(x):\n    return eval(x)\n"
    # Pretend the "eval" finding's title was already known before the fix.
    original_titles = {f.title for f in __import__("analyzers.tools.bandit_runner", fromlist=["run_bandit"]).run_bandit(code)}
    result = verify_security(code, original_finding_titles=original_titles)
    assert result.passed is True


# ── diff ─────────────────────────────────────────────────────────────
def test_build_diff_reports_added_and_removed_lines():
    original = "a = 1\nb = 2\n"
    proposed = "a = 1\nb = 3\nc = 4\n"
    stats = build_diff(original, proposed)

    assert stats.lines_removed == 1
    assert stats.lines_added == 2
    assert "+c = 4" in stats.unified_diff


def test_build_diff_on_identical_code():
    stats = build_diff("a = 1\n", "a = 1\n")
    assert stats.lines_added == 0
    assert stats.lines_removed == 0


# ── behavior (tests.py) ──────────────────────────────────────────────
def test_behavior_without_tests_reports_unverified():
    result = verify_behavior("def f(): return 1", test_code=None, allow_execution=True)
    assert result.passed is False
    assert "no tests were provided" in result.detail


def test_behavior_disabled_by_default_reports_why():
    result = verify_behavior(
        "def f(): return 1",
        test_code="def test_f(): assert True",
        allow_execution=False,
    )
    assert result.passed is False
    assert "disabled" in result.detail


def test_behavior_execution_runs_real_pytest_and_passes():
    fixed_code = "def add(a, b):\n    return a + b\n"
    test_code = "from solution import add\n\ndef test_add():\n    assert add(2, 3) == 5\n"

    result = verify_behavior(fixed_code, test_code, allow_execution=True)
    assert result.passed is True


def test_behavior_execution_catches_a_real_regression():
    """This is the exact example from the master prompt: a syntactically
    valid fix that silently changes `+` to `*` must fail behavior
    verification even though syntax/lint/security all pass it."""
    regressed_code = "def add(a, b):\n    return a * b\n"
    test_code = "from solution import add\n\ndef test_add():\n    assert add(2, 3) == 5\n"

    result = verify_behavior(regressed_code, test_code, allow_execution=True)
    assert result.passed is False
