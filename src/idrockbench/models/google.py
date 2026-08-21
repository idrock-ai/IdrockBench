"""Google Gemini provider."""

from __future__ import annotations

from ..core import ModelResponse
from ..registry import register_provider
from .base import ModelProvider, env_key


@register_provider
class GeminiProvider(ModelProvider):
    name = "gemini"

    def _client(self):
        if getattr(self, "_c", None) is None:
            from google import genai

            self._c = genai.Client(api_key=self.api_key or env_key("GEMINI_API_KEY", "GOOGLE_API_KEY"))
        return self._c

    def _complete(self, prompt: str, max_tokens: int) -> ModelResponse:
        from google.genai import types

        cfg = types.GenerateContentConfig(
            temperature=self.temperature,
            max_output_tokens=max_tokens,
            **({"top_p": self.top_p} if self.top_p is not None else {}),
        )
        r = self._client().models.generate_content(
            model=self.model, contents=prompt, config=cfg
        )
        cand = (r.candidates or [None])[0]
        reason = str(getattr(cand, "finish_reason", "") or "STOP")
        usage = getattr(r, "usage_metadata", None)
        return ModelResponse(
            text=getattr(r, "text", "") or "",
            finish_reason="length" if "MAX_TOKENS" in reason else "stop",
            prompt_tokens=getattr(usage, "prompt_token_count", 0) or 0,
            completion_tokens=getattr(usage, "candidates_token_count", 0) or 0,
        )
