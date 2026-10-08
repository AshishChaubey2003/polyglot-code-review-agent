"""
Shared state for the review/repair LangGraph.

Fields written by more than one parallel branch (the bug/security/
quality agents all append findings) use `Annotated[list, operator.add]`
so LangGraph merges their writes instead of one overwriting another --
the standard pattern for fan-out/fan-in in LangGraph.
"""

from __future__ import annotations

import operator
from typing import Annotated, Optional, TypedDict

from models.finding import Finding
from models.fix import CodeFix, ProposedFix
from models.retrieval import RetrievedContext


class ReviewState(TypedDict, total=False):
    # input
    code: str
    language: str
    mode: str  # "review" | "repair"

    # guardrail outcome
    input_allowed: bool
    input_block_reasons: list[str]

    # static analysis (written once, by one node)
    static_findings: list[Finding]

    # retrieval (written once)
    retrieved_context: list[RetrievedContext]

    # parallel LLM review branches -- each node appends only its own
    # findings, LangGraph concatenates them via operator.add
    findings: Annotated[list[Finding], operator.add]

    # aggregation / report
    all_findings: list[Finding]
    summary: str
    halted_reason: Optional[str]

    # repair mode only
    generated_fix: Optional[CodeFix]
    proposed_fix: Optional[ProposedFix]
