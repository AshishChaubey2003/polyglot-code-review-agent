"""
Query transformation: turn (code + static findings) into one or more
retrieval queries plus optional metadata filters.

This is the one place an LLM gets to influence *what* is searched for.
Its output is validated twice: once by Pydantic (QueryPlan's shape) and
once by rag.metadata.validate_filters() (every filter key/value against
an explicit allow-list). If the LLM is unavailable or misbehaves, this
falls back to a deterministic query built from the findings themselves
-- retrieval degrades, it never breaks.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from config import logger
from models.retrieval import QueryPlan
from rag.metadata import validate_filters
from services.llm_service import LLMService, LLMServiceError

_PROMPT_TEMPLATE = """\
You are helping retrieve relevant security/quality reference material for
a code review. Given the code and the static-analysis findings below,
propose 1-3 short search queries and, only if confident, metadata filters.

Code (language: {language}):
```
{code}
```

Static findings:
{findings_text}

Return queries that describe the *topics* to look up (e.g. "SQL injection
parameterized queries", "hardcoded credentials"), not the code itself.
"""


@dataclass
class TransformedQuery:
    queries: list[str]
    filters: dict[str, str]
    dropped_filters: list[str] = field(default_factory=list)


def _fallback_query(language: str, findings: list) -> TransformedQuery:
    """Deterministic fallback: one query per distinct finding title,
    capped at 3, plus a language filter when all findings share one."""
    titles = []
    for f in findings:
        title = getattr(f, "title", None) or str(f)
        if title not in titles:
            titles.append(title)
    queries = titles[:3] or [f"{language} code review best practices"]
    filters = {"language": language} if language else {}
    result = validate_filters(filters)
    return TransformedQuery(queries=queries, filters=result.filters, dropped_filters=result.dropped)


def transform_query(
    code: str,
    findings: list,
    language: str,
    llm_service: LLMService | None = None,
) -> TransformedQuery:
    """Returns a TransformedQuery. Never raises -- falls back to a
    deterministic query on any LLM failure."""
    service = llm_service or LLMService()

    findings_text = "\n".join(
        f"- [{getattr(f, 'severity', '?')}] {getattr(f, 'title', str(f))}: "
        f"{getattr(f, 'description', '')}"
        for f in findings
    ) or "(no static findings)"

    prompt = _PROMPT_TEMPLATE.format(language=language, code=code, findings_text=findings_text)

    try:
        plan: QueryPlan = service.structured_generate(prompt, QueryPlan)
    except LLMServiceError as exc:
        logger.warning("Query transform LLM call failed, using deterministic fallback: %s", exc)
        return _fallback_query(language, findings)

    queries = [q for q in plan.queries if q and q.strip()][:3]
    if not queries:
        return _fallback_query(language, findings)

    validated = validate_filters(plan.filters)
    if validated.dropped:
        logger.info("Query transform proposed filters were partially dropped: %s", validated.dropped)

    return TransformedQuery(queries=queries, filters=validated.filters, dropped_filters=validated.dropped)
