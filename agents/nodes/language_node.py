"""Language detection. Phase scope: Python has a real analyzer; every
other language is accepted (not rejected) so the LLM review agents can
still run on it, but static analysis and repair mode are Python-only --
callers see this reflected in which findings have source='ast'/'ruff'/
'bandit' vs. only 'llm'."""

from __future__ import annotations

from agents.state import ReviewState

SUPPORTED_STATIC_ANALYSIS_LANGUAGES = {"python"}


def detect_language(state: ReviewState) -> dict:
    # The language is supplied by the caller (UI dropdown / API field),
    # not sniffed from the code -- sniffing language from arbitrary
    # source text is unreliable and not worth the false confidence.
    language = (state.get("language") or "python").lower()
    return {"language": language}
