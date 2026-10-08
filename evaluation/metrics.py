"""
Precision/recall/F1/false-positive-rate against the real static
analyzers (PythonAnalyzer -- AST + Ruff + Bandit, no mocks), computed
at the category level: did the analyzer surface at least one finding
in each category the example expects, and did it avoid surfacing a
category it shouldn't have?

Six examples is a sanity-check dataset, not a statistically meaningful
sample -- every function here that returns a rate says so in its
result, and `benchmarks.py` repeats the caveat in its own report.
"""

from __future__ import annotations

from dataclasses import dataclass

from analyzers.python_analyzer import PythonAnalyzer
from evaluation.dataset import LabeledExample, load_dataset

_ANALYZER = PythonAnalyzer()
_ALL_CATEGORIES = {"bug", "security", "quality"}


@dataclass
class MetricsReport:
    precision: float
    recall: float
    f1: float
    false_positive_rate: float
    sample_size: int
    caveat: str = (
        "Computed over a {n}-example hand-built dataset -- too small for "
        "a statistically significant estimate. Treat these numbers as a "
        "regression smoke test, not a benchmark claim."
    )

    def __post_init__(self):
        self.caveat = self.caveat.format(n=self.sample_size)


def _categories_found(example: LabeledExample) -> set[str]:
    findings = _ANALYZER.analyze(example.code)
    return {f.category for f in findings}


def evaluate_static_analyzer() -> MetricsReport:
    examples = load_dataset()

    true_positives = 0
    false_positives = 0
    false_negatives = 0

    for example in examples:
        found = _categories_found(example)
        expected = example.expected_categories

        true_positives += len(found & expected)
        false_positives += len(found - expected)
        false_negatives += len(expected - found)

    precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) else 1.0
    recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) else 1.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0

    # false positive rate: of all (example, category) pairs where the
    # category was NOT expected, how many were still flagged.
    not_expected_pairs = sum(len(_ALL_CATEGORIES - e.expected_categories) for e in examples)
    fp_rate = false_positives / not_expected_pairs if not_expected_pairs else 0.0

    return MetricsReport(
        precision=precision, recall=recall, f1=f1,
        false_positive_rate=fp_rate, sample_size=len(examples),
    )
