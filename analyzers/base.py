"""
LanguageAnalyzer interface.

Every language -- Python today, JavaScript/TypeScript/Java/Go in Phase
10 -- implements exactly this interface. The LangGraph static_analysis
node (Phase 3) calls `analyze()` without caring which language it got;
it is each analyzer's own job to know which deterministic tools apply
to that language.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from models.finding import Finding


class LanguageAnalyzer(ABC):
    """Deterministic, non-LLM analysis for one language."""

    language: str  # e.g. "python" -- set by each subclass

    @abstractmethod
    def analyze(self, code: str) -> list[Finding]:
        """Run every deterministic tool for this language and return a
        flat list of normalized Finding objects.

        Must never raise for ordinary bad-but-parseable code. A tool
        that fails to run (missing binary, timeout) becomes a Finding
        describing that failure, not an exception -- the review should
        degrade gracefully, not crash the whole pipeline because one
        analyzer is unavailable.
        """
        raise NotImplementedError
