"""Anthropic Messages API provider."""

from __future__ import annotations

from ..core import ModelResponse
from ..registry import register_provider
from .base import ModelProvider, env_key


@register_provider
class AnthropicProvider(ModelProvider):
    name = "anthropic"

    def _client(self):
        if getattr(self, "_c", None) is None:
            import anthropic

            self._c = anthropic.Anthropic(
                api_key=self.api_key or env_key("ANTHROPIC_API_KEY"),
                timeout=self.timeout,
                max_retries=0,
            )
        return self._c

    def _complete(self, prompt: str, max_tokens: int) -> ModelResponse:
        kwargs = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": self.temperature,
            "messages": [{"role": "user", "content": prompt}],
        }
        if self.top_p is not None:
            kwargs["top_p"] = self.top_p
        r = self._client().messages.create(**kwargs)
        text = "".join(b.text for b in r.content if getattr(b, "type", "") == "text")
        return ModelResponse(
            text=text,
            # Anthropic reports "max_tokens"; normalise to the OpenAI spelling
            # so truncation detection is provider-independent.
            finish_reason="length" if r.stop_reason == "max_tokens" else (r.stop_reason or "stop"),
            prompt_tokens=r.usage.input_tokens or 0,
            completion_tokens=r.usage.output_tokens or 0,
        )
