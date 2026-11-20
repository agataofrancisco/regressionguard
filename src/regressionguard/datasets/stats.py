"""Contagens de casos por alvo, categoria e severidade (para `ai-eval datasets stats`)."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable

from regressionguard.datasets.models import Dataset


def summarize(datasets: Iterable[Dataset]) -> dict[str, object]:
    """Resume um conjunto de datasets validados."""
    by_target: Counter[str] = Counter()
    by_category: Counter[str] = Counter()
    by_severity: Counter[str] = Counter()
    total = 0
    for dataset in datasets:
        for case in dataset.cases:
            total += 1
            by_target[dataset.manifest.target] += 1
            by_category[f"{dataset.manifest.target}/{case.category}"] += 1
            by_severity[case.severity] += 1
    return {
        "total": total,
        "by_target": dict(sorted(by_target.items())),
        "by_category": dict(sorted(by_category.items())),
        "by_severity": dict(sorted(by_severity.items())),
    }
