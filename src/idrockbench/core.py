from __future__ import annotations

import dataclasses
import hashlib
import json
import platform
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from .extraction import NON_SCORING, ParseStatus


@dataclass(slots=True)
class Item:
    id: str
    payload: dict[str, Any]
    gold: Any
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ModelResponse:
    text: str
    finish_reason: str = "stop"
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_s: float = 0.0
    error: str | None = None

    @property
    def truncated(self) -> bool:
        return self.finish_reason in ("length", "max_tokens")


@dataclass(slots=True)
class ItemResult:
    item_id: str
    prompt: str
    response: str
    status: ParseStatus
    extracted: str | None
    gold: Any
    score: float
    strategy: str = ""
    evidence: str = ""
    meta: dict[str, Any] = field(default_factory=dict)
    finish_reason: str = "stop"
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_s: float = 0.0
    error: str | None = None

    @property
    def scorable(self) -> bool:
        return self.status not in NON_SCORING

    def to_json(self) -> str:
        d = dataclasses.asdict(self)
        d["status"] = self.status.value
        return json.dumps(d, ensure_ascii=False)


@dataclass(slots=True)
class TaskResult:
    task: str
    task_version: str
    dataset_id: str
    dataset_sha256: str
    n_items: int
    n_scored: int
    metrics: dict[str, Any]
    diagnostics: dict[str, Any]
    breakdown: dict[str, dict[str, Any]] = field(default_factory=dict)

    @property
    def primary(self) -> float | None:
        return self.metrics.get("primary")


def sha256_file(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def git_sha(cwd=None) -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=cwd, capture_output=True, text=True, timeout=5, check=True,
        )
        dirty = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=cwd, capture_output=True, text=True, timeout=5, check=False,
        ).stdout.strip()
        return out.stdout.strip() + ("-dirty" if dirty else "")
    except Exception:
        return "unknown"


@dataclass(slots=True)
class RunManifest:
    run_id: str
    model: str
    provider: str
    model_revision: str = ""
    quantization: str = ""
    organization: str = ""
    license: str = ""
    weights_url: str = ""

    temperature: float = 0.0
    top_p: float | None = None
    seed: int = 0
    max_tokens: dict[str, int] = field(default_factory=dict)
    reasoning: str = "default"
    chat_template: bool = True

    harness_version: str = ""
    harness_git_sha: str = ""
    python_version: str = field(default_factory=lambda: sys.version.split()[0])
    platform: str = field(default_factory=platform.platform)
    package_versions: dict[str, str] = field(default_factory=dict)

    started_at: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat(timespec="seconds")
    )
    finished_at: str = ""
    tasks: dict[str, dict[str, Any]] = field(default_factory=dict)
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)
