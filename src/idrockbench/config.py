from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .data.loader import REPO_ROOT

CONFIG_DIR = REPO_ROOT / "configs"


@dataclass(slots=True)
class TaskConfig:
    task: str
    dataset: str
    split: str = "test"
    dataset_config: str | None = None
    dataset_revision: str | None = None
    max_tokens: int | None = None
    seed: int = 0
    reasoning: str | None = None

    concurrency: int | None = None
    timeout: int | None = None

    options: dict[str, Any] = field(default_factory=dict)
    weight: float = 1.0

    @classmethod
    def load(cls, name: str) -> TaskConfig:
        path = _find(CONFIG_DIR / "tasks", name)
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        data.setdefault("task", path.stem)
        return cls(**data)


@dataclass(slots=True)
class ModelConfig:
    model: str
    provider: str
    name: str = ""
    organization: str = "Unknown"
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
    max_tokens_scale: float = 1.0
    concurrency: int = 4
    timeout: int = 300
    extra_body: dict[str, Any] = field(default_factory=dict)
    notes: str = ""
    publish: bool = True

    def __post_init__(self) -> None:
        if not self.name:
            self.name = self.model
        if isinstance(self.reasoning, bool):
            self.reasoning = "off" if self.reasoning is False else "on"
        self.reasoning = str(self.reasoning)

    @property
    def is_open_weights(self) -> bool:
        return self.license.lower() not in ("unknown", "proprietary", "closed", "")

    @classmethod
    def load(cls, name: str) -> ModelConfig:
        path = _find(CONFIG_DIR / "models", name)
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return cls(**data)


@dataclass(slots=True)
class SuiteConfig:
    name: str
    tasks: list[str]
    description: str = ""
    require_complete: bool = True
    reported: list[str] = field(default_factory=list)

    @classmethod
    def load(cls, name: str) -> SuiteConfig:
        path = _find(CONFIG_DIR / "suites", name)
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        data.setdefault("name", path.stem)
        return cls(**data)


def _find(directory: Path, name: str) -> Path:
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
