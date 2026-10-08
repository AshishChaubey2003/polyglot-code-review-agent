"""Combine static_findings (deterministic) and findings (the three LLM
agents, already merged by LangGraph's operator.add reducer) into the
final ReviewResult-shaping fields. Deduplicates near-identical
findings by (category, title) so the same issue surfaced by both a
tool and an LLM agent isn't shown twice."""

from __future__ import annotations

from agents.state import ReviewState
from models.finding import Finding


def _dedupe(findings: list[Finding]) -> list[Finding]:
    seen: set[tuple[str, str]] = set()
    out: list[Finding] = []
    for f in findings:
        key = (f.category, f.title.strip().lower())
        if key in seen:
            continue
        seen.add(key)
        out.append(f)
    return out


def run_aggregate(state: ReviewState) -> dict:
    all_findings = _dedupe(list(state.get("static_findings", [])) + list(state.get("findings", [])))
    counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for f in all_findings:
        counts[f.severity] += 1

    summary = (
        f"{len(all_findings)} finding(s): "
        f"{counts['critical']} critical, {counts['high']} high, "
        f"{counts['medium']} medium, {counts['low']} low."
    )
    return {"all_findings": all_findings, "summary": summary}
