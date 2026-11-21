"""Ponto de entrada da CLI `ai-eval`.

Codigos de saida: 0 = aprovado (com ou sem avisos); 1 = gate critico falhado (compare) ou dataset
invalido (datasets validate); 2 = uso invalido, configuracao ou comparacao recusada.
"""

from __future__ import annotations

from pathlib import Path

import typer

from regressionguard import __version__
from regressionguard.cli.datasets_cmd import datasets_app
from regressionguard.comparison.engine import ComparisonError, ComparisonReport, compare
from regressionguard.comparison.gates import load_gates
from regressionguard.report.render import (
    compare_json,
    render_compare_html,
    render_index_html,
    render_run_html,
    run_json,
)
from regressionguard.runner.records import RunRecord
from regressionguard.runner.run import RunOptions, run_suite
from regressionguard.runner.suites import load_config_set, load_suite
from regressionguard.store.audit import read_audit, write_audit
from regressionguard.store.duck import RunExistsError, RunStore
from regressionguard.targets.base import ConfigError

app = typer.Typer(
    name="ai-eval",
    help="RegressionGuard: avalia sistemas com LLMs e detecta regressoes.",
    no_args_is_help=True,
    add_completion=False,
    # ajuda em texto simples: o render Rich quebra em pipes do Git Bash no Windows
    rich_markup_mode=None,
)
app.add_typer(datasets_app, name="datasets")

RootOption = typer.Option(
    Path("."), help="Raiz do repositorio (onde estao datasets/, targets/, config/)."
)


@app.callback()
def main() -> None:
    """RegressionGuard: avalia sistemas com LLMs e detecta regressoes."""


@app.command("version")
def version() -> None:
    """Mostra a versao instalada."""
    typer.echo(__version__)


def _fail(message: str, code: int = 2) -> None:
    typer.echo(message, err=True)
    raise typer.Exit(code=code)


def _db_path(root: Path) -> Path:
    return root / "regressionguard.duckdb"


def _pct(value: float | None) -> str:
    return "n/d" if value is None else f"{value * 100:.1f}%"


def _fmt(value: float | None, unit: str = "") -> str:
    return "n/d" if value is None else f"{value:.4g}{unit}"


@app.command("run")
def run_command(
    suite: str = typer.Option("full", help="Suite de datasets (ver datasets/suites.yaml)."),
    config_set: str = typer.Option(
        "v1", "--config-set", help="Conjunto de configuracoes (targets/sets)."
    ),
    mode: str = typer.Option(
        "mock", help="mock (deterministico, sem rede) ou live (LLM real, precisa de --max-usd)."
    ),
    repeats: int = typer.Option(1, min=1, help="Repeticoes por caso."),
    seed: int = typer.Option(0, help="Seed base; a repeticao r usa seed + r."),
    max_usd: float | None = typer.Option(
        None, help="Orcamento maximo em USD (obrigatorio em live)."
    ),
    tag: str | None = typer.Option(None, help="Etiqueta da run (ex.: baseline)."),
    root: Path = RootOption,
) -> None:
    """Executa uma suite e guarda a run (DuckDB + JSON em reports/runs)."""
    try:
        options = RunOptions(
            suite=load_suite(root, suite),
            config_set=load_config_set(root, config_set),
            mode=mode,
            root=root,
            repeats=repeats,
            seed=seed,
            max_usd=max_usd,
            tag=tag,
        )
        record = run_suite(options)
    except ConfigError as exc:
        _fail(f"erro de configuracao: {exc}")
    with RunStore(_db_path(root)) as store:
        store.save_run(record)
    audit = write_audit(record, root / "reports" / "runs")
    summary = record.summary
    typer.echo(f"Run {record.run_id} | {record.status} | modo {record.mode} | suite {record.suite}")
    if record.incomplete_reason:
        typer.echo(f"Incompleta: {record.incomplete_reason} (nao usada para gates)")
    typer.echo(
        f"Casos {summary.total_cases} | sucesso {_pct(summary.pass_rate)} | "
        f"criticos {_pct(summary.critical_pass_rate)}"
    )
    typer.echo(f"Falhas de seguranca {summary.security_failures} | instaveis {summary.flaky_cases}")
    typer.echo(
        f"Latencia p50 {_fmt(summary.latency_p50_ms, ' ms')} "
        f"p95 {_fmt(summary.latency_p95_ms, ' ms')} "
        f"({record.latency_source}) | custo {_fmt(summary.cost_usd, ' USD')}"
    )
    if record.mode == "mock":
        typer.echo("provider: mock (deterministico; latencia sintetica; custo zero)")
    typer.echo(f"Auditoria: {audit}")
    typer.echo(f"Base de dados: {_db_path(root)}")


