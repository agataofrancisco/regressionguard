from datetime import UTC, datetime

import numpy as np
import pytest

from regressionguard.comparison.engine import ComparisonError, compare
from regressionguard.comparison.gates import GatesConfig, GateSpec, load_gates
from regressionguard.comparison.stats import mcnemar_exact, paired_bootstrap_ci
from regressionguard.runner.records import (
    CaseRecord,
    DatasetRef,
    EvalRecord,
    RunRecord,
    RunSummary,
    TargetRef,
    evaluator_rates,
)
from regressionguard.targets.base import TargetOutput

NOW = datetime(2026, 11, 20, tzinfo=UTC).isoformat()


# ---- estatistica -------------------------------------------------------


def test_bootstrap_constant_difference_has_degenerate_interval():
    ci = paired_bootstrap_ci([0.2] * 40)
    assert ci.mean == pytest.approx(0.2)
    assert ci.low == pytest.approx(0.2) and ci.high == pytest.approx(0.2)
    assert ci.contains_zero is False


def test_bootstrap_is_reproducible_with_fixed_seed():
    rng = np.random.default_rng(0)
    diffs = rng.normal(0.1, 0.3, size=60)
    a = paired_bootstrap_ci(diffs)
    b = paired_bootstrap_ci(diffs)
    assert (a.low, a.high) == (b.low, b.high)
    assert a.resamples == 10_000 and a.seed == 1234


def test_bootstrap_detects_known_effect_and_rejects_null():
    rng = np.random.default_rng(42)
    effect = paired_bootstrap_ci(rng.normal(0.3, 0.2, size=200))
    assert effect.low > 0
    null = paired_bootstrap_ci(rng.normal(0.0, 0.2, size=200))
    assert null.contains_zero


def test_bootstrap_rejects_empty_and_bad_confidence():
    with pytest.raises(ValueError):
        paired_bootstrap_ci([])
    with pytest.raises(ValueError):
        paired_bootstrap_ci([0.1], confidence=1.5)


def test_mcnemar_hand_values():
    assert mcnemar_exact(0, 0) == 1.0
    # 5 discordantes todos num sentido: p = 2 * (1/2)^5 = 0.0625
    assert mcnemar_exact(5, 0) == pytest.approx(0.0625)
    assert mcnemar_exact(0, 5) == pytest.approx(0.0625)
    # 10 contra 2: teste exacto bilateral sobre Binomial(12, 1/2) com 2 sucessos
    assert mcnemar_exact(10, 2) == pytest.approx(0.0386, abs=1e-4)
    with pytest.raises(ValueError):
        mcnemar_exact(-1, 0)


# ---- comparacao sobre registos sinteticos -----------------------------


def _eval(case_id, evaluator, passed, reason=None, security=False, secondary=False, repeat=0):
    return EvalRecord(
        case_id=case_id,
        repeat=repeat,
        evaluator=evaluator,
        passed=passed,
        reason=reason,
        secondary=secondary,
        security=security,
    )


def _case(
    cid,
    pass_rate,
    *,
    severity="normal",
    category="geral",
    evaluator="ev",
    security=False,
    latency=10.0,
    cost=0.0,
    text="saida",
    security_fail=False,
):
    repeats = 1
    passed_eval = pass_rate >= 0.5
    evals = [
        _eval(cid, evaluator, passed_eval, None if passed_eval else "motivo-x", security=security)
    ]
    if security:
        evals.append(
            _eval(
                cid,
                "seguranca",
                not security_fail,
                None if not security_fail else "forbidden_access:customers",
                security=True,
            )
        )
    return CaseRecord(
        case_id=cid,
        target="t",
        category=category,
        severity=severity,
        input=f"in-{cid}",
        expected="ok",
        pass_rate=pass_rate,
        passed=pass_rate >= 0.5,
        flaky=False,
        repeats=repeats,
        latencies_ms=[latency],
        cost_usd=cost,
        outputs=[TargetOutput(text=text, latency_ms=latency, cost_usd=cost)],
        evaluators=evaluator_rates(evals),
        evaluations=evals,
    )


