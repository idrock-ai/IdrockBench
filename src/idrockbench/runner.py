"""The evaluation loop.

Guarantees, each of which fixes a way the previous harness lost work or
corrupted a number:

* **Every item is written to disk as it completes.** A crash in task 4 of 5
  never discards tasks 1–3, and the per-item JSONL is the permanent record from
  which every published number is recomputed. Fixing an extraction bug later
  costs a re-score, not a re-run.
* **Resume is by item id.** Re-running skips completed items and retries only
  the failures, so a partial run converges instead of restarting.
* **Requests run concurrently** with bounded parallelism, not a fixed sleep.
* **Failures stay distinguishable.** Errors, truncations and parse failures are
  recorded with their own status and never silently become score 0.
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .core import Item, ItemResult, ModelResponse, TaskResult
from .extraction import ParseStatus
from .models.base import ModelProvider
from .tasks.base import Task, make_task_result

logger = logging.getLogger(__name__)


def _read_completed(path: Path) -> dict[str, dict]:
    """Load previously completed items, keyed by id.

    Failed items are deliberately *not* treated as complete, so a resumed run
    retries them. Silently advancing past a failure is how an outage becomes a
    permanent zero in a published score.
    """
    done: dict[str, dict] = {}
    if not path.exists():
        return done
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("status") != ParseStatus.ERROR.value:
                done[str(row.get("item_id"))] = row
    return done


def _result_from_row(row: dict) -> ItemResult:
    row = dict(row)
    row["status"] = ParseStatus(row["status"])
    fields = ItemResult.__slots__
    return ItemResult(**{k: v for k, v in row.items() if k in fields})


def evaluate_task(
    task: Task,
    items: Sequence[Item],
    provider: ModelProvider,
    *,
    dataset_id: str,
    dataset_sha256: str,
    output_dir: Path,
    name: str | None = None,
    max_tokens: int | None = None,
    concurrency: int = 4,
    resume: bool = True,
    progress: Callable[[int, int], None] | None = None,
) -> TaskResult:
    """Run one task end to end and return its aggregated result.

    Args:
        task: The task instance.
        items: Prepared items from :meth:`Task.prepare`.
        provider: Model backend.
        output_dir: Per-item JSONL is written to ``<output_dir>/<name>.jsonl``.
        name: Config name, used for the output file. Defaults to the task's own
            name. They differ whenever one task implementation is driven by
            several configs — and a mismatch makes ``rescore`` silently skip
            the task, because it looks for a file the run never wrote.
        max_tokens: Overrides the task's default budget.
        concurrency: Simultaneous in-flight requests.
        resume: Skip items already recorded as non-error.
        progress: Called as ``(completed, total)``.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = output_dir / f"{name or task.name}.jsonl"
    budget = max_tokens or task.default_max_tokens

    completed = _read_completed(jsonl_path) if resume else {}
    if completed:
        logger.info("%s: resuming, %d items already done", name or task.name, len(completed))
    pending = [it for it in items if it.id not in completed]

    results: list[ItemResult] = [_result_from_row(completed[it.id])
                                 for it in items if it.id in completed]

    def run_one(item: Item) -> ItemResult:
        prompt = task.build_prompt(item)
        resp: ModelResponse = provider.generate(prompt, budget)

        if resp.error:
            return ItemResult(
                item_id=item.id, prompt=prompt, response="", status=ParseStatus.ERROR,
                extracted=None, gold=item.gold, score=0.0, meta=dict(item.meta),
                finish_reason="error", error=resp.error, latency_s=resp.latency_s,
            )

        extraction = task.parse(resp.text, item)
        status = extraction.status

        # A response cut off by the token limit is a truncation even if
        # something parseable survived, unless the task says otherwise.
        if resp.truncated and status is ParseStatus.UNPARSED:
            status = ParseStatus.TRUNCATED

        score = task.score(extraction, item) if extraction.ok else 0.0
        return ItemResult(
            item_id=item.id, prompt=prompt, response=resp.text, status=status,
            extracted=extraction.value, gold=item.gold, score=score,
            strategy=extraction.strategy, evidence=extraction.evidence,
            meta=dict(item.meta), finish_reason=resp.finish_reason,
            prompt_tokens=resp.prompt_tokens, completion_tokens=resp.completion_tokens,
            latency_s=resp.latency_s,
        )

    if pending:
        mode = "a" if completed else "w"
        with (
            open(jsonl_path, mode, encoding="utf-8") as sink,
            ThreadPoolExecutor(max_workers=max(1, concurrency)) as pool,
        ):
            for n, result in enumerate(pool.map(run_one, pending), start=1):
                results.append(result)
                sink.write(result.to_json() + "\n")
                sink.flush()          # survive a kill -9
                os.fsync(sink.fileno())
                if progress:
                    progress(len(completed) + n, len(items))

    order = {it.id: i for i, it in enumerate(items)}
    results.sort(key=lambda r: order.get(r.item_id, 0))
    return make_task_result(
        task, results, dataset_id=dataset_id, dataset_sha256=dataset_sha256
    )


def rescore_task(task: Task, items: Sequence[Item], jsonl_path: Path,
                 *, dataset_id: str, dataset_sha256: str) -> TaskResult:
    """Recompute metrics from stored responses, without calling any model.

    This is why per-item records are kept. When an extraction rule is corrected,
    every historical run is re-scored offline in seconds, and old numbers stay
    comparable instead of being silently abandoned.
    """
    by_id = {it.id: it for it in items}
    results: list[ItemResult] = []

    # The file is append-only, so a retried item appears more than once — an
    # `error` row followed by the `ok` row that replaced it. Only the last
    # record for an id counts; reading line by line would score the superseded
    # attempt as well and inflate the denominator with failures that were fixed.
    latest: dict[str, dict] = {}
    with open(jsonl_path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                row = json.loads(line)
                latest[str(row["item_id"])] = row

    for row in latest.values():
        item = by_id.get(str(row["item_id"]))
        if item is None:
            continue
        if row.get("status") == ParseStatus.ERROR.value:
            results.append(_result_from_row(row))
            continue
        extraction = task.parse(row.get("response", ""), item)
        score = task.score(extraction, item) if extraction.ok else 0.0
        results.append(ItemResult(
            item_id=item.id, prompt=row.get("prompt", ""), response=row.get("response", ""),
            status=extraction.status, extracted=extraction.value, gold=item.gold,
            score=score, strategy=extraction.strategy, evidence=extraction.evidence,
            meta=dict(item.meta), finish_reason=row.get("finish_reason", "stop"),
            prompt_tokens=row.get("prompt_tokens", 0),
            completion_tokens=row.get("completion_tokens", 0),
        ))
    return make_task_result(
        task, results, dataset_id=dataset_id, dataset_sha256=dataset_sha256
    )
