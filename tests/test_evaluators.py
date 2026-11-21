from pathlib import Path

import pytest

from regressionguard.datasets.models import Case
from regressionguard.evaluators import deterministic as det
from regressionguard.evaluators import judge as judge_mod
from regressionguard.evaluators import semantic as sem
from regressionguard.evaluators.registry import EvalContext, UnknownEvaluator, get, names
from regressionguard.targets.base import TargetOutput

ROOT = Path(__file__).resolve().parents[1]


def _case(expected=None, criteria=None, evaluators=("exact_match",)):
    if expected is None and not criteria:
        expected = "referencia"  # o modelo exige um label; os testes de SQL/schema nao o usam
    return Case(
        id="t-1",
        input="entrada",
        expected=expected,
        criteria=criteria or {},
        category="teste",
        severity="normal",
        source="teste",
        evaluators=list(evaluators),
    )


def _ctx(output: TargetOutput, expected=None, criteria=None) -> EvalContext:
    return EvalContext(case=_case(expected=expected, criteria=criteria), output=output, root=ROOT)


VALID_EXTRACTION = {
    "order_id": "PED-1042",
    "customer_tier": "ouro",
    "items": [{"name": "Caneca", "qty": 2}],
    "total": 45.9,
    "refund_requested": False,
}


# ---- registo -------------------------------------------------------------


def test_all_builtin_evaluators_are_registered():
    expected = {
        "json_schema",
        "tool_called",
        "forbidden_access",
        "citations_exist",
        "sql_read_only",
        "exact_match",
        "token_f1",
        "field_f1",
        "similarity",
        "llm_judge",
    }
    assert expected <= set(names())
    assert get("llm_judge").secondary is True
    assert get("sql_read_only").security is True


def test_unknown_evaluator_raises_domain_error():
    with pytest.raises(UnknownEvaluator):
        get("nao-existe")


# ---- deterministicos (positivos e negativos) ----------------------------


def test_json_schema_accepts_valid_extraction():
    result = det.json_schema(_ctx(TargetOutput(data=VALID_EXTRACTION)))
    assert result.passed and result.reason is None


def test_json_schema_names_missing_field_after_rename():
    renamed = {**VALID_EXTRACTION, "total_eur": VALID_EXTRACTION["total"]}
    del renamed["total"]
    result = det.json_schema(_ctx(TargetOutput(data=renamed)))
    assert not result.passed
    assert result.reason == "schema_invalid:required:total"


def test_json_schema_rejects_wrong_types_and_bad_order_id():
    bad = {**VALID_EXTRACTION, "order_id": "1042", "refund_requested": "nao"}
    result = det.json_schema(_ctx(TargetOutput(data=bad)))
    assert not result.passed and result.reason.startswith("schema_invalid:")


def test_json_schema_without_output_fails_with_reason():
    result = det.json_schema(_ctx(TargetOutput(error="provider: timeout")))
    assert result.passed is False and result.reason == "no_structured_output"


def test_tool_called_exact_match_and_wrong_tool():
    ok = _ctx(TargetOutput(tool_calls=["sql_read"]), criteria={"expected_tools": ["sql_read"]})
    assert det.tool_called(ok).passed
    wrong = _ctx(TargetOutput(tool_calls=["web"]), criteria={"expected_tools": ["sql_read"]})
    result = det.tool_called(wrong)
    assert not result.passed and result.reason == "wrong_tool:web"
    none_expected = _ctx(TargetOutput(tool_calls=[]), criteria={"expected_tools": []})
    assert det.tool_called(none_expected).passed


def test_forbidden_access_flags_forbidden_table():
    crit = {"forbidden_tables": ["customers", "payments"]}
    assert det.forbidden_access(
        _ctx(TargetOutput(accessed_tables=["orders"]), criteria=crit)
    ).passed
    result = det.forbidden_access(
        _ctx(TargetOutput(accessed_tables=["orders", "customers"]), criteria=crit)
    )
    assert not result.passed and result.reason == "forbidden_access:customers"


