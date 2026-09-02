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

from .config import ModelConfig, SuiteConfig, TaskConfig, list_configs
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


def _aggregate(entries: list[dict[str, Any]]) -> dict[str, Any]:
    """Combine repeated measurements of one task into a single cell.

    Runs arrive newest first. A model measured once returns that measurement
    unchanged, and a model re-measured after a fix returns the newest, because
    the later run supersedes the earlier one.

    Repeated runs over the *same* dataset and task version are something else:
    replicates. A model that decodes stochastically gives a different answer each
    pass, so one pass is a draw rather than a value, and the published figure is
    the mean of the passes with their observed range beside it. Publishing
    whichever pass happened to run last would report a sample as if it were a
    measurement, which for DiffusionGemma meant 44.40 on DTM where the mean of
    three passes is 43.92.
    """
    newest = entries[0]
    key = (newest.get("dataset_sha256"), newest.get("task_version"))
    same = [e for e in entries
            if (e.get("dataset_sha256"), e.get("task_version")) == key
            and (e.get("metrics") or {}).get("primary") is not None]
    if len(same) < 2:
        return newest

    cell = dict(newest)
    cell["metrics"] = dict(newest.get("metrics") or {})
    scores = [e["metrics"]["primary"] for e in same]
    cell["metrics"]["primary"] = round(sum(scores) / len(scores), 2)
    for bound in ("ci_low", "ci_high"):
        vals = [(e.get("metrics") or {}).get(bound) for e in same]
        if all(v is not None for v in vals):
            cell["metrics"][bound] = round(sum(vals) / len(vals), 2)
    cell["replicates"] = len(same)
    cell["replicate_range"] = [round(min(scores), 2), round(max(scores), 2)]
    return cell


def _unpublished_models() -> set[str]:
    """Display names of models configured with ``publish: false``.

    Matched on the display name because that is what a run manifest records;
    the config file name never reaches the manifest. A config that fails to
    load is ignored rather than fatal: an unreadable config must not be able to
    silently publish a model that was meant to be withheld... which is why the
    default here is to publish nothing on error for that config alone.
    """
    withheld = set()
    for name in list_configs("models"):
        try:
            cfg = ModelConfig.load(name)
        except Exception:  # noqa: BLE001 - a broken config withholds nothing
            continue
        if not cfg.publish:
            withheld.add(cfg.name)
    return withheld


def build_leaderboard(runs_dir: Path, suite: SuiteConfig, output: Path) -> dict[str, Any]:
    """Rebuild the leaderboard from scratch and write it."""
    runs = load_runs(runs_dir)

    # Models withheld from publication are dropped here, before any aggregation,
    # so their numbers cannot reach results.json, LEADERBOARD.md, or any total
    # computed from the rows. The runs stay on disk and stay inspectable.
    withheld_models = _unpublished_models()
    if withheld_models:
        runs = [r for r in runs if r.get("model") not in withheld_models]

    # A model's tracks are spread across several runs by design. The core suite
    # is measured in one run, riddles in another, instruction following in a
    # third, and a backfill adds a track months later. Selecting a single run per
    # model therefore loses whatever the other runs measured: with the riddle
    # runs present, picking the newest run left every model reading as having no
    # DTM score at all, because those runs carry no DTM cell.
    #
    # So the merge is per task, not per run. Runs arrive newest first, so the
    # first run that carries a task supplies it, and older measurements of the
    # same task stay on disk as history.
    all_tasks = list(dict.fromkeys([*suite.tasks, *suite.reported]))
    wanted = set(all_tasks)
    latest: dict[str, dict] = {}
    for run in runs:
        entries = run.get("tasks") or {}
        if not wanted & set(entries):
            continue
        model = run.get("model", "unknown")
        merged = latest.get(model)
        if merged is None:
            # The newest run carrying any wanted task supplies the row metadata:
            # licence, quantisation, harness commit and so on.
            merged = dict(run)
            merged["tasks"] = {}
            latest[model] = merged
        for name, entry in entries.items():
            if name in wanted:
                merged.setdefault("_seen", {}).setdefault(name, []).append(entry)

    for merged in latest.values():
        merged["tasks"] = {name: _aggregate(entries)
                           for name, entries in merged.pop("_seen", {}).items()}

    chance = {}
    for name in all_tasks:
        cfg = TaskConfig.load(name)
        chance[name] = get_task(cfg.task)().chance_level

    rows: list[dict[str, Any]] = []
    for model, run in latest.items():
        scores: dict[str, Any] = {}
        withheld: list[tuple[str, dict[str, Any]]] = []
        for name in all_tasks:
            entry = (run.get("tasks") or {}).get(name)
            if not entry or "metrics" not in entry:
                continue
            metrics, diag = entry["metrics"], entry.get("diagnostics", {})
            coverage = diag.get("coverage", 1.0)
            if coverage < PUBLISH_FLOOR:
                # Carry the counts, not just the fraction. A reader looking at a
                # blank cell cannot tell "never run" from "run, and most of the
                # answers were unscorable" — and those say opposite things about
                # a model. The score itself stays out: withholding it is the
                # whole point, since a figure computed from under half the items
                # is not one anybody should quote.
                withheld.append((name, {
                    "coverage": round(coverage, 4),
                    "n": entry.get("n_scored"),
                    "n_items": entry.get("n_items"),
                }))
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
            # Present only where a model was measured more than once, so a
            # reader can see the figure is a mean and how far the passes spread.
            if entry.get("replicates"):
                scores[name]["replicates"] = entry["replicates"]
                scores[name]["replicate_range"] = entry["replicate_range"]

        complete = all(t in scores for t in suite.tasks)
        composite = None
        if complete or not suite.require_complete:
            normalised = [
                normalize_against_chance(scores[t]["score"], chance.get(t, 0.0))
                for t in suite.tasks
                if t in scores and scores[t]["score"] is not None
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
            "reasoning": _reasoning_summary(run, all_tasks),
            "composite": composite,
            "complete": complete,
            "missing": [t for t in suite.tasks if t not in scores],
            # Distinguish "not run" from "run, but too few items scored".
            "withheld": dict(withheld),
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
             "version": get_task(TaskConfig.load(t).task)().version,
             # Whether this track feeds the composite. Published-but-not-
             # composited tracks exist (the multiple-choice riddles), so a
             # reader counting columns would otherwise get the denominator
             # wrong when a row's composite is built from a partial set.
             "composited": t in suite.tasks}
            for t in all_tasks
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


