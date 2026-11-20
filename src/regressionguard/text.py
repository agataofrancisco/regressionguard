"""Normalizacao de texto partilhada por alvos e avaliadores. Funcoes puras e defensivas."""

from __future__ import annotations

import json
import re
import unicodedata
from typing import Any

_TOKEN = re.compile(r"[a-z0-9]+")
_CITATION = re.compile(r"\[[^\]]*\]")
_PUNCT = re.compile(r"[^\w\s]", re.UNICODE)
_WS = re.compile(r"\s+")

NORMALIZATION_STEPS = (
    "strip",
    "casefold",
    "strip_accents",
    "strip_punct",
    "collapse_ws",
    "strip_citations",
)


def as_text(value: Any) -> str:
    """Converte qualquer valor para texto sem lancar excepcoes."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    except (TypeError, ValueError):
        return str(value)


def strip_accents(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def strip_citations(text: str) -> str:
    """Remove marcas de citacao do tipo [faq-001]."""
    return _CITATION.sub(" ", text)


def tokens(text: str) -> list[str]:
    """Tokens em minusculas, sem acentos, so alfanumericos."""
    folded = strip_accents(as_text(text)).casefold()
    return _TOKEN.findall(folded)


def normalize(text: str, steps: list[str] | tuple[str, ...]) -> str:
    """Aplica os passos de normalizacao declarados, pela ordem dada."""
    result = as_text(text)
    for step in steps:
        if step == "strip":
            result = result.strip()
        elif step == "casefold":
            result = result.casefold()
        elif step == "strip_accents":
            result = strip_accents(result)
        elif step == "strip_punct":
            result = _PUNCT.sub(" ", result)
        elif step == "collapse_ws":
            result = _WS.sub(" ", result).strip()
        elif step == "strip_citations":
            result = strip_citations(result)
        else:
            raise ValueError(f"passo de normalizacao desconhecido: {step}")
    return result
