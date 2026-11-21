import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

import regressionguard.runner.run as run_mod
from regressionguard.evaluators.judge import JudgeVerdict
from regressionguard.runner.run import RunOptions, evaluate_output, run_suite
from regressionguard.runner.suites import ConfigSet, Suite
from regressionguard.targets.base import ConfigError, Target, TargetConfig, TargetOutput

ROOT = Path(__file__).resolve().parents[1]
FIXED_NOW = datetime(2026, 11, 20, 12, 0, tzinfo=UTC)
MANIFEST = {
    "name": "t",
    "version": "1.0.0",
    "target": "fake",
    "author": "teste",
    "date": "2026-11-20",
}


class FakeTarget(Target):
    """Alvo de teste: devolve o que a funcao `behave(input, seed)` disser."""

    def __init__(self, config, behave, estimate=0.0):
        super().__init__(config)
        self._behave = behave
        self._estimate = estimate  # float, None ou funcao(case_input) -> float | None
        self.calls = 0

    def max_cost_per_call(self, case_input):
        if callable(self._estimate):
            return self._estimate(case_input)
        return self._estimate

    @property
    def provider_label(self) -> str:
        return "mock"

    def run(self, case_input, *, seed=None):
        self.calls += 1
        return self._behave(case_input, seed)


def _write_dataset(tmp_path: Path, cases: list[dict], name: str = "data.jsonl") -> str:
    lines = [json.dumps({"manifest": MANIFEST})] + [json.dumps(c) for c in cases]
    (tmp_path / name).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return name


def _case(cid: str, expected="ok", evaluators=("exact_match",), severity="normal", **extra) -> dict:
    return {
        "id": cid,
        "input": cid,
        "expected": expected,
        "category": "teste",
        "severity": severity,
        "source": "teste",
        "evaluators": list(evaluators),
        **extra,
    }


def _options(tmp_path, behave, *, datasets, mode="mock", **kwargs) -> RunOptions:
    cfg = TargetConfig(target="fake", version="f1", provider="mock", params={})
    suite = Suite("s", "", tuple(datasets), kwargs.pop("severity", None))
    config_set = ConfigSet("f", {"fake": "fake.yaml"})
    return (
        RunOptions(
            suite=suite,
            config_set=config_set,
            mode=mode,
            root=tmp_path,
            now=lambda: FIXED_NOW,
            **kwargs,
        ),
        cfg,
        behave,
    )


@pytest.fixture
def patch_target(monkeypatch):
    """Substitui a fabrica de alvos por um FakeTarget criado para cada teste."""
    holder = {}

    def factory(config, *, root, mode="mock", http_client=None):
        target = FakeTarget(config, holder["behave"], holder.get("estimate", 0.0))
        holder["target"] = target
        return target

    monkeypatch.setattr(run_mod, "build_target", factory)
    monkeypatch.setattr(
        run_mod, "load_target_config", lambda path: TargetConfig(target="fake", version="f1")
    )
    return holder


def _run(tmp_path, patch_target, behave, datasets, estimate=0.0, **kwargs):
    patch_target["behave"] = behave
    patch_target["estimate"] = estimate
    options, _, _ = _options(tmp_path, behave, datasets=datasets, **kwargs)
    (tmp_path / "fake.yaml").write_text("target: fake\nversion: f1\n", encoding="utf-8")
    return run_suite(options)


def test_repeats_produce_pass_rate_and_flaky_flag(tmp_path, patch_target):
    dataset = _write_dataset(tmp_path, [_case("c1")])

    def behave(case_input, seed):
        # passa nas repeticoes 0, 1 e 2 e falha nas 3 e 4: taxa 0.6
        return TargetOutput(text="ok" if seed % 5 < 3 else "errado", latency_ms=1.0)

    record = _run(tmp_path, patch_target, behave, [dataset], repeats=5)
    case = record.cases[0]
    assert case.pass_rate == pytest.approx(0.6)
    assert case.flaky is True and case.passed is True
    assert case.repeats == 5 and len(case.latencies_ms) == 5


def test_budget_stops_run_and_marks_incomplete(tmp_path, patch_target):
    dataset = _write_dataset(tmp_path, [_case(f"c{i}") for i in range(5)])

    def behave(case_input, seed):
        return TargetOutput(text="ok", cost_usd=0.5)

    record = _run(tmp_path, patch_target, behave, [dataset], estimate=0.5, mode="live", max_usd=1.2)
    assert record.status == "incomplete"
    assert record.incomplete_reason == "budget_reached"
    assert patch_target["target"].calls == 2  # 0.5 + 0.5 = 1.0; o terceiro custaria 1.5 > 1.2
    assert record.summary.cost_usd == pytest.approx(1.0)


def test_live_mode_requires_max_usd(tmp_path, patch_target):
    dataset = _write_dataset(tmp_path, [_case("c1")])
    with pytest.raises(ConfigError, match="max-usd"):
        _run(tmp_path, patch_target, lambda i, s: TargetOutput(text="ok"), [dataset], mode="live")