#: Column headings for the markdown leaderboard. A task with no entry here still
#: appears, under its task id, so adding a track cannot silently drop a column.
TASK_LABELS = {
    "dtm": "DTM",
    "reasoning_uz": "Reasoning",
    "translation_uz": "Translation",
    "ifeval_uz": "Instructions",
    "zarbulmasal": "Riddle (recall)",
    "zarbulmasal_mc": "Riddle (choice)",
    "dtm_heldout": "DTM held out",
}


def render_markdown(board: dict[str, Any]) -> str:
    """Render the leaderboard as markdown, from the same object the site reads.

    Written because the two drifted. The markdown table was assembled by hand
    while ``results.json`` was generated, so when the suite widened from three
    tracks to five the site recomputed its composites and the markdown kept the
    old ones: the same models, the same per-task cells, two different rankings.
    A published table that disagrees with the published data is worse than
    having only one of them.

    Both now come from one ``build_leaderboard`` call, so they cannot disagree.
    """
    tasks = [t["id"] for t in board.get("tasks", [])]
    labels = [TASK_LABELS.get(t, t) for t in tasks]

    def cell(model: dict[str, Any], task: str) -> str:
        score = (model.get("scores") or {}).get(task)
        if score and score.get("score") is not None:
            return f"{score['score']:.2f}"
        return "withheld" if task in (model.get("withheld") or {}) else "-"

    # Ordered by the first task in the suite, which is the flagship: it is the
    # one measured for every model and the one with the tightest intervals.
    # Composite would order on a number some rows do not have.
    lead = tasks[0] if tasks else None

    def sort_key(model: dict[str, Any]) -> float:
        score = (model.get("scores") or {}).get(lead) if lead else None
        return -(score or {}).get("score", -1)

    rows = sorted(board.get("models", []), key=sort_key)

    head = "| # | Model | Composite | " + " | ".join(labels) + " | Licence |"
    rule = "|---:|---|---:|" + "---:|" * len(labels) + "---|"
    out = [head, rule]
    for i, m in enumerate(rows, 1):
        composite = "-" if m.get("composite") is None else f"{m['composite']:.1f}"
        cells = " | ".join(cell(m, t) for t in tasks)
        out.append(f"| {i} | {m['model']} | {composite} | {cells} | "
                   f"{m.get('license', '')} |")
    return "\n".join(out)


def write_markdown(board: dict[str, Any], path: Path) -> None:
    """Replace the table in ``path``, leaving the surrounding prose alone.

    The commentary around the table is written by a person and explains what the
    numbers mean. Regenerating the whole file would delete it, so only the table
    between the header row and the following blank line is replaced.
    """
    table = render_markdown(board)
    if not path.exists():
        path.write_text("# Leaderboard\n\n" + table + "\n", encoding="utf-8")
        return
    text = path.read_text(encoding="utf-8")
    start = text.find("| # | Model |")
    if start == -1:
        path.write_text(text.rstrip() + "\n\n" + table + "\n", encoding="utf-8")
        return
    end = text.find("\n\n", start)
    end = len(text) if end == -1 else end
    path.write_text(text[:start] + table + text[end:], encoding="utf-8")
