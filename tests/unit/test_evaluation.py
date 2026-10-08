from __future__ import annotations

from evaluation.benchmarks import run_benchmark
from evaluation.dataset import load_dataset
from evaluation.metrics import evaluate_static_analyzer
from tests.fakes.fake_embeddings import FakeEmbeddings


def test_dataset_loads_all_labeled_examples():
    examples = load_dataset()
    assert len(examples) == 6
    assert any(e.expected_clean for e in examples)


def test_metrics_report_has_a_caveat_naming_the_sample_size():
    report = evaluate_static_analyzer()
    assert report.sample_size == 6
    assert "6-example" in report.caveat
    assert 0.0 <= report.precision <= 1.0
    assert 0.0 <= report.recall <= 1.0


def test_metrics_report_recalls_known_security_findings():
    # the real Bandit/AST analyzer should catch the hand-labeled
    # security issues in this tiny dataset -- recall should not be zero
    report = evaluate_static_analyzer()
    assert report.recall > 0.0


def test_benchmark_runs_all_three_strategies():
    results = run_benchmark(FakeEmbeddings())
    names = {r.name for r in results}
    assert names == {"vector_only", "hybrid_rrf", "hybrid_rrf_rerank"}
    for r in results:
        assert 0.0 <= r.hit_rate <= 1.0
        assert r.total == 5
