"""Leitura de `datasets/suites.yaml` e de conjuntos de configuracao de alvos (`targets/sets`)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from regressionguard.targets.base import ConfigError

SUITES_FILE = "datasets/suites.yaml"
SETS_DIR = "targets/sets"


@dataclass(frozen=True)
class Suite:
    name: str
    description: str
    datasets: tuple[str, ...]
    severity: str | None


@dataclass(frozen=True)
class ConfigSet:
    name: str
    targets: dict[str, str]  # nome do alvo -> caminho da configuracao (relativo a raiz)


def _read_yaml(path: Path) -> dict:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ConfigError(f"nao foi possivel ler {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ConfigError(f"{path}: esperado um mapa YAML")
    return raw


def load_suite(root: Path, name: str) -> Suite:
    raw = _read_yaml(root / SUITES_FILE).get("suites", {})
    if name not in raw:
        raise ConfigError(f"suite desconhecida: {name} (disponiveis: {', '.join(sorted(raw))})")
    entry = raw[name] or {}
    datasets = entry.get("datasets")
    if not isinstance(datasets, list) or not all(isinstance(d, str) for d in datasets):
        raise ConfigError(f"suite {name}: 'datasets' tem de ser uma lista de caminhos")
    severity = entry.get("severity")
    if severity not in (None, "critical", "normal"):
        raise ConfigError(f"suite {name}: severity invalida: {severity}")
    return Suite(name, str(entry.get("description", "")), tuple(datasets), severity)


def load_config_set(root: Path, name: str) -> ConfigSet:
    path = root / SETS_DIR / f"{name}.yaml"
    if not path.exists():
        raise ConfigError(f"conjunto de configuracao desconhecido: {name} ({path})")
    raw = _read_yaml(path)
    targets = {key: str(value) for key, value in raw.items() if key not in ("name", "description")}
    if not targets:
        raise ConfigError(f"{path}: nenhum alvo configurado")
    return ConfigSet(name, targets)


def default_dataset_paths(root: Path) -> list[Path]:
    """Todos os datasets referidos nas suites (sem repetidos, ordem estavel)."""
    raw = _read_yaml(root / SUITES_FILE).get("suites", {})
    seen: dict[str, None] = {}
    for entry in raw.values():
        for dataset in (entry or {}).get("datasets", []) or []:
            seen.setdefault(str(dataset), None)
    return [root / dataset for dataset in seen]
