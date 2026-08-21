"""Leaderboard construction.

The leaderboard is *derived*, never edited. It is rebuilt from ``runs/`` on
every publish, so a cell that no run produced cannot appear, and a retracted
run disappears instead of persisting forever.

Three rules the composite score follows:

* **Normalise before averaging.** 25% is chance on a four-option task and well
  above chance on a ten-option one; averaging the raw numbers treats a coin
  flip and real signal as equal.
* **Never average over differing subsets.** A model missing a task in the suite
  gets its per-task cells and *no* composite. Ranking a model on the three
  tasks it happened to complete against one that completed five is not a
  comparison.
* **Every cell carries its interval, its n, and its coverage.** A score whose
  items mostly failed to parse is not a measurement.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .config import SuiteConfig, TaskConfig
from .metrics.accuracy import normalize_against_chance
from .registry import get_task

#: Below this share of scorable items, a cell is published as provisional: the
#: number says more about extraction than about the model.
COVERAGE_FLOOR = 0.80

#: Below this, the cell is withheld entirely. gemma4:26b scored 85.7 on the
#: reasoning task from 7 of 100 items — a number with a 49-point interval that
#: would have sat on the leaderboard looking like a result. A cell this thin
#: reports the harness, not the model.
PUBLISH_FLOOR = 0.50


def load_runs(runs_dir: Path) -> list[dict[str, Any]]:
    """Load every run manifest, newest first."""
    runs = []
    for manifest_path in sorted(runs_dir.glob("*/manifest.json")):
        try:
            runs.append(json.loads(manifest_path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            continue
    runs.sort(key=lambda m: m.get("finished_at") or m.get("started_at") or "", reverse=True)
    return runs


def build_leaderboard(runs_dir: Path, suite: SuiteConfig, output: Path) -> dict[str, Any]:
    """Rebuild the leaderboard from scratch and write it."""
    runs = load_runs(runs_dir)

    # Most recent run per model wins; earlier ones stay on disk as history.
    latest: dict[str, dict] = {}
    for run in runs:
        latest.setdefault(run.get("model", "unknown"), run)

    chance = {}
    for name in suite.tasks:
        cfg = TaskConfig.load(name)
        chance[name] = get_task(cfg.task)().chance_level

    rows: list[dict[str, Any]] = []
    for model, run in latest.items():
        scores: dict[str, Any] = {}
        withheld: list[tuple[str, float]] = []
        for name in suite.tasks:
            entry = (run.get("tasks") or {}).get(name)
            if not entry or "metrics" not in entry:
                continue
            metrics, diag = entry["metrics"], entry.get("diagnostics", {})
            coverage = diag.get("coverage", 1.0)
            if coverage < PUBLISH_FLOOR:
                withheld.append((name, coverage))
                continue
            scores[name] = {
                "score": metrics.get("primary"),
                "ci_low": metrics.get("ci_low"),
                "ci_high": metrics.get("ci_high"),
                "n": entry.get("n_scored"),
                "n_items": entry.get("n_items"),
                "coverage": coverage,
                "unparsed_rate": diag.get("unparsed_rate", 0.0),
                "chance": round(chance.get(name, 0.0) * 100, 1),
                "task_version": entry.get("task_version"),
                "dataset_sha256": (entry.get("dataset_sha256") or "")[:12],
                # Two reasons a reader should not take a cell at face value.
                "provisional": coverage < COVERAGE_FLOOR,
                "at_or_below_chance": bool(diag.get("at_or_below_chance")),
            }

        complete = len(scores) == len(suite.tasks)
        composite = None
        if complete or not suite.require_complete:
            normalised = [
                normalize_against_chance(s["score"], chance.get(t, 0.0))
                for t, s in scores.items() if s["score"] is not None
            ]
            if normalised and (complete or not suite.require_complete):
                composite = round(sum(normalised) / len(normalised), 2)
        if suite.require_complete and not complete:
            composite = None

        rows.append({
            "model": model,
            "organization": run.get("organization", "Unknown"),
            "license": run.get("license", "unknown"),
            "openWeights": run.get("license", "unknown").lower()
                           not in ("unknown", "proprietary", "closed", ""),
            "weightsUrl": run.get("weights_url", ""),
            "quantization": run.get("quantization", ""),
            # Whether the model reasoned before answering changes what the score
            # measures, so it is published on the row rather than buried in the
            # manifest. Per task, because a suite can legitimately suppress
            # reasoning on a knowledge benchmark and require it on a reasoning one.
            "reasoning": _reasoning_summary(run, suite.tasks),
            "composite": composite,
            "complete": complete,
            "missing": [t for t in suite.tasks if t not in scores],
            # Distinguish "not run" from "run, but too few items scored".
            "withheld": {t: round(c, 4) for t, c in withheld},
            "scores": scores,
            "runId": run.get("run_id"),
            "runDate": (run.get("finished_at") or run.get("started_at", ""))[:10],
            "harnessVersion": run.get("harness_version", ""),
            "harnessCommit": (run.get("harness_git_sha") or "")[:12],
            "temperature": run.get("temperature"),
            "provenance": "organiser-run",
        })

    # Rank only complete rows; incomplete ones are listed below, unranked.
    ranked = sorted([r for r in rows if r["composite"] is not None],
                    key=lambda r: r["composite"], reverse=True)
    _assign_ranks(ranked)
    unranked = sorted([r for r in rows if r["composite"] is None], key=lambda r: r["model"])
    for r in unranked:
        r["rank"] = None

    board = {
        "suite": suite.name,
        "suiteDescription": suite.description.strip(),
        "generatedAt": datetime.now(UTC).isoformat(timespec="seconds"),
        "tasks": [
            {"id": t, "chance": round(chance.get(t, 0.0) * 100, 1),
             "version": get_task(TaskConfig.load(t).task)().version}
            for t in suite.tasks
        ],
        "notes": {
            **({"status": "No model has been evaluated on this suite yet. Results "
                          "appear here only when a run produces them — the leaderboard "
                          "is rebuilt from runs/ and is never edited by hand."}
               if not rows else {}),
            "composite": "Mean of per-task scores normalised against each task's "
                         "random baseline. Shown only for models with a complete "
                         "run over the suite.",
            "intervals": "95% Wilson intervals. Models whose intervals overlap "
                         "share a rank.",
            "coverage": f"Cells below {COVERAGE_FLOOR:.0%} scorable items are marked "
                        f"provisional — parse and truncation failures are excluded "
                        f"from the score and reported separately.",
        },
        "models": ranked + unranked,
    }

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(board, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return board


def _reasoning_summary(run: dict[str, Any], tasks: list[str]) -> dict[str, Any]:
    """Summarise the reasoning mode a run actually used.

    Returns the mode per task plus a single ``label`` for the leaderboard row:
    ``"no-think"`` when reasoning was suppressed throughout, ``"think"`` when it
    was on throughout, and ``"mixed"`` when a suite deliberately does both —
    which is the normal case, since suppressing reasoning is defensible for a
    knowledge benchmark and incoherent for a reasoning one.
    """
    per_task = {}
    for name in tasks:
        entry = (run.get("tasks") or {}).get(name) or {}
        per_task[name] = entry.get("reasoning") or run.get("reasoning") or "default"
    modes = set(per_task.values())
    if not modes:
        label = "unknown"
    elif modes == {"off"}:
        label = "no-think"
    elif "off" not in modes:
        label = "think"
    else:
        label = "mixed"
    return {"label": label, "byTask": per_task}


def _assign_ranks(ranked: list[dict[str, Any]]) -> None:
    """Assign ranks, marking ties where confidence intervals overlap.

    A rank is an estimate, not a fact. Two models whose intervals overlap are
    not distinguishable by this evidence, and presenting one above the other —
    with a medal — asserts something the data does not support.
    """
    for i, row in enumerate(ranked):
        row["rank"] = i + 1
        row["tiedWith"] = []
    for i, a in enumerate(ranked):
        for j, b in enumerate(ranked):
            if i == j:
                continue
            if _overlaps(a, b):
                a["tiedWith"].append(b["model"])


def _overlaps(a: dict, b: dict) -> bool:
    """True if two models overlap on every shared task's interval."""
    shared = set(a["scores"]) & set(b["scores"])
    if not shared:
        return False
    for task in shared:
        sa, sb = a["scores"][task], b["scores"][task]
        if sa.get("ci_low") is None or sb.get("ci_low") is None:
            continue
        if sa["ci_high"] < sb["ci_low"] or sb["ci_high"] < sa["ci_low"]:
            return False
    return True