def test_citations_missing_when_required():
    result = det.citations_exist(
        _ctx(TargetOutput(retrieved_ids=["faq-001"]), criteria={"requires_citation": True})
    )
    assert not result.passed and result.reason == "missing_citation"
    optional = det.citations_exist(_ctx(TargetOutput(retrieved_ids=["faq-001"])))
    assert optional.passed


def test_citation_not_in_context_is_rejected():
    out = TargetOutput(citations=["faq-999"], retrieved_ids=["faq-001"])
    result = det.citations_exist(_ctx(out, criteria={"requires_citation": True}))
    assert not result.passed and result.reason == "citation_not_in_context:faq-999"


def test_citations_existing_in_context_pass():
    out = TargetOutput(citations=["faq-001"], retrieved_ids=["faq-001", "faq-002"])
    assert det.citations_exist(_ctx(out, criteria={"requires_citation": True})).passed


@pytest.mark.parametrize(
    ("sql", "reason"),
    [
        ("UPDATE orders SET status = 'x'", "sql:write_statement"),
        ("DELETE FROM orders", "sql:write_statement"),
        ("DROP TABLE orders", "sql:write_statement"),
        ("SELECT 1; DROP TABLE orders", "sql:multiple_statements"),
        ("SELECT * FROM (", "sql:parse_error"),
        ("GRANT ALL ON orders TO bob", "sql:non_select:grant"),
    ],
)
def test_sql_read_only_rejects_writes_and_multi_statements(sql, reason):
    result = det.sql_read_only(_ctx(TargetOutput(sql=[sql])))
    assert not result.passed and result.reason == reason


def test_sql_read_only_accepts_select_queries():
    out = TargetOutput(sql=["SELECT status FROM orders WHERE order_id = 'PED-1'", "SELECT 1"])
    result = det.sql_read_only(_ctx(out))
    assert result.passed and result.details["checked"] == 2


# ---- semanticos com valores calculados a mao ---------------------------


def test_exact_match_declares_normalization():
    result = sem.exact_match(_ctx(TargetOutput(text=" lisboa "), expected="Lisboa"))
    assert result.passed
    assert result.details["normalization"] == ["strip", "casefold"]


def test_exact_match_fails_on_different_text():
    result = sem.exact_match(_ctx(TargetOutput(text="Porto"), expected="Lisboa"))
    assert not result.passed and result.reason == "exact_mismatch"


def test_token_f1_matches_hand_computed_value():
    # esperado "a b c d" (4 tokens), saida "a b x" (3 tokens): comuns = 2
    # precisao = 2/3, cobertura = 2/4, F1 = 2*(2/3)*(1/2)/((2/3)+(1/2)) = 4/7
    precision, recall, f1 = sem.token_f1_scores("a b c d", "a b x")
    assert precision == pytest.approx(2 / 3)
    assert recall == pytest.approx(0.5)
    assert f1 == pytest.approx(4 / 7)


def test_token_f1_threshold_and_normalization_details():
    result = sem.token_f1(
        _ctx(
            TargetOutput(text="O plano custa 25 euros [faq-001]."),
            expected="O plano custa 25 euros.",
        )
    )
    assert result.passed and result.score == pytest.approx(1.0)
    assert "strip_citations" in result.details["normalization"]
    low = sem.token_f1(
        _ctx(TargetOutput(text="x y"), expected="a b c d", criteria={"threshold": 0.7})
    )
    assert not low.passed and low.reason == "f1_below_threshold"


def test_field_f1_hand_computed_threshold():
    # 5 campos no esperado e 5 na saida; 4 coincidem: precisao = cobertura = 0.8, F1 = 0.8
    renamed = {**VALID_EXTRACTION, "total": 99.0}
    ctx = _ctx(TargetOutput(data=renamed), expected=VALID_EXTRACTION)
    assert not sem.field_f1(ctx).passed  # limiar por omissao 0.9
    lower = sem.field_f1(
        _ctx(TargetOutput(data=renamed), expected=VALID_EXTRACTION, criteria={"threshold": 0.79})
    )
    assert lower.passed and lower.details["f1"] == pytest.approx(0.8)
    assert lower.details["numeric_tolerance"] == sem.NUMERIC_TOLERANCE


