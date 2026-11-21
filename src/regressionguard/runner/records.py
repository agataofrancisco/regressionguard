"""Modelos do registo de uma run (a unidade que se guarda, audita e compara)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from regressionguard.targets.base import TargetOutput


class EvalRecord(BaseModel):
    """Resultado de um avaliador numa repeticao de um caso."""

    model_config = ConfigDict(extra="forbid")

    case_id: str
    repeat: int
    evaluator: str
    passed: bool
    score: float | None = None
    reason: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    secondary: bool = False
    security: bool = False


class EvaluatorRate(BaseModel):
    """Taxa de sucesso de um avaliador num caso, agregada sobre as repeticoes."""

    model_config = ConfigDict(extra="forbid")

    evaluator: str
    pass_rate: float
    secondary: bool = False
    security: bool = False
    reasons: list[str] = Field(default_factory=list)


class CaseRecord(BaseModel):
    """Resultado de um caso golden numa run."""

    model_config = ConfigDict(extra="forbid")

    case_id: str
    target: str
    category: str
    severity: Literal["critical", "normal"]
    input: Any
    expected: Any
    pass_rate: float
    passed: bool
    flaky: bool
    repeats: int
    latencies_ms: list[float] = Field(default_factory=list)
    cost_usd: float = 0.0
    abstained_rate: float = 0.0
    error_rate: float = 0.0
    trace_ids: list[str] = Field(default_factory=list)
    outputs: list[TargetOutput] = Field(default_factory=list)
    evaluators: list[EvaluatorRate] = Field(default_factory=list)
    evaluations: list[EvalRecord] = Field(default_factory=list)


class DatasetRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    name: str
    version: str
    target: str
    content_hash: str


class TargetRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target: str
    version: str
    config_hash: str
    provider: str
    config_path: str


class RunSummary(BaseModel):
    """Metricas agregadas de uma run (secao 'resumo' do relatorio)."""

    model_config = ConfigDict(extra="forbid")

    total_cases: int
    pass_rate: float
    critical_pass_rate: float | None
    pass_rate_by_category: dict[str, float]
    pass_rate_by_severity: dict[str, float]
    latency_p50_ms: float | None
    latency_p95_ms: float | None
    cost_usd: float
    cost_per_case_usd: float | None
    abstention_rate: float
    error_rate: float
    security_failures: int
    flaky_cases: int


class RunRecord(BaseModel):
    """Run completa: configuracao, datasets, resultados por caso e resumo."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    created_at: str
    commit: str
    suite: str
    config_set: str
    mode: Literal["mock", "live"]
    status: Literal["complete", "incomplete"]
    incomplete_reason: str | None = None
    tag: str | None = None
    repeats: int
    seed: int
    max_usd: float | None = None
    latency_source: str
    datasets: list[DatasetRef]
    targets: list[TargetRef]
    summary: RunSummary
    cases: list[CaseRecord]

    def dataset_fingerprint(self) -> str:
        """Identidade dos datasets usados (caminho + hash), para recusar comparacoes mistas."""
        import hashlib

        parts = sorted(f"{d.path}:{d.content_hash}" for d in self.datasets)
        return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def evaluator_rates(evaluations: list[EvalRecord]) -> list[EvaluatorRate]:
    """Taxa de sucesso por avaliador, agregada sobre as repeticoes de um caso."""
    names: list[str] = []
    for record in evaluations:
        if record.evaluator not in names:
            names.append(record.evaluator)
    rates: list[EvaluatorRate] = []
    for name in names:
        rows = [r for r in evaluations if r.evaluator == name]
        reasons = sorted({r.reason for r in rows if not r.passed and r.reason})
        rates.append(
            EvaluatorRate(
                evaluator=name,
                pass_rate=round(sum(r.passed for r in rows) / len(rows), 6),
                secondary=rows[0].secondary,
                security=rows[0].security,
                reasons=reasons,
            )
        )
    return rates
