"""
FastAPI surface over the same orchestration services/review_service.py
that app.py (Streamlit) uses -- no logic is duplicated between the two
frontends.

Run: uvicorn api.main:app --reload
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from config import is_configured
from human_loop.approval import ApprovalError, get_approval_store
from human_loop.decisions import ApplyFixError, apply_fix
from services.review_service import run_repair, run_review

app = FastAPI(
    title="Polyglot AI Code Review & Repair Agent",
    description=(
        "Review mode analyzes code and returns findings; it never modifies anything. "
        "Repair mode additionally proposes a fix, which is guarded and verified but "
        "NEVER applied until a human explicitly approves it via /approve."
    ),
    version="0.1.0",
)


class ReviewRequest(BaseModel):
    code: str
    language: str = "python"


class ApprovalDecisionRequest(BaseModel):
    approval_id: str
    decided_by: str = "api-user"


@app.get("/health")
def health():
    return {"status": "ok", "llm_configured": is_configured()}


@app.post("/review")
def review(request: ReviewRequest):
    result = run_review(request.code, request.language)
    return result.model_dump()


@app.post("/repair")
def repair(request: ReviewRequest):
    review_result, approval_record, halted_reason = run_repair(request.code, request.language)
    response = {"review": review_result.model_dump()}

    if approval_record is None:
        response["proposed_fix"] = None
        response["halted_reason"] = halted_reason
    else:
        response["approval_id"] = approval_record.approval_id
        response["proposed_fix"] = approval_record.proposed_fix.model_dump()
        response["halted_reason"] = None

    return response


@app.post("/verify")
def verify(approval_id: str):
    """Returns the independent verification report for a pending or
    decided proposal, without approving or rejecting it."""
    try:
        record = get_approval_store().get(approval_id)
    except ApprovalError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return record.proposed_fix.verification.model_dump()


@app.post("/approve")
def approve(request: ApprovalDecisionRequest):
    try:
        record = get_approval_store().approve(request.approval_id, decided_by=request.decided_by)
    except ApprovalError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"approval_id": record.approval_id, "status": record.proposed_fix.approval_status}


@app.post("/reject")
def reject(request: ApprovalDecisionRequest):
    try:
        record = get_approval_store().reject(request.approval_id, decided_by=request.decided_by)
    except ApprovalError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"approval_id": record.approval_id, "status": record.proposed_fix.approval_status}


@app.post("/apply")
def apply(request: ApprovalDecisionRequest):
    try:
        applied = apply_fix(get_approval_store(), request.approval_id)
    except ApplyFixError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"approval_id": applied.approval_id, "fixed_code": applied.fixed_code, "applied_at": applied.applied_at}
