"""Historico de runs em DuckDB (ficheiro local, sem servidor).

Tabelas: `runs` (metadados e resumo), `case_results` (um registo por caso) e `evaluator_results`
(um registo por avaliador e repeticao). Uma run e reconstruida a partir destas tabelas, por isso
as consultas SQL e a comparacao leem a mesma fonte.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import duckdb

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

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id VARCHAR PRIMARY KEY,
    created_at VARCHAR NOT NULL,
    commit_sha VARCHAR NOT NULL,
    suite VARCHAR NOT NULL,
    config_set VARCHAR NOT NULL,
    mode VARCHAR NOT NULL,
    status VARCHAR NOT NULL,
    incomplete_reason VARCHAR,
    tag VARCHAR,
    repeats INTEGER NOT NULL,
    seed INTEGER NOT NULL,
    max_usd DOUBLE,
    latency_source VARCHAR NOT NULL,
    datasets_json VARCHAR NOT NULL,
    targets_json VARCHAR NOT NULL,
    summary_json VARCHAR NOT NULL
);
CREATE TABLE IF NOT EXISTS case_results (
    run_id VARCHAR NOT NULL,
    case_id VARCHAR NOT NULL,
    target VARCHAR NOT NULL,
    category VARCHAR NOT NULL,
    severity VARCHAR NOT NULL,
    input_json VARCHAR NOT NULL,
    expected_json VARCHAR NOT NULL,
    pass_rate DOUBLE NOT NULL,
    passed BOOLEAN NOT NULL,
    flaky BOOLEAN NOT NULL,
    repeats INTEGER NOT NULL,
    latencies_json VARCHAR NOT NULL,
    cost_usd DOUBLE NOT NULL,
    abstained_rate DOUBLE NOT NULL,
    error_rate DOUBLE NOT NULL,
    trace_ids_json VARCHAR NOT NULL,
    outputs_json VARCHAR NOT NULL,
    seq INTEGER NOT NULL,
    PRIMARY KEY (run_id, case_id)
);
CREATE TABLE IF NOT EXISTS evaluator_results (
    run_id VARCHAR NOT NULL,
    case_id VARCHAR NOT NULL,
    repeat INTEGER NOT NULL,
    evaluator VARCHAR NOT NULL,
    passed BOOLEAN NOT NULL,
    score DOUBLE,
    reason VARCHAR,
    details_json VARCHAR NOT NULL,
    secondary BOOLEAN NOT NULL,
    security BOOLEAN NOT NULL,
    seq INTEGER NOT NULL
);
"""


class RunExistsError(ValueError):
    """Ja existe uma run com este run_id."""


class StoreSchemaError(RuntimeError):
    """Base de dados criada por uma versao anterior do esquema."""


def _dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


