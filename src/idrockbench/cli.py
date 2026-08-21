"""Command line interface.

    idrockbench list                          what is available
    idrockbench validate                      check every dataset
    idrockbench run --model llama3.1-8b-ollama --suite core
    idrockbench rescore runs/<run_id>         recompute from stored responses
    idrockbench report                        build the leaderboard
    idrockbench show runs/<run_id>            summarise one run
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

from . import __version__
from .config import ModelConfig, SuiteConfig, TaskConfig, list_configs
from .core import RunManifest, git_sha
from .data.loader import REPO_ROOT, load
from .registry import available_providers, available_tasks, get_provider, get_task
from .report import build_leaderboard, summarise_run
from .runner import evaluate_task, rescore_task

RUNS_DIR = REPO_ROOT / "runs"
logger = logging.getLogger("idrockbench")


def _slug(text: str) -> str:
    """Filesystem- and shell-safe run id. A display name like "Llama 3.1 8B"
    otherwise produces a directory with spaces in it."""
    out = re.sub(r"[^A-Za-z0-9._-]+", "-", text).strip("-").lower()
    return re.sub(r"-{2,}", "-", out) or "run"


def _utc_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def _instantiate_task(cfg: TaskConfig):
    return get_task(cfg.task)(seed=cfg.seed, options=cfg.options)


def cmd_list(args: argparse.Namespace) -> int:
    print("Task implementations :", ", ".join(available_tasks()))
    print("Model providers      :", ", ".join(available_providers()))
    print("Task configs         :", ", ".join(list_configs("tasks")))
    print("Model configs        :", ", ".join(list_configs("models")))
    print("Suites               :", ", ".join(list_configs("suites")))
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    """Check every dataset against its task's declared invariants.

    Run in CI. A dataset defect caught here cannot become a published number.
    """
    names = args.tasks or list_configs("tasks")
    failed = 0
    for name in names:
        cfg = TaskConfig.load(name)
        task = _instantiate_task(cfg)
        try:
            ds = load(cfg.dataset, split=cfg.split, config=cfg.dataset_config,
                      revision=cfg.dataset_revision)
        except Exception as exc:
            print(f"✗ {name}: {exc}")
            failed += 1
            continue
        problems = task.validate(ds.rows)
        items = task.prepare(ds.rows)
        mark = "✗" if problems else "✓"
        print(f"{mark} {name}: {len(ds)} rows -> {len(items)} items, sha256 {ds.sha256[:12]}")
        for p in problems[: args.limit]:
            print(f"    · {p}")
        if len(problems) > args.limit:
            print(f"    · … and {len(problems) - args.limit} more")
        if problems:
            failed += 1
    if failed and args.strict:
        print(f"\n{failed} dataset(s) reported problems.", file=sys.stderr)
        return 1
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    model_cfg = ModelConfig.load(args.model)
    if args.suite:
        task_names = SuiteConfig.load(args.suite).tasks
    elif args.tasks:
        task_names = args.tasks
    else:
        task_names = SuiteConfig.load("core").tasks

    run_id = args.run_id or f"{_slug(model_cfg.name)}-{_utc_stamp()}"
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    provider = get_provider(model_cfg.provider)(
        model_cfg.model,
        base_url=model_cfg.base_url,
        temperature=model_cfg.temperature,
        top_p=model_cfg.top_p,
        seed=model_cfg.seed,
        timeout=model_cfg.timeout,
        reasoning=model_cfg.reasoning,
        extra_body=model_cfg.extra_body,
    )
    described = provider.describe()

    manifest = RunManifest(
        run_id=run_id,
        model=model_cfg.name,
        provider=model_cfg.provider,
        model_revision=described.get("revision", ""),
        quantization=model_cfg.quantization or described.get("quantization", ""),
        organization=model_cfg.organization,
        license=model_cfg.license,
        weights_url=model_cfg.weights_url,
        temperature=model_cfg.temperature,
        top_p=model_cfg.top_p,
        seed=model_cfg.seed,
        reasoning=model_cfg.reasoning,
        harness_version=__version__,
        harness_git_sha=git_sha(REPO_ROOT),
        notes=args.notes or "",
    )

    print(f"Run {run_id}")
    print(f"  model    {model_cfg.name}  ({model_cfg.provider}/{model_cfg.model})")
    if manifest.quantization:
        print(f"  quant    {manifest.quantization}")
    print(f"  tasks    {', '.join(task_names)}")
    print(f"  output   {run_dir}\n")

    for name in task_names:
        cfg = TaskConfig.load(name)
        task = _instantiate_task(cfg)
        ds = load(cfg.dataset, split=cfg.split, config=cfg.dataset_config,
                  revision=cfg.dataset_revision)
        items = task.prepare(ds.rows)
        if args.limit:
            items = items[: args.limit]
        budget = cfg.max_tokens or task.default_max_tokens
        if model_cfg.max_tokens_scale != 1.0:
            budget = int(budget * model_cfg.max_tokens_scale)

        # A task may require reasoning even when the model config disables it.
        # Disabling thinking is a defensible protocol for a knowledge benchmark
        # and an incoherent one for a reasoning benchmark — measuring reasoning
        # with reasoning switched off is exactly the mistake this harness was
        # rebuilt to remove. The task wins, and the manifest records what was
        # actually used per task, not just the model-level default.
        reasoning = cfg.reasoning if cfg.reasoning is not None else model_cfg.reasoning
        provider.reasoning = reasoning

        # Concurrency and timeout follow generation length, which is a property
        # of the task rather than the model.
        concurrency = args.concurrency or cfg.concurrency or model_cfg.concurrency
        provider.timeout = cfg.timeout or model_cfg.timeout

        print(f"[{name}] {len(items)} items, max_tokens={budget}")

        def progress(done: int, total: int, _n=name) -> None:
            if done % 25 == 0 or done == total:
                pct = done / total * 100 if total else 100
                print(f"  {_n}: {done}/{total} ({pct:.0f}%)", end="\r", flush=True)

        try:
            result = evaluate_task(
                task, items, provider,
                dataset_id=cfg.dataset, dataset_sha256=ds.sha256,
                output_dir=run_dir, name=name, max_tokens=budget,
                concurrency=concurrency,
                resume=not args.no_resume, progress=progress,
            )
        except KeyboardInterrupt:
            print("\n  interrupted — completed items are saved; re-run to resume")
            raise
        except Exception as exc:
            # One task failing must never discard the tasks already completed.
            logger.exception("task %s failed", name)
            manifest.tasks[name] = {"error": f"{type(exc).__name__}: {exc}"}
            _write_manifest(run_dir, manifest)
            print(f"\n  ✗ {name} failed: {exc}")
            continue

        manifest.max_tokens[name] = budget
        manifest.tasks[name] = {
            "task_version": task.version,
            "dataset": cfg.dataset,
            "dataset_sha256": ds.sha256,
            "max_tokens": budget,
            "reasoning": reasoning,
            "concurrency": concurrency,
            "timeout": provider.timeout,
            "options": dict(cfg.options),
            "n_items": result.n_items,
            "n_scored": result.n_scored,
            "metrics": result.metrics,
            "diagnostics": result.diagnostics,
            "breakdown": result.breakdown,
        }
        _write_manifest(run_dir, manifest)

        d = result.diagnostics
        print(f"\n  {name}: {result.primary}  "
              f"[{result.metrics.get('ci_low')}, {result.metrics.get('ci_high')}]  "
              f"n={result.n_scored}/{result.n_items}  "
              f"unparsed={d['unparsed_rate']:.1%} truncated={d['truncated_rate']:.1%} "
              f"errors={d['error_rate']:.1%}")
        if d.get("at_or_below_chance"):
            print(f"  ⚠ {name} is at or below its {task.chance_level:.0%} chance level — "
                  f"check the extractor before trusting this number")

    manifest.finished_at = datetime.now(UTC).isoformat(timespec="seconds")
    _write_manifest(run_dir, manifest)
    print(f"\nManifest: {run_dir / 'manifest.json'}")
    return 0


def cmd_rescore(args: argparse.Namespace) -> int:
    """Recompute metrics from stored responses, with no model calls."""
    run_dir = Path(args.run_dir)
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    manifest.setdefault("tasks", {})
    failed = False

    # Rescore every task that has per-item records, not only those the manifest
    # lists. The JSONL is the record and the manifest is an index of it, so when
    # they disagree the records win.
    #
    # They disagree more easily than they should: re-running one task with
    # --tasks writes a fresh manifest and drops the entries for tasks it did not
    # run. qwen35-2b and qwen35-0.8b each kept 2062 dtm rows and 800 translation
    # rows on disk while their manifests listed only reasoning_uz, so both showed
    # as unmeasured on two tracks they had in fact completed.
    recorded = {f.stem for f in run_dir.glob("*.jsonl")}
    known = set(list_configs("tasks"))
    for orphan in sorted(recorded - known):
        print(f"{orphan}: per-item records with no task config, skipped",
              file=sys.stderr)

    for name in sorted((recorded & known) | set(manifest["tasks"])):
        jsonl = run_dir / f"{name}.jsonl"
        if not jsonl.exists():
            print(f"{name}: no per-item records at {jsonl.name} — cannot rescore",
                  file=sys.stderr)
            failed = True
            continue
        cfg = TaskConfig.load(name)
        task = _instantiate_task(cfg)
        ds = load(cfg.dataset, split=cfg.split)
        items = task.prepare(ds.rows)
        result = rescore_task(task, items, jsonl,
                              dataset_id=cfg.dataset, dataset_sha256=ds.sha256)
        entry = manifest["tasks"].setdefault(name, {})
        restored = "  (entry restored)" if not entry else ""
        before = entry.get("metrics", {}).get("primary")
        entry.setdefault("dataset", cfg.dataset)
        entry.setdefault("max_tokens", cfg.max_tokens or task.default_max_tokens)
        entry.setdefault("options", dict(cfg.options))
        entry.update({
            "n_items": result.n_items,
            "n_scored": result.n_scored,
            "task_version": task.version,
            "metrics": result.metrics,
            "diagnostics": result.diagnostics,
            "breakdown": result.breakdown,
            # Record the dataset actually scored against, not the one the
            # original run saw. Leaving the old fingerprint in place makes the
            # manifest claim provenance it no longer has — the published number
            # would cite a checksum that matches no file anyone can obtain.
            "dataset_id": cfg.dataset,
            "dataset_sha256": ds.sha256,
            "rescored_at": datetime.now(UTC).isoformat(timespec="seconds"),
        })
        print(f"{name}: {before} -> {result.primary}  "
              f"(task version {task.version}){restored}")
    (run_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return 1 if failed else 0


def cmd_report(args: argparse.Namespace) -> int:
    suite = SuiteConfig.load(args.suite)
    out = Path(args.output) if args.output else REPO_ROOT / "site" / "results.json"
    board = build_leaderboard(RUNS_DIR, suite, out)
    print(f"{len(board['models'])} model(s) -> {out}")
    for row in board["models"]:
        composite = row.get("composite")
        label = f"{composite:.1f}" if composite is not None else "  — (incomplete)"
        print(f"  {label:>8}  {row['model']}")
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    print(summarise_run(Path(args.run_dir)))
    return 0


def _write_manifest(run_dir: Path, manifest: RunManifest) -> None:
    (run_dir / "manifest.json").write_text(
        json.dumps(manifest.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="idrockbench", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="show tasks, providers and configs").set_defaults(fn=cmd_list)

    p = sub.add_parser("validate", help="check datasets against task invariants")
    p.add_argument("tasks", nargs="*", help="task configs (default: all)")
    p.add_argument("--limit", type=int, default=10, help="problems to print per task")
    p.add_argument("--strict", action="store_true", help="exit non-zero on any problem")
    p.set_defaults(fn=cmd_validate)

    p = sub.add_parser("run", help="evaluate a model")
    p.add_argument("--model", required=True, help="model config name")
    p.add_argument("--suite", help="suite config name (default: core)")
    p.add_argument("--tasks", nargs="*", help="task configs, overriding --suite")
    p.add_argument("--limit", type=int, help="first N items per task (smoke test)")
    p.add_argument("--concurrency", type=int, help="override the model's concurrency")
    p.add_argument("--run-id", help="reuse an id to resume a run")
    p.add_argument("--no-resume", action="store_true", help="re-run completed items")
    p.add_argument("--notes", help="free text stored in the manifest")
    p.set_defaults(fn=cmd_run)

    p = sub.add_parser("rescore", help="recompute metrics from stored responses")
    p.add_argument("run_dir")
    p.set_defaults(fn=cmd_rescore)

    p = sub.add_parser("report", help="build the leaderboard from runs/")
    p.add_argument("--suite", default="core")
    p.add_argument("--output")
    p.set_defaults(fn=cmd_report)

    p = sub.add_parser("show", help="summarise one run")
    p.add_argument("run_dir")
    p.set_defaults(fn=cmd_show)

    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S",
    )
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
