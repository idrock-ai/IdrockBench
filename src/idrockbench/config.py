"""Configuration.

Tasks, models and suites are YAML, not code. Adding a benchmark to the suite,
pointing a task at a new dataset, or registering a model is a config edit — the
runner never needs to know the list.

    configs/tasks/dtm.yaml       one task: dataset, split, budget, options
    configs/models/*.yaml        one model: provider, id, licence, weights
    configs/suites/*.yaml        which tasks make up a published leaderboard
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .data.loader import REPO_ROOT

CONFIG_DIR = REPO_ROOT / "configs"


@dataclass(slots=True)
class TaskConfig:
    """How one task is run."""

    task: str
    dataset: str
    split: str = "test"
    dataset_config: str | None = None
    dataset_revision: str | None = None
    max_tokens: int | None = None
    seed: int = 0
    #: Overrides the model's reasoning setting for this task. A reasoning
    #: benchmark must be able to demand reasoning even from a model configured
    #: to suppress it for cheaper tasks — otherwise the suite measures reasoning
    #: with reasoning switched off.
    reasoning: str | None = None

    #: Override the model's concurrency and per-request timeout for this task.
    #:
    #: Both belong to the task, not the model, because they follow generation
    #: length. A direct-answer task emits ~2 tokens and wants high concurrency;
    #: a reasoning task emits thousands and wants low concurrency and a long
    #: timeout. Getting this wrong is silent: running 16 concurrent 8192-token
    #: generations against a 300s timeout produced 26 read-timeouts on a single
    #: model, each recorded as an error rather than a score.
    concurrency: int | None = None
    timeout: int | None = None

    options: dict[str, Any] = field(default_factory=dict)
    #: Weight in the composite score. Equal by default, and any deviation is
    #: published rather than buried in code.
    weight: float = 1.0

    @classmethod
    def load(cls, name: str) -> TaskConfig:
        path = _find(CONFIG_DIR / "tasks", name)
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        data.setdefault("task", path.stem)
        return cls(**data)


@dataclass(slots=True)
class ModelConfig:
    """A model under evaluation, with the metadata a leaderboard row needs."""

    model: str
    provider: str
    name: str = ""
    organization: str = "Unknown"
    #: SPDX identifier, or "proprietary". Never guessed from the model name —
    #: a licence claim about a third party is a factual assertion.
    license: str = "unknown"
    weights_url: str = ""
    params_b: float | None = None
    quantization: str = ""
    base_url: str | None = None
    api_key_env: str | None = None
    temperature: float = 0.0
    top_p: float | None = None
    seed: int = 0
    reasoning: str = "default"
    #: Multiplies the task's token budget for this model. Some reasoning models
    #: cannot produce a direct answer at all — deepseek-r1 emits its whole
    #: response as reasoning and only writes an answer once that finishes, so a
    #: budget sized for a one-letter reply yields an empty string every time.
    #: Recorded per task in the manifest, so an unequal budget is visible rather
    #: than hidden.
    max_tokens_scale: float = 1.0
    concurrency: int = 4
    timeout: int = 300
    extra_body: dict[str, Any] = field(default_factory=dict)
    notes: str = ""
    #: Whether this model's scores may appear on the published leaderboard and
    #: the site. False keeps a model fully measured and its runs intact while
    #: withholding the numbers from publication — for a model evaluated under an
    #: agreement that does not permit publishing, or one whose owner has not
    #: released the results. It is a publication decision, not a data one:
    #: nothing is deleted and `idrockbench show <run>` still reports the scores.
    publish: bool = True

    def __post_init__(self) -> None:
        if not self.name:
            self.name = self.model
        # YAML 1.1 parses bare `off`/`on`/`no`/`yes` as booleans, so
        # `reasoning: off` arrives as False and silently fails a string
        # compare — leaving thinking enabled when the config says otherwise.
        if isinstance(self.reasoning, bool):
            self.reasoning = "off" if self.reasoning is False else "on"
        self.reasoning = str(self.reasoning)

    @property
    def is_open_weights(self) -> bool:
        """Derived from the declared licence, never from the model's name."""
        return self.license.lower() not in ("unknown", "proprietary", "closed", "")

    @classmethod
    def load(cls, name: str) -> ModelConfig:
        path = _find(CONFIG_DIR / "models", name)
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return cls(**data)


@dataclass(slots=True)
class SuiteConfig:
    """A named set of tasks that make up a published leaderboard."""

    name: str
    tasks: list[str]
    description: str = ""
    #: A model missing any of these gets per-task cells but no composite score.
    #: Averaging over whatever subset a model happens to have makes two rows
    #: incomparable while presenting them as a ranking.
    require_complete: bool = True
    #: Published on the leaderboard but excluded from the composite. For a track
    #: that measures the same items a composited one already covers: the riddle
    #: set is scored both as free recall and as multiple choice, and counting
    #: both would give riddles double the weight of every other subject.
    reported: list[str] = field(default_factory=list)

    @classmethod
    def load(cls, name: str) -> SuiteConfig:
        path = _find(CONFIG_DIR / "suites", name)
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        data.setdefault("name", path.stem)
        return cls(**data)


def _find(directory: Path, name: str) -> Path:
    """Resolve a config by bare name, stem, or path."""
    candidates = [Path(name), directory / name,
                  directory / f"{name}.yaml", directory / f"{name}.yml"]
    for c in candidates:
        if c.exists() and c.is_file():
            return c
    available = sorted(p.stem for p in directory.glob("*.y*ml")) if directory.exists() else []
    raise FileNotFoundError(
        f"No config {name!r} in {directory}. Available: {', '.join(available) or '(none)'}"
    )


def list_configs(kind: str) -> list[str]:
    directory = CONFIG_DIR / kind
    if not directory.exists():
        return []
    return sorted(p.stem for p in directory.glob("*.y*ml"))
