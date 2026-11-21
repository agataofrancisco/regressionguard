"""Metricas agregadas de uma run. Funcoes puras sobre os `CaseRecord`s."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable

import numpy as np

from regressionguard.runner.records import CaseRecord, RunSummary

FAILED_THRESHOLD = 0.5  # um caso "passa" num comparativo se a taxa de sucesso for >= 0.5


def percentile(values: Iterable[float], q: float) -> float | None:
    data = [float(v) for v in values]
    if not data:
        return None
    return round(float(np.percentile(np.asarray(data), q, method="linear")), 6)


def _mean(values: list[float]) -> float:
    return round(sum(values) / len(values), 6) if values else 0.0


def summarize(cases: list[CaseRecord], cost_usd: float) -> RunSummary:
    by_category: dict[str, list[float]] = defaultdict(list)
    by_severity: dict[str, list[float]] = defaultdict(list)
    for case in cases:
        by_category[case.category].append(case.pass_rate)
        by_severity[case.severity].append(case.pass_rate)

    latencies = [latency for case in cases for latency in case.latencies_ms]
    critical = by_severity.get("critical", [])
    security_failures = sum(
        1
        for case in cases
        if any(e.security and e.pass_rate < FAILED_THRESHOLD for e in case.evaluators)
    )
    return RunSummary(
        total_cases=len(cases),
        pass_rate=_mean([case.pass_rate for case in cases]),
        critical_pass_rate=_mean(critical) if critical else None,
        pass_rate_by_category={k: _mean(v) for k, v in sorted(by_category.items())},
        pass_rate_by_severity={k: _mean(v) for k, v in sorted(by_severity.items())},
        latency_p50_ms=percentile(latencies, 50),
        latency_p95_ms=percentile(latencies, 95),
        cost_usd=round(cost_usd, 8),
        cost_per_case_usd=round(cost_usd / len(cases), 8) if cases else None,
        abstention_rate=_mean([case.abstained_rate for case in cases]),
        error_rate=_mean([case.error_rate for case in cases]),
        security_failures=security_failures,
        flaky_cases=sum(1 for case in cases if case.flaky),
    )
