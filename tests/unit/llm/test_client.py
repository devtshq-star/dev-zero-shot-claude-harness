import pytest

from llm.client import LLMClient


class _FakeProvider:
    """Stand-in provider that either returns a fixed (text, usage) or raises."""

    def __init__(self, *, text=None, usage=None, exc=None):
        self._text = text
        self._usage = usage or {"prompt_tokens": 1, "completion_tokens": 2, "estimated_cost_usd": 0.0}
        self._exc = exc
        self.calls = 0

    def call_model_with_usage(self, prompt, *, system=None):
        self.calls += 1
        if self._exc is not None:
            raise self._exc
        return self._text, self._usage


def _client(primary, fallback):
    # Bypass __init__ (which reads .env / builds real providers) and inject fakes.
    c = LLMClient.__new__(LLMClient)
    c._primary_name, c._primary = "primary", primary
    c._fallback_name, c._fallback = ("fallback", fallback) if fallback is not None else (None, None)
    return c


def test_primary_success_does_not_touch_fallback():
    primary = _FakeProvider(text="from-primary")
    fallback = _FakeProvider(text="from-fallback")
    client = _client(primary, fallback)

    text, _ = client.call_model_with_usage("q")

    assert text == "from-primary"
    assert primary.calls == 1
    assert fallback.calls == 0


def test_primary_failure_falls_back():
    primary = _FakeProvider(exc=RuntimeError("429 rate limit"))
    fallback = _FakeProvider(text="from-fallback")
    client = _client(primary, fallback)

    text, usage = client.call_model_with_usage("q")

    assert text == "from-fallback"
    assert primary.calls == 1
    assert fallback.calls == 1
    assert usage["completion_tokens"] == 2


def test_primary_failure_without_fallback_raises():
    primary = _FakeProvider(exc=RuntimeError("boom"))
    client = _client(primary, None)

    with pytest.raises(RuntimeError, match="boom"):
        client.call_model_with_usage("q")


def test_call_model_returns_text_via_fallback():
    primary = _FakeProvider(exc=RuntimeError("down"))
    fallback = _FakeProvider(text="ok")
    client = _client(primary, fallback)

    assert client.call_model("q") == "ok"
