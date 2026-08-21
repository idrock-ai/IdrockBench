from __future__ import annotations

import abc
import random
from collections.abc import Iterable, Sequence
from typing import Any

from ..core import Item, ItemResult, TaskResult
from ..extraction import Extraction, ParseStatus


class Task(abc.ABC):
    name: str = ""

    version: str = ""

    description: str = ""

    primary_metric: str = "accuracy"

    chance_level: float = 0.0

    default_max_tokens: int = 2048

    higher_is_better: bool = True

    def __init__(self, *, seed: int = 0, options: dict[str, Any] | None = None) -> None:
        self.seed = seed
        self.options = options or {}
        self.rng = random.Random(seed)

    def prepare(self, records: Sequence[dict]) -> list[Item]:
        return [
            Item(id=str(r.get("id", i)), payload=dict(r), gold=r.get("answer"))
            for i, r in enumerate(records)
        ]

    def validate(self, records: Sequence[dict]) -> list[str]:
        return []

    @abc.abstractmethod
    def build_prompt(self, item: Item) -> str:
        pass

    @abc.abstractmethod
    def parse(self, response: str, item: Item) -> Extraction:
        pass

    @abc.abstractmethod
    def score(self, extraction: Extraction, item: Item) -> float:
        pass

    def aggregate(self, results: Sequence[ItemResult]) -> dict[str, Any]:
        from ..metrics.accuracy import accuracy_with_ci

        scorable = [r for r in results if r.scorable]
        acc = accuracy_with_ci([r.score for r in scorable])
        return {
            "primary": acc["accuracy"],
            "accuracy": acc["accuracy"],
            "ci_low": acc["ci_low"],
            "ci_high": acc["ci_high"],
            "n": len(scorable),
        }

    def breakdown_keys(self) -> tuple[str, ...]:
        return ()


def make_task_result(
    task: Task,
    results: Sequence[ItemResult],
    *,
    dataset_id: str,
    dataset_sha256: str,
) -> TaskResult:
    from ..metrics.accuracy import accuracy_with_ci

    n = len(results)
    counts = {s: 0 for s in ParseStatus}
    for r in results:
        counts[r.status] += 1
    scorable = [r for r in results if r.scorable]

    diagnostics = {
        "n_items": n,
        "n_scored": len(scorable),
        "unparsed_rate": round(counts[ParseStatus.UNPARSED] / n, 4) if n else 0.0,
        "truncated_rate": round(counts[ParseStatus.TRUNCATED] / n, 4) if n else 0.0,
        "error_rate": round(counts[ParseStatus.ERROR] / n, 4) if n else 0.0,
        "refusal_rate": round(counts[ParseStatus.REFUSAL] / n, 4) if n else 0.0,
        "coverage": round(len(scorable) / n, 4) if n else 0.0,
        "strategies": _count(r.strategy for r in results if r.strategy),
        "chance_level": task.chance_level,
    }

    metrics = task.aggregate(results)
    primary = metrics.get("primary")
    if primary is not None and task.chance_level:
        diagnostics["at_or_below_chance"] = primary <= task.chance_level * 100

    breakdown: dict[str, dict[str, Any]] = {}
    for key in task.breakdown_keys():
        groups: dict[str, list[ItemResult]] = {}
        for r in results:
            groups.setdefault(str(r.meta.get(key, "unknown")), []).append(r)
        breakdown[key] = {}
        for value, rows in sorted(groups.items()):
            ok = [r for r in rows if r.scorable]
            acc = accuracy_with_ci([r.score for r in ok])
            breakdown[key][value] = {
                "accuracy": acc["accuracy"],
                "ci_low": acc["ci_low"],
                "ci_high": acc["ci_high"],
                "n": len(ok),
                "n_items": len(rows),
                "coverage": round(len(ok) / len(rows), 4) if rows else 0.0,
            }

    return TaskResult(
        task=task.name,
        task_version=task.version,
        dataset_id=dataset_id,
        dataset_sha256=dataset_sha256,
        n_items=n,
        n_scored=len(scorable),
        metrics=metrics,
        diagnostics=diagnostics,
        breakdown=breakdown,
    )


def _count(values: Iterable[str]) -> dict[str, int]:
    out: dict[str, int] = {}
    for v in values:
        out[v] = out.get(v, 0) + 1
    return dict(sorted(out.items(), key=lambda kv: -kv[1]))
