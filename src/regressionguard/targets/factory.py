"""Constroi o adaptador de um alvo a partir da configuracao e do modo de execucao."""

from __future__ import annotations

from pathlib import Path

import httpx

from regressionguard.targets.base import ConfigError, Target, TargetConfig
from regressionguard.targets.extraction import ExtractionTarget
from regressionguard.targets.http import HttpTarget
from regressionguard.targets.live import ChatClient
from regressionguard.targets.minirag import MiniRagTarget, load_corpus

MODES = ("mock", "live")


def build_target(
    config: TargetConfig,
    *,
    root: Path,
    mode: str = "mock",
    http_client: httpx.Client | None = None,
) -> Target:
    """Escolhe a implementacao: http (externo), mock (regras) ou live (LLM).

    `mode=live` exige `params.live` na configuracao; sem isso recusa em vez de
    fingir que houve execucao real.
    """
    if mode not in MODES:
        raise ConfigError(f"modo desconhecido: {mode}")
    if config.provider == "http":
        return HttpTarget(config, client=http_client)

    llm: ChatClient | None = None
    if mode == "live":
        live = config.params.get("live")
        if not isinstance(live, dict):
            raise ConfigError(f"config_not_live: '{config.version}' nao tem params.live")
        llm = ChatClient.from_params(live, http=http_client)

    if config.target == "extraction":
        return ExtractionTarget(config, llm)
    if config.target == "minirag":
        corpus = load_corpus(root / str(config.params.get("corpus", "targets/minirag/faq.json")))
        return MiniRagTarget(config, corpus, llm)
    raise ConfigError(f"alvo desconhecido: {config.target}")
