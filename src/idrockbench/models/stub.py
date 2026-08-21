from __future__ import annotations

from ..core import ModelResponse
from ..registry import register_provider
from .base import ModelProvider


@register_provider
class StubProvider(ModelProvider):
    name = "stub"

    def _complete(self, prompt: str, max_tokens: int) -> ModelResponse:
        if "Javob:" in prompt:
            return ModelResponse(text="Javob: A", finish_reason="stop", completion_tokens=3)
        return ModelResponse(text="Bu sinov javobi.", finish_reason="stop", completion_tokens=4)

    def describe(self) -> dict[str, str]:
        return {"provider": "stub", "model": self.model,
                "revision": "n/a", "quantization": "n/a"}
