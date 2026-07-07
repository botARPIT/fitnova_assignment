# Task 05: Flag Contestation & Review Workflow

## Objective
Implement the flag contestation API and review workflow. Advisors can contest flags they disagree with, and team leaders can accept or overturn contested flags.

## Parallelization
**Group B** — Depends on Task 01 (database) and Task 04 (pipeline).

## Context
From the requirements:
- *"any advisor to contest a flag"* — advisors should be able to dispute machine-generated flags
- *"a team-leader can accept or overturn it"* — two-level review: advisor contests → team leader resolves
- *"the contest decision feeds back into the next scoring pass"* — discarded flags should influence future analysis

## Files to Create

### 1. `backend/routers/reviews.py`

```python
"""Flag contestation and review workflow endpoints."""

import logging

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from db.connection import get_pool
from db import repository as repo

log = logging.getLogger("fitnova.routes.reviews")
router = APIRouter(prefix="/api/calls", tags=["reviews"])


class ContestFlagRequest(BaseModel):
    flag_index: int
    reason: str
    reviewer_id: str | None = None


class ReviewFlagRequest(BaseModel):
    decision: str  # "accepted" or "overturned"


@router.post("/{call_id}/contest-flag")
async def contest_flag(
    request: Request,
    call_id: str,
    body: ContestFlagRequest,
):
    """Contest a flag on a call.
    
    An advisor (or anyone reviewing) can contest a flag they disagree with.
    This creates a flag_review record with decision='contested'.
    A team leader can later accept or overturn it.
    """
    pool = await get_pool()
    
    # Verify call exists and is completed
    call = await repo.get_call(pool, call_id)
    if not call:
        raise HTTPException(404, f"Call {call_id} not found")
    if call.get("status") != "completed":
        raise HTTPException(400, "Can only contest flags on completed calls")
    
    # Verify flag index is valid
    flags = call.get("flags") or []
    if body.flag_index < 0 or body.flag_index >= len(flags):
        raise HTTPException(400, f"Invalid flag_index {body.flag_index}. Call has {len(flags)} flags.")
    
    # Create the review
    review = await repo.create_flag_review(
        pool,
        call_id=call_id,
        flag_index=body.flag_index,
        reviewer_id=body.reviewer_id,
        decision="contested",
        reason=body.reason,
    )
    
    # Serialize UUIDs
    for key in review:
        if hasattr(review[key], 'hex'):
            review[key] = str(review[key])
        elif hasattr(review[key], 'isoformat'):
            review[key] = review[key].isoformat()
    
    log.info(f"Flag {body.flag_index} on call {call_id} contested: {body.reason}")
    
    return {
        "status": "contested",
        "review": review,
        "flag": flags[body.flag_index],
    }


@router.patch("/{call_id}/reviews/{review_id}")
async def resolve_review(
    request: Request,
    call_id: str,
    review_id: str,
    body: ReviewFlagRequest,
):
    """Resolve a flag contest (team leader accepts or overturns).
    
    - 'accepted': The flag stands. The contest is acknowledged but the flag remains.
    - 'overturned': The flag is removed from the active flags.
    """
    pool = await get_pool()
    
    if body.decision not in ("accepted", "overturned"):
        raise HTTPException(400, "Decision must be 'accepted' or 'overturned'")
    
    review = await repo.update_flag_review(pool, review_id, body.decision)
    if not review:
        raise HTTPException(404, f"Review {review_id} not found")
    
    # If overturned, move the flag from flags → discarded_flags
    if body.decision == "overturned":
        call = await repo.get_call(pool, call_id)
        if call:
            flags = call.get("flags") or []
            discarded = call.get("discarded_flags") or []
            flag_index = review.get("flag_index", -1)
            
            if 0 <= flag_index < len(flags):
                moved_flag = flags.pop(flag_index)
                moved_flag["overturned"] = True
                moved_flag["overturn_reason"] = review.get("reason", "")
                discarded.append(moved_flag)
                
                # Recalculate overall score (flags removed = higher score)
                scores = call.get("scores") or {}
                dim_scores = [v for v in scores.values() if isinstance(v, (int, float))]
                overall = round(sum(dim_scores) / len(dim_scores), 2) if dim_scores else 0
                
                await repo.save_report(
                    pool,
                    call_id=call_id,
                    scores=scores,
                    overall_score=overall,
                    flags=flags,
                    discarded_flags=discarded,
                )
                
                log.info(f"Flag {flag_index} on call {call_id} overturned — moved to discarded")
    
    # Serialize
    for key in review:
        if hasattr(review[key], 'hex'):
            review[key] = str(review[key])
        elif hasattr(review[key], 'isoformat'):
            review[key] = review[key].isoformat()
    
    return {"status": body.decision, "review": review}


@router.get("/{call_id}/reviews")
async def list_reviews(request: Request, call_id: str):
    """List all flag reviews for a call."""
    pool = await get_pool()
    reviews = await repo.list_flag_reviews(pool, call_id)
    
    for r in reviews:
        for key in r:
            if hasattr(r[key], 'hex'):
                r[key] = str(r[key])
            elif hasattr(r[key], 'isoformat'):
                r[key] = r[key].isoformat()
    
    return {"reviews": reviews}
```

## Files to Modify

### 2. `backend/main.py`
Add to imports:
```python
from routers import reviews
```

Add router registration:
```python
app.include_router(reviews.router)
```

## Workflow Design

```
┌─────────────────────────────────────────────┐
│ Call Analysis Complete                       │
│ flags: [flag_0, flag_1, flag_2]             │
└─────────┬───────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────┐
│ POST /api/calls/{id}/contest-flag           │
│ body: { flag_index: 1, reason: "..." }      │
│ → Creates flag_review with decision=        │
│   "contested"                               │
└─────────┬───────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────┐
│ Team Leader Reviews                         │
│ PATCH /api/calls/{id}/reviews/{review_id}   │
│ body: { decision: "overturned" }            │
│                                             │
│ If overturned:                              │
│   → Move flag from flags → discarded_flags  │
│   → Mark flag as overturned                 │
│   → Recalculate overall_score              │
│                                             │
│ If accepted:                                │
│   → Flag stays, review recorded             │
└─────────────────────────────────────────────┘
```

## Acceptance Criteria
1. `POST /api/calls/{id}/contest-flag` creates a contest with reason
2. `PATCH /api/calls/{id}/reviews/{review_id}` with `decision: "overturned"` moves flag to discarded
3. `PATCH /api/calls/{id}/reviews/{review_id}` with `decision: "accepted"` keeps flag and records review
4. `GET /api/calls/{id}/reviews` lists all reviews for a call
5. Overall score is recalculated when flags are overturned
6. Invalid flag indices return 400
7. Non-completed calls cannot have flags contested
