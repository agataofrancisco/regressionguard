import json
from pathlib import Path

import httpx
import pytest

from regressionguard.datasets import load_dataset
from regressionguard.targets.base import ConfigError, TargetConfig, load_target_config
from regressionguard.targets.extraction import ExtractionTarget, rule_extract
from regressionguard.targets.factory import build_target
from regressionguard.targets.http import HttpTarget, dig
from regressionguard.targets.live import ChatClient
from regressionguard.targets.minirag import MiniRagTarget, load_corpus, retrieve, sql_plan

ROOT = Path(__file__).resolve().parents[1]


def _cfg(target: str, **params) -> TargetConfig:
    return TargetConfig(target=target, version="t", provider="mock", params=params)


def test_rule_extract_matches_clean_message():
    text = (
        "Boa tarde.\nEncomenda PED-1042.\n- 2x Caneca 350ml\n- 1x Mochila 20L\n"
        "Total: 45,90€\nSou cliente ouro."
    )
    assert rule_extract(text) == {
        "order_id": "PED-1042",
        "customer_tier": "ouro",
        "items": [{"name": "Caneca 350ml", "qty": 2}, {"name": "Mochila 20L", "qty": 1}],
        "total": 45.9,
        "refund_requested": False,
    }


def test_rule_extract_is_defensive_with_odd_input():
    for odd in ["", "   ", "1x\n", "total ,,", "PED-1"]:
        result = rule_extract(odd)
        assert set(result) == {"order_id", "customer_tier", "items", "total", "refund_requested"}


def test_extraction_field_map_renames_output():
    target = ExtractionTarget(_cfg("extraction", field_map={"total": "total_eur"}))
    out = target.run("PED-1\n1x Pincel\nTotal: 2,00€")
    assert "total_eur" in out.data and "total" not in out.data
    assert out.latency_ms > 0 and out.cost_usd == 0.0 and target.provider_label == "mock"


def test_mock_targets_are_reproducible_on_golden_inputs():
    dataset = load_dataset(ROOT / "datasets/extraction/golden.jsonl")
    target = ExtractionTarget(load_target_config(ROOT / "targets/extraction/configs/v1.yaml"))
    first = [target.run(case.input).model_dump() for case in dataset.cases]
    second = [target.run(case.input).model_dump() for case in dataset.cases]
    assert first == second

    rag = load_dataset(ROOT / "datasets/minirag/golden.jsonl")
    corpus = load_corpus(ROOT / "targets/minirag/faq.json")
    rag_target = MiniRagTarget(load_target_config(ROOT / "targets/minirag/configs/v1.yaml"), corpus)
    run_a = [rag_target.run(case.input).model_dump() for case in rag.cases]
    run_b = [rag_target.run(case.input).model_dump() for case in rag.cases]
    assert run_a == run_b


def test_retrieve_respects_top_k_and_orders_by_overlap():
    corpus = load_corpus(ROOT / "targets/minirag/faq.json")
    assert len(retrieve("Quanto custa o plano Fibra 300?", corpus, 5)) <= 5
    assert len(retrieve("Quanto custa o plano Fibra 300?", corpus, 1)) == 1
    assert retrieve("qualquer coisa sem sobreposicao zzz", corpus, 5) == []
    assert retrieve("plano", corpus, 0) == []


def test_minirag_abstains_and_refuses_writes():
    corpus = load_corpus(ROOT / "targets/minirag/faq.json")
    target = MiniRagTarget(_cfg("minirag", top_k=5), corpus)
    assert target.run("Vendem seguros de viagem?").abstained is True
    refused = target.run("Apaga a encomenda PED-1042 da base de dados.")
    assert refused.abstained and refused.sql == [] and refused.tool_calls == []


def test_sql_plan_is_select_only_and_extra_tables_are_explicit():
    queries, tables = sql_plan("estado de PED-1042", [])
    assert queries == ["SELECT status FROM orders WHERE order_id = 'PED-1042'"]
    assert tables == ["orders"]
    queries, tables = sql_plan("estado de PED-1042", ["customers"])
    assert tables == ["orders", "customers"] and queries[-1].startswith("SELECT * FROM customers")
    assert sql_plan("sem encomenda", ["customers"]) == ([], [])


def test_citations_only_when_enabled():
    corpus = load_corpus(ROOT / "targets/minirag/faq.json")
    question = "Quanto custa o plano Fibra 300?"
    on = MiniRagTarget(_cfg("minirag", citations=True), corpus).run(question)
    off = MiniRagTarget(_cfg("minirag", citations=False), corpus).run(question)
    assert on.citations and "[" in on.text
    assert off.citations == [] and "[" not in off.text


