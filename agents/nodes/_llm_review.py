"""Shared helper for the three parallel LLM review agents (bug,
security, quality). Each agent only differs by its category and
prompt focus -- this keeps that difference to one function call per
node instead of duplicating the structured-output/error-handling
plumbing three times.

Any LLM failure here degrades gracefully: the review continues with
fewer findings (from static analysis and the other two LLM agents)
rather than failing the whole request, and the quality signal of "did
it answer at all" surfaces by the finding count, not an exception.
"""

from __future__ import annotations

from config import logger
from models.finding import Finding, FindingList
from services.llm_service import LLMService, LLMServiceError

_PROMPT_TEMPLATE = """\
You are a {focus} reviewer for {language} code. Review the code below \
and the retrieved reference material, and report ONLY {category}-category \
issues you are confident about. Do not repeat issues already listed under \
"Already found by static analysis" -- look for what those tools would miss.

Code:
```
{code}
```

Already found by static analysis:
{existing_findings}

Retrieved reference material:
{retrieved_context}

For every issue, set source="llm" and category="{category}". Return an \
empty findings list if you see nothing you're confident about -- never \
invent an issue to have something to report.
"""


def run_llm_review(
    code: str,
    language: str,
    category: str,
    focus: str,
    existing_findings: list[Finding],
    retrieved_context: list,
    llm_service: LLMService | None = None,
) -> list[Finding]:
    service = llm_service or LLMService()

    existing_text = "\n".join(f"- {f.title}" for f in existing_findings) or "(none)"
    context_text = "\n\n".join(c.text for c in retrieved_context[:3]) or "(none retrieved)"

    prompt = _PROMPT_TEMPLATE.format(
        focus=focus, language=language, category=category, code=code,
        existing_findings=existing_text, retrieved_context=context_text,
    )

    try:
        result: FindingList = service.structured_generate(prompt, FindingList)
    except LLMServiceError as exc:
        logger.warning("%s review agent failed, contributing no findings: %s", category, exc)
        return []

    # Defensive: never trust the LLM to have respected the requested
    # category even though the prompt asked for it explicitly.
    return [f for f in result.findings if f.category == category]
