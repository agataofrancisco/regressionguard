"""Contrato dos alvos (sistemas avaliados) e configuracao versionada."""

from __future__ import annotations

import hashlib
import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError


class ConfigError(ValueError):
    """Configuracao de alvo invalida ou incompleta."""


class TargetOutput(BaseModel):
    """Saida normalizada de qualquer alvo. Os avaliadores so leem este modelo."""

    model_config = ConfigDict(extra="forbid")

    text: str = ""
    data: dict[str, Any] | None = None
    citations: list[str] = Field(default_factory=list)
    retrieved_ids: list[str] = Field(default_factory=list)
    tool_calls: list[str] = Field(default_factory=list)
    sql: list[str] = Field(default_factory=list)
    accessed_tables: list[str] = Field(default_factory=list)
    abstained: bool = False
    error: str | None = None
    cost_usd: float = 0.0
    latency_ms: float = 0.0
    trace_id: str | None = None


class TargetConfig(BaseModel):
    """Configuracao de um alvo: uma 'versao' do sistema (prompt, parametros, modelo)."""

    model_config = ConfigDict(extra="forbid")

    target: str = Field(min_length=1)
    version: str = Field(min_length=1)
    provider: Literal["mock", "http"] = "mock"
    params: dict[str, Any] = Field(default_factory=dict)

    def config_hash(self) -> str:
        text = json.dumps(self.model_dump(mode="json"), sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_target_config(path: Path | str) -> TargetConfig:
    """Le um YAML de configuracao de alvo. Lanca ConfigError com a causa."""
    file_path = Path(path)
    try:
        raw = yaml.safe_load(file_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ConfigError(f"nao foi possivel ler {file_path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ConfigError(f"{file_path}: a configuracao tem de ser um mapa YAML")
    try:
        return TargetConfig.model_validate(raw)
    except ValidationError as exc:
        raise ConfigError(f"{file_path}: {exc.errors()[0]['msg']}") from exc


class Target(ABC):
    """Adaptador de um sistema de IA. `run` devolve erros em `TargetOutput.error`."""

    def __init__(self, config: TargetConfig) -> None:
        self.config = config

    @property
    def name(self) -> str:
        return self.config.target

    @property
    @abstractmethod
    def provider_label(self) -> str:
        """Etiqueta do provedor para relatorios: 'mock', 'live:<modelo>' ou 'http'."""

    def max_cost_per_call(self, case_input: Any) -> float | None:
        """Limite superior do custo (USD) de UMA chamada, calculado ANTES de a fazer.

        None = desconhecido. Em `--mode live` um alvo sem limite a priori nao corre (ConfigError,
        sem chamadas feitas). Por omissao o alvo nao declara limite.
        """
        return None

    @abstractmethod
    def run(self, case_input: Any, *, seed: int | None = None) -> TargetOutput:
        """Executa o alvo sobre o input de um caso."""
