"""Model provider interface.

A provider turns a prompt into a :class:`ModelResponse`. It must distinguish
three outcomes the old harness collapsed into "score 0":

* a completed answer,
* a response cut off by the token limit (``finish_reason="length"``),
* a request that failed after retries (``error`` set).

Add a provider by subclassing :class:`ModelProvider` and decorating with
``@register_provider``; a new file in this package is discovered automatically.
"""

from __future__ import annotations

import abc
import os
import random
import time
from typing import Any

from ..core import ModelResponse

#: Retried with exponential backoff and jitter. Anything else fails fast.
RETRYABLE = ("rate", "429", "500", "502", "503", "504", "timeout", "timed out",
             "connection", "overloaded", "temporarily")


class ModelProvider(abc.ABC):
    """Base class for model backends."""

    name: str = ""

    def __init__(
        self,
        model: str,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        temperature: float = 0.0,
        top_p: float | None = None,
        seed: int = 0,
        timeout: int = 300,
        max_retries: int = 5,
        reasoning: str = "default",
        extra_body: dict[str, Any] | None = None,
    ) -> None:
        self.model = model
        self.api_key = api_key
        self.base_url = base_url
        self.temperature = temperature
        self.top_p = top_p
        self.seed = seed
        self.timeout = timeout
        self.max_retries = max_retries
        self.reasoning = reasoning
        self.extra_body = extra_body or {}

    @abc.abstractmethod
    def _complete(self, prompt: str, max_tokens: int) -> ModelResponse:
        """Perform one request. Raise on failure; retries are handled above."""

    def describe(self) -> dict[str, str]:
        """Provenance recorded in the run manifest.

        Override to report the resolved revision or quantisation — an Ollama
        tag like ``deepseek-r1:32b`` is a 4-bit distill, and publishing it as
        the full model is the kind of claim that gets a leaderboard corrected
        in public.
        """
        return {"provider": self.name, "model": self.model, "revision": "", "quantization": ""}

    def generate(self, prompt: str, max_tokens: int) -> ModelResponse:
        """Complete a prompt, retrying transient failures with backoff."""
        last = ""
        for attempt in range(self.max_retries):
            started = time.monotonic()
            try:
                resp = self._complete(prompt, max_tokens)
                resp.latency_s = round(time.monotonic() - started, 3)
                return resp
            except Exception as exc:  # noqa: BLE001 - classified below
                last = f"{type(exc).__name__}: {exc}"
                if not any(t in last.lower() for t in RETRYABLE):
                    break
                if attempt < self.max_retries - 1:
                    delay = min(2 ** attempt, 30) * (0.5 + random.random())
                    time.sleep(delay)
        return ModelResponse(
            text="", finish_reason="error", error=last,
            latency_s=round(time.monotonic() - started, 3),
        )


def env_key(*names: str) -> str | None:
    for n in names:
        v = os.environ.get(n)
        if v:
            return v
    return None
