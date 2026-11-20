"""Registo de avaliadores por nome. Um avaliador e uma funcao pura (contexto -> resultado)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from regressionguard.datasets.models import Case
from regressionguard.targets.base import TargetOutput


class EvalResult(BaseModel):
    """Resultado de um avaliador num caso e numa repeticao."""

    passed: bool
    score: float | None = None
    reason: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


@dataclass(frozen=True)
class EvalContext:
    case: Case
    output: TargetOutput
    root: Path
    judge: Any | None = None  # ver evaluators/judge.py (Judge)


EvaluatorFn = Callable[[EvalContext], EvalResult]


@dataclass(frozen=True)
class EvaluatorSpec:
    name: str
    fn: EvaluatorFn
    secondary: bool = False  # sinal secundario: nunca decide se um caso passa
    security: bool = False
    description: str = ""


class UnknownEvaluator(KeyError):
    """Nome de avaliador nao registado."""


_REGISTRY: dict[str, EvaluatorSpec] = {}


def register(
    name: str,
    *,
    secondary: bool = False,
    security: bool = False,
    description: str = "",
) -> Callable[[EvaluatorFn], EvaluatorFn]:
    """Regista um avaliador. Nomes duplicados sao erro (evita colisoes silenciosas)."""

    def decorator(fn: EvaluatorFn) -> EvaluatorFn:
        if name in _REGISTRY:
            raise ValueError(f"avaliador ja registado: {name}")
        _REGISTRY[name] = EvaluatorSpec(name, fn, secondary, security, description)
        return fn

    return decorator


def get(name: str) -> EvaluatorSpec:
    try:
        return _REGISTRY[name]
    except KeyError as exc:
        raise UnknownEvaluator(name) from exc


def names() -> list[str]:
    return sorted(_REGISTRY)


def specs() -> list[EvaluatorSpec]:
    return [_REGISTRY[name] for name in sorted(_REGISTRY)]
