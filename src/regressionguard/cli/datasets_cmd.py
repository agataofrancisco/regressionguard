"""Subcomandos `ai-eval datasets validate|stats`."""

from __future__ import annotations

from pathlib import Path

import typer

from regressionguard.datasets import validate_dataset
from regressionguard.datasets.stats import summarize
from regressionguard.evaluators.registry import names as evaluator_names
from regressionguard.runner.suites import default_dataset_paths

datasets_app = typer.Typer(help="Validar e resumir datasets golden.", no_args_is_help=True)


def _paths(paths: list[Path] | None, root: Path) -> list[Path]:
    return paths if paths else default_dataset_paths(root)


@datasets_app.command("validate")
def validate(
    paths: list[Path] = typer.Argument(None, help="Ficheiros JSONL (por omissao, os das suites)."),
    root: Path = typer.Option(Path("."), help="Raiz do repositorio."),
) -> None:
    """Valida o formato, os ids e os avaliadores declarados. Sai com 1 se houver erros."""
    known = set(evaluator_names())
    failed = False
    for path in _paths(paths, root):
        dataset, issues = validate_dataset(path)
        for issue in issues:
            failed = True
            typer.echo(str(issue), err=True)
        if dataset is not None:
            for case in dataset.cases:
                for name in case.evaluators:
                    if name not in known:
                        failed = True
                        typer.echo(
                            f"[unknown_evaluator] {path}: caso {case.id} usa '{name}'", err=True
                        )
            if not issues:
                typer.echo(f"OK {path} v{dataset.version_id} ({len(dataset.cases)} casos)")
    raise typer.Exit(code=1 if failed else 0)


@datasets_app.command("stats")
def stats(
    paths: list[Path] = typer.Argument(None, help="Ficheiros JSONL (por omissao, os das suites)."),
    root: Path = typer.Option(Path("."), help="Raiz do repositorio."),
) -> None:
    """Mostra o total de casos e a distribuicao por alvo, categoria e severidade."""
    datasets = []
    for path in _paths(paths, root):
        dataset, issues = validate_dataset(path)
        if dataset is None:
            for issue in issues:
                typer.echo(str(issue), err=True)
            raise typer.Exit(code=1)
        datasets.append(dataset)
    summary = summarize(datasets)
    typer.echo(f"Total de casos: {summary['total']}")
    for title, key in (
        ("Alvo", "by_target"),
        ("Categoria", "by_category"),
        ("Severidade", "by_severity"),
    ):
        typer.echo(f"\n{title}:")
        for label, count in summary[key].items():  # type: ignore[union-attr]
            typer.echo(f"  {label:<32} {count:>4}")
