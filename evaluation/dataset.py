"""
A small labeled evaluation dataset, built from the same real fixture
files used by the analyzer unit tests (tests/fixtures/*.py), each
paired with the finding categories/titles a correct review is expected
to surface.

Six examples is NOT enough to claim statistically significant
precision/recall -- evaluation/metrics.py and benchmarks.py say this
explicitly every time they report a number. This dataset exists to
make retrieval/analyzer regressions visible during development, not to
produce a publishable benchmark.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "tests" / "fixtures"


@dataclass
class LabeledExample:
    name: str
    code: str
    expected_categories: set[str]  # at least one finding in each of these categories is expected
    expected_clean: bool = False  # True means "no findings at all" is the correct outcome


_LABELS: dict[str, dict] = {
    "clean_code.py": {"expected_categories": set(), "expected_clean": True},
    "syntax_error.py": {"expected_categories": {"bug"}},
    "undefined_name.py": {"expected_categories": {"bug"}},
    "unused_import.py": {"expected_categories": {"quality"}},
    "hardcoded_password.py": {"expected_categories": {"security"}},
    "eval_usage.py": {"expected_categories": {"security"}},
}


def load_dataset() -> list[LabeledExample]:
    examples = []
    for filename, label in _LABELS.items():
        path = FIXTURES_DIR / filename
        examples.append(
            LabeledExample(
                name=filename,
                code=path.read_text(encoding="utf-8"),
                expected_categories=label["expected_categories"],
                expected_clean=label.get("expected_clean", False),
            )
        )
    return examples
