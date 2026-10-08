"""Phase 1 unit tests: environment-driven configuration.

No network calls. `config.py` reads its constants at import time, so
these tests reload the module after changing env vars.
"""

from __future__ import annotations

import importlib


def test_is_configured_false_without_key(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    # Set to empty rather than delete: config.py calls load_dotenv() on
    # reload, which fills in any variable that is *missing* from the
    # environment using the developer's real .env file. An empty string
    # counts as "present" so dotenv leaves it alone, keeping this test
    # independent of whether a .env with a real key exists.
    monkeypatch.setenv("GROQ_API_KEY", "")

    import config
    importlib.reload(config)

    assert config.is_configured() is False


def test_is_configured_true_with_key(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.setenv("GROQ_API_KEY", "fake-key-for-test")

    import config
    importlib.reload(config)

    assert config.is_configured() is True


def test_unknown_provider_is_never_configured(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "some-future-provider")
    monkeypatch.setenv("GROQ_API_KEY", "fake-key-for-test")

    import config
    importlib.reload(config)

    assert config.is_configured() is False
