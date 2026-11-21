"""Executa uma suite sobre um conjunto de configuracoes de alvo, com repeticoes e orcamento.

Regras principais (ver specs/eval-runs e docs/learn/06):
- um caso passa numa repeticao se nenhum avaliador PRIMARIO falhar e o alvo nao devolver erro;
- avaliadores secundarios (juiz LLM) so correm se houver juiz, e nunca decidem a passagem;
- `--mode live` tem orcamento: antes de cada chamada estima-se o custo pelo maior custo observado;
  se a chamada nao cabe no orcamento, a run para e fica `incomplete: budget_reached`.
"""

from __future__ import annotations

import subprocess
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from regressionguard.datasets import Dataset, load_dataset
from regressionguard.datasets.models import Case
from regressionguard.evaluators import registry
from regressionguard.evaluators.judge import Judge
from regressionguard.evaluators.registry import EvalContext, EvalResult
from regressionguard.runner.records import (
    CaseRecord,
    DatasetRef,
    EvalRecord,
    RunRecord,
    TargetRef,
    evaluator_rates,
)
from regressionguard.runner.suites import ConfigSet, Suite
from regressionguard.runner.summary import FAILED_THRESHOLD, summarize
from regressionguard.targets.base import ConfigError, Target, TargetOutput, load_target_config
from regressionguard.targets.factory import build_target

BUDGET_REACHED = "budget_reached"


@dataclass(frozen=True)
class RunOptions:
    suite: Suite
    config_set: ConfigSet
    mode: str
    root: Path
    repeats: int = 1
    seed: int = 0
    max_usd: float | None = None
    tag: str | None = None
    judge: Judge | None = None
    http_client: httpx.Client | None = None
    now: Callable[[], datetime] = lambda: datetime.now(UTC)  # noqa: E731 - injetavel em testes


