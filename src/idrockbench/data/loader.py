"""Dataset loading, hashing and resolution.

Three properties every load guarantees:

* **Paths resolve against the repo, not the shell's working directory.** A
  CWD-relative default silently picks up a stray file, or falls through to a
  remote fetch and reports a package error instead of "file not found".
* **Missing local files are errors.** A path that does not exist is never
  retried as a Hub id.
* **Every load returns a content hash.** A score is bound to exact bytes, so a
  quietly-edited dataset cannot masquerade as the one a published number used.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..core import sha256_file, sha256_text
from ..registry import get_loader, register_loader

#: Repository root, resolved from this file rather than the CWD.
REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = REPO_ROOT / "data"


@dataclass(slots=True)
class Dataset:
    """Loaded rows plus the provenance needed to cite them."""

    id: str
    rows: list[dict[str, Any]]
    sha256: str
    source: str
    revision: str = ""

    def __len__(self) -> int:
        return len(self.rows)


@register_loader(".json")
def _load_json(path: Path) -> list[dict]:
    with open(path, encoding="utf-8-sig") as f:
        data = json.load(f)
    if isinstance(data, dict):
        for key in ("data", "rows", "items", "examples"):
            if isinstance(data.get(key), list):
                return list(data[key])
        return [data]
    return list(data)


@register_loader(".jsonl")
def _load_jsonl(path: Path) -> list[dict]:
    with open(path, encoding="utf-8-sig") as f:
        return [json.loads(line) for line in f if line.strip()]


@register_loader(".csv")
def _load_csv(path: Path) -> list[dict]:
    # utf-8-sig strips the BOM that otherwise turns the first column name into
    # "﻿question_id" and makes every lookup of it fail.
    with open(path, encoding="utf-8-sig", newline="") as f:
        return [dict(r) for r in csv.DictReader(f)]


@register_loader(".tsv")
def _load_tsv(path: Path) -> list[dict]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        return [dict(r) for r in csv.DictReader(f, delimiter="\t")]


def resolve_path(source: str) -> Path | None:
    """Resolve a dataset reference to a file, or ``None`` if it is a Hub id.

    Tried in order: as given, relative to the CWD, relative to ``data/``,
    relative to the repo root. A bare name like ``dtm_benchmark.json`` finds
    ``data/dtm_benchmark.json`` from anywhere.
    """
    if "://" in source:
        return None
    p = Path(source).expanduser()
    for candidate in (p, Path.cwd() / p, DATA_DIR / p, REPO_ROOT / p):
        if candidate.exists() and candidate.is_file():
            return candidate.resolve()
    # A path-looking reference that does not exist is an error, not a Hub id.
    if p.suffix or p.parts[:1] in (("."), ("..")) or len(p.parts) > 1:
        if "/" in source and not p.suffix:
            return None  # looks like "org/dataset"
        raise FileNotFoundError(
            f"Dataset file not found: {source!r}. Looked in {Path.cwd()}, {DATA_DIR}, "
            f"{REPO_ROOT}. Give a path relative to the repo, or a HuggingFace id "
            f"like 'org/name'."
        )
    return None


def load(source: str, *, split: str = "test", config: str | None = None,
         revision: str | None = None) -> Dataset:
    """Load a dataset from a local file or the HuggingFace Hub.

    Args:
        source: Repo-relative path, absolute path, or ``"org/name"`` Hub id.
        split: Hub split. Ignored for local files.
        config: Hub config name.
        revision: Hub revision (commit sha, tag). Strongly recommended — an
            unpinned Hub dataset can change under a published number.
    """
    path = resolve_path(source)

    if path is not None:
        loader = get_loader(path.suffix)
        if loader is None:
            raise ValueError(
                f"No loader for {path.suffix!r}. Supported: .json .jsonl .csv .tsv. "
                f"Register another with @register_loader in idrockbench/data/."
            )
        rows = loader(path)
        if not rows:
            raise ValueError(f"Dataset {path} is empty.")
        return Dataset(
            id=source, rows=rows, sha256=sha256_file(path), source=str(path)
        )

    try:
        from datasets import load_dataset
    except ImportError as exc:
        raise ImportError(
            f"{source!r} is not a local file, so it is treated as a HuggingFace "
            f"dataset id, which needs the 'datasets' package: pip install datasets"
        ) from exc

    kwargs: dict[str, Any] = {"split": split}
    if config:
        kwargs["name"] = config
    if revision:
        kwargs["revision"] = revision
    ds = load_dataset(source, **kwargs)
    rows = [dict(r) for r in ds]
    digest = sha256_text(json.dumps(rows, sort_keys=True, ensure_ascii=False, default=str))
    return Dataset(
        id=source, rows=rows, sha256=digest,
        source=f"hf://{source}" + (f"@{revision}" if revision else ""),
        revision=revision or "",
    )
