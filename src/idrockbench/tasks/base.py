"""The Task interface.

A task is five methods. The runner handles concurrency, retries, checkpointing,
per-item logging and diagnostics, so a task only describes *what* to ask and
*how* to score it.

    @register_task
    class MyTask(Task):
        name = "my_task"
        version = "1.0"
        primary_metric = "accuracy"
        chance_level = 0.25

        def prepare(self, records): ...      # rows -> Items       (optional)
        def build_prompt(self, item): ...    # Item -> str
        def parse(self, response, item): ... # str  -> Extraction
        def score(self, extraction, item): ...  # -> float in [0, 1]
        def aggregate(self, results): ...    # -> metrics dict     (optional)

See ``docs/guides/adding-a-benchmark.md`` for a worked example.
"""

from __future__ import annotations

import abc
import random
from collections.abc import Iterable, Sequence
from typing import Any

from ..core import Item, ItemResult, TaskResult
from ..extraction import Extraction, ParseStatus


class Task(abc.ABC):
    """Base class for every benchmark."""

    #: Registry key and the column name in results. Required.
    name: str = ""

    #: Bump on **any** change that can move a score — prompt wording, extraction
    #: rules, scoring, dataset default. Published numbers name this version, and
    #: numbers from different versions are never sorted together. Required.
    version: str = ""

    description: str = ""

    #: Which key in :meth:`aggregate`'s output is the headline number.
    primary_metric: str = "accuracy"

    #: Score a content-free responder achieves, in ``[0, 1]``. Used to
    #: normalise before aggregating across tasks, and to flag suspicious cells:
    #: a score at or below chance usually means a broken extractor, not a weak
    #: model. Multiple choice: ``1 / n_options``. Generative: ``0.0``.
    chance_level: float = 0.0

    #: Token budget. Recorded in the manifest — an unrecorded budget makes a
    #: truncation-driven score look like a capability difference.
    default_max_tokens: int = 2048

    #: Higher is better. False for error-style metrics such as MetricX.
    higher_is_better: bool = True

    def __init__(self, *, seed: int = 0, options: dict[str, Any] | None = None) -> None:
        self.seed = seed
        self.options = options or {}
        self.rng = random.Random(seed)

    # -- dataset -> items ---------------------------------------------------

    def prepare(self, records: Sequence[dict]) -> list[Item]:
        """Turn raw dataset rows into :class:`Item`s.

        Override to reshape rows, filter invalid ones, or expand one row into
        several (a translation row becomes one item per direction). The default
        passes rows through, keying on ``id`` or position.
        """
        return [
            Item(id=str(r.get("id", i)), payload=dict(r), gold=r.get("answer"))
            for i, r in enumerate(records)
        ]

    def validate(self, records: Sequence[dict]) -> list[str]:
        """Return a list of dataset problems, empty if clean.

        Run by ``idrockbench validate`` and in CI. This is where a task
        declares its invariants — "the gold index must be inside the option
        list", "every option must be non-empty and distinct". An invariant
        checked here cannot silently corrupt a published number later.
        """
        return []

    # -- prompt -> score ----------------------------------------------------

    @abc.abstractmethod
    def build_prompt(self, item: Item) -> str:
        """Render the prompt sent to the model."""

    @abc.abstractmethod
    def parse(self, response: str, item: Item) -> Extraction:
        """Extract the answer. Return an UNPARSED extraction rather than
        guessing — a fabricated answer is worse than a recorded parse failure."""

    @abc.abstractmethod
    def score(self, extraction: Extraction, item: Item) -> float:
        """Score a parsed answer in ``[0, 1]``. Only called when
        ``extraction.ok``; non-scoring statuses never reach here."""

    # -- aggregation --------------------------------------------------------

    def aggregate(self, results: Sequence[ItemResult]) -> dict[str, Any]:
        """Compute metrics from item results.

        The default is mean score over *scorable* items, with a Wilson 95%
        interval. Override for corpus-level metrics (BLEU) or multi-metric
        tasks (IFEval's strict/loose × prompt/instruction grid).
        """
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
        """Which ``Item.meta`` keys to report sub-scores for (subject,
        category, direction). Reported with their own n and CI."""
        return ()


def make_task_result(
    task: Task,
    results: Sequence[ItemResult],
    *,
    dataset_id: str,
    dataset_sha256: str,
) -> TaskResult:
    """Assemble a :class:`TaskResult`, including the diagnostics.

    The diagnostics block is not optional decoration. ``unparsed_rate`` is what
    separates "this model is weak" from "our extractor is broken", and it is
    the single number that would have caught most of the defects this harness
    was rebuilt to fix.
    """
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
        # A headline at or below chance is nearly always an extraction failure.
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