def git_commit(root: Path) -> str:
    """Commit atual (+dirty se houver alteracoes). Sem git devolve 'unknown'."""
    try:
        head = subprocess.run(
            ["git", "rev-parse", "--short=12", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=15,
            check=True,
        ).stdout.strip()
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=15,
            check=True,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    return f"{head}+dirty" if status.strip() else head


def evaluate_output(
    case: Case, output: TargetOutput, root: Path, judge: Judge | None
) -> tuple[list[EvalRecord], bool]:
    """Corre os avaliadores de um caso sobre uma saida. Devolve (registos, passou)."""
    records: list[EvalRecord] = []
    primary_ok = output.error is None
    for name in case.evaluators:
        spec = registry.get(name)
        if spec.secondary and judge is None:
            continue
        try:
            result: EvalResult = spec.fn(
                EvalContext(case=case, output=output, root=root, judge=judge)
            )
        except Exception as exc:  # noqa: BLE001 - um avaliador com bug nao aborta a run
            result = EvalResult(passed=False, reason=f"evaluator_error:{type(exc).__name__}")
        records.append(
            EvalRecord(
                case_id=case.id,
                repeat=-1,  # preenchido pelo chamador
                evaluator=name,
                passed=result.passed,
                score=result.score,
                reason=result.reason,
                details=result.details,
                secondary=spec.secondary,
                security=spec.security,
            )
        )
        if not spec.secondary and not result.passed:
            primary_ok = False
    return records, primary_ok


def _aggregate_case(
    case: Case,
    target_name: str,
    outputs: list[TargetOutput],
    repeat_evals: list[list[EvalRecord]],
    repeat_passed: list[bool],
) -> CaseRecord:
    repeats = len(outputs)
    pass_rate = sum(repeat_passed) / repeats if repeats else 0.0
    all_evals = [r for evals in repeat_evals for r in evals]
    return CaseRecord(
        case_id=case.id,
        target=target_name,
        category=case.category,
        severity=case.severity,
        input=case.input,
        expected=case.expected,
        pass_rate=round(pass_rate, 6),
        passed=pass_rate >= FAILED_THRESHOLD,
        flaky=0.0 < pass_rate < 1.0,
        repeats=repeats,
        latencies_ms=[round(o.latency_ms, 4) for o in outputs],
        cost_usd=round(sum(o.cost_usd for o in outputs), 8),
        abstained_rate=round(sum(o.abstained for o in outputs) / repeats, 6) if repeats else 0.0,
        error_rate=round(sum(o.error is not None for o in outputs) / repeats, 6)
        if repeats
        else 0.0,
        trace_ids=sorted({o.trace_id for o in outputs if o.trace_id}),
        outputs=outputs,
        evaluators=evaluator_rates(all_evals),
        evaluations=all_evals,
    )


def _safe_run(target: Target, case_input: Any, seed: int) -> TargetOutput:
    try:
        return target.run(case_input, seed=seed)
    except Exception as exc:  # noqa: BLE001 - erro do alvo vira resultado, nao excecao
        return TargetOutput(error=f"target_exception: {type(exc).__name__}: {exc}")


def _latency_source(targets: dict[str, Target]) -> str:
    labels = {t.provider_label for t in targets.values()}
    if all(label == "mock" for label in labels):
        return "synthetic-mock"
    return "measured"


def run_suite(opts: RunOptions) -> RunRecord:
    """Executa a suite e devolve o registo completo (nao escreve nada em disco)."""
    if opts.repeats < 1:
        raise ConfigError("--repeats tem de ser pelo menos 1")
    if opts.mode == "live" and opts.max_usd is None:
        raise ConfigError("o modo live exige --max-usd")
    if opts.max_usd is not None and opts.max_usd < 0:
        raise ConfigError("--max-usd nao pode ser negativo")

    datasets: list[Dataset] = []
    for rel in opts.suite.datasets:
        datasets.append(load_dataset(opts.root / rel))

    targets: dict[str, Target] = {}
    target_refs: list[TargetRef] = []
    for name, rel in sorted(opts.config_set.targets.items()):
        cfg = load_target_config(opts.root / rel)
        if cfg.target != name:
            raise ConfigError(f"{rel}: o alvo e '{cfg.target}' mas o conjunto diz '{name}'")
        target = build_target(cfg, root=opts.root, mode=opts.mode, http_client=opts.http_client)
        targets[name] = target
        target_refs.append(
            TargetRef(
                target=name,
                version=cfg.version,
                config_hash=cfg.config_hash(),
                provider=target.provider_label,
                config_path=rel,
            )
        )
    for dataset in datasets:
        if dataset.manifest.target not in targets:
            raise ConfigError(
                f"o conjunto '{opts.config_set.name}' nao configura o alvo "
                f"'{dataset.manifest.target}'"
            )

    severity = opts.suite.severity
    spent = 0.0
    max_call_cost = 0.0
    status, reason = "complete", None
    case_records: list[CaseRecord] = []

    for dataset in datasets:
        target = targets[dataset.manifest.target]
        for case in dataset.cases:
            if severity is not None and case.severity != severity:
                continue
            outputs: list[TargetOutput] = []
            repeat_evals: list[list[EvalRecord]] = []
            repeat_passed: list[bool] = []
            for repeat in range(opts.repeats):
                if opts.max_usd is not None and spent + max_call_cost > opts.max_usd:
                    status, reason = "incomplete", BUDGET_REACHED
                    break
                output = _safe_run(target, case.input, opts.seed + repeat)
                spent += output.cost_usd
                max_call_cost = max(max_call_cost, output.cost_usd)
                records, passed = evaluate_output(case, output, opts.root, opts.judge)
                for record in records:
                    record.repeat = repeat
                outputs.append(output)
                repeat_evals.append(records)
                repeat_passed.append(passed)
            if outputs:
                case_records.append(
                    _aggregate_case(
                        case, dataset.manifest.target, outputs, repeat_evals, repeat_passed
                    )
                )
            if status == "incomplete":
                break
        if status == "incomplete":
            break

    now = opts.now()
    return RunRecord(
        run_id=f"{now.strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:6]}",
        created_at=now.isoformat(timespec="seconds"),
        commit=git_commit(opts.root),
        suite=opts.suite.name,
        config_set=opts.config_set.name,
        mode=opts.mode,  # type: ignore[arg-type]
        status=status,  # type: ignore[arg-type]
        incomplete_reason=reason,
        tag=opts.tag,
        repeats=opts.repeats,
        seed=opts.seed,
        max_usd=opts.max_usd,
        latency_source=_latency_source(targets),
        datasets=[
            DatasetRef(
                path=str(path),
                name=ds.manifest.name,
                version=ds.version_id,
                target=ds.manifest.target,
                content_hash=ds.content_hash,
            )
            for ds, path in zip(datasets, opts.suite.datasets, strict=True)
        ],
        targets=target_refs,
        summary=summarize(case_records, spent),
        cases=case_records,
    )
