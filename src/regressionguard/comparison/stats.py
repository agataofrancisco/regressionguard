"""Estatistica emparelhada: IC por bootstrap sobre casos e teste exacto de McNemar.

Porque emparelhar: baseline e candidato sao avaliados sobre os MESMOS casos. A variancia
entre casos (alguns sao faceis, outros dificeis) e removida ao olhar para a diferenca por caso.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.stats import binomtest

DEFAULT_RESAMPLES = 10_000
DEFAULT_SEED = 1234


@dataclass(frozen=True)
class BootstrapCI:
    mean: float
    low: float
    high: float
    confidence: float
    resamples: int
    seed: int

    @property
    def width(self) -> float:
        return self.high - self.low

    @property
    def contains_zero(self) -> bool:
        return self.low <= 0.0 <= self.high


def paired_bootstrap_ci(
    diffs: list[float] | np.ndarray,
    *,
    confidence: float = 0.95,
    resamples: int = DEFAULT_RESAMPLES,
    seed: int = DEFAULT_SEED,
) -> BootstrapCI:
    """IC percentilico da media das diferencas, reamostrando CASOS com reposicao.

    Nao assume normalidade. Com seed fixa o resultado e reprodutivel.
    """
    values = np.asarray(diffs, dtype=float)
    if values.size == 0:
        raise ValueError("sem casos emparelhados")
    if not 0.0 < confidence < 1.0:
        raise ValueError("confidence tem de estar entre 0 e 1")
    rng = np.random.default_rng(seed)
    indices = rng.integers(0, values.size, size=(resamples, values.size))
    means = values[indices].mean(axis=1)
    alpha = (1.0 - confidence) / 2.0
    low, high = np.quantile(means, [alpha, 1.0 - alpha])
    return BootstrapCI(
        mean=round(float(values.mean()), 6),
        low=round(float(low), 6),
        high=round(float(high), 6),
        confidence=confidence,
        resamples=resamples,
        seed=seed,
    )


def mcnemar_exact(only_baseline_pass: int, only_candidate_pass: int) -> float:
    """p-valor bilateral do teste exacto de McNemar sobre os pares discordantes.

    b = casos que passam so no baseline; c = casos que passam so no candidato.
    Sob H0 (sem diferenca), b e c seguem Binomial(b + c, 1/2).
    """
    b, c = int(only_baseline_pass), int(only_candidate_pass)
    if b < 0 or c < 0:
        raise ValueError("contagens negativas")
    n = b + c
    if n == 0:
        return 1.0
    return float(binomtest(min(b, c), n, 0.5, alternative="two-sided").pvalue)
