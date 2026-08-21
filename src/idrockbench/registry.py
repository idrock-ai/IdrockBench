"""Registries for the extension points.

Tasks, model providers and dataset loaders all register by name. Adding one
means writing a module and decorating a class — no edits to the runner, the
CLI, or any list of imports.

    from idrockbench.registry import register_task
    from idrockbench.tasks.base import Task

    @register_task
    class MyTask(Task):
        name = "my_task"
        ...

Modules under ``idrockbench.tasks`` and ``idrockbench.models`` are imported
automatically on first lookup, so a new file in either package is discovered
without being referenced anywhere.
"""

from __future__ import annotations

import importlib
import pkgutil
from collections.abc import Callable
from typing import TypeVar

_TASKS: dict[str, type] = {}
_PROVIDERS: dict[str, type] = {}
_LOADERS: dict[str, Callable] = {}

_T = TypeVar("_T", bound=type)


def register_task(cls: _T) -> _T:
    """Register a :class:`~idrockbench.tasks.base.Task` under its ``name``."""
    name = getattr(cls, "name", "")
    if not name:
        raise ValueError(f"{cls.__name__} must set a class-level `name`.")
    if not getattr(cls, "version", ""):
        raise ValueError(
            f"{cls.__name__} must set a class-level `version`. Bump it whenever a "
            f"change can move a score, so published numbers stay comparable."
        )
    if name in _TASKS and _TASKS[name] is not cls:
        raise ValueError(f"Task name {name!r} is already registered by {_TASKS[name]!r}.")
    _TASKS[name] = cls
    return cls


def register_provider(cls: _T) -> _T:
    """Register a model provider under its ``name``."""
    name = getattr(cls, "name", "")
    if not name:
        raise ValueError(f"{cls.__name__} must set a class-level `name`.")
    _PROVIDERS[name] = cls
    return cls


def register_loader(suffix: str) -> Callable[[Callable], Callable]:
    """Register a dataset file loader for a suffix, e.g. ``".parquet"``."""

    def deco(fn: Callable) -> Callable:
        _LOADERS[suffix.lower()] = fn
        return fn

    return deco


def _autodiscover(package: str) -> None:
    mod = importlib.import_module(package)
    for info in pkgutil.iter_modules(mod.__path__):
        if info.name.startswith("_"):
            continue
        importlib.import_module(f"{package}.{info.name}")


_discovered: set[str] = set()


def _ensure(package: str) -> None:
    if package not in _discovered:
        _discovered.add(package)
        _autodiscover(package)


def get_task(name: str) -> type:
    _ensure("idrockbench.tasks")
    if name not in _TASKS:
        raise KeyError(f"Unknown task {name!r}. Available: {', '.join(available_tasks())}")
    return _TASKS[name]


def get_provider(name: str) -> type:
    _ensure("idrockbench.models")
    if name not in _PROVIDERS:
        raise KeyError(
            f"Unknown provider {name!r}. Available: {', '.join(available_providers())}"
        )
    return _PROVIDERS[name]


def get_loader(suffix: str):
    _ensure("idrockbench.data")
    return _LOADERS.get(suffix.lower())


def available_tasks() -> list[str]:
    _ensure("idrockbench.tasks")
    return sorted(_TASKS)


def available_providers() -> list[str]:
    _ensure("idrockbench.models")
    return sorted(_PROVIDERS)
