"""
Phase 2 unit tests: the Ruff wrapper.

These run the REAL `ruff` CLI against the fixture files -- not a mock --
because the whole point of this layer is deterministic, non-LLM ground
truth, and a mocked subprocess call wouldn't prove the integration
actually works. `ruff` must be installed (it's in requirements.txt).
"""

from __future__ import annotations

from analyzers.tools.ruff_runner import run_ruff


def test_clean_code_has_no_ruff_findings(load_fixture):
    code = load_fixture("clean_code.py")
    findings = run_ruff(code)
    assert findings == []


def test_unused_import_is_flagged(load_fixture):
    code = load_fixture("unused_import.py")
    findings = run_ruff(code)

    codes = [f.title.split(":")[0] for f in findings]
    assert "F401" in codes
    assert all(f.source == "ruff" for f in findings)


def test_undefined_name_is_flagged_as_a_bug(load_fixture):
    code = load_fixture("undefined_name.py")
    findings = run_ruff(code)

    f821 = [f for f in findings if f.title.startswith("F821")]
    assert len(f821) == 1
    assert f821[0].category == "bug"
    assert f821[0].severity == "high"