def test_field_f1_perfect_match_scores_one():
    result = sem.field_f1(_ctx(TargetOutput(data=VALID_EXTRACTION), expected=VALID_EXTRACTION))
    assert result.passed and result.score == pytest.approx(1.0)


def test_values_equal_rules():
    assert sem.values_equal(12.5, 12.504)
    assert not sem.values_equal(12.5, 12.52)
    assert sem.values_equal(None, None) and not sem.values_equal(None, 0)
    assert sem.values_equal(False, False) and not sem.values_equal(False, 0)
    assert sem.values_equal("Cabo USB", " cabo usb ")
    assert sem.values_equal(
        [{"name": "a", "qty": 1}, {"name": "b", "qty": 2}],
        [{"name": "b", "qty": 2}, {"name": "a", "qty": 1}],
    )
    assert not sem.values_equal([1, 2], [1, 2, 3])


def test_similarity_hand_value():
    # difflib: 2*M/T com M=2 (ab) e T=6 -> 4/6 = 0.6667 para "abc" vs "abd"
    result = sem.similarity(
        _ctx(TargetOutput(text="abd"), expected="abc", criteria={"threshold": 0.6})
    )
    assert result.passed and result.score == pytest.approx(2 / 3, rel=1e-4)


# ---- juiz LLM (sinal secundario) ---------------------------------------


class _FakeJudge:
    def __init__(self, score: float) -> None:
        self._score = score

    def score(self, rubric, *, case_input, expected, output):
        assert "rubrica" in rubric.lower() or rubric
        return judge_mod.JudgeVerdict(score=self._score, rationale="fake")


def test_llm_judge_is_skipped_without_judge():
    ctx = _ctx(TargetOutput(text="x"), criteria={"rubric": "targets/minirag/faq.json"})
    result = judge_mod.llm_judge(ctx)
    assert result.reason == "judge_disabled"


def test_llm_judge_records_rubric_hash_and_threshold(tmp_path):
    rubric = tmp_path / "rubrica.md"
    rubric.write_text("Avalia a fidelidade da resposta.", encoding="utf-8")
    ctx = EvalContext(
        case=_case(expected="x", criteria={"rubric": "rubrica.md", "threshold": 0.6}),
        output=TargetOutput(text="x"),
        root=tmp_path,
        judge=_FakeJudge(0.8),
    )
    result = judge_mod.llm_judge(ctx)
    assert result.passed and result.details["signal"] == "secondary"
    assert len(result.details["rubric_sha256"]) == 64


def test_llm_judge_low_score_fails(tmp_path):
    (tmp_path / "r.md").write_text("regra", encoding="utf-8")
    ctx = EvalContext(
        case=_case(expected="x", criteria={"rubric": "r.md"}),
        output=TargetOutput(text="x"),
        root=tmp_path,
        judge=_FakeJudge(0.1),
    )
    result = judge_mod.llm_judge(ctx)
    assert not result.passed and result.reason == "judge_low_score"


def test_cohens_kappa_hand_computed_value():
    # juiz [T,T,F,F], humanos [T,F,F,F]: concordancia 3/4; pe = 0.5*0.25 + 0.5*0.75 = 0.5
    # kappa = (0.75 - 0.5) / (1 - 0.5) = 0.5
    calibration = judge_mod.cohens_kappa([True, True, False, False], [True, False, False, False])
    assert calibration.n == 4
    assert calibration.agreement == pytest.approx(0.75)
    assert calibration.kappa == pytest.approx(0.5)


def test_cohens_kappa_edge_cases():
    perfect = judge_mod.cohens_kappa([True, False], [True, False])
    assert perfect.kappa == pytest.approx(1.0)
    with pytest.raises(ValueError):
        judge_mod.cohens_kappa([True], [True, False])
    with pytest.raises(ValueError):
        judge_mod.cohens_kappa([], [])


def test_calibrate_binarizes_scores_with_threshold():
    calibration = judge_mod.calibrate(
        [0.9, 0.2, 0.7, 0.4], [True, False, True, True], threshold=0.5
    )
    assert calibration.n == 4
    assert calibration.agreement == pytest.approx(0.75)
