"""
In-memory human-in-the-loop approval state machine.

A ProposedFix coming out of the graph always has approval_status
"pending" -- nothing in this codebase ever sets it to "approved" except
a human calling `approve()` here, explicitly. `apply_fix()` is the only
place fixed code is ever written out, and it refuses to run against
anything that isn't "approved".

In-memory by design for this phase: a restart loses pending approvals,
which is the right failure mode for "never silently apply an
unreviewed fix" -- losing state is safer than attempting to recover and
guessing wrong about whether something was actually approved.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from models.fix import ProposedFix


class ApprovalError(Exception):
    """Raised on an invalid approval-state transition."""


@dataclass
class ApprovalRecord:
    approval_id: str
    proposed_fix: ProposedFix
    created_at: str
    decided_at: str | None = None
    decided_by: str | None = None


class ApprovalStore:
    """One process-local store. A real deployment would back this with
    a database keyed by review session; the interface here is written
    so that swap is a storage-layer change only."""

    def __init__(self) -> None:
        self._records: dict[str, ApprovalRecord] = {}

    def submit(self, proposed_fix: ProposedFix) -> ApprovalRecord:
        approval_id = str(uuid.uuid4())
        record = ApprovalRecord(
            approval_id=approval_id,
            proposed_fix=proposed_fix,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self._records[approval_id] = record
        return record

    def get(self, approval_id: str) -> ApprovalRecord:
        record = self._records.get(approval_id)
        if record is None:
            raise ApprovalError(f"No approval record found for id {approval_id!r}.")
        return record

    def approve(self, approval_id: str, decided_by: str = "user") -> ApprovalRecord:
        record = self.get(approval_id)
        if record.proposed_fix.approval_status != "pending":
            raise ApprovalError(
                f"Cannot approve: fix is already '{record.proposed_fix.approval_status}'."
            )
        # A failing verification report does NOT block approval -- the
        # human reviewing the diff may have good reason to override
        # (e.g. a known false positive). It is never hidden: the UI
        # shows the verification report alongside the Approve button,
        # and the decision + the report both stay in the audit record.
        record.proposed_fix = record.proposed_fix.model_copy(update={"approval_status": "approved"})
        record.decided_at = datetime.now(timezone.utc).isoformat()
        record.decided_by = decided_by
        return record

    def reject(self, approval_id: str, decided_by: str = "user") -> ApprovalRecord:
        record = self.get(approval_id)
        if record.proposed_fix.approval_status != "pending":
            raise ApprovalError(
                f"Cannot reject: fix is already '{record.proposed_fix.approval_status}'."
            )
        record.proposed_fix = record.proposed_fix.model_copy(update={"approval_status": "rejected"})
        record.decided_at = datetime.now(timezone.utc).isoformat()
        record.decided_by = decided_by
        return record

    def all_records(self) -> list[ApprovalRecord]:
        return list(self._records.values())


_STORE = ApprovalStore()


def get_approval_store() -> ApprovalStore:
    return _STORE
