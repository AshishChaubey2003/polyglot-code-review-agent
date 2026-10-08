"""
LLM abstraction layer.

Every agent/node calls into LLMService instead of constructing its own
ChatGroq()/ChatOpenAI()/etc. That is what lets the provider change later
(Gemini, OpenAI, Anthropic, local) via environment variables only -- no
changes to calling code.

`generate()` -- plain text completion (Phase 1).
`structured_generate()` -- validated Pydantic output (Phase 4). Uses
LangChain's `.with_structured_output()`, which asks the provider for
tool-call-shaped output and parses it into the given schema. If the
provider returns something that fails validation, this retries once
with the validation error fed back to the model before giving up --
never silently substitutes a default value for a field the model got
wrong, per the "never fabricate" rule.
"""

from __future__ import annotations

import json
import time
from typing import Type, TypeVar

from pydantic import BaseModel

from config import GROQ_API_KEY, LLM_MODEL, LLM_PROVIDER, logger

T = TypeVar("T", bound=BaseModel)


class LLMServiceError(Exception):
    """Raised when the LLM layer cannot produce a usable response."""


class LLMConfigurationError(LLMServiceError):
    """Raised when the selected provider is missing required credentials
    or is not one this service implements."""


class StructuredOutputError(LLMServiceError):
    """Raised when the model's output could not be validated against the
    requested schema, even after one retry with the validation error fed
    back to it."""


class LLMService:
    """Thin, provider-agnostic wrapper around a chat LLM.

    Only 'groq' is implemented. A second provider means one more branch
    in `_build_client()`; nothing else in the codebase changes, because
    every caller only ever sees `generate()` / `structured_generate()`.
    """

    def __init__(
        self,
        provider: str = LLM_PROVIDER,
        model: str = LLM_MODEL,
        timeout: float = 30.0,
        max_retries: int = 2,
    ) -> None:
        self.provider = provider
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries
        self._client = None  # built lazily -- import-time has no side effects

    def _build_client(self):
        if self.provider == "groq":
            if not GROQ_API_KEY:
                raise LLMConfigurationError(
                    "GROQ_API_KEY is not set. Add it to your .env file "
                    "(see .env.example)."
                )
            from langchain_groq import ChatGroq

            return ChatGroq(model=self.model, temperature=0.2, timeout=self.timeout)

        raise LLMConfigurationError(
            f"Unknown LLM_PROVIDER '{self.provider}'. Only 'groq' is implemented."
        )

    @property
    def client(self):
        if self._client is None:
            self._client = self._build_client()
        return self._client

    def generate(self, prompt: str) -> str:
        """Plain text completion. Retries transient failures with
        backoff, then raises LLMServiceError. Never fabricates a
        response on failure."""
        last_error: Exception | None = None

        for attempt in range(1, self.max_retries + 2):
            try:
                result = self.client.invoke(prompt)
                return result.content
            except LLMConfigurationError:
                raise  # not transient -- don't retry a missing API key
            except Exception as exc:  # noqa: BLE001 -- broad on purpose, logged below
                last_error = exc
                logger.warning(
                    "LLM call failed (attempt %s/%s): %s",
                    attempt, self.max_retries + 1, exc,
                )
                if attempt <= self.max_retries:
                    time.sleep(min(2 ** attempt, 8))

        raise LLMServiceError(
            f"LLM generation failed after {self.max_retries + 1} attempt(s)"
        ) from last_error

    def structured_generate(self, prompt: str, schema: Type[T]) -> T:
        """Return a validated instance of `schema`.

        Tries once, and if the provider's structured-output call itself
        raises (not a validation issue, a call failure), retries that
        once more with the error appended to the prompt. Two failures
        in a row raise StructuredOutputError -- this never returns a
        schema instance built from invented defaults.
        """
        # Attempt 1 uses the provider's tool/function-calling mode (the
        # default). Attempt 2 switches to JSON mode with the schema spelled
        # out in the prompt: Llama models on Groq frequently fail tool
        # calls when an argument is a multi-line string full of quotes --
        # exactly what a code fix is -- while JSON mode handles it fine.
        # Using a *different* strategy on the retry, not the same call
        # again, is what makes the retry worth having.
        json_schema_text = json.dumps(schema.model_json_schema(), indent=2)
        attempts = [
            ("tool-calling", None, prompt),
            (
                "json-mode",
                "json_mode",
                f"{prompt}\n\nRespond with ONLY a single JSON object (no markdown "
                f"fences, no commentary) that validates against this JSON schema:\n"
                f"{json_schema_text}",
            ),
        ]
        errors: list[str] = []
        last_error: Exception | None = None

        for label, method, current_prompt in attempts:
            try:
                if method is None:
                    structured_client = self.client.with_structured_output(schema)
                else:
                    structured_client = self.client.with_structured_output(schema, method=method)
                result = structured_client.invoke(current_prompt)
                if result is None:
                    raise ValueError("model returned no structured output")
                # with_structured_output normally returns a validated
                # instance already; this guards against a provider/version
                # returning a plain dict instead.
                if isinstance(result, schema):
                    return result
                return schema.model_validate(result)
            except LLMConfigurationError:
                raise  # not retryable -- a missing key won't fix itself
            except Exception as exc:  # noqa: BLE001 -- includes pydantic ValidationError
                last_error = exc
                detail = f"{label}: {type(exc).__name__}: {str(exc)[:300]}"
                errors.append(detail)
                logger.warning("structured_generate failed (%s)", detail)

        raise StructuredOutputError(
            "Could not get valid structured output after 2 attempts -- "
            + " | ".join(errors)
        ) from last_error


def get_llm_service() -> LLMService:
    """Factory used everywhere instead of constructing LLMService directly."""
    return LLMService()
