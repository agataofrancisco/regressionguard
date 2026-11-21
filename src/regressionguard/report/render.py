"""Renderizacao de relatorios HTML (autonomos, sem servidor) e JSON."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from regressionguard.comparison.engine import ComparisonReport
from regressionguard.runner.records import RunRecord

TEMPLATE_DIR = Path(__file__).parent / "templates"


def _environment() -> Environment:
    return Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        autoescape=select_autoescape(["html", "j2"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def _pct(value: float | None) -> str:
    return "n/d" if value is None else f"{value * 100:.1f}%"


def _num(value: float | None, unit: str = "") -> str:
    return "n/d" if value is None else f"{value:.4g}{unit}"


_ENV = _environment()
_ENV.filters["pct"] = _pct
_ENV.filters["num"] = _num


def render_run_html(record: RunRecord, index_href: str = "index.html") -> str:
    failed = [case for case in record.cases if not case.passed]
    template = _ENV.get_template("run.html.j2")
    return template.render(run=record, failed=failed, index_href=index_href)


def render_compare_html(report: ComparisonReport, index_href: str = "index.html") -> str:
    template = _ENV.get_template("compare.html.j2")
    return template.render(report=report, index_href=index_href)


def render_index_html(runs: list[dict[str, Any]], comparisons: list[dict[str, str]]) -> str:
    template = _ENV.get_template("index.html.j2")
    return template.render(runs=runs, comparisons=comparisons)


def run_json(record: RunRecord) -> str:
    return record.model_dump_json(indent=2)


def compare_json(report: ComparisonReport) -> str:
    return report.model_dump_json(indent=2)