def test_judge_cannot_rescue_a_deterministic_failure(tmp_path, patch_target):
    (tmp_path / "rubrica.md").write_text("regra", encoding="utf-8")
    case = _case(
        "c1",
        expected={"a": 1},
        evaluators=["json_schema", "llm_judge"],
        criteria={"rubric": "rubrica.md"},
    )
    dataset = _write_dataset(tmp_path, [case])

    class HighJudge:
        def score(self, rubric, *, case_input, expected, output):
            return JudgeVerdict(score=1.0, rationale="excelente")

    record = _run(
        tmp_path,
        patch_target,
        lambda i, s: TargetOutput(data={"errado": True}),
        [dataset],
        judge=HighJudge(),
    )
    assert record.cases[0].passed is False
    assert record.cases[0].pass_rate == 0.0


def test_judge_failure_alone_does_not_fail_a_case(tmp_path, patch_target):
    (tmp_path / "rubrica.md").write_text("regra", encoding="utf-8")
    case = _case(
        "c1",
        expected="ok",
        evaluators=["exact_match", "llm_judge"],
        criteria={"rubric": "rubrica.md"},
    )
    dataset = _write_dataset(tmp_path, [case])

    class LowJudge:
        def score(self, rubric, *, case_input, expected, output):
            return JudgeVerdict(score=0.0, rationale="mau")

    record = _run(
        tmp_path, patch_target, lambda i, s: TargetOutput(text="ok"), [dataset], judge=LowJudge()
    )
    assert record.cases[0].passed is True
    judge_rate = next(e for e in record.cases[0].evaluators if e.evaluator == "llm_judge")
    assert judge_rate.secondary is True and judge_rate.pass_rate == 0.0


def test_secondary_evaluators_are_skipped_without_judge(tmp_path, patch_target):
    case = _case(
        "c1", expected="ok", evaluators=["exact_match", "llm_judge"], criteria={"rubric": "x.md"}
    )
    dataset = _write_dataset(tmp_path, [case])
    record = _run(tmp_path, patch_target, lambda i, s: TargetOutput(text="ok"), [dataset])
    assert [e.evaluator for e in record.cases[0].evaluators] == ["exact_match"]


def test_evaluator_exception_is_contained(tmp_path, patch_target, monkeypatch):
    from regressionguard.evaluators import registry

    def boom(ctx):
        raise RuntimeError("bug no avaliador")

    monkeypatch.setitem(
        registry._REGISTRY,
        "boom",
        registry.EvaluatorSpec("boom", boom, False, False, ""),
    )
    dataset = _write_dataset(
        tmp_path, [_case("c1", evaluators=["boom"]), _case("c2", evaluators=["exact_match"])]
    )
    record = _run(tmp_path, patch_target, lambda i, s: TargetOutput(text="ok"), [dataset])
    by_id = {c.case_id: c for c in record.cases}
    assert by_id["c1"].passed is False
    assert by_id["c1"].evaluations[0].reason == "evaluator_error:RuntimeError"
    assert by_id["c2"].passed is True  # a run continua


def test_target_exception_becomes_error_output(tmp_path, patch_target):
    dataset = _write_dataset(tmp_path, [_case("c1")])

    def behave(case_input, seed):
        raise ValueError("falhou")

    record = _run(tmp_path, patch_target, behave, [dataset])
    assert record.cases[0].error_rate == 1.0
    assert record.cases[0].passed is False


def test_severity_filter_selects_critical_cases_only(tmp_path, patch_target):
    dataset = _write_dataset(
        tmp_path,
        [_case("c1", severity="critical"), _case("c2", severity="normal")],
    )
    record = _run(
        tmp_path, patch_target, lambda i, s: TargetOutput(text="ok"), [dataset], severity="critical"
    )
    assert [c.case_id for c in record.cases] == ["c1"]


def test_evaluate_output_marks_primary_failure():
    from regressionguard.datasets.models import Case

    case = Case(
        id="x",
        input="i",
        expected="ok",
        category="c",
        severity="normal",
        source="s",
        evaluators=["exact_match"],
    )
    records, passed = evaluate_output(case, TargetOutput(text="nao"), ROOT, judge=None)
    assert passed is False and records[0].reason == "exact_mismatch"


def test_mock_run_on_real_suite_is_reproducible():
    from regressionguard.runner.suites import load_config_set, load_suite

    suite = load_suite(ROOT, "full")
    config = load_config_set(ROOT, "v1")
    opts = RunOptions(suite=suite, config_set=config, mode="mock", root=ROOT, now=lambda: FIXED_NOW)
    first = run_suite(opts)
    second = run_suite(opts)
    assert [c.model_dump() for c in first.cases] == [c.model_dump() for c in second.cases]
    assert first.summary == second.summary
    assert first.latency_source == "synthetic-mock"


