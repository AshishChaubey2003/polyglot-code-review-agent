"""Repair-mode node: ask the LLM for a CodeFix given the findings
already surfaced in review mode. The fix is a PROPOSAL only -- this
node does not guard, verify, or apply anything; that happens in
verify_node.py and human_loop/approval.py."""

from __future__ import annotations

from agents.state import ReviewState
from models.fix import CodeFix
from services.llm_service import LLMService, LLMServiceError

_PROMPT_TEMPLATE = """\
Fix the following {language} code to resolve the findings listed below. \
Make the SMALLEST change that resolves them -- do not refactor unrelated \
code, rename things, or change behavior the findings didn't flag.

Code:
```
{code}
```

Findings to fix:
{findings_text}

Return the complete fixed file content, a short explanation, and the \
list of line numbers you changed (1-indexed, in the ORIGINAL file).
"""


def run_generate_fix(state: ReviewState) -> dict:
    service = LLMService()
    findings = state.get("all_findings") or state.get("static_findings", [])
    findings_text = "\n".join(f"- [{f.severity}] {f.title}: {f.description}" for f in findings) or "(none)"

    prompt = _PROMPT_TEMPLATE.format(language=state["language"], code=state["code"], findings_text=findings_text)

    try:
        fix: CodeFix = service.structured_generate(prompt, CodeFix)
    except LLMServiceError as exc:
        return {"halted_reason": f"Fix generation failed: {exc}"}

    return {"generated_fix": fix}