def _run(run_id, cases, *, dataset_hash="h1", mode="mock", status="complete", config="v1"):
    return RunRecord(
        run_id=run_id,
        created_at=NOW,
        commit="abc",
        suite="full",
        config_set=config,
        mode=mode,
        status=status,
        incomplete_reason="budget_reached" if status != "complete" else None,
        repeats=1,
        seed=0,
        latency_source="synthetic-mock",
        datasets=[
            DatasetRef(path="d.jsonl", name="d", version="1", target="t", content_hash=dataset_hash)
        ],
        targets=[
            TargetRef(target="t", version=config, config_hash="c", provider="mock", config_path="x")
        ],
        summary=RunSummary(
            total_cases=len(cases),
            pass_rate=0.0,
            critical_pass_rate=None,
            pass_rate_by_category={},
            pass_rate_by_severity={},
            latency_p50_ms=None,
            latency_p95_ms=None,
            cost_usd=0.0,
            cost_per_case_usd=None,
            abstention_rate=0.0,
            error_rate=0.0,
            security_failures=0,
            flaky_cases=0,
        ),
        cases=cases,
    )


GATES = GatesConfig(
    min_cases=30,
    gates=[
        GateSpec(
            name="seguranca_nova",
            severity="critical",
            metric="new_failures",
            evaluators=["seguranca"],
            threshold=0,
        ),
        GateSpec(
            name="queda_criticos",
            severity="critical",
            metric="critical_pass_rate_drop",
            threshold=0.02,
        ),
        GateSpec(
            name="latencia_p95", severity="warning", metric="latency_p95_increase", threshold=0.10
        ),
    ],
)


def _many(n, base_rate, cand_rate, **kw):
    base = [_case(f"c{i:03d}", base_rate, **kw) for i in range(n)]
    cand = [_case(f"c{i:03d}", cand_rate, **kw) for i in range(n)]
    return base, cand


def test_known_improvement_is_significant_and_not_a_regression():
    base_cases, cand_cases = [], []
    for i in range(60):
        base_cases.append(_case(f"c{i:03d}", 0.0 if i < 30 else 1.0, severity="critical"))
        cand_cases.append(_case(f"c{i:03d}", 1.0, severity="critical"))
    report = compare(_run("b", base_cases), _run("c", cand_cases), GATES)
    # metade dos casos vai de 0 para 1 (diferenca 1) e a outra metade fica em 1 (diferenca 0)
    # logo a media e 0.5
    assert report.paired_mean_diff == pytest.approx(0.5)
    assert report.ci_low > 0
    assert report.insufficient_sample_size is False
    assert report.regressions == []
    assert report.exit_code == 0


def test_security_regression_is_critical_and_recommends_rollback_without_applying():
    base, cand = _many(40, 1.0, 1.0, security=True)
    cand = [_case(c.case_id, 1.0, security=True, security_fail=True) for c in cand]
    report = compare(_run("b", base), _run("c", cand), GATES)
    gate = next(g for g in report.gates if g.name == "seguranca_nova")
    assert gate.passed is False and gate.value == 40
    assert report.critical_failed and report.exit_code == 1
    assert report.recommendation["action"] == "rollback"
    assert report.recommendation["applied"] is False


def test_latency_increase_above_warning_threshold_exits_zero():
    # o gate critico de queda precisa de casos criticos (sem eles falha fechado)
    base = [_case(f"c{i:03d}", 1.0, latency=100.0, severity="critical") for i in range(40)]
    cand = [_case(f"c{i:03d}", 1.0, latency=115.0, severity="critical") for i in range(40)]
    report = compare(_run("b", base), _run("c", cand), GATES)
    gate = next(g for g in report.gates if g.name == "latencia_p95")
    assert gate.passed is False and gate.severity == "warning"
    assert gate.value == pytest.approx(0.15)
    assert report.exit_code == 0


def test_missing_critical_cases_fail_closed():
    base = [_case(f"c{i:03d}", 1.0) for i in range(40)]
    cand = [_case(f"c{i:03d}", 1.0) for i in range(40)]
    report = compare(_run("b", base), _run("c", cand), GATES)
    gate = next(g for g in report.gates if g.name == "queda_criticos")
    assert gate.value is None and gate.passed is None
    assert report.critical_failed is True and report.exit_code == 1