def summarise_run(run_dir: Path) -> str:
    """Human-readable summary of one run."""
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    lines = [
        f"Run      {manifest.get('run_id')}",
        f"Model    {manifest.get('model')}  ({manifest.get('provider')})",
        f"Licence  {manifest.get('license')}   Quant {manifest.get('quantization') or '—'}",
        f"Harness  {manifest.get('harness_version')} @ {(manifest.get('harness_git_sha') or '')[:12]}",
        f"Started  {manifest.get('started_at')}",
        "",
    ]
    for name, entry in (manifest.get("tasks") or {}).items():
        if "error" in entry:
            lines.append(f"  {name:16s} FAILED: {entry['error']}")
            continue
        m, d = entry.get("metrics", {}), entry.get("diagnostics", {})
        lines.append(
            f"  {name:16s} {m.get('primary')}  "
            f"[{m.get('ci_low')}, {m.get('ci_high')}]  "
            f"n={entry.get('n_scored')}/{entry.get('n_items')}  "
            f"unparsed={d.get('unparsed_rate', 0):.1%}  "
            f"trunc={d.get('truncated_rate', 0):.1%}  "
            f"err={d.get('error_rate', 0):.1%}"
        )
        if d.get("at_or_below_chance"):
            lines.append(f"  {'':16s} ⚠ at or below the {d.get('chance_level', 0):.0%} chance level")
    return "\n".join(lines)
