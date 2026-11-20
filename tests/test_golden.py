from pathlib import Path

from regressionguard.datasets import load_dataset
from regressionguard.datasets.stats import summarize
from regressionguard.evaluators import names as evaluator_names
from regressionguard.runner.suites import default_dataset_paths

ROOT = Path(__file__).resolve().parents[1]


def _all_datasets():
    return [load_dataset(path) for path in default_dataset_paths(ROOT)]


def test_golden_set_has_more_than_80_labelled_cases():
    summary = summarize(_all_datasets())
    assert summary["total"] > 80
    assert set(summary["by_target"]) == {"extraction", "minirag"}
    assert summary["by_severity"]["critical"] > 0


def test_security_categories_are_covered():
    categories = summarize(_all_datasets())["by_category"]
    assert "minirag/security_write" in categories
    assert "minirag/security_read" in categories
    assert "extraction/injection" in categories


def test_every_declared_evaluator_is_registered_and_case_ids_are_unique():
    known = set(evaluator_names())
    seen_ids: set[str] = set()
    for dataset in _all_datasets():
        for case in dataset.cases:
            assert set(case.evaluators) <= known, case.id
            assert case.id not in seen_ids, case.id
            seen_ids.add(case.id)


def test_datasets_declare_their_target_consistently():
    for dataset in _all_datasets():
        expected = dataset.manifest.target
        assert expected in {"extraction", "minirag"}
        assert dataset.manifest.version
