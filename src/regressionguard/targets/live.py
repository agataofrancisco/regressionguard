"""Cliente LLM compativel com OpenAI, usado apenas em `--mode live`.

Nunca e chamado em mock nem em CI. A chave vem de uma variavel de ambiente (nunca de ficheiros
do repositorio). O custo e calculado a partir do `usage` devolvido e dos precos declarados
na configuracao do alvo: um preco errado da um custo errado.
"""

from __future__ import annotations

import math
import os
import time
from dataclasses import dataclass
from typing import Any

import httpx

from regressionguard.targets.base import ConfigError

DEFAULT_BASE_URL = "https://api.openai.com/v1"


@dataclass(frozen=True)
class ChatResult:
    text: str
    cost_usd: float
    latency_ms: float


class ChatClient:
    """Chamada `chat/completions` com temperatura 0 e seed quando suportada."""

    def __init__(
        self,
        *,
        model: str,
        api_key: str,
        price_input_per_1k: float,
        price_output_per_1k: float,
        max_tokens: int,
        base_url: str = DEFAULT_BASE_URL,
        timeout_s: float = 60.0,
        http: httpx.Client | None = None,
    ) -> None:
        self.model = model
        self._api_key = api_key
        self._price_in = price_input_per_1k
        self._price_out = price_output_per_1k
        self._max_tokens = max_tokens
        self._base_url = base_url.rstrip("/")
        self._http = http or httpx.Client(timeout=timeout_s)

    @classmethod
    def from_params(cls, live: dict[str, Any], http: httpx.Client | None = None) -> ChatClient:
        """Constroi o cliente a partir de `params.live` da configuracao do alvo."""
        model = live.get("model")
        if not isinstance(model, str) or not model:
            raise ConfigError("params.live.model em falta")
        env_name = str(live.get("api_key_env", "REGRESSIONGUARD_API_KEY"))
        api_key = os.environ.get(env_name, "")
        if not api_key:
            raise ConfigError(f"a variavel de ambiente {env_name} nao esta definida")
        prices = [live.get("price_input_per_1k"), live.get("price_output_per_1k")]
        if any(price is None for price in prices):
            raise ConfigError(
                "params.live.price_input_per_1k e price_output_per_1k sao obrigatorios "
                "(sem precos o custo nao e medido e o --max-usd nao tem significado)"
            )
        max_tokens = live.get("max_tokens")
        if not isinstance(max_tokens, int) or isinstance(max_tokens, bool) or max_tokens < 1:
            raise ConfigError(
                "params.live.max_tokens e obrigatorio (inteiro >= 1): sem limite de saida "
                "nao ha limite de custo a priori"
            )
        return cls(
            model=model,
            api_key=api_key,
            price_input_per_1k=float(prices[0]),
            price_output_per_1k=float(prices[1]),
            max_tokens=max_tokens,
            base_url=str(
                live.get("base_url", os.environ.get("REGRESSIONGUARD_BASE_URL", DEFAULT_BASE_URL))
            ),
            http=http,
        )

    def worst_case_cost(self, messages: list[dict[str, str]]) -> float:
        """Limite superior do custo de UMA chamada, calculado ANTES de a fazer.

        Pressuposto conservador: um token ocupa pelo menos 3 caracteres, por isso
        ceil(chars/3) e um limite superior dos tokens de entrada em texto PT/EN.
        A saida e limitada por `max_tokens`, que e enviado no pedido.
        """
        chars = sum(len(str(message.get("content", ""))) for message in messages)
        prompt_tokens_bound = math.ceil(chars / 3)
        return (
            prompt_tokens_bound / 1000.0 * self._price_in
            + self._max_tokens / 1000.0 * self._price_out
        )

    def complete(self, messages: list[dict[str, str]], *, seed: int | None = None) -> ChatResult:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": 0,
            "max_tokens": self._max_tokens,
        }
        if seed is not None:
            payload["seed"] = seed
        started = time.perf_counter()
        response = self._http.post(
            f"{self._base_url}/chat/completions",
            json=payload,
            headers={"Authorization": f"Bearer {self._api_key}"},
        )
        response.raise_for_status()
        body = response.json()
        latency = (time.perf_counter() - started) * 1000.0
        choices = body.get("choices") or [{}]
        text = str((choices[0].get("message") or {}).get("content") or "")
        usage = body.get("usage") or {}
        cost = (
            float(usage.get("prompt_tokens", 0)) / 1000.0 * self._price_in
            + float(usage.get("completion_tokens", 0)) / 1000.0 * self._price_out
        )
        return ChatResult(text=text, cost_usd=cost, latency_ms=latency)
