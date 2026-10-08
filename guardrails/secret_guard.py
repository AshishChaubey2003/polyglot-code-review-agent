"""
Secret detection.

Shared by input_guard (don't send obvious secrets to a third-party LLM
unnecessarily) and output_guard (don't let a generated fix reproduce a
detected secret verbatim). Pattern-based, not exhaustive -- this catches
common, high-confidence shapes, not every possible credential format.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_PATTERNS: dict[str, re.Pattern] = {
    "aws_access_key": re.compile(r"AKIA[0-9A-Z]{16}"),
    "generic_api_key_assignment": re.compile(
        r"(?i)(api[_-]?key|secret[_-]?key|access[_-]?token)\s*[=:]\s*['\"][A-Za-z0-9_\-]{16,}['\"]"
    ),
    "hardcoded_password_assignment": re.compile(
        r"(?i)password\s*=\s*['\"][^'\"]{4,}['\"]"
    ),
    "private_key_block": re.compile(r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "slack_token": re.compile(r"xox[baprs]-[0-9A-Za-z-]{10,}"),
    "jwt_like": re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
}


@dataclass(frozen=True)
class SecretMatch:
    kind: str
    line: int
    masked: str


def _mask(text: str) -> str:
    if len(text) <= 8:
        return "*" * len(text)
    return text[:4] + "*" * (len(text) - 8) + text[-4:]


def find_secrets(code: str) -> list[SecretMatch]:
    """Scan `code` line by line for secret-shaped substrings.

    Returns masked matches -- callers must never log or display the raw
    matched text, only `.masked`.
    """
    matches: list[SecretMatch] = []
    for line_number, line in enumerate(code.splitlines(), start=1):
        for kind, pattern in _PATTERNS.items():
            found = pattern.search(line)
            if found:
                matches.append(SecretMatch(kind=kind, line=line_number, masked=_mask(found.group(0))))
    return matches
