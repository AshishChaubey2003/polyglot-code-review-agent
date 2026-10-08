"""Repair-mode node: runs output/code/scope guardrails on the generated
fix, then independent verification (syntax/lint/security/behavior),
and assembles the ProposedFix the human approves or rejects. Nothing
here applies the fix -- it only ever builds the proposal and its
evidence."""

from __future__ import annotations

from agents.state import ReviewState
from config import ALLOW_TEST_EXECUTION
from guardrails.code_guard import check_generated_code
from guardrails.output_guard import check_fix_output
from guardrails.scope_guard import check_fix_scope
from models.fix import ProposedFix, VerificationReport, VerificationStepResult
from verification.diff import build_diff
from verification.lint import verify_lint
from verification.security import verify_security
from verification.syntax import verify_syntax
from verification.tests import verify_behavior


def run_verify_fix(state: ReviewState) -> dict:
    fix = state.get("generated_fix")
    if fix is None:
        return {"halted_reason": state.get("halted_reason") or "No fix was generated to verify."}

    original_code = state["code"]
    findings = state.get("all_findings") or state.get("static_findings", [])

    output_result = check_fix_output(fix, original_code)
    if not output_result.allowed:
        return {"halted_reason": f"Output guard rejected the fix: {'; '.join(output_result.reasons)}"}

    code_result = check_generated_code(fix.fixed_code, state["language"])
    if not code_result.allowed:
        return {"halted_reason": f"Code guard rejected the fix: {code_result.reason}"}

    finding_lines = [f.line for f in findings if f.line is not None]
    scope_result = check_fix_scope(fix.changed_lines, finding_lines)
    if not scope_result.allowed:
        return {"halted_reason": f"Scope guard rejected the fix: {scope_result.reason}"}

    bug_titles = {f.title for f in findings if f.category == "bug"}
    security_titles = {f.title for f in findings if f.category == "security"}

    steps: list[VerificationStepResult] = [
        verify_syntax(fix.fixed_code),
        verify_lint(fix.fixed_code, original_bug_titles=bug_titles),
        verify_security(fix.fixed_code, original_finding_titles=security_titles),
        verify_behavior(fix.fixed_code, test_code=None, allow_execution=ALLOW_TEST_EXECUTION),
    ]
    report = VerificationReport(steps=steps)

    proposed = ProposedFix(
        original_code=original_code,
        fix=fix,
        diff=build_diff(original_code, fix.fixed_code).unified_diff,
        verification=report,
        approval_status="pending",
    )
    return {"proposed_fix": proposed}
