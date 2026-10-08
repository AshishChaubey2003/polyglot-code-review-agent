"""Aggregate review output -- what app.py and api/main.py both return."""

from __future__ import annotations

from pydantic import BaseModel

from models.finding import Finding


class ReviewResult(BaseModel):
    """The complete output of a review run, before any repair step."""

    findings: list[Finding]
    summary: str
    language: str
    mode: str  # "review" | "repair"

    @property
    def counts_by_severity(self) -> dict[str, int]:
        counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        for f in self.findings:
            counts[f.severity] += 1
        return counts
