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

        text = message.get("content") or ""
        done = str(data.get("done_reason") or "stop")
        return ModelResponse(
            text=text,
            finish_reason="length" if done == "length" else done,
            prompt_tokens=int(data.get("prompt_eval_count") or 0),
            completion_tokens=int(data.get("eval_count") or 0),
        )

    def describe(self) -> dict[str, str]:
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