class RunStore:
    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._con = duckdb.connect(str(self.path))
        self._con.execute(SCHEMA)
        self._check_schema()

    def _check_schema(self) -> None:
        """`CREATE TABLE IF NOT EXISTS` nao altera tabelas antigas: detetar cedo."""
        expected = {"case_results": "seq", "evaluator_results": "seq"}
        for table, column in expected.items():
            found = self._con.execute(
                "SELECT 1 FROM information_schema.columns WHERE table_name = ? AND column_name = ?",
                [table, column],
            ).fetchone()
            if found is None:
                self._con.close()
                raise StoreSchemaError(
                    f"{self.path} usa um esquema antigo ({table} sem '{column}'). "
                    "Apague o ficheiro e volte a correr as runs."
                )

    def close(self) -> None:
        self._con.close()

    def __enter__(self) -> RunStore:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def exists(self, run_id: str) -> bool:
        row = self._con.execute("SELECT 1 FROM runs WHERE run_id = ?", [run_id]).fetchone()
        return row is not None

    def save_run(self, record: RunRecord) -> None:
        """Grava a run inteira numa transacao. Recusa run_id repetido."""
        if self.exists(record.run_id):
            raise RunExistsError(f"a run {record.run_id} ja existe")
        con = self._con
        con.execute("BEGIN TRANSACTION")
        try:
            con.execute(
                "INSERT INTO runs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    record.run_id,
                    record.created_at,
                    record.commit,
                    record.suite,
                    record.config_set,
                    record.mode,
                    record.status,
                    record.incomplete_reason,
                    record.tag,
                    record.repeats,
                    record.seed,
                    record.max_usd,
                    record.latency_source,
                    _dump([d.model_dump() for d in record.datasets]),
                    _dump([t.model_dump() for t in record.targets]),
                    record.summary.model_dump_json(),
                ],
            )
            for case_seq, case in enumerate(record.cases):
                con.execute(
                    "INSERT INTO case_results VALUES (" + ", ".join(["?"] * 18) + ")",
                    [
                        record.run_id,
                        case.case_id,
                        case.target,
                        case.category,
                        case.severity,
                        _dump(case.input),
                        _dump(case.expected),
                        case.pass_rate,
                        case.passed,
                        case.flaky,
                        case.repeats,
                        _dump(case.latencies_ms),
                        case.cost_usd,
                        case.abstained_rate,
                        case.error_rate,
                        _dump(case.trace_ids),
                        _dump([o.model_dump() for o in case.outputs]),
                        case_seq,
                    ],
                )
                for seq, ev in enumerate(case.evaluations):
                    con.execute(
                        "INSERT INTO evaluator_results VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        [
                            record.run_id,
                            ev.case_id,
                            ev.repeat,
                            ev.evaluator,
                            ev.passed,
                            ev.score,
                            ev.reason,
                            _dump(ev.details),
                            ev.secondary,
                            ev.security,
                            seq,
                        ],
                    )
            con.execute("COMMIT")
        except Exception:
            con.execute("ROLLBACK")
            raise

    def load_run(self, run_id: str) -> RunRecord:
        con = self._con
        row = con.execute("SELECT * FROM runs WHERE run_id = ?", [run_id]).fetchone()
        if row is None:
            raise KeyError(f"run desconhecida: {run_id}")
        (
            rid,
            created_at,
            commit_sha,
            suite,
            config_set,
            mode,
            status,
            incomplete_reason,
            tag,
            repeats,
            seed,
            max_usd,
            latency_source,
            datasets_json,
            targets_json,
            _summary_json,
        ) = row
        evals_by_case: dict[str, list[EvalRecord]] = {}
        for ev in con.execute(
            "SELECT case_id, repeat, evaluator, passed, score, reason, details_json, "
            "secondary, security "
            "FROM evaluator_results WHERE run_id = ? ORDER BY case_id, seq",
            [run_id],
        ).fetchall():
            case_id, rep, evaluator, passed, score, reason, details, secondary, security = ev
            evals_by_case.setdefault(case_id, []).append(
                EvalRecord(
                    case_id=case_id,
                    repeat=rep,
                    evaluator=evaluator,
                    passed=passed,
                    score=score,
                    reason=reason,
                    details=json.loads(details),
                    secondary=secondary,
                    security=security,
                )
            )
        cases: list[CaseRecord] = []
        for c in con.execute(
            "SELECT case_id, target, category, severity, input_json, expected_json, "
            "pass_rate, passed, "
            "flaky, repeats, latencies_json, cost_usd, abstained_rate, error_rate, trace_ids_json, "
            "outputs_json FROM case_results WHERE run_id = ? ORDER BY seq",
            [run_id],
        ).fetchall():
            (
                case_id,
                target,
                category,
                sev,
                inp,
                exp,
                rate,
                passed,
                flaky,
                reps,
                lat,
                cost,
                ab,
                er,
                tr,
                outs,
            ) = c
            cases.append(
                _rebuild_case(
                    case_id, target, category, sev, inp, exp, rate, passed, flaky, reps,
                    lat, cost, ab, er, tr, outs, evals_by_case.get(case_id, []),
                )
            )  # fmt: skip
        datasets = [DatasetRef(**d) for d in json.loads(datasets_json)]
        targets = [TargetRef(**t) for t in json.loads(targets_json)]
        return RunRecord(
            run_id=rid,
            created_at=created_at,
            commit=commit_sha,
            suite=suite,
            config_set=config_set,
            mode=mode,
            status=status,
            incomplete_reason=incomplete_reason,
            tag=tag,
            repeats=repeats,
            seed=seed,
            max_usd=max_usd,
            latency_source=latency_source,
            datasets=datasets,
            targets=targets,
            summary=RunSummary.model_validate_json(_summary_json),
            cases=cases,
        )

    def list_runs(self) -> list[dict[str, Any]]:
        rows = self._con.execute(
            "SELECT run_id, created_at, commit_sha, suite, config_set, mode, status, tag, "
            "summary_json "
            "FROM runs ORDER BY created_at, run_id"
        ).fetchall()
        result = []
        for run_id, created, commit_sha, suite, config_set, mode, status, tag, summary in rows:
            data = json.loads(summary)
            result.append(
                {
                    "run_id": run_id,
                    "created_at": created,
                    "commit": commit_sha,
                    "suite": suite,
                    "config_set": config_set,
                    "mode": mode,
                    "status": status,
                    "tag": tag,
                    "pass_rate": data.get("pass_rate"),
                    "critical_pass_rate": data.get("critical_pass_rate"),
                    "cost_usd": data.get("cost_usd"),
                }
            )
        return result


def _rebuild_case(
    case_id: str,
    target: str,
    category: str,
    severity: str,
    input_json: str,
    expected_json: str,
    pass_rate: float,
    passed: bool,
    flaky: bool,
    repeats: int,
    latencies_json: str,
    cost_usd: float,
    abstained_rate: float,
    error_rate: float,
    trace_ids_json: str,
    outputs_json: str,
    evaluations: list[EvalRecord],
) -> CaseRecord:
    return CaseRecord(
        case_id=case_id,
        target=target,
        category=category,
        severity=severity,
        input=json.loads(input_json),
        expected=json.loads(expected_json),
        pass_rate=pass_rate,
        passed=passed,
        flaky=flaky,
        repeats=repeats,
        latencies_ms=json.loads(latencies_json),
        cost_usd=cost_usd,
        abstained_rate=abstained_rate,
        error_rate=error_rate,
        trace_ids=json.loads(trace_ids_json),
        outputs=[TargetOutput(**o) for o in json.loads(outputs_json)],
        evaluators=evaluator_rates(evaluations),
        evaluations=evaluations,
    )
