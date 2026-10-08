"""
Ruff wrapper.

Calls the installed `ruff` CLI as a subprocess against a temp file and
parses its JSON output into Finding objects. Subprocess rather than
Ruff's Python API, because the CLI's `--output-format=json` is Ruff's
stable, documented contract to depend on.
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

# Codes that indicate a likely runtime bug rather than a style nit.
# Everything else Ruff reports is treated as "quality" -- this keeps the
# category honest without hardcoding Ruff's hundreds of rule codes.
_BUG_CODES = {"F821", "F822", "F823", "F701", "F702", "F706", "F707"}


def _category_for(code: str) -> str:
    return "bug" if code in _BUG_CODES else "quality"


def _severity_for(code: str) -> str:
    return "high" if code in _BUG_CODES else "low"


def run_ruff(code: str) -> list[Finding]:
    """Run Ruff against `code`.

    Returns [] on a clean file. Returns a single descriptive Finding
    (never raises) if Ruff itself cannot run -- not installed, times
    out, or produces output that isn't valid JSON.
    """
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as tmp:
        tmp.write(code)
        tmp_path = Path(tmp.name)

    try:
        result = subprocess.run(
            ["ruff", "check", "--output-format=json", str(tmp_path)],
            capture_output=True,
            text=True,
            timeout=_TIMEOUT_SECONDS,
        )
    except FileNotFoundError:
        logger.error("ruff is not installed or not on PATH")
        return [tool_unavailable_finding("ruff", "ruff")]
    except subprocess.TimeoutExpired:
        logger.warning("ruff timed out after %ss", _TIMEOUT_SECONDS)
        return [tool_timeout_finding("ruff", "ruff", _TIMEOUT_SECONDS)]
    finally:
        tmp_path.unlink(missing_ok=True)

    # Ruff exits non-zero when it finds issues -- that is normal, not a failure.
    if not result.stdout.strip():
        return []

    try:
        raw_findings = json.loads(result.stdout)
    except json.JSONDecodeError:
        logger.error("ruff produced output that was not valid JSON: %s", result.stdout[:500])
        return [tool_unavailable_finding("ruff", "ruff", detail="produced unparseable output")]

    findings: list[Finding] = []
    for item in raw_findings:
        code_str = item.get("code") or "UNKNOWN"
        fix = item.get("fix") or {}
        location = item.get("location") or {}
        findings.append(
            Finding(
                category=_category_for(code_str),
                severity=_severity_for(code_str),
                title=f"{code_str}: {item.get('message', 'Ruff finding')}",
                description=item.get("message", ""),
                line=location.get("row"),
                evidence=item.get("message", ""),
                recommendation=fix.get("message") or "See the Ruff rule documentation for this code.",
                source="ruff",
            )
        )
    return findings
