"""Accuracy-style metrics with intervals.

Every published cell carries an interval. A bare point estimate invites
readers to rank differences that are inside the noise floor: at n=200, a
15.5% and a 6.5% score have overlapping 95% intervals, and seven of the ten
rows on the old leaderboard were mutually indistinguishable.
"""

from __future__ import annotations

import math
from collections.abc import Sequence


def wilson_interval(successes: float, n: int, z: float = 1.959963985) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion, as percentages.

    Wilson rather than Wald: the normal approximation undercovers badly at the
    small n and extreme proportions this benchmark actually operates at, and it
    can produce bounds outside [0, 1]. Wilson stays inside and holds its
    coverage near 0 and 1 — exactly where a broken extractor puts a score.
    """
    if n <= 0:
        return (0.0, 0.0)
    p = successes / n
    z2 = z * z
    denom = 1 + z2 / n
    centre = (p + z2 / (2 * n)) / denom
    half = (z / denom) * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n))
    return (round(max(0.0, centre - half) * 100, 2), round(min(1.0, centre + half) * 100, 2))


def accuracy_with_ci(scores: Sequence[float]) -> dict[str, float]:
    """Mean score as a percentage, with a Wilson 95% interval.

    Partial-credit scores are not Bernoulli, so the interval is approximate for
    those tasks; it is reported anyway because an approximate interval is far
    more honest than none, and the task documents its scoring.
    """
    n = len(scores)
    if n == 0:
        return {"accuracy": 0.0, "ci_low": 0.0, "ci_high": 0.0, "n": 0, "correct": 0.0}
    total = float(sum(scores))
    lo, hi = wilson_interval(total, n)
    return {
        "accuracy": round(total / n * 100, 2),
        "ci_low": lo,
        "ci_high": hi,
        "n": n,
        "correct": round(total, 2),
    }


def normalize_against_chance(score_pct: float, chance: float) -> float:
    """Rescale so the random baseline is 0 and a perfect score is 100.

        normalised = (raw - chance) / (1 - chance) * 100,  clamped at 0

    Required before averaging across tasks. Raw 25% is chance on a 4-option
    benchmark and well above chance on a 10-option one; averaging the two
    treats a coin flip and real signal as equal. Clamped at zero because a
    below-chance score carries no information about capability.
    """
    if chance >= 1.0:
        return 0.0
    raw = score_pct / 100.0
    return round(max(0.0, (raw - chance) / (1 - chance)) * 100, 2)


def minimum_n(half_width_pct: float, p: float = 0.5, z: float = 1.959963985) -> int:
    """Items needed for a target 95% half-width, in percentage points.

    ``minimum_n(5)`` -> 385. Use when sizing a new benchmark or a validation
    sample; p=0.5 is the conservative worst case.
    """
    if half_width_pct <= 0:
        raise ValueError("half_width_pct must be positive")
    e = half_width_pct / 100.0
    return math.ceil(z * z * p * (1 - p) / (e * e))
