"""Avaliadores semanticos: exact match, F1 por token e F1 por campo, similaridade com limiar.

Cada avaliador declara a normalizacao e a tolerancia usadas e devolve-as em `details`,
para que um resultado nunca seja lido sem o seu criterio de comparacao.
"""

from __future__ import annotations

import difflib
from collections import Counter
from typing import Any

from regressionguard.evaluators.registry import EvalContext, EvalResult, register
from regressionguard.text import as_text, normalize

EXACT_STEPS = ["strip", "casefold"]
TOKEN_STEPS = ["strip_citations", "strip_punct", "casefold", "strip_accents", "collapse_ws"]
SIMILARITY_STEPS = ["strip", "casefold", "strip_accents", "collapse_ws"]
NUMERIC_TOLERANCE = 0.005  # diferenca absoluta maxima entre numeros (cêntimos)


def _steps(ctx: EvalContext, default: list[str]) -> list[str]:
    raw = ctx.case.criteria.get("normalize", default)
    if not isinstance(raw, list):
        return list(default)
    return [as_text(step) for step in raw]


def _safe_normalize(text: str, steps: list[str]) -> tuple[str, str | None]:
    """Devolve (texto, erro). Passos desconhecidos viram erro de configuracao, nao excepcao."""
    try:
        return normalize(text, steps), None
    except ValueError as exc:
        return "", str(exc)


@register(
    "exact_match", description="Igualdade apos normalizacao declarada (por omissao strip+casefold)."
)
def exact_match(ctx: EvalContext) -> EvalResult:
    steps = _steps(ctx, EXACT_STEPS)
    expected, err_e = _safe_normalize(as_text(ctx.case.expected), steps)
    actual, err_a = _safe_normalize(ctx.output.text, steps)
    if err_e or err_a:
        return EvalResult(
            passed=False, reason="config:normalization", details={"error": err_e or err_a}
        )
    passed = expected == actual
    return EvalResult(
        passed=passed,
        score=1.0 if passed else 0.0,
        reason=None if passed else "exact_mismatch",
        details={"normalization": steps, "expected": expected, "actual": actual},
    )


def token_f1_scores(expected: str, actual: str) -> tuple[float, float, float]:
    """Precisao, cobertura e F1 sobre multiconjuntos de tokens. Funcao pura."""
    exp_tokens = Counter(expected.split())
    act_tokens = Counter(actual.split())
    if not exp_tokens and not act_tokens:
        return 1.0, 1.0, 1.0
    if not exp_tokens or not act_tokens:
        return 0.0, 0.0, 0.0
    common = sum((exp_tokens & act_tokens).values())
    precision = common / sum(act_tokens.values())
    recall = common / sum(exp_tokens.values())
    if precision + recall == 0:
        return precision, recall, 0.0
    return precision, recall, 2 * precision * recall / (precision + recall)


@register(
    "token_f1", description="F1 sobre tokens (precisao e cobertura), com limiar configuravel."
)
def token_f1(ctx: EvalContext) -> EvalResult:
    steps = _steps(ctx, TOKEN_STEPS)
    threshold = _float(ctx.case.criteria.get("threshold"), 0.7)
    expected, err_e = _safe_normalize(as_text(ctx.case.expected), steps)
    actual, err_a = _safe_normalize(ctx.output.text, steps)
    if err_e or err_a:
        return EvalResult(
            passed=False, reason="config:normalization", details={"error": err_e or err_a}
        )
    precision, recall, f1 = token_f1_scores(expected, actual)
    passed = f1 >= threshold
    return EvalResult(
        passed=passed,
        score=round(f1, 6),
        reason=None if passed else "f1_below_threshold",
        details={
            "normalization": steps,
            "precision": round(precision, 6),
            "recall": round(recall, 6),
            "f1": round(f1, 6),
            "threshold": threshold,
        },
    )


def values_equal(expected: Any, actual: Any) -> bool:
    """Igualdade de campos: texto normalizado, numeros com tolerancia, listas sem ordem."""
    if expected is None or actual is None:
        return expected is None and actual is None
    if isinstance(expected, bool) or isinstance(actual, bool):
        return isinstance(expected, bool) and isinstance(actual, bool) and expected == actual
    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        return abs(float(expected) - float(actual)) <= NUMERIC_TOLERANCE
    if isinstance(expected, str) and isinstance(actual, str):
        return normalize(expected, SIMILARITY_STEPS) == normalize(actual, SIMILARITY_STEPS)
    if isinstance(expected, list) and isinstance(actual, list):
        if len(expected) != len(actual):
            return False
        remaining = list(actual)
        for item in expected:
            match = next((i for i, cand in enumerate(remaining) if values_equal(item, cand)), None)
            if match is None:
                return False
            remaining.pop(match)
        return True
    if isinstance(expected, dict) and isinstance(actual, dict):
        return set(expected) == set(actual) and all(
            values_equal(expected[k], actual[k]) for k in expected
        )
    return False


@register("field_f1", description="F1 por campo de um objeto estruturado (limiar por omissao 0.9).")
def field_f1(ctx: EvalContext) -> EvalResult:
    threshold = _float(ctx.case.criteria.get("threshold"), 0.9)
    expected = ctx.case.expected
    if not isinstance(expected, dict):
        return EvalResult(passed=False, reason="config:expected_not_object")
    data = ctx.output.data
    if data is None:
        return EvalResult(
            passed=False, reason="no_structured_output", details={"error": ctx.output.error}
        )
    matched = [
        key for key, value in expected.items() if key in data and values_equal(value, data[key])
    ]
    mismatched = sorted(set(expected) - set(matched))
    precision = len(matched) / len(data) if data else 0.0
    recall = len(matched) / len(expected) if expected else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    passed = f1 >= threshold
    return EvalResult(
        passed=passed,
        score=round(f1, 6),
        reason=None if passed else f"field_f1_below_threshold:{','.join(mismatched[:3])}",
        details={
            "precision": round(precision, 6),
            "recall": round(recall, 6),
            "f1": round(f1, 6),
            "threshold": threshold,
            "matched": sorted(matched),
            "numeric_tolerance": NUMERIC_TOLERANCE,
            "normalization": SIMILARITY_STEPS,
        },
    )


@register("similarity", description="Similaridade de sequencia (difflib) com limiar configuravel.")
def similarity(ctx: EvalContext) -> EvalResult:
    steps = _steps(ctx, SIMILARITY_STEPS)
    threshold = _float(ctx.case.criteria.get("threshold"), 0.8)
    expected, err_e = _safe_normalize(as_text(ctx.case.expected), steps)
    actual, err_a = _safe_normalize(ctx.output.text, steps)
    if err_e or err_a:
        return EvalResult(
            passed=False, reason="config:normalization", details={"error": err_e or err_a}
        )
    ratio = difflib.SequenceMatcher(None, expected, actual).ratio()
    passed = ratio >= threshold
    return EvalResult(
        passed=passed,
        score=round(ratio, 6),
        reason=None if passed else "similarity_below_threshold",
        details={"normalization": steps, "threshold": threshold, "ratio": round(ratio, 6)},
    )


def _float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