def _print_comparison(report: ComparisonReport) -> None:
    typer.echo(
        f"Candidato {report.candidate_id} contra baseline {report.baseline_id} "
        f"({report.n_cases} casos)"
    )
    typer.echo(
        f"Sucesso: {_pct(report.pass_rate_baseline)} -> {_pct(report.pass_rate_candidate)} "
        f"(diferenca {report.pass_rate_diff * 100:+.1f} pp)"
    )
    typer.echo(
        f"IC 95% da diferenca: [{report.ci_low:+.3f}, {report.ci_high:+.3f}] | "
        f"McNemar p={report.mcnemar_p_value:.4g} (so baseline {report.mcnemar_only_baseline}, "
        f"so candidato {report.mcnemar_only_candidate})"
    )
    if report.insufficient_sample_size:
        typer.echo("Amostra insuficiente: " + "; ".join(report.insufficient_reasons))
    for warning in report.warnings:
        typer.echo(f"aviso: {warning}")
    typer.echo("Gates:")
    for gate in report.gates:
        state = "NAO AVALIAVEL" if gate.passed is None else ("OK" if gate.passed else "FALHOU")
        value = "n/d" if gate.value is None else f"{gate.value:.4g}"
        typer.echo(
            f"  [{gate.severity:<8}] {state:<13} {gate.name} "
            f"(valor {value}, limiar {gate.threshold})"
        )
        for item in gate.evidence[:5]:
            typer.echo(f"        - {item}")
    typer.echo(f"Casos regredidos: {len(report.regressions)}")
    for entry in report.regressions[:10]:
        typer.echo(f"  - {entry.case_id} [{entry.severity}] {', '.join(entry.reasons) or 'falha'}")
    if report.recommendation.get("action") == "rollback":
        typer.echo(
            "Recomendacao: rollback para "
            f"{report.recommendation['rollback_to']['run_id']} (nao executado)"
        )


@app.command("compare")
def compare_command(
    baseline: str = typer.Option(..., help="Id da run baseline."),
    candidate: str = typer.Option(..., help="Id da run candidata."),
    gates: Path | None = typer.Option(
        None, help="Ficheiro de gates (por omissao config/gates.yaml)."
    ),
    html: bool = typer.Option(False, "--html", help="Gera tambem o relatorio HTML."),
    root: Path = RootOption,
) -> None:
    """Compara duas runs. Sai com 1 se um gate critico falhar."""
    try:
        gates_config = load_gates(gates or root / "config" / "gates.yaml")
    except ConfigError as exc:
        _fail(f"erro de configuracao: {exc}")
    with RunStore(_db_path(root)) as store:
        try:
            base_run = store.load_run(baseline)
            cand_run = store.load_run(candidate)
        except KeyError as exc:
            _fail(str(exc))
    try:
        report = compare(base_run, cand_run, gates_config)
    except ComparisonError as exc:
        _fail(str(exc))
    _print_comparison(report)
    out_dir = root / "reports" / "comparisons"
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{baseline}__{candidate}"
    (out_dir / f"{stem}.json").write_text(compare_json(report), encoding="utf-8")
    typer.echo(f"Comparacao: {out_dir / (stem + '.json')}")
    if html:
        (out_dir / f"{stem}.html").write_text(
            render_compare_html(report, index_href="../index.html"), encoding="utf-8"
        )
        typer.echo(f"Relatorio HTML: {out_dir / (stem + '.html')}")
    raise typer.Exit(code=report.exit_code)


