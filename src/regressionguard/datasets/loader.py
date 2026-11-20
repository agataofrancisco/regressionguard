"""Leitura e validacao de datasets JSONL.

Formato: a primeira linha nao vazia e `{"manifest": {...}}`; cada linha seguinte e um caso.
Os erros trazem o ficheiro e o numero da linha. Funcoes puras: nunca lancam por dados
mal formados, devolvem `Issue`s.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from regressionguard.datasets.models import Case, Dataset, Manifest, canonical_hash


@dataclass(frozen=True)
class Issue:
    code: str
    path: str
    line: int | None
    message: str

    def __str__(self) -> str:
        location = f"{self.path}:{self.line}" if self.line is not None else self.path
        return f"[{self.code}] {location}: {self.message}"


class DatasetError(Exception):
    """Dataset invalido. `issues` contem todos os problemas encontrados."""

    def __init__(self, issues: list[Issue]) -> None:
        self.issues = issues
        super().__init__("; ".join(str(issue) for issue in issues))


def _pydantic_message(exc: ValidationError) -> str:
    parts = []
    for err in exc.errors():
        location = ".".join(str(part) for part in err.get("loc", ())) or "registo"
        parts.append(f"{location}: {err.get('msg', 'invalido')}")
    return "; ".join(parts)


def parse_dataset(text: str, path: str) -> tuple[Dataset | None, list[Issue]]:
    """Valida o texto de um dataset. Devolve (dataset ou None, lista de issues)."""
    issues: list[Issue] = []
    manifest: Manifest | None = None
    cases: list[Case] = []
    seen: dict[str, int] = {}
    first_record = True

    for line_no, raw in enumerate(text.splitlines(), start=1):
        if not raw.strip():
            continue
        try:
            record = json.loads(raw)
        except json.JSONDecodeError as exc:
            issues.append(Issue("invalid_json", path, line_no, str(exc)))
            first_record = False
            continue
        if not isinstance(record, dict):
            issues.append(
                Issue("invalid_record", path, line_no, "a linha tem de ser um objeto JSON")
            )
            first_record = False
            continue

        if first_record:
            first_record = False
            if "manifest" not in record:
                issues.append(
                    Issue(
                        "missing_manifest", path, line_no, "a primeira linha tem de ser o manifesto"
                    )
                )
            else:
                try:
                    manifest = Manifest.model_validate(record["manifest"])
                except ValidationError as exc:
                    issues.append(Issue("invalid_manifest", path, line_no, _pydantic_message(exc)))
                continue

        if "manifest" in record and set(record) == {"manifest"}:
            issues.append(
                Issue(
                    "duplicate_manifest",
                    path,
                    line_no,
                    "o manifesto so pode aparecer na primeira linha",
                )
            )
            continue

        try:
            case = Case.model_validate(record)
        except ValidationError as exc:
            issues.append(Issue("invalid_case", path, line_no, _pydantic_message(exc)))
            continue
        if case.id in seen:
            issues.append(
                Issue(
                    "duplicate_case_id",
                    path,
                    line_no,
                    f"id '{case.id}' ja definido na linha {seen[case.id]}",
                )
            )
            continue
        seen[case.id] = line_no
        cases.append(case)

    if manifest is None and not any(issue.code == "missing_manifest" for issue in issues):
        issues.append(Issue("invalid_manifest", path, None, "manifesto em falta ou invalido"))
    if not cases and not issues:
        issues.append(Issue("empty_dataset", path, None, "o dataset nao tem casos"))
    if issues or manifest is None:
        return None, issues

    dataset = Dataset(
        manifest=manifest,
        cases=cases,
        path=path,
        content_hash=canonical_hash(manifest, cases),
    )
    return dataset, []


def validate_dataset(path: Path | str) -> tuple[Dataset | None, list[Issue]]:
    """Le um ficheiro JSONL e valida-o. Nunca lanca excepcoes de conteudo."""
    file_path = Path(path)
    try:
        text = file_path.read_text(encoding="utf-8")
    except OSError as exc:
        return None, [Issue("unreadable", str(file_path), None, str(exc))]
    return parse_dataset(text, str(file_path))


def load_dataset(path: Path | str) -> Dataset:
    """Carrega um dataset valido ou lanca `DatasetError` com todos os issues."""
    dataset, issues = validate_dataset(path)
    if dataset is None:
        raise DatasetError(issues)
    return dataset
