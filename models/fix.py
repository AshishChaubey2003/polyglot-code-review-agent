"""Repair-mode models. A CodeFix is a PROPOSAL -- nothing writes it to
disk or treats it as final until it has passed guardrails, independent
verification, and explicit human approval (see human_loop/approval.py)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class CodeFix(BaseModel):
    """What the LLM proposes. Never applied directly."""

    fixed_code: str
    explanation: str
    changed_lines: list[int]


class VerificationStepResult(BaseModel):
    name: Literal["syntax", "lint", "security", "tests", "behavior"]
    passed: bool
    detail: str


class VerificationReport(BaseModel):
    """Independent, deterministic verification of a proposed fix.

    `all_passed` is a property, not a stored field: it is always
    derived from the step results, never set independently, so it can't
    drift from what was actually checked.
    """

    steps: list[VerificationStepResult]

    @property
    def all_passed(self) -> bool:
        return all(s.passed for s in self.steps)

    def summary_line(self) -> str:
        parts = [f"{s.name}: {'PASS' if s.passed else 'FAIL'}" for s in self.steps]
        return " | ".join(parts)


class ProposedFix(BaseModel):
    """Everything the UI needs to show before asking for human approval."""

    original_code: str
    fix: CodeFix
    diff: str
    verification: VerificationReport
    approval_status: Literal["pending", "approved", "rejected"] = "pending"
