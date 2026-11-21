"""JSON de auditoria: cada run e tambem escrita como ficheiro (reports/runs/<run_id>.json)."""

from __future__ import annotations

from pathlib import Path

from regressionguard.runner.records import RunRecord


def write_audit(record: RunRecord, directory: Path | str) -> Path:
    """Escreve o registo completo da run. Devolve o caminho do ficheiro."""
    target_dir = Path(directory)
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / f"{record.run_id}.json"
    path.write_text(record.model_dump_json(indent=2), encoding="utf-8")
    return path


def read_audit(path: Path | str) -> RunRecord:
    """Le e valida um JSON de auditoria (lanca ValidationError se estiver corrompido)."""
    return RunRecord.model_validate_json(Path(path).read_text(encoding="utf-8"))
