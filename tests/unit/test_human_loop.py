from __future__ import annotations

import pytest

from human_loop.approval import ApprovalError, ApprovalStore
from human_loop.decisions import ApplyFixError, apply_fix
from models.fix import CodeFix, ProposedFix, VerificationReport, VerificationStepResult


def _proposed_fix(all_pass: bool = True) -> ProposedFix:
    steps = [VerificationStepResult(name="syntax", passed=all_pass, detail="d")]
    return ProposedFix(
        original_code="x = 1\n",
        fix=CodeFix(fixed_code="x = 2\n", explanation="e", changed_lines=[1]),
        diff="--- a\n+++ b\n",
        verification=VerificationReport(steps=steps),
    )


def test_submit_creates_a_pending_record():
    store = ApprovalStore()
    record = store.submit(_proposed_fix())
    assert record.proposed_fix.approval_status == "pending"
    assert record.decided_at is None


def test_approve_transitions_to_approved():
    store = ApprovalStore()
    record = store.submit(_proposed_fix())
    approved = store.approve(record.approval_id)
    assert approved.proposed_fix.approval_status == "approved"
    assert approved.decided_at is not None


def test_approve_allowed_even_when_verification_failed():
    """Human override is allowed -- verification failing doesn't take
    the decision out of the human's hands, it just informs it."""
    store = ApprovalStore()
    record = store.submit(_proposed_fix(all_pass=False))
    approved = store.approve(record.approval_id)
    assert approved.proposed_fix.approval_status == "approved"


def test_reject_transitions_to_rejected():
    store = ApprovalStore()
    record = store.submit(_proposed_fix())
    rejected = store.reject(record.approval_id)
    assert rejected.proposed_fix.approval_status == "rejected"


def test_cannot_approve_twice():
    store = ApprovalStore()
    record = store.submit(_proposed_fix())
    store.approve(record.approval_id)
    with pytest.raises(ApprovalError):
        store.approve(record.approval_id)


def test_cannot_reject_after_approve():
    store = ApprovalStore()
    record = store.submit(_proposed_fix())
    store.approve(record.approval_id)
    with pytest.raises(ApprovalError):
        store.reject(record.approval_id)


def test_unknown_approval_id_raises():
    store = ApprovalStore()
    with pytest.raises(ApprovalError):
        store.get("not-a-real-id")


def test_apply_fix_requires_approved_status():
    store = ApprovalStore()
    record = store.submit(_proposed_fix())
    with pytest.raises(ApplyFixError):
        apply_fix(store, record.approval_id)


def test_apply_fix_returns_fixed_code_once_approved():
    store = ApprovalStore()
    record = store.submit(_proposed_fix())
    store.approve(record.approval_id)
    applied = apply_fix(store, record.approval_id)
    assert applied.fixed_code == "x = 2\n"


def test_apply_fix_rejects_a_rejected_fix():
    store = ApprovalStore()
    record = store.submit(_proposed_fix())
    store.reject(record.approval_id)
    with pytest.raises(ApplyFixError):
        apply_fix(store, record.approval_id)