def test_first_call_that_would_exceed_cap_is_never_made(tmp_path, patch_target):
    dataset = _write_dataset(tmp_path, [_case("c1"), _case("c2")])
    record = _run(
        tmp_path,
        patch_target,
        lambda i, s: TargetOutput(text="ok", cost_usd=0.0),
        [dataset],
        estimate=2.0,
        mode="live",
        max_usd=1.0,
    )
    assert patch_target["target"].calls == 0
    assert record.status == "incomplete" and record.incomplete_reason == "budget_reached"
    assert record.cases == []


def test_mid_run_large_call_is_not_made(tmp_path, patch_target):
    dataset = _write_dataset(
        tmp_path,
        [
            _case("c1"),
            _case("c2"),
            _case("c3"),
        ],
    )
    bounds = {"c1": 0.4, "c2": 0.4, "c3": 0.9}
    # o custo real de cada chamada e igual ao limite a priori (pior caso)
    record = _run(
        tmp_path,
        patch_target,
        lambda i, s: TargetOutput(text="ok", cost_usd=bounds[i]),
        [dataset],
        estimate=lambda case_input: bounds[case_input],
        mode="live",
        max_usd=1.0,
    )
    # 0.4 + 0.4 cabem; o terceiro (0.8 + 0.9 = 1.7 > 1.0) nao e feito
    assert patch_target["target"].calls == 2
    assert [c.case_id for c in record.cases] == ["c1", "c2"]
    assert record.incomplete_reason == "budget_reached"


def test_missing_cost_bound_refuses_before_any_call(tmp_path, patch_target):
    dataset = _write_dataset(tmp_path, [_case("c1"), _case("c2")])
    with pytest.raises(ConfigError, match="custo maximo"):
        _run(
            tmp_path,
            patch_target,
            lambda i, s: TargetOutput(text="ok"),
            [dataset],
            estimate=None,
            mode="live",
            max_usd=1.0,
        )
    assert patch_target["target"].calls == 0


def test_provider_cost_above_bound_is_reported_not_hidden(tmp_path, patch_target):
    dataset = _write_dataset(tmp_path, [_case("c1"), _case("c2")])
    record = _run(
        tmp_path,
        patch_target,
        lambda i, s: TargetOutput(text="ok", cost_usd=5.0),
        [dataset],
        estimate=0.1,
        mode="live",
        max_usd=100.0,
    )
    assert record.status == "incomplete"
    assert record.incomplete_reason == "provider_cost_above_bound"
    assert patch_target["target"].calls == 1


def test_live_run_with_fake_transport_never_exceeds_cap(tmp_path, monkeypatch):
    """Ponta a ponta com ChatClient real e transporte falso: o gasto nunca passa o teto."""
    import json

    import httpx

    import regressionguard.runner.run as run_module
    from regressionguard.runner.run import RunOptions, run_suite
    from regressionguard.runner.suites import ConfigSet, Suite

    NL = chr(10)
    monkeypatch.setenv("REGRESSIONGUARD_API_KEY", "chave-falsa")
    live_yaml = (
        NL.join(
            [
                "target: extraction",
                "version: live-test",
                "provider: mock",
                "params:",
                "  live:",
                "    model: modelo-teste",
                "    price_input_per_1k: 0.01",
                "    price_output_per_1k: 0.02",
                "    max_tokens: 512",
            ]
        )
        + NL
    )
    (tmp_path / "live.yaml").write_text(live_yaml, encoding="utf-8")
    cases = [
        {
            "id": f"e{i:02d}",
            "input": f"PED-{i:04d} 1x Caneca total 2,00 euros",
            "expected": "x",
            "category": "teste",
            "severity": "normal",
            "source": "teste",
            "evaluators": ["exact_match"],
        }
        for i in range(40)
    ]
    manifest = {
        "name": "t",
        "version": "1",
        "target": "extraction",
        "author": "a",
        "date": "2026-11-21",
    }
    lines = [json.dumps({"manifest": manifest})] + [json.dumps(c) for c in cases]
    (tmp_path / "data.jsonl").write_text(NL.join(lines) + NL, encoding="utf-8")

    requests = []

    def handler(request):
        requests.append(request)
        # uso real pequeno: 30 tokens de entrada e 10 de saida, abaixo do limite a priori
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "{}"}}],
                "usage": {"prompt_tokens": 30, "completion_tokens": 10},
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    max_usd = 0.03
    options = RunOptions(
        suite=Suite("s", "", ("data.jsonl",), None),
        config_set=ConfigSet("live", {"extraction": "live.yaml"}),
        mode="live",
        root=tmp_path,
        max_usd=max_usd,
        http_client=client,
        now=lambda: FIXED_NOW,
    )
    record = run_suite(options)
    assert record.summary.cost_usd <= max_usd
    assert record.status == "incomplete" and record.incomplete_reason == "budget_reached"
    assert len(requests) == len(record.cases) < len(cases)
    assert len(requests) > 0
    assert all(json.loads(r.content)["max_tokens"] == 512 for r in requests)
    assert run_module.BUDGET_REACHED == "budget_reached"
