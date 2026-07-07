"""API endpoints for the flag contestation and review workflow.

Thin routers — all business logic lives in services/review_service.py.
"""

import logging

from fastapi import APIRouter, Body, Header, HTTPException, Request
from pydantic import BaseModel

from db.connection import get_pool
from services import review_service
from errors import ReviewError, ReviewPermissionError, ReviewNotFoundError

log = logging.getLogger("fitnova.routers.reviews")

router = APIRouter(prefix="/api", tags=["reviews"])


class ContestRequest(BaseModel):
    contest_reason: str


class DecisionRequest(BaseModel):
    decision: str
    decision_reason: str | None = None


@router.post("/calls/{call_id}/flags/{flag_id}/contest")
async def contest_flag(
    call_id: str,
    flag_id: str,
    body: ContestRequest,
    request: Request,
    x_advisor_id: str = Header(..., alias="X-Advisor-ID"),
):
    """Contest an AI-generated flag.

    The advisor identity comes from the X-Advisor-ID header.
    Never send reviewer_id in the request body.
    """
    pool = await get_pool()
    try:
        review = await review_service.contest_flag(
            pool,
            call_id=call_id,
            flag_id=flag_id,
            advisor_id=x_advisor_id,
            contest_reason=body.contest_reason,
        )
    except (ReviewError, ReviewPermissionError, ReviewNotFoundError) as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)

    return review


@router.post("/reviews/{review_id}/decision")
async def resolve_review(
    review_id: str,
    body: DecisionRequest,
    request: Request,
    x_advisor_id: str = Header(..., alias="X-Advisor-ID"),
):
    """Resolve a contested flag review.

    Allowed decisions: accepted, overturned
    Only team_leaders and directors may resolve reviews.
    """
    pool = await get_pool()
    try:
        resolved = await review_service.resolve_review(
            pool,
            review_id=review_id,
            team_leader_id=x_advisor_id,
            decision=body.decision,
            decision_reason=body.decision_reason,
        )
    except (ReviewError, ReviewPermissionError, ReviewNotFoundError) as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)

    return resolved


@router.get("/calls/{call_id}/reviews")
async def list_call_reviews(call_id: str, request: Request):
    """List all flag reviews for a call."""
    pool = await get_pool()
    reviews = await review_service.get_call_reviews(pool, call_id)
    return {"reviews": reviews, "count": len(reviews)}


@router.get("/reviews/pending")
async def list_pending_reviews(request: Request):
    """List all reviews awaiting team leader action."""
    pool = await get_pool()
    reviews = await review_service.get_pending_reviews(pool)
    return {"reviews": reviews, "count": len(reviews)}
