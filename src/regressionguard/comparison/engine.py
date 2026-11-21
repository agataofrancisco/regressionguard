"""Comparacao emparelhada baseline vs candidato, gates e recomendacao (sem rollback automatico).

Ordem das verificacoes: mesmos datasets -> mesmo modo -> runs completas -> casos comuns.
Qualquer falha antes da estatistica levanta `ComparisonError` com um codigo estavel.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Literal

from pydantic import BaseModel, Field

from regressionguard.comparison.gates import GatesConfig, GateSpec
from regressionguard.comparison.stats import mcnemar_exact, paired_bootstrap_ci
from regressionguard.runner.records import CaseRecord, RunRecord, RunSummary, TargetRef
from regressionguard.runner.summary import percentile

PASS_THRESHOLD = 0.5
METHOD = (
    "bootstrap percentilico emparelhado por caso (95%, 10000 reamostragens, seed 1234)"
    " + McNemar exacto"
)


class ComparisonError(Exception):
    """Comparacao recusada. `code` e estavel (ex.: dataset_version_mismatch)."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"[{code}] {message}")


class RegressionEntry(BaseModel):
    case_id: str
    category: str
    severity: str
    input: Any
    expected: Any
    baseline_pass_rate: float
    candidate_pass_rate: float
    baseline_output: str
    candidate_output: str
    failed_evaluators: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)


class GateResult(BaseModel):
    name: str
    severity: Literal["critical", "warning"]
    metric: str
    value: float | None
    threshold: float
    passed: bool | None  # None = nao avaliavel com os dados disponiveis
    description: str = ""
    evidence: list[str] = Field(default_factory=list)


class ComparisonReport(BaseModel):
    baseline_id: str
    candidate_id: str
    mode: str
    method: str = METHOD
    n_cases: int
    only_in_baseline: list[str]
    only_in_candidate: list[str]
    pass_rate_baseline: float
    pass_rate_candidate: float
    pass_rate_diff: float
    paired_mean_diff: float
    ci_low: float
    ci_high: float
    ci_width: float
    ci_contains_zero: bool
    mcnemar_only_baseline: int
    mcnemar_only_candidate: int
    mcnemar_p_value: float
    insufficient_sample_size: bool
    insufficient_reasons: list[str] = Field(default_factory=list)
    by_category: dict[str, dict[str, float | int]]
    regressions: list[RegressionEntry]
    gates: list[GateResult]
    critical_failed: bool
    recommendation: dict[str, Any]
    baseline_summary: RunSummary
    candidate_summary: RunSummary
    baseline_targets: list[TargetRef]
    candidate_targets: list[TargetRef]
    warnings: list[str] = Field(default_factory=list)
    exit_code: int


def _check_comparable(baseline: RunRecord, candidate: RunRecord) -> None:
    if baseline.dataset_fingerprint() != candidate.dataset_fingerprint():
        raise ComparisonError(
            "dataset_version_mismatch",
            "as runs usam versoes diferentes dos datasets; recria o baseline com a versao actual",
        )
    if baseline.mode != candidate.mode:
        raise ComparisonError(
            "mode_mismatch", f"baseline em {baseline.mode} e candidato em {candidate.mode}"
        )
    for run in (baseline, candidate):
        if run.status != "complete":
            raise ComparisonError(
                "run_incomplete", f"a run {run.run_id} esta incompleta ({run.incomplete_reason})"
            )


def _mean(values: list[float]) -> float:
    return round(sum(values) / len(values), 6) if values else 0.0


def _evaluator_rate(case: CaseRecord, name: str) -> float | None:
    for rate in case.evaluators:
        if rate.evaluator == name:
            return rate.pass_rate
    return None


def _new_failures(
    common: list[str],
    base: dict[str, CaseRecord],
    cand: dict[str, CaseRecord],
    evaluators: list[str],
) -> tuple[int, list[str]]:
    """Casos em que algum avaliador listado passava no baseline e falha no candidato."""
    count = 0
    evidence: list[str] = []
    for cid in common:
        for name in evaluators:
            before, after = _evaluator_rate(base[cid], name), _evaluator_rate(cand[cid], name)
            if before is None or after is None:
                continue
            if before >= PASS_THRESHOLD and after < PASS_THRESHOLD:
                count += 1
                match = next((r for r in cand[cid].evaluators if r.evaluator == name), None)
                reason = match.reasons[0] if match and match.reasons else ""
                evidence.append(f"{cid}: {name}" + (f" ({reason})" if reason else ""))
                break
    return count, evidence[:20]


