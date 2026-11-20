"""Ponto de entrada da CLI `ai-eval`."""

import typer

from regressionguard import __version__
from regressionguard.cli.datasets_cmd import datasets_app

app = typer.Typer(
    name="ai-eval",
    help="RegressionGuard: avalia sistemas com LLMs e detecta regressoes.",
    no_args_is_help=True,
    add_completion=False,
)


@app.callback()
def main() -> None:
    """RegressionGuard: avalia sistemas com LLMs e detecta regressoes."""


@app.command("version")
def version() -> None:
    """Mostra a versao instalada."""
    typer.echo(__version__)


app.add_typer(datasets_app, name="datasets")


if __name__ == "__main__":
    app()