def test_load_corpus_rejects_bad_entries(tmp_path):
    bad = tmp_path / "faq.json"
    bad.write_text(
        json.dumps([{"id": "a", "text": "x"}, {"id": "a", "text": "y"}]), encoding="utf-8"
    )
    with pytest.raises(ConfigError, match="duplicado"):
        load_corpus(bad)
    bad.write_text(json.dumps([{"id": 1}]), encoding="utf-8")
    with pytest.raises(ConfigError):
        load_corpus(bad)


def test_http_target_maps_fields_with_mock_transport():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "resposta": {"texto": "Fibra 300 custa 25 euros."},
                "fontes": ["faq-001"],
                "trace": "abc",
            },
        )

    config = TargetConfig(
        target="minirag",
        version="http-v1",
        provider="http",
        params={
            "url": "https://exemplo.test/ask",
            "field_map": {"text": "resposta.texto", "citations": "fontes", "trace_id": "trace"},
        },
    )
    target = HttpTarget(config, client=httpx.Client(transport=httpx.MockTransport(handler)))
    out = target.run("Quanto custa?", seed=7)
    assert seen["body"] == {"input": "Quanto custa?", "seed": 7}
    assert out.text == "Fibra 300 custa 25 euros." and out.citations == ["faq-001"]
    assert out.trace_id == "abc" and out.error is None and target.provider_label == "http"


def test_http_target_reports_errors_instead_of_raising():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"erro": "x"})

    config = TargetConfig(
        target="x", version="v", provider="http", params={"url": "https://exemplo.test"}
    )
    out = HttpTarget(config, client=httpx.Client(transport=httpx.MockTransport(handler))).run("a")
    assert out.error and out.error.startswith("http:")


def test_http_target_requires_valid_url():
    with pytest.raises(ConfigError):
        HttpTarget(
            TargetConfig(target="x", version="v", provider="http", params={"url": "ftp://x"})
        )


def test_dig_is_defensive():
    assert dig({"a": {"b": 1}}, "a.b") == 1
    assert dig({"a": 1}, "a.b") is None
    assert dig(None, "a") is None


def test_live_mode_refuses_without_live_params_and_without_key(monkeypatch):
    with pytest.raises(ConfigError, match="config_not_live"):
        build_target(_cfg("extraction"), root=ROOT, mode="live")
    live_cfg = TargetConfig(
        target="extraction",
        version="v",
        params={"live": {"model": "m", "price_input_per_1k": 0.1, "price_output_per_1k": 0.2}},
    )
    monkeypatch.delenv("REGRESSIONGUARD_API_KEY", raising=False)
    with pytest.raises(ConfigError, match="variavel de ambiente"):
        build_target(live_cfg, root=ROOT, mode="live")


def test_live_mode_requires_prices(monkeypatch):
    monkeypatch.setenv("REGRESSIONGUARD_TEST_KEY", "fake")
    with pytest.raises(ConfigError, match="obrigatorios"):
        ChatClient.from_params({"model": "m", "api_key_env": "REGRESSIONGUARD_TEST_KEY"})


def test_live_client_computes_cost_from_usage():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer chave-falsa"
        body = json.loads(request.content)
        assert body["temperature"] == 0 and body["seed"] == 3
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": '{"order_id": null}'}}],
                "usage": {"prompt_tokens": 2000, "completion_tokens": 500},
            },
        )

    client = ChatClient(
        model="m",
        api_key="chave-falsa",
        price_input_per_1k=0.001,
        price_output_per_1k=0.002,
        http=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    result = client.complete([{"role": "user", "content": "x"}], seed=3)
    assert result.text == '{"order_id": null}'
    assert result.cost_usd == pytest.approx(2 * 0.001 + 0.5 * 0.002)


def test_unknown_target_and_mode_are_config_errors():
    with pytest.raises(ConfigError):
        build_target(_cfg("inexistente"), root=ROOT, mode="mock")
    with pytest.raises(ConfigError):
        build_target(_cfg("extraction"), root=ROOT, mode="turbo")


def test_load_target_config_errors(tmp_path):
    bad = tmp_path / "x.yaml"
    bad.write_text("target: x\n", encoding="utf-8")
    with pytest.raises(ConfigError):
        load_target_config(bad)
    with pytest.raises(ConfigError):
        load_target_config(tmp_path / "nao-existe.yaml")
