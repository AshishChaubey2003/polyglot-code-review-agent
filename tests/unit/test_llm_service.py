"""Phase 1 unit tests: the provider-agnostic LLM service.

No network calls, no real Groq key needed — the underlying client is
faked via `_build_client`. Run: pytest tests/unit -v
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from pydantic import BaseModel

from services.llm_service import (
    LLMConfigurationError,
    LLMService,
    LLMServiceError,
    StructuredOutputError,
)


@dataclass
class FakeMessage:
    content: str


class FakeClient:
    """Stands in for ChatGroq. Returns canned replies, or raises on demand."""

    def __init__(self, replies: list[str] | None = None, raises: Exception | None = None):
        self.replies = replies or []
        self.raises = raises
        self.calls = 0

    def invoke(self, prompt: str) -> FakeMessage:
        self.calls += 1
        if self.raises:
            raise self.raises
        index = min(self.calls - 1, len(self.replies) - 1)
        return FakeMessage(self.replies[index])


def test_unknown_provider_raises_configuration_error():
    service = LLMService(provider="not-a-real-provider")
    with pytest.raises(LLMConfigurationError):
        _ = service.client


def test_missing_api_key_raises_configuration_error(monkeypatch):
    monkeypatch.setattr("services.llm_service.GROQ_API_KEY", "")
    service = LLMService(provider="groq")
    with pytest.raises(LLMConfigurationError):
        _ = service.client


def test_generate_returns_content_on_success(monkeypatch):
    service = LLMService(provider="groq")
    monkeypatch.setattr(service, "_build_client", lambda: FakeClient(["LLM connection OK."]))

    assert service.generate("ping") == "LLM connection OK."


def test_generate_retries_then_raises_on_persistent_failure(monkeypatch):
    service = LLMService(provider="groq", max_retries=1)
    fake_client = FakeClient(raises=RuntimeError("network down"))
    monkeypatch.setattr(service, "_build_client", lambda: fake_client)
    monkeypatch.setattr("time.sleep", lambda _: None)  # don't actually wait in tests

    with pytest.raises(LLMServiceError):
        service.generate("ping")

    assert fake_client.calls == 2  # original attempt + 1 retry


def test_generate_succeeds_after_one_transient_failure(monkeypatch):
    """First call raises, second succeeds -- confirms retry actually retries."""
    service = LLMService(provider="groq", max_retries=1)

    attempts = {"n": 0}

    class FlakyClient:
        def invoke(self, prompt):
            attempts["n"] += 1
            if attempts["n"] == 1:
                raise RuntimeError("transient")
            return FakeMessage("LLM connection OK.")

    monkeypatch.setattr(service, "_build_client", lambda: FlakyClient())
    monkeypatch.setattr("time.sleep", lambda _: None)

    assert service.generate("ping") == "LLM connection OK."
    assert attempts["n"] == 2


def test_configuration_error_is_not_retried(monkeypatch):
    """A missing API key is not transient -- retrying it wastes time and
    produces a confusing multi-attempt log for a problem retrying can't fix."""
    service = LLMService(provider="groq", max_retries=2)

    def raise_config_error():
        raise LLMConfigurationError("no key")

    monkeypatch.setattr(service, "_build_client", raise_config_error)

    with pytest.raises(LLMConfigurationError):
        service.generate("ping")


class Dummy(BaseModel):
    x: int
    label: str


class FakeStructuredClient:
    """Stands in for `client.with_structured_output(schema)`."""

    def __init__(self, results: list, raises_then_succeeds: bool = False):
        self.results = results
        self.raises_then_succeeds = raises_then_succeeds
        self.calls = 0

    def invoke(self, prompt: str):
        self.calls += 1
        if self.raises_then_succeeds and self.calls == 1:
            raise RuntimeError("provider call failed")
        return self.results[min(self.calls - 1, len(self.results) - 1)]


class FakeClientWithStructuredOutput:
    def __init__(self, structured_client):
        self._structured_client = structured_client

    def with_structured_output(self, schema, method=None):
        self.methods_requested = getattr(self, "methods_requested", []) + [method]
        return self._structured_client


def test_structured_generate_returns_validated_instance(monkeypatch):
    service = LLMService(provider="groq")
    fake_result = Dummy(x=1, label="ok")
    monkeypatch.setattr(
        service, "_build_client",
        lambda: FakeClientWithStructuredOutput(FakeStructuredClient([fake_result])),
    )

    result = service.structured_generate("describe something", Dummy)
    assert result == fake_result


