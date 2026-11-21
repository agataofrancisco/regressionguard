import json
import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from regressionguard.cli.main import app

ROOT = Path(__file__).resolve().parents[1]
runner = CliRunner()


@pytest.fixture
def repo(tmp_path) -> Path:
    """Copia dos dados versionados (datasets, alvos, gates) para um diretorio temporario."""
    for folder in ("datasets", "targets", "config"):
        shutil.copytree(ROOT / folder, tmp_path / folder)
    return tmp_path


def _invoke(*args: str):
    return runner.invoke(app, list(args), catch_exceptions=False)


def _run_id(output: str) -> str:
    line = next(line for line in output.splitlines() if line.startswith("Run "))
    return line.split()[1]


def test_datasets_validate_and_stats(repo):
    result = _invoke("datasets", "validate", "--root", str(repo))
    assert result.exit_code == 0, result.output
    assert "OK" in result.output
    stats = _invoke("datasets", "stats", "--root", str(repo))
    assert "Total de casos: 90" in stats.output


def test_run_mock_writes_store_and_audit(repo):
    result = _invoke(
        "run", "--suite", "full", "--config-set", "v1", "--mode", "mock", "--root", str(repo)
    )
    assert result.exit_code == 0, result.output
    assert "provider: mock" in result.output
    assert (repo / "regressionguard.duckdb").exists()
    audits = list((repo / "reports" / "runs").glob("*.json"))
    assert len(audits) == 1
    data = json.loads(audits[0].read_text(encoding="utf-8"))
    assert data["mode"] == "mock" and data["summary"]["total_cases"] == 90


def test_live_without_max_usd_is_refused_before_any_call(repo):
    result = _invoke("run", "--mode", "live", "--root", str(repo))
    assert result.exit_code == 2
    assert "max-usd" in result.output
    assert not (repo / "regressionguard.duckdb").exists()


def test_unknown_suite_and_config_set_are_usage_errors(repo):
    assert _invoke("run", "--suite", "nao-existe", "--root", str(repo)).exit_code == 2
    assert _invoke("run", "--config-set", "nao-existe", "--root", str(repo)).exit_code == 2


def test_compare_regression_exits_one_and_identical_exits_zero(repo):
    base = _run_id(
        _invoke("run", "--config-set", "v1", "--tag", "baseline", "--root", str(repo)).output
    )
    cand = _run_id(_invoke("run", "--config-set", "no-citations", "--root", str(repo)).output)
    failing = _invoke("compare", "--baseline", base, "--candidate", cand, "--root", str(repo))
    assert failing.exit_code == 1, failing.output
    assert "FALHOU" in failing.output and "citations_regression" in failing.output
    assert "rollback" in failing.output and "nao executado" in failing.output
    same = _invoke("compare", "--baseline", base, "--candidate", base, "--root", str(repo))
    assert same.exit_code == 0, same.output


def test_compare_unknown_run_is_usage_error(repo):
    _invoke("run", "--root", str(repo))
    result = _invoke("compare", "--baseline", "x", "--candidate", "y", "--root", str(repo))
    assert result.exit_code == 2


def test_report_html_is_standalone(repo):
    run_id = _run_id(_invoke("run", "--config-set", "v1", "--root", str(repo)).output)
    result = _invoke("report", "--run", run_id, "--html", "--root", str(repo))
    assert result.exit_code == 0, result.output
    html = (repo / "reports" / "html" / f"{run_id}.html").read_text(encoding="utf-8")
    assert html.startswith("<!doctype html>")
    assert "provider: mock" in html and "Casos falhados" in html
    assert "<script" not in html and "http://" not in html and "https://" not in html
    assert '<link rel="stylesheet"' not in html


def test_report_requires_exactly_one_format(repo):
    run_id = _run_id(_invoke("run", "--root", str(repo)).output)
    assert _invoke("report", "--run", run_id, "--root", str(repo)).exit_code == 2
    assert (
        _invoke("report", "--run", run_id, "--html", "--json", "--root", str(repo)).exit_code == 2
    )


def test_index_lists_runs_and_links_pages(repo):
    run_id = _run_id(_invoke("run", "--root", str(repo)).output)
    result = _invoke("index", "--root", str(repo))
    assert result.exit_code == 0
    index = (repo / "reports" / "index.html").read_text(encoding="utf-8")
    assert run_id in index and f"html/{run_id}.html" in index
    assert (repo / "reports" / "html" / f"{run_id}.html").exists()


def test_import_duplicate_is_refused_and_mismatch_blocks_compare(repo):
    run_id = _run_id(_invoke("run", "--root", str(repo)).output)
    audit = repo / "reports" / "runs" / f"{run_id}.json"
    assert _invoke("import", str(audit), "--root", str(repo)).exit_code == 2  # ja existe

    data = json.loads(audit.read_text(encoding="utf-8"))
    data["run_id"] = "importada-1"
    data["datasets"][0]["content_hash"] = "0" * 64  # simula um dataset com outra versao
    tampered = repo / "importada.json"
    tampered.write_text(json.dumps(data), encoding="utf-8")
    assert _invoke("import", str(tampered), "--root", str(repo)).exit_code == 0
    result = _invoke(
        "compare", "--baseline", run_id, "--candidate", "importada-1", "--root", str(repo)
    )
    assert result.exit_code == 2
    assert "dataset_version_mismatch" in result.output


def test_runs_listing(repo):
    assert "Sem runs" in _invoke("runs", "--root", str(repo)).output
    _invoke("run", "--root", str(repo))
    assert "mock" in _invoke("runs", "--root", str(repo)).output
