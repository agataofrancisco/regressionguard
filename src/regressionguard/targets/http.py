"""Adaptador HTTP: avalia um servico externo sem alterar o harness."""

from __future__ import annotations

import time
from typing import Any

import httpx

from regressionguard.targets.base import ConfigError, Target, TargetConfig, TargetOutput


def dig(body: Any, path: str) -> Any:
    """Le um caminho pontilhado (ex.: 'resposta.texto') de forma defensiva."""
    current = body
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _as_str_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if item is not None]


def _as_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _ms_since(started: float) -> float:
    return (time.perf_counter() - started) * 1000.0


class HttpTarget(Target):
    """Envia {"input", "seed"} por POST e mapeia campos da resposta via `field_map`.

    params:
      url (obrigatorio), timeout_s (opcional, por omissao 10),
      field_map: {text, data, citations, retrieved_ids, abstained, cost_usd, trace_id}
      -> caminho pontilhado na resposta JSON.
    """

    def __init__(self, config: TargetConfig, client: httpx.Client | None = None) -> None:
        super().__init__(config)
        url = config.params.get("url")
        if not isinstance(url, str) or not url.startswith(("http://", "https://")):
            raise ConfigError("o alvo http precisa de params.url com http:// ou https://")
        self._url = url
        self._timeout = float(config.params.get("timeout_s", 10))
        self._field_map: dict[str, str] = dict(config.params.get("field_map", {}))
        self._client = client or httpx.Client(timeout=self._timeout)

    @property
    def provider_label(self) -> str:
        return "http"

    def max_cost_per_call(self, case_input: Any) -> float | None:
        """Limite declarado em `params.max_call_usd` (o servico externo e que fixa o custo)."""
        value = self.config.params.get("max_call_usd")
        if value is None:
            return None
        try:
            bound = float(value)
        except (TypeError, ValueError):
            return None
        return bound if bound >= 0 else None

    def _field(self, body: Any, key: str, default: str) -> Any:
        return dig(body, self._field_map.get(key, default))

    def run(self, case_input: Any, *, seed: int | None = None) -> TargetOutput:
        started = time.perf_counter()
        try:
            response = self._client.post(self._url, json={"input": case_input, "seed": seed})
            response.raise_for_status()
            body = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            return TargetOutput(error=f"http: {exc}", latency_ms=_ms_since(started))
        latency = _ms_since(started)
        text = self._field(body, "text", "text")
        data = self._field(body, "data", "data")
        trace = self._field(body, "trace_id", "trace_id")
        return TargetOutput(
            text="" if text is None else str(text),
            data=data if isinstance(data, dict) else None,
            citations=_as_str_list(self._field(body, "citations", "citations")),
            retrieved_ids=_as_str_list(self._field(body, "retrieved_ids", "retrieved_ids")),
            abstained=bool(self._field(body, "abstained", "abstained")),
            cost_usd=_as_float(self._field(body, "cost_usd", "cost_usd")),
            latency_ms=latency,
            trace_id=None if trace is None else str(trace),
        )
