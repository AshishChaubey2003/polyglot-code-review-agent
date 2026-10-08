"""
Behavior verification -- the step that proves (or admits it cannot
prove) that a fix preserves intended behavior, not just valid syntax.

Security principle (see the project README's Security section): user
code is untrusted, and the initial version of this system does not
execute it. Running arbitrary test code means running arbitrary code --
that needs a real sandbox (container, resource limits, no network, no
filesystem access) before it is safe to turn on by default.

So: execution is OFF by default (`ALLOW_TEST_EXECUTION` in config/.env).
When off, or when no test code is supplied, this step reports truthfully
that behavior could not be verified -- it never claims verification that
didn't happen. When explicitly enabled, it runs pytest in a subprocess
with a hard timeout as a best-effort minimum, which is NOT a substitute
for real sandboxing and should not be enabled against untrusted input in
a shared environment.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

from config import logger
from models.fix import VerificationStepResult

_TIMEOUT_SECONDS = 10


def verify_behavior(
    fixed_code: str,
    test_code: str | None,
    allow_execution: bool,
) -> VerificationStepResult:
    if not test_code:
        return VerificationStepResult(
            name="behavior", passed=False,
            detail="Behavior could not be fully verified because no tests were provided.",
        )

    if not allow_execution:
        return VerificationStepResult(
            name="behavior", passed=False,
            detail=(
                "Behavior could not be fully verified because test execution is "
                "disabled (ALLOW_TEST_EXECUTION=false). Enabling it runs the fixed "
                "code and the supplied tests in a subprocess -- only do this in an "
                "environment you trust; it is not a full sandbox."
            ),
        )

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        (tmp_path / "solution.py").write_text(fixed_code)
        (tmp_path / "test_solution.py").write_text(test_code)

        try:
            result = subprocess.run(
                [sys.executable, "-m", "pytest", str(tmp_path), "-q"],
                capture_output=True, text=True, timeout=_TIMEOUT_SECONDS,
                cwd=str(tmp_path),
            )
        except subprocess.TimeoutExpired:
            logger.warning("behavior verification timed out after %ss", _TIMEOUT_SECONDS)
            return VerificationStepResult(
                name="behavior", passed=False,
                detail=f"Test run did not finish within {_TIMEOUT_SECONDS}s.",
            )

        passed = result.returncode == 0
        tail = (result.stdout or result.stderr).strip().splitlines()[-5:]
        return VerificationStepResult(
            name="behavior", passed=passed,
            detail="All provided tests passed." if passed else "\n".join(tail),
        )
