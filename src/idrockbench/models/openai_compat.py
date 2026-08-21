"""OpenAI-compatible providers: OpenAI, vLLM, TGI, Ollama, Together, and friends."""

from __future__ import annotations

from typing import Any

from ..core import ModelResponse
from ..registry import register_provider
from .base import ModelProvider, env_key


class _OpenAICompat(ModelProvider):
    default_base_url: str | None = None
    key_env: tuple[str, ...] = ("OPENAI_API_KEY",)

    def _client(self):
        if getattr(self, "_c", None) is None:
            from openai import OpenAI

            self._c = OpenAI(
                api_key=self.api_key or env_key(*self.key_env) or "not-needed",
                base_url=self.base_url or self.default_base_url,
                timeout=self.timeout,
                max_retries=0,  # retry policy lives in ModelProvider.generate
            )
        return self._c

    def _extra(self) -> dict[str, Any]:
        extra = dict(self.extra_body)
        if self.reasoning == "off":
            # Ollama disables thinking with think=false; gpt-oss takes a level.
            extra["think"] = "low" if "gpt-oss" in self.model.lower() else False
        elif self.reasoning not in ("default", ""):
            extra["think"] = self.reasoning
        return extra

    def _complete(self, prompt: str, max_tokens: int) -> ModelResponse:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": self.temperature,
            "max_tokens": max_tokens,
        }
        if self.top_p is not None:
            kwargs["top_p"] = self.top_p
        if self.seed:
            kwargs["seed"] = self.seed
        extra = self._extra()
        if extra:
            kwargs["extra_body"] = extra

        r = self._client().chat.completions.create(**kwargs)
        choice = r.choices[0]
        usage = getattr(r, "usage", None)
        return ModelResponse(
            text=(choice.message.content or ""),
            finish_reason=choice.finish_reason or "stop",
            prompt_tokens=getattr(usage, "prompt_tokens", 0) or 0,
            completion_tokens=getattr(usage, "completion_tokens", 0) or 0,
        )


@register_provider
class OpenAIProvider(_OpenAICompat):
    name = "openai"
    default_base_url = None


@register_provider
class LocalProvider(_OpenAICompat):
    """Any self-hosted OpenAI-compatible server (vLLM, TGI, LM Studio)."""

    name = "local"
    default_base_url = "http://localhost:8000/v1"
    key_env = ("LOCAL_API_KEY", "OPENAI_API_KEY")
