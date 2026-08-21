import pytest

from idrockbench.core import ModelResponse
from idrockbench.models.base import ModelProvider


class StubProvider(ModelProvider):
    """Scripted model, so the whole pipeline is testable without an API key."""

    name = "stub"

    def __init__(self, responses=None, **kwargs):
        kwargs.setdefault("max_retries", 1)
        super().__init__(kwargs.pop("model", "stub-model"), **kwargs)
        self.responses = responses or {}
        self.default = "Javob: A"
        self.calls = []

    def _complete(self, prompt, max_tokens):
        self.calls.append(prompt)
        for needle, reply in self.responses.items():
            if needle in prompt:
                if isinstance(reply, Exception):
                    raise reply
                return ModelResponse(text=reply, finish_reason="stop")
        return ModelResponse(text=self.default, finish_reason="stop")


@pytest.fixture
def stub():
    return StubProvider
