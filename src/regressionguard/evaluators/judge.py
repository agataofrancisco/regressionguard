"""Juiz LLM: sinal SECUNDARIO com rubrica versionada e calibracao contra labels humanos.

Regras (ver specs/evaluators): o juiz nunca decide se um caso passa (`secondary=True`), e a sua
concordancia com humanos e medida com kappa de Cohen numa amostra de calibracao.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from regressionguard.evaluators.registry import EvalContext, EvalResult, register
from regressionguard.text import as_text


@dataclass(frozen=True)
class JudgeVerdict:
    score: float  # 0.0 a 1.0
    rationale: str


class Judge(Protocol):
    """Qualquer juiz (LLM ou fake em testes) implementa esta interface."""

    def score(
        self, rubric: str, *, case_input: Any, expected: Any, output: str
    ) -> JudgeVerdict: ...


@register(
    "llm_judge", secondary=True, description="Juiz LLM com rubrica versionada (sinal secundario)."
)
def llm_judge(ctx: EvalContext) -> EvalResult:
    if ctx.judge is None:
        return EvalResult(passed=True, reason="judge_disabled", details={"skipped": True})
    rubric_rel = as_text(ctx.case.criteria.get("rubric", ""))
    try:
        rubric = (ctx.root / rubric_rel).read_text(encoding="utf-8")
    except OSError as exc:
        return EvalResult(
            passed=False, reason="config:rubric_unreadable", details={"error": str(exc)}
        )
    verdict = ctx.judge.score(
        rubric,
        case_input=ctx.case.input,
        expected=ctx.case.expected,
        output=ctx.output.text,
    )
    threshold = float(ctx.case.criteria.get("threshold", 0.5))
    passed = verdict.score >= threshold
    return EvalResult(
        passed=passed,
        score=round(float(verdict.score), 6),
        reason=None if passed else "judge_low_score",
        details={
            "rubric": rubric_rel,
            "rubric_sha256": hashlib.sha256(rubric.encode("utf-8")).hexdigest(),
            "threshold": threshold,
            "rationale": verdict.rationale[:500],
            "signal": "secondary",
        },
    )


@dataclass(frozen=True)
class Calibration:
    n: int
    agreement: float
    kappa: float


def cohens_kappa(judge: Sequence[bool], human: Sequence[bool]) -> Calibration:
    """Kappa de Cohen para duas classificacoes binarias emparelhadas."""
    if len(judge) != len(human):
        raise ValueError("juiz e humanos tem de ter o mesmo numero de itens")
    n = len(judge)
    if n == 0:
        raise ValueError("amostra de calibracao vazia")
    agree = sum(1 for j, h in zip(judge, human, strict=True) if j == h)
    p_o = agree / n
    p_judge_yes = sum(judge) / n
    p_human_yes = sum(human) / n
    p_e = p_judge_yes * p_human_yes + (1 - p_judge_yes) * (1 - p_human_yes)
    kappa = 1.0 if p_e == 1.0 and p_o == 1.0 else (0.0 if p_e == 1.0 else (p_o - p_e) / (1 - p_e))
    return Calibration(n=n, agreement=round(p_o, 6), kappa=round(kappa, 6))


def calibrate(
    scores: Sequence[float], human: Sequence[bool], threshold: float = 0.5
) -> Calibration:
    """Binariza as notas do juiz pelo limiar e compara com os labels humanos."""
    return cohens_kappa([score >= threshold for score in scores], human)
