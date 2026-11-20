import json

import pytest

from regressionguard.datasets import DatasetError, load_dataset, validate_dataset
from regressionguard.datasets.loader import parse_dataset

MANIFEST = {
    "name": "demo",
    "version": "1.0.0",
    "target": "extraction",
    "description": "teste",
    "author": "eu",
    "date": "2026-11-20",
}


def _case(**overrides):
    case = {
        "id": "c-001",
        "input": "PED-1234 total 10,00€",
        "expected": {"order_id": "PED-1234"},
        "category": "happy",
        "severity": "normal",
        "source": "manual",
        "evaluators": ["json_schema"],
    }
    case.update(overrides)
    return case


def _text(*records):
    return "\n".join(json.dumps(record, ensure_ascii=False) for record in records) + "\n"


def test_valid_dataset_loads_and_hashes(tmp_path):
    path = tmp_path / "ok.jsonl"
    path.write_text(_text({"manifest": MANIFEST}, _case(), _case(id="c-002")), encoding="utf-8")
    dataset = load_dataset(path)
    assert dataset.manifest.name == "demo"
    assert [c.id for c in dataset.cases] == ["c-001", "c-002"]
    assert len(dataset.content_hash) == 64
    assert dataset.version_id.startswith("1.0.0+")


def test_hash_ignores_whitespace_but_changes_with_content(tmp_path):
    base = _text({"manifest": MANIFEST}, _case())
    spaced = json.dumps({"manifest": MANIFEST}, indent=2) + "\n\n" + json.dumps(_case()) + "\n"
    changed = _text({"manifest": MANIFEST}, _case(expected={"order_id": "PED-9999"}))
    h_base = parse_dataset(base, "a")[0].content_hash
    assert parse_dataset(spaced, "b")[0] is None  # manifesto multilinha nao e uma linha JSONL
    compact = _text({"manifest": MANIFEST}, _case())
    assert parse_dataset(compact, "c")[0].content_hash == h_base
    assert parse_dataset(changed, "d")[0].content_hash != h_base


def test_case_without_id_reports_file_and_line(tmp_path):
    bad = _case()
    del bad["id"]
    path = tmp_path / "bad.jsonl"
    path.write_text(_text({"manifest": MANIFEST}, _case(), bad), encoding="utf-8")
    dataset, issues = validate_dataset(path)
    assert dataset is None
    assert issues[0].code == "invalid_case"
    assert issues[0].line == 3
    assert str(path) in str(issues[0])


def test_case_without_category_is_rejected():
    bad = _case()
    del bad["category"]
    _, issues = parse_dataset(_text({"manifest": MANIFEST}, bad), "x")
    assert [i.code for i in issues] == ["invalid_case"]
    assert "category" in issues[0].message


def test_duplicate_case_id_is_rejected():
    text = _text({"manifest": MANIFEST}, _case(), _case())
    _, issues = parse_dataset(text, "dup")
    assert [i.code for i in issues] == ["duplicate_case_id"]
    assert issues[0].line == 3


def test_case_needs_expected_or_criteria():
    _, issues = parse_dataset(_text({"manifest": MANIFEST}, _case(expected=None)), "x")
    assert issues and issues[0].code == "invalid_case"


def test_criteria_only_case_is_valid():
    text = _text({"manifest": MANIFEST}, _case(expected=None, criteria={"forbidden_tables": ["x"]}))
    dataset, issues = parse_dataset(text, "x")
    assert issues == []
    assert dataset.cases[0].criteria == {"forbidden_tables": ["x"]}


def test_missing_manifest_and_bad_json():
    _, issues = parse_dataset(_text(_case()), "x")
    assert issues[0].code == "missing_manifest"
    _, issues = parse_dataset('{"manifest": ' + json.dumps(MANIFEST) + "}\n{nao json\n", "y")
    assert [i.code for i in issues] == ["invalid_json"]
    assert issues[0].line == 2


def test_empty_dataset_and_unreadable_file(tmp_path):
    _, issues = parse_dataset(_text({"manifest": MANIFEST}), "x")
    assert issues[0].code == "empty_dataset"
    dataset, issues = validate_dataset(tmp_path / "nao-existe.jsonl")
    assert dataset is None and issues[0].code == "unreadable"


def test_load_dataset_raises_with_all_issues(tmp_path):
    path = tmp_path / "bad.jsonl"
    path.write_text(
        _text({"manifest": MANIFEST}, _case(category=""), _case(id="")), encoding="utf-8"
    )
    with pytest.raises(DatasetError) as info:
        load_dataset(path)
    assert len(info.value.issues) == 2


def test_invalid_severity_is_rejected():
    _, issues = parse_dataset(_text({"manifest": MANIFEST}, _case(severity="alta")), "x")
    assert issues[0].code == "invalid_case"
