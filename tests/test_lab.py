"""Laboratorio: as 4 regressoes controladas tem de ser detectadas, e a baseline contra si propria
nao pode gerar gates criticos (falsos positivos). Corre com `pytest -m lab`.
"""

from datetime import UTC, datetime
from pathlib import Path

import pytest

import regressionguard as rg
from regressionguard.runner.run import RunOptions, run_suite
from regressionguard.runner.suites import load_config_set, load_suite

pytestmark = pytest.mark.lab

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 11, 20, 10, 0, tzinfo=UTC)

# regressao -> gate critico que tem de falhar
EXPECTED_GATE = {
    "no-citations": "citations_regression",
    "unauthorized-select": "security_violations_new",
    "schema-change": "schema_regression",
    "k1": "critical_pass_rate_drop",
}


@pytest.fixture(scope="module")
def gates():
    return rg.load_gates(ROOT / "config" / "gates.yaml")


@pytest.fixture(scope="module")
def runs():
    suite = load_suite(ROOT, "full")
    out = {}
    for name in ["v1", *EXPECTED_GATE]:
        out[name] = run_suite(
            RunOptions(
                suite=suite,
                config_set=load_config_set(ROOT, name),
                mode="mock",
                root=ROOT,
                now=lambda: NOW,
            )
        )
    return out


@pytest.mark.parametrize("regression", sorted(EXPECTED_GATE))
def test_each_controlled_regression_is_detected_by_its_gate(runs, gates, regression):
    report = rg.compare(runs["v1"], runs[regression], gates)
    failed = {g.name for g in report.gates if g.severity == "critical" and g.passed is not True}
    assert EXPECTED_GATE[regression] in failed, (regression, failed)
    assert report.exit_code == 1
    assert report.recommendation["applied"] is False


def test_baseline_against_itself_has_no_critical_false_positive(runs, gates):
    report = rg.compare(runs["v1"], runs["v1"], gates)
    assert report.critical_failed is False
    assert report.exit_code == 0
    assert report.regressions == []


def test_lab_summary_is_printed_for_the_case_study(runs, gates, capsys):
    rows = []
    for regression in sorted(EXPECTED_GATE):
        report = rg.compare(runs["v1"], runs[regression], gates)
        failing = [g.name for g in report.gates if g.passed is False]
        rows.append(
            f"{regression:<20} exit={report.exit_code} regressoes={len(report.regressions)} "
            f"sucesso {report.pass_rate_baseline:.3f}->{report.pass_rate_candidate:.3f} "
            f"gates={','.join(failing)}"
        )
    print("\n".join(rows))
    assert len(rows) == 4
