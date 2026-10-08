"""Phase 2 unit tests: the shared Finding schema."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from models.finding import Finding


def test_valid_finding_constructs():
    finding = Finding(
        category="security",
        severity="high",
        title="Hardcoded password",
        description="A password literal was found in source.",
        line=5,
        evidence='password = "SuperSecret123!"',
        recommendation="Load the password from an environment variable.",
        source="bandit",
    )
    assert finding.line == 5
    assert finding.source == "bandit"


def test_invalid_category_is_rejected():
    with pytest.raises(ValidationError):
        Finding(
            category="not-a-real-category",
            severity="high",
            title="x",
            description="x",
            evidence="x",
            recommendation="x",
            source="bandit",
        )


def test_invalid_severity_is_rejected():
    with pytest.raises(ValidationError):
        Finding(
            category="bug",
            severity="super-critical",
            title="x",
            description="x",
            evidence="x",
            recommendation="x",
            source="ast",
        )


def test_line_is_optional():
    finding = Finding(
        category="quality",
        severity="low",
        title="x",
        description="x",
        evidence="x",
        recommendation="x",
        source="ruff",
    )
    assert finding.line is None


def test_finding_is_frozen():
    finding = Finding(
        category="bug", severity="low", title="x", description="x",
        evidence="x", recommendation="x", source="ast",
    )
    with pytest.raises(ValidationError):
        finding.severity = "critical"