def test_structured_generate_accepts_a_plain_dict_result(monkeypatch):
    """Guards against a provider/version returning a dict instead of an
    already-validated model instance -- it should still validate it."""
    service = LLMService(provider="groq")
    monkeypatch.setattr(
        service, "_build_client",
        lambda: FakeClientWithStructuredOutput(FakeStructuredClient([{"x": 2, "label": "from-dict"}])),
    )

    result = service.structured_generate("describe something", Dummy)
    assert isinstance(result, Dummy)
    assert result.x == 2


def test_structured_generate_retries_once_then_succeeds(monkeypatch):
    service = LLMService(provider="groq")
    fake_structured = FakeStructuredClient([Dummy(x=3, label="recovered")], raises_then_succeeds=True)
    monkeypatch.setattr(service, "_build_client", lambda: FakeClientWithStructuredOutput(fake_structured))

    result = service.structured_generate("describe something", Dummy)
    assert result.label == "recovered"
    assert fake_structured.calls == 2


def test_structured_generate_raises_after_two_failures(monkeypatch):
    service = LLMService(provider="groq")

    class AlwaysFails:
        def invoke(self, prompt):
            raise RuntimeError("provider down")

    monkeypatch.setattr(service, "_build_client", lambda: FakeClientWithStructuredOutput(AlwaysFails()))

    with pytest.raises(StructuredOutputError):
        service.structured_generate("describe something", Dummy)


def test_structured_generate_retry_switches_to_json_mode(monkeypatch):
    """The retry must use a DIFFERENT strategy (JSON mode), not repeat the
    same tool call that just failed -- that is what makes it worth doing."""
    service = LLMService(provider="groq")
    fake_structured = FakeStructuredClient([Dummy(x=4, label="ok")], raises_then_succeeds=True)
    outer = FakeClientWithStructuredOutput(fake_structured)
    monkeypatch.setattr(service, "_build_client", lambda: outer)

    service.structured_generate("describe something", Dummy)
    assert outer.methods_requested == [None, "json_mode"]


def test_structured_generate_json_mode_prompt_includes_the_schema(monkeypatch):
    service = LLMService(provider="groq")
    prompts: list[str] = []

    class Recording:
        def invoke(self, prompt):
            prompts.append(prompt)
            if len(prompts) == 1:
                raise RuntimeError("tool call failed")
            return Dummy(x=5, label="ok")

    monkeypatch.setattr(service, "_build_client", lambda: FakeClientWithStructuredOutput(Recording()))
    service.structured_generate("describe something", Dummy)

    assert "label" in prompts[1] and "JSON" in prompts[1]


def test_structured_generate_error_message_contains_the_real_cause(monkeypatch):
    service = LLMService(provider="groq")

    class AlwaysFails:
        def invoke(self, prompt):
            raise RuntimeError("tool_use_failed: bad function call")

    monkeypatch.setattr(service, "_build_client", lambda: FakeClientWithStructuredOutput(AlwaysFails()))

    with pytest.raises(StructuredOutputError) as excinfo:
        service.structured_generate("describe something", Dummy)

    message = str(excinfo.value)
    assert "tool_use_failed" in message
    assert "tool-calling" in message and "json-mode" in message


def test_structured_generate_validation_error_is_retried_not_crashed(monkeypatch):
    """A schema-invalid reply used to escape as a raw pydantic
    ValidationError and crash the caller; it must be retried and, if it
    keeps failing, surface as StructuredOutputError."""
    service = LLMService(provider="groq")
    bad = FakeStructuredClient([{"x": "not-an-int"}])
    monkeypatch.setattr(service, "_build_client", lambda: FakeClientWithStructuredOutput(bad))

    with pytest.raises(StructuredOutputError):
        service.structured_generate("describe something", Dummy)
    assert bad.calls == 2


def test_structured_generate_none_result_is_treated_as_failure(monkeypatch):
    service = LLMService(provider="groq")
    none_client = FakeStructuredClient([None])
    monkeypatch.setattr(service, "_build_client", lambda: FakeClientWithStructuredOutput(none_client))

    with pytest.raises(StructuredOutputError):
        service.structured_generate("describe something", Dummy)
