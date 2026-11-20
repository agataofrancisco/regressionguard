"""Avaliadores: deterministicos, semanticos e juiz LLM (sinal secundario).

Importar este pacote regista todos os avaliadores embutidos.
"""

from regressionguard.evaluators import deterministic, judge, semantic  # noqa: F401
from regressionguard.evaluators.registry import EvalContext, EvalResult, get, names, register, specs

__all__ = ["EvalContext", "EvalResult", "get", "names", "register", "specs"]
