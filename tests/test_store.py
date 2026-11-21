from datetime import UTC, datetime
from pathlib import Path

import pytest

from regressionguard.runner.run import RunOptions, run_suite
from regressionguard.runner.suites import load_config_set, load_suite
from regressionguard.store.audit import read_audit, write_audit
from regressionguard.store.duck import RunExistsError, RunStore

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 11, 20, 9, 30, tzinfo=UTC)


@pytest.fixture(scope="module")
def record():
    options = RunOptions(
        suite=load_suite(ROOT, "full"),
        config_set=load_config_set(ROOT, "v1"),
        mode="mock",
        root=ROOT,
        now=lambda: NOW,
    )
    return run_suite(options)


def test_store_round_trip_rebuilds_identical_run(tmp_path, record):
    with RunStore(tmp_path / "r.duckdb") as store:
        store.save_run(record)
        loaded = store.load_run(record.run_id)
    assert loaded.model_dump() == record.model_dump()


def test_duplicate_run_id_is_refused(tmp_path, record):
    with RunStore(tmp_path / "r.duckdb") as store:
        store.save_run(record)
        with pytest.raises(RunExistsError):
            store.save_run(record)
        assert store.exists(record.run_id)


def test_unknown_run_raises_key_error(tmp_path):
    with RunStore(tmp_path / "r.duckdb") as store, pytest.raises(KeyError):
        store.load_run("nao-existe")


def test_list_runs_reports_summary_columns(tmp_path, record):
    with RunStore(tmp_path / "r.duckdb") as store:
        store.save_run(record)
        rows = store.list_runs()
    assert rows[0]["run_id"] == record.run_id
    assert rows[0]["pass_rate"] == pytest.approx(record.summary.pass_rate)
    assert rows[0]["commit"] == record.commit


def test_audit_json_round_trip(tmp_path, record):
    path = write_audit(record, tmp_path / "runs")
    assert path.name == f"{record.run_id}.json"
    assert read_audit(path).model_dump() == record.model_dump()


def test_corrupted_audit_is_rejected(tmp_path):
    bad = tmp_path / "x.json"
    bad.write_text('{"run_id": "x"}', encoding="utf-8")
    with pytest.raises(ValueError):
        read_audit(bad)


def test_stale_schema_is_detected_with_clear_error(tmp_path):
    import duckdb

    from regressionguard.store.duck import StoreSchemaError

    old = tmp_path / "antigo.duckdb"
    con = duckdb.connect(str(old))
    con.execute("CREATE TABLE case_results (run_id VARCHAR)")
    con.execute("CREATE TABLE evaluator_results (run_id VARCHAR)")
    con.close()
    with pytest.raises(StoreSchemaError, match="esquema antigo"):
        RunStore(old)