def _evaluate_gate(
    spec: GateSpec,
    values: dict[str, Any],
) -> GateResult:
    """Avalia um gate. `values` tem as metricas ja calculadas (ver compare)."""
    if spec.metric == "new_failures":
        value: float | None = float(values["new_failures"][spec.name])
        evidence = values["new_failures_evidence"][spec.name]
    else:
        value = values.get(spec.metric)
        evidence = []
    if value is None:
        passed: bool | None = None
    else:
        passed = value <= spec.threshold
    return GateResult(
        name=spec.name,
        severity=spec.severity,
        metric=spec.metric,
        value=None if value is None else round(float(value), 6),
        threshold=spec.threshold,
        passed=passed,
        description=spec.description,
        evidence=evidence,
    )


def compare(
    baseline: RunRecord,
    candidate: RunRecord,
    gates: GatesConfig | None = None,
) -> ComparisonReport:
    """Compara duas runs. Nunca executa rollback: apenas recomenda."""
    _check_comparable(baseline, candidate)
    gates = gates or GatesConfig()
    base = {c.case_id: c for c in baseline.cases}
    cand = {c.case_id: c for c in candidate.cases}
    common = sorted(set(base) & set(cand))
    if not common:
        raise ComparisonError("no_common_cases", "as runs nao tem casos em comum")
    only_base = sorted(set(base) - set(cand))
    only_cand = sorted(set(cand) - set(base))

    diffs = [cand[cid].pass_rate - base[cid].pass_rate for cid in common]
    ci = paired_bootstrap_ci(diffs)
    base_pass = [base[cid].pass_rate >= PASS_THRESHOLD for cid in common]
    cand_pass = [cand[cid].pass_rate >= PASS_THRESHOLD for cid in common]
    only_b = sum(1 for bp, cp in zip(base_pass, cand_pass, strict=True) if bp and not cp)
    only_c = sum(1 for bp, cp in zip(base_pass, cand_pass, strict=True) if cp and not bp)
    p_value = mcnemar_exact(only_b, only_c)

    reasons: list[str] = []
    if len(common) < gates.min_cases:
        reasons.append(f"{len(common)} casos < min_cases={gates.min_cases}")
    if ci.contains_zero and ci.width > gates.max_ci_width:
        reasons.append(f"IC 95% inclui zero e tem largura {ci.width:.3f} > {gates.max_ci_width}")

    by_cat: dict[str, list[str]] = defaultdict(list)
    for cid in common:
        by_cat[base[cid].category].append(cid)
    by_category = {
        category: {
            "n": len(ids),
            "baseline": _mean([base[i].pass_rate for i in ids]),
            "candidate": _mean([cand[i].pass_rate for i in ids]),
            "diff": round(
                _mean([cand[i].pass_rate for i in ids]) - _mean([base[i].pass_rate for i in ids]), 6
            ),
        }
        for category, ids in sorted(by_cat.items())
    }

    regressions = []
    for cid in common:
        if base[cid].pass_rate >= PASS_THRESHOLD and cand[cid].pass_rate < PASS_THRESHOLD:
            failed = [r for r in cand[cid].evaluations if not r.passed and not r.secondary]
            regressions.append(
                RegressionEntry(
                    case_id=cid,
                    category=cand[cid].category,
                    severity=cand[cid].severity,
                    input=cand[cid].input,
                    expected=cand[cid].expected,
                    baseline_pass_rate=base[cid].pass_rate,
                    candidate_pass_rate=cand[cid].pass_rate,
                    baseline_output=base[cid].outputs[0].text if base[cid].outputs else "",
                    candidate_output=cand[cid].outputs[0].text if cand[cid].outputs else "",
                    failed_evaluators=sorted({r.evaluator for r in failed}),
                    reasons=sorted({r.reason for r in failed if r.reason}),
                )
            )

    common_base = [base[i] for i in common]
    common_cand = [cand[i] for i in common]
    crit = [i for i in common if base[i].severity == "critical"]
    base_lat = [v for c in common_base for v in c.latencies_ms]
    cand_lat = [v for c in common_cand for v in c.latencies_ms]
    base_p95, cand_p95 = percentile(base_lat, 95), percentile(cand_lat, 95)
    base_cost = sum(c.cost_usd for c in common_base)
    cand_cost = sum(c.cost_usd for c in common_cand)

    new_fail: dict[str, int] = {}
    new_fail_evidence: dict[str, list[str]] = {}
    for spec in gates.gates:
        if spec.metric == "new_failures":
            new_fail[spec.name], new_fail_evidence[spec.name] = _new_failures(
                common, base, cand, spec.evaluators
            )

    values: dict[str, Any] = {
        "new_failures": new_fail,
        "new_failures_evidence": new_fail_evidence,
        "critical_pass_rate_drop": (
            round(
                _mean([base[i].pass_rate for i in crit]) - _mean([cand[i].pass_rate for i in crit]),
                6,
            )
            if crit
            else None
        ),
        "pass_rate_drop": round(
            _mean([c.pass_rate for c in common_base]) - _mean([c.pass_rate for c in common_cand]), 6
        ),
        "latency_p95_increase": (
            round(cand_p95 / base_p95 - 1.0, 6) if base_p95 and cand_p95 is not None else None
        ),
        "cost_per_case_increase": (
            round((cand_cost / base_cost) - 1.0, 6) if base_cost > 0 else None
        ),
    }
    gate_results = [_evaluate_gate(spec, values) for spec in gates.gates]
    critical_failed = any(g.severity == "critical" and g.passed is not True for g in gate_results)
    failed_names = [g.name for g in gate_results if g.passed is not True]

    recommendation: dict[str, Any]
    if critical_failed:
        recommendation = {
            "action": "rollback",
            "applied": False,
            "reason": [
                g.name for g in gate_results if g.severity == "critical" and g.passed is not True
            ],
            "rollback_to": {
                "run_id": baseline.run_id,
                "config_set": baseline.config_set,
                "targets": [t.model_dump() for t in baseline.targets],
            },
            "message": "recomendacao apenas: nenhum rollback foi executado",
        }
    else:
        recommendation = {"action": "none", "applied": False, "failed_gates": failed_names}

    warnings: list[str] = []
    if baseline.mode == "mock":
        warnings.append(
            "provider: mock. As saidas sao deterministas: nao ha variacao entre repeticoes, "
            "a latencia e sintetica e o custo e zero. Estes numeros nao medem um modelo real."
        )
    if reasons:
        warnings.append("comparacao nao conclusiva: " + "; ".join(reasons))
    if values["cost_per_case_increase"] is None:
        warnings.append("gate de custo nao avaliavel: custo do baseline e zero")

    return ComparisonReport(
        baseline_id=baseline.run_id,
        candidate_id=candidate.run_id,
        mode=baseline.mode,
        n_cases=len(common),
        only_in_baseline=only_base,
        only_in_candidate=only_cand,
        pass_rate_baseline=_mean([c.pass_rate for c in common_base]),
        pass_rate_candidate=_mean([c.pass_rate for c in common_cand]),
        pass_rate_diff=round(
            _mean([c.pass_rate for c in common_cand]) - _mean([c.pass_rate for c in common_base]), 6
        ),
        paired_mean_diff=ci.mean,
        ci_low=ci.low,
        ci_high=ci.high,
        ci_width=round(ci.width, 6),
        ci_contains_zero=ci.contains_zero,
        mcnemar_only_baseline=only_b,
        mcnemar_only_candidate=only_c,
        mcnemar_p_value=round(p_value, 6),
        insufficient_sample_size=bool(reasons),
        insufficient_reasons=reasons,
        by_category=by_category,
        regressions=regressions,
        gates=gate_results,
        critical_failed=critical_failed,
        recommendation=recommendation,
        baseline_summary=baseline.summary,
        candidate_summary=candidate.summary,
        baseline_targets=baseline.targets,
        candidate_targets=candidate.targets,
        warnings=warnings,
        exit_code=1 if critical_failed else 0,
    )
