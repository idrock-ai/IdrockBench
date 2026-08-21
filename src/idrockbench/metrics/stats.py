"""Significance testing between two models on the same items.

Leaderboard positions get argued about. These give a defensible answer to
"is model A actually better than model B, or is that gap noise?"
"""

from __future__ import annotations

import math
import random
from collections.abc import Sequence


def mcnemar(a_correct: Sequence[bool], b_correct: Sequence[bool]) -> dict[str, float]:
    """Paired test for two models scored on the *same* items.

    Only the disagreements carry information: ``b`` = A right/B wrong,
    ``c`` = A wrong/B right. Uses the exact binomial when ``b + c < 25``, where
    the chi-square approximation is unreliable.
    """
    if len(a_correct) != len(b_correct):
        raise ValueError("paired test needs equal-length, item-aligned inputs")
    b = sum(1 for x, y in zip(a_correct, b_correct, strict=True) if x and not y)
    c = sum(1 for x, y in zip(a_correct, b_correct, strict=True) if y and not x)
    n = b + c
    if n == 0:
        return {"b": 0, "c": 0, "p_value": 1.0, "test": "none"}
    if n < 25:
        # Exact two-sided binomial with p=0.5.
        tail = sum(math.comb(n, k) for k in range(0, min(b, c) + 1)) / (2 ** n)
        return {"b": b, "c": c, "p_value": round(min(1.0, 2 * tail), 6), "test": "exact"}
    stat = (abs(b - c) - 1) ** 2 / n
    p = math.erfc(math.sqrt(stat / 2))
    return {"b": b, "c": c, "chi2": round(stat, 4), "p_value": round(p, 6), "test": "chi2"}


def paired_bootstrap(
    a_scores: Sequence[float],
    b_scores: Sequence[float],
    *,
    n_samples: int = 1000,
    seed: int = 12345,
) -> dict[str, float]:
    """Paired bootstrap over items: how often does A beat B on a resample?

    Works for partial-credit and corpus metrics where McNemar's binary
    correct/incorrect framing does not apply.
    """
    if len(a_scores) != len(b_scores):
        raise ValueError("paired test needs equal-length, item-aligned inputs")
    n = len(a_scores)
    if n == 0:
        return {"delta": 0.0, "p_value": 1.0, "n_samples": 0}
    rng = random.Random(seed)
    observed = (sum(a_scores) - sum(b_scores)) / n
    wins = 0
    for _ in range(n_samples):
        idx = [rng.randrange(n) for _ in range(n)]
        delta = sum(a_scores[i] - b_scores[i] for i in idx) / n
        if (delta > 0) == (observed > 0) and delta != 0:
            wins += 1
    return {
        "delta": round(observed * 100, 3),
        "p_value": round(1 - wins / n_samples, 4),
        "n_samples": n_samples,
        "seed": seed,
    }