@app.command("report")
def report_command(
    run: str | None = typer.Option(None, help="Id da run a reportar."),
    html: bool = typer.Option(False, "--html", help="Relatorio HTML autonomo."),
    as_json: bool = typer.Option(False, "--json", help="Resumo em JSON."),
    out: Path | None = typer.Option(None, help="Ficheiro de saida (por omissao em reports/)."),
    root: Path = RootOption,
) -> None:
    """Gera o relatorio de uma run (HTML ou JSON)."""
    if run is None:
        _fail("indique --run <id>")
    if html == as_json:
        _fail("indique exatamente um de --html ou --json")
    with RunStore(_db_path(root)) as store:
        try:
            record = store.load_run(run)
        except KeyError as exc:
            _fail(str(exc))
    if html:
        target = out or root / "reports" / "html" / f"{run}.html"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(render_run_html(record, index_href="../index.html"), encoding="utf-8")
    else:
        target = out or root / "reports" / "runs" / f"{run}.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(run_json(record), encoding="utf-8")
    typer.echo(f"Relatorio: {target}")


@app.command("runs")
def runs_command(
    limit: int = typer.Option(25, min=1, help="Numero maximo de runs."),
    root: Path = RootOption,
) -> None:
    """Lista as runs guardadas (mais antigas primeiro)."""
    with RunStore(_db_path(root)) as store:
        rows = store.list_runs()
    if not rows:
        typer.echo("Sem runs guardadas.")
        return
    typer.echo(
        f"{'run_id':<24} {'modo':<5} {'estado':<10} {'sucesso':>8} {'criticos':>9} "
        f"{'commit':<14} tag"
    )
    for row in rows[-limit:]:
        typer.echo(
            f"{row['run_id']:<24} {row['mode']:<5} {row['status']:<10} {_pct(row['pass_rate']):>8} "
            f"{_pct(row['critical_pass_rate']):>9} {row['commit']:<14} {row['tag'] or ''}"
        )


@app.command("import")
def import_command(
    file: Path = typer.Argument(..., help="JSON de auditoria de uma run."),
    root: Path = RootOption,
) -> None:
    """Importa um JSON de auditoria (ex.: baseline descarregado de um artefacto de CI)."""
    try:
        record: RunRecord = read_audit(file)
    except (OSError, ValueError) as exc:
        _fail(f"ficheiro invalido: {exc}")
    with RunStore(_db_path(root)) as store:
        try:
            store.save_run(record)
        except RunExistsError as exc:
            _fail(str(exc))
    typer.echo(f"Importada a run {record.run_id}")


@app.command("index")
def index_command(root: Path = RootOption) -> None:
    """Gera reports/index.html com as runs e as comparacoes, e a pagina de cada run."""
    reports = root / "reports"
    with RunStore(_db_path(root)) as store:
        rows = store.list_runs()
        for row in rows:
            record = store.load_run(row["run_id"])
            page = reports / "html" / f"{record.run_id}.html"
            page.parent.mkdir(parents=True, exist_ok=True)
            page.write_text(render_run_html(record, index_href="../index.html"), encoding="utf-8")
    comparisons = []
    comp_dir = reports / "comparisons"
    if comp_dir.exists():
        for html_file in sorted(comp_dir.glob("*.html")):
            comparisons.append({"href": f"comparisons/{html_file.name}", "label": html_file.stem})
    (reports / "index.html").write_text(render_index_html(rows, comparisons), encoding="utf-8")
    typer.echo(f"Indice: {reports / 'index.html'} ({len(rows)} runs)")


if __name__ == "__main__":
    app()
