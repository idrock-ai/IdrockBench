from __future__ import annotations

import math
from collections.abc import Sequence


def wilson_interval(successes: float, n: int, z: float = 1.959963985) -> tuple[float, float]:
    if n <= 0:
        return (0.0, 0.0)
    p = successes / n
    z2 = z * z
    denom = 1 + z2 / n
    centre = (p + z2 / (2 * n)) / denom
    half = (z / denom) * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n))
    return (round(max(0.0, centre - half) * 100, 2), round(min(1.0, centre + half) * 100, 2))


def accuracy_with_ci(scores: Sequence[float]) -> dict[str, float]:
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
    if chance >= 1.0:
        return 0.0
    raw = score_pct / 100.0
    return round(max(0.0, (raw - chance) / (1 - chance)) * 100, 2)


def minimum_n(half_width_pct: float, p: float = 0.5, z: float = 1.959963985) -> int:
    if half_width_pct <= 0:
        raise ValueError("half_width_pct must be positive")
    e = half_width_pct / 100.0
    return math.ceil(z * z * p * (1 - p) / (e * e))