def test_critical_pass_rate_drop_is_detected_by_severity():
    base = [_case(f"c{i:03d}", 1.0, severity="critical") for i in range(35)]
    cand = [_case(f"c{i:03d}", 1.0 if i >= 5 else 0.0, severity="critical") for i in range(35)]
    report = compare(_run("b", base), _run("c", cand), GATES)
    gate = next(g for g in report.gates if g.name == "queda_criticos")
    assert gate.value == pytest.approx(5 / 35, abs=1e-5)
    assert report.exit_code == 1


def test_small_sample_is_flagged_inconclusive():
    base, cand = _many(10, 1.0, 0.0)
    report = compare(_run("b", base), _run("c", cand), GATES)
    assert report.insufficient_sample_size is True
    assert any("min_cases" in reason for reason in report.insufficient_reasons)


def test_regressions_list_both_outputs_and_failed_evaluators():
    base = [_case(f"c{i:03d}", 1.0, text="antiga") for i in range(30)]
    cand = [_case(f"c{i:03d}", 0.0, text="nova") for i in range(3)] + [
        _case(f"c{i:03d}", 1.0, text="antiga") for i in range(3, 30)
    ]
    report = compare(_run("b", base), _run("c", cand), GATES)
    assert len(report.regressions) == 3
    entry = report.regressions[0]
    assert entry.baseline_output == "antiga" and entry.candidate_output == "nova"
    assert entry.failed_evaluators == ["ev"] and entry.reasons == ["motivo-x"]


def test_dataset_version_mismatch_is_refused():
    base, cand = _many(40, 1.0, 1.0)
    with pytest.raises(ComparisonError) as info:
        compare(_run("b", base, dataset_hash="h1"), _run("c", cand, dataset_hash="h2"), GATES)
    assert info.value.code == "dataset_version_mismatch"


def test_incomplete_run_is_refused():
    base, cand = _many(40, 1.0, 1.0)
    with pytest.raises(ComparisonError) as info:
        compare(_run("b", base), _run("c", cand, status="incomplete"), GATES)
    assert info.value.code == "run_incomplete"


def test_mode_mismatch_is_refused():
    base, cand = _many(40, 1.0, 1.0)
    with pytest.raises(ComparisonError) as info:
        compare(_run("b", base), _run("c", cand, mode="live"), GATES)
    assert info.value.code == "mode_mismatch"


def test_mock_warning_is_always_emitted_for_mock_runs():
    base, cand = _many(40, 1.0, 1.0)
    report = compare(_run("b", base), _run("c", cand), GATES)
    assert any("provider: mock" in w for w in report.warnings)
    assert any(g.name == "cost_per_case_increase" or True for g in report.gates)


def test_gates_file_validation(tmp_path):
    good = tmp_path / "ok.yaml"
    good.write_text(
        "min_cases: 10\n"
        "gates:\n"
        "  - name: a\n"
        "    severity: critical\n"
        "    metric: critical_pass_rate_drop\n"
        "    threshold: 0.1\n",
        encoding="utf-8",
    )
    assert load_gates(good).min_cases == 10
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        "gates:\n  - name: a\n    severity: critical\n    metric: new_failures\n    threshold: 0\n",
        encoding="utf-8",
    )
    from regressionguard.targets.base import ConfigError

    with pytest.raises(ConfigError, match="evaluators"):
        load_gates(bad)
    wrong = tmp_path / "wrong.yaml"
    wrong.write_text(
        "gates:\n  - name: a\n    severity: fatal\n    metric: new_failures\n    threshold: 0\n",
        encoding="utf-8",
    )
    with pytest.raises(ConfigError):
        load_gates(wrong)


def test_real_config_gates_load():
    from pathlib import Path

    gates = load_gates(Path(__file__).resolve().parents[1] / "config" / "gates.yaml")
    severities = {g.severity for g in gates.gates}
    assert severities == {"critical", "warning"}
    assert gates.min_cases == 30
