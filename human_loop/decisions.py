"""
Applying an approved fix.

This app never had a file path to begin with -- the user pastes or
uploads code, it isn't opened from a path on disk (that's a GitHub PR
integration concern, explicitly deferred -- see services/github_service.py).
So "applying" a fix here means handing back the approved fixed code and
an audit record, not writing to a filesystem. A caller that does have a
real file (the GitHub integration, once built) is the one place a write
to disk would happen, and it would call through here first.
"""

from __future__ import annotations

from dataclasses import dataclass

from human_loop.approval import ApprovalError, ApprovalStore
from models.fix import ProposedFix


class ApplyFixError(Exception):
    """Raised when asked to apply a fix that isn't in an applyable state."""


@dataclass
class AppliedFix:
    approval_id: str
    fixed_code: str
    applied_at: str


def apply_fix(store: ApprovalStore, approval_id: str) -> AppliedFix:
    """Returns the approved fix's code for the caller to use. Refuses
    anything not explicitly approved -- there is no path from
    'pending' or 'rejected' straight to applied."""
    try:
        record = store.get(approval_id)
    except ApprovalError as exc:
        raise ApplyFixError(str(exc)) from exc

    fix: ProposedFix = record.proposed_fix
    if fix.approval_status != "approved":
        raise ApplyFixError(
            f"Cannot apply a fix in status '{fix.approval_status}' -- it must be 'approved' first."
        )

    return AppliedFix(
        approval_id=approval_id,
        fixed_code=fix.fix.fixed_code,
        applied_at=record.decided_at or "",
    )
