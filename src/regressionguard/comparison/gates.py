"""Gates versionados (config/gates.yaml): carregamento e modelos. A avaliacao esta em engine.py."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from regressionguard.targets.base import ConfigError

Metric = Literal[
    "new_failures",
    "critical_pass_rate_drop",
    "pass_rate_drop",
    "latency_p95_increase",
    "cost_per_case_increase",
]


class GateSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    severity: Literal["critical", "warning"]
    metric: Metric
    evaluators: list[str] = Field(default_factory=list)
    threshold: float = Field(ge=0)
    description: str = ""


class GatesConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    min_cases: int = Field(default=30, ge=1)
    max_ci_width: float = Field(default=0.20, gt=0)
    gates: list[GateSpec] = Field(default_factory=list)


def load_gates(path: Path | str) -> GatesConfig:
    """Le e valida o YAML de gates. Erros lancam ConfigError com a causa."""
    file_path = Path(path)
    try:
        raw = yaml.safe_load(file_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ConfigError(f"nao foi possivel ler {file_path}: {exc}") from exc
    try:
        config = GatesConfig.model_validate(raw or {})
    except ValidationError as exc:
        raise ConfigError(f"{file_path}: {exc.errors()[0]['msg']}") from exc
    for gate in config.gates:
        if gate.metric == "new_failures" and not gate.evaluators:
            raise ConfigError(f"{file_path}: o gate {gate.name} precisa de 'evaluators'")
    names = [gate.name for gate in config.gates]
    if len(names) != len(set(names)):
        raise ConfigError(f"{file_path}: nomes de gates repetidos")
    return config
