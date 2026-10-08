"""
Bandit wrapper.

Calls the installed `bandit` CLI as a subprocess with JSON output.
Bandit's severity/confidence scale is mapped onto the shared Finding
severity scale; confidence is folded into the recommendation text
rather than dropped -- a LOW-confidence HIGH-severity finding should
read differently from a HIGH-confidence one, and the schema has no
separate confidence field yet.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

from analyzers.tools._shared import tool_timeout_finding, tool_unavailable_finding
from config import logger
from models.finding import Finding

_TIMEOUT_SECONDS = 15

_SEVERITY_MAP = {"LOW": "low", "MEDIUM": "medium", "HIGH": "high"}


def run_bandit(code: str) -> list[Finding]:
    """Run Bandit against `code`.

    Returns [] on a clean file. Returns a single descriptive Finding
    (never raises) if Bandit itself cannot run.
    """
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as tmp:
        tmp.write(code)
        tmp_path = Path(tmp.name)

    try:
        result = subprocess.run(
            ["bandit", "-f", "json", str(tmp_path)],
            capture_output=True,
            text=True,
            timeout=_TIMEOUT_SECONDS,
        )
    except FileNotFoundError:
        logger.error("bandit is not installed or not on PATH")
        return [tool_unavailable_finding("bandit", "bandit")]
    except subprocess.TimeoutExpired:
        logger.warning("bandit timed out after %ss", _TIMEOUT_SECONDS)
        return [tool_timeout_finding("bandit", "bandit", _TIMEOUT_SECONDS)]
    finally:
        tmp_path.unlink(missing_ok=True)

    # Bandit exits 1 when it finds issues -- not a failure.
    if not result.stdout.strip():
        return []

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        logger.error("bandit produced output that was not valid JSON: %s", result.stdout[:500])
        return [tool_unavailable_finding("bandit", "bandit", detail="produced unparseable output")]

    findings: list[Finding] = []
    for item in payload.get("results", []):
        severity = _SEVERITY_MAP.get(item.get("issue_severity", "").upper(), "medium")
        findings.append(
            Finding(
                category="security",
                severity=severity,
                title=f"{item.get('test_id', 'B000')}: {item.get('issue_text', 'Bandit finding')}",
                description=item.get("issue_text", ""),
                line=item.get("line_number"),
                evidence=(item.get("code") or "").strip() or item.get("issue_text", ""),
                recommendation=(
                    f"See {item.get('more_info', 'Bandit documentation')} "
                    f"(confidence: {item.get('issue_confidence', 'UNKNOWN')})"
                ),
                source="bandit",
            )
        )
    return findings
