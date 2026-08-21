"""Ollama, over its native ``/api/chat`` endpoint.

Deliberately not the OpenAI-compatible ``/v1`` route, for three reasons that
each cost real accuracy:

* **``think`` is only honoured natively.** Sent through the compat endpoint it
  is silently discarded, so a reasoning model keeps thinking and burns its whole
  budget. Measured on qwen3.5:9b against a hard Uzbek grammar item: default
  spends 2048 tokens and returns an *empty* answer (``done_reason=length``);
  ``think=false`` returns a real answer in 697 tokens, three times faster.
* **Reasoning arrives in its own field.** ``message.thinking`` is separate from
  ``message.content``, so the answer never has to be recovered by stripping
  ``<think>`` tags out of prose — and an unterminated trace cannot leak into it.
* **``done_reason`` is explicit**, so a truncation is reported as a truncation
  rather than guessed at from a token count.
"""

from __future__ import annotations

from typing import Any

from ..core import ModelResponse
from ..registry import register_provider
from .base import ModelProvider


@register_provider
class OllamaProvider(ModelProvider):
    name = "ollama"
    default_base_url = "http://localhost:11434"

    def _host(self) -> str:
        base = (self.base_url or self.default_base_url).rstrip("/")
        # Accept an OpenAI-style base URL and strip back to the host, so a
        # config written either way works.
        for suffix in ("/v1/chat/completions", "/v1"):
            if base.endswith(suffix):
                base = base[: -len(suffix)]
        return base

    def _session(self):
        if getattr(self, "_s", None) is None:
            import requests

            self._s = requests.Session()
        return self._s

    def _complete(self, prompt: str, max_tokens: int) -> ModelResponse:
        options: dict[str, Any] = {
            "temperature": self.temperature,
            "num_predict": max_tokens,
        }
        if self.top_p is not None:
            options["top_p"] = self.top_p
        if self.seed:
            options["seed"] = self.seed
        options.update(self.extra_body.get("options", {}))

        body: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "keep_alive": "30m",
            "options": options,
        }
        if self.reasoning == "off":
            body["think"] = False
        elif self.reasoning not in ("default", ""):
            body["think"] = self.reasoning
        for k, v in self.extra_body.items():
            if k != "options":
                body[k] = v

        r = self._session().post(
            f"{self._host()}/api/chat", json=body, timeout=self.timeout
        )
        if r.status_code >= 400:
            raise RuntimeError(f"HTTP {r.status_code}: {r.text[:300]}")
        data = r.json()
        message = data.get("message") or {}

        # `thinking` is returned separately and is deliberately not scored: it
        # is the model's scratchpad, not its answer.
        text = message.get("content") or ""
        done = str(data.get("done_reason") or "stop")
        return ModelResponse(
            text=text,
            finish_reason="length" if done == "length" else done,
            prompt_tokens=int(data.get("prompt_eval_count") or 0),
            completion_tokens=int(data.get("eval_count") or 0),
        )

    def describe(self) -> dict[str, str]:
        """Resolve the digest and quantisation from the daemon.

        An Ollama tag hides both the exact weights and the quantisation, and
        quantisation moves scores by more than most model-to-model differences.
        `deepseek-r1:32b` is a 4-bit Qwen distill, not DeepSeek-R1.
        """
        info = {"provider": self.name, "model": self.model,
                "revision": "", "quantization": ""}
        try:
            r = self._session().post(
                f"{self._host()}/api/show", json={"model": self.model}, timeout=15
            )
            if r.ok:
                d = r.json()
                details = d.get("details") or {}
                info["quantization"] = details.get("quantization_level", "")
                info["revision"] = (d.get("digest") or "")[:16]
                info["parameter_size"] = details.get("parameter_size", "")
                info["family"] = details.get("family", "")
        except Exception:
            pass
        return info
