from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .config import ModelConfig, SuiteConfig, TaskConfig, list_configs
from .metrics.accuracy import normalize_against_chance
from .registry import get_task

COVERAGE_FLOOR = 0.80

PUBLISH_FLOOR = 0.50


def load_runs(runs_dir: Path) -> list[dict[str, Any]]:
    runs = []
    for manifest_path in sorted(runs_dir.glob("*/manifest.json")):
        try:
            runs.append(json.loads(manifest_path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            continue
    runs.sort(key=lambda m: m.get("finished_at") or m.get("started_at") or "", reverse=True)
    return runs


def _aggregate(entries: list[dict[str, Any]]) -> dict[str, Any]:
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
    withheld = set()
    for name in list_configs("models"):
        try:
            cfg = ModelConfig.load(name)
        except Exception:  # noqa: BLE001
            continue
        if not cfg.publish:
            withheld.add(cfg.name)
    return withheld


def build_leaderboard(runs_dir: Path, suite: SuiteConfig, output: Path) -> dict[str, Any]:
    runs = load_runs(runs_dir)

    withheld_models = _unpublished_models()
    if withheld_models:
        runs = [r for r in runs if r.get("model") not in withheld_models]

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
                "provisional": coverage < COVERAGE_FLOOR,
                "at_or_below_chance": bool(diag.get("at_or_below_chance")),
            }
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
            "reasoning": _reasoning_summary(run, all_tasks),
            "composite": composite,
            "complete": complete,
            "missing": [t for t in suite.tasks if t not in scores],
            "withheld": dict(withheld),
            "scores": scores,
            "runId": run.get("run_id"),
            "runDate": (run.get("finished_at") or run.get("started_at", ""))[:10],
            "harnessVersion": run.get("harness_version", ""),
            "harnessCommit": (run.get("harness_git_sha") or "")[:12],
            "temperature": run.get("temperature"),
            "provenance": "organiser-run",
        })

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
    tasks = [t["id"] for t in board.get("tasks", [])]
    labels = [TASK_LABELS.get(t, t) for t in tasks]

    def cell(model: dict[str, Any], task: str) -> str:
        score = (model.get("scores") or {}).get(task)
        if score and score.get("score") is not None:
            return f"{score['score']:.2f}"
        return "withheld" if task in (model.get("withheld") or {}) else "-"

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
