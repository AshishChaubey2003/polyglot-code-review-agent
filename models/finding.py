"""
Shared finding schema.

Every analyzer -- AST, Ruff, Bandit today, the LLM review agents and RAG
in later phases -- returns findings in exactly this shape. Downstream
code (aggregation, the report, the UI) only ever needs to know this
model, never which tool produced a given finding. This is also what
rules out regex-parsing free-text LLM output later (Phase 4): the LLM
will be asked to return this schema directly, validated by Pydantic.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel

Category = Literal["bug", "security", "quality"]
Severity = Literal["low", "medium", "high", "critical"]
Source = Literal["ast", "ruff", "bandit", "llm", "rag"]


class Finding(BaseModel):
    """One normalized, evidence-backed finding."""

    category: Category
    severity: Severity
    title: str
    description: str
    line: Optional[int] = None
    evidence: str
    recommendation: str
    source: Source

    model_config = {"frozen": True}  # a finding is a record, not mutated in place


class FindingList(BaseModel):
    """Wrapper schema for structured LLM output -- `with_structured_output`
    needs one top-level model, not a bare list, so every LLM review node
    asks for this and unwraps `.findings`."""

    findings: list[Finding]
