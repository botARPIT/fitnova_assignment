"""Review service — business logic for the flag contestation workflow.

Responsibilities:
  - Permission checks (advisors contest, team_leaders resolve)
  - Create contests (validate flag exists, no duplicate PENDING review)
  - Resolve reviews (validate PENDING, enforce role, update in transaction)
  - Compute effective flag status from review history

Routers should never manipulate flags or reviews directly — always go
through this service.
"""

import logging

from errors import (
    ReviewError,
    ReviewPermissionError,
    ReviewNotFoundError,
)
from db import review_repository

log = logging.getLogger("fitnova.services.review")

ALLOWED_RESOLVE_DECISIONS = {"accepted", "overturned"}
RESOLVER_ROLES = {"team_leader", "director"}
CONTESTOR_ROLES = {"advisor"}


async def _get_advisor_role(pool, advisor_id: str) -> str | None:
    """Look up an advisor's role. Returns None if advisor doesn't exist."""
    from db.analytics_repository import get_advisor_by_id
    advisor = await get_advisor_by_id(pool, advisor_id)
    if not advisor:
        return None
    return advisor.get("role", "advisor")


async def _get_call_advisor_id(pool, call_id: str) -> str | None:
    from db.call_repository import get_call
    call = await get_call(pool, call_id)
    if not call or not call.get("advisor_id"):
        return None
    return str(call["advisor_id"])


async def contest_flag(
    pool,
    *,
    call_id: str,
    flag_id: str,
    advisor_id: str,
    contest_reason: str,
) -> dict:
    """Contest a flag — creates a PENDING review.

    Validates:
      1. The flag exists in the call's report
      2. No PENDING review already exists for this flag
      3. The advisor exists

    Returns the created review record.
    """
    # 1. Verify flag exists
    flag_data = await review_repository.get_flag_by_id(pool, call_id, flag_id)
    if not flag_data:
        raise ReviewNotFoundError(f"Flag {flag_id} not found on call {call_id}")

    # 2. Check no existing PENDING review
    existing = await review_repository.get_pending_review_for_flag(
        pool, flag_id=flag_id, call_id=call_id,
    )
    if existing:
        raise ReviewError(
            f"Flag {flag_id} already has a PENDING review ({existing['id']})"
        )

    # 3. Verify advisor exists and is allowed to contest
    role = await _get_advisor_role(pool, advisor_id)
    if role is None:
        raise ReviewNotFoundError({
            "code": "advisor_not_found",
            "entity": "advisor",
            "entity_id": advisor_id,
            "detail": "Advisor not found",
        })
    if role not in CONTESTOR_ROLES:
        raise ReviewPermissionError(
            f"Advisor {advisor_id} has role '{role}', "
            f"but only {CONTESTOR_ROLES} can contest flags"
        )

    call_advisor_id = await _get_call_advisor_id(pool, call_id)
    if call_advisor_id is None:
        raise ReviewNotFoundError({
            "code": "call_advisor_not_found",
            "entity": "call",
            "entity_id": call_id,
            "detail": "Call advisor not found",
        })
    if str(advisor_id) != call_advisor_id:
        raise ReviewPermissionError(
            "Only the advisor who owns this call can contest its flags"
        )

    # 4. Create review
    review = await review_repository.create_review(
        pool,
        call_id=call_id,
        flag_id=flag_id,
        advisor_id=advisor_id,
        contest_reason=contest_reason,
    )

    log.info(
        f"Flag {flag_id} contested by advisor {advisor_id} "
        f"→ review {review['id']} (PENDING)"
    )
    return review


async def resolve_review(
    pool,
    *,
    review_id: str,
    team_leader_id: str,
    decision: str,
    decision_reason: str | None,
) -> dict:
    """Resolve a PENDING review — accept or overturn.

    Validates:
      1. The review exists and is PENDING
      2. The resolver is a team_leader or director
      3. The decision is valid (accepted or overturned)

    Runs inside a database transaction to prevent concurrent approvals.
    """
    # 1. Validate decision
    if decision not in ALLOWED_RESOLVE_DECISIONS:
        raise ReviewError(
            f"Invalid decision '{decision}'. Must be one of: {ALLOWED_RESOLVE_DECISIONS}"
        )

    # 2. Verify resolver has appropriate role
    role = await _get_advisor_role(pool, team_leader_id)
    if role is None:
        raise ReviewNotFoundError({
            "code": "reviewer_not_found",
            "entity": "team_leader",
            "entity_id": team_leader_id,
            "detail": "Team leader not found",
        })
    if role not in RESOLVER_ROLES:
        raise ReviewPermissionError(
            f"Advisor {team_leader_id} has role '{role}', "
            f"but only {RESOLVER_ROLES} can resolve reviews"
        )

    # 3. Resolve in transaction
    async with pool.acquire() as conn:
        async with conn.transaction():
            # Fetch current state inside the transaction
            review = await review_repository.get_review(conn, review_id)
            if not review:
                raise ReviewNotFoundError(f"Review {review_id} not found")
            if review["status"] != "PENDING":
                raise ReviewError(
                    f"Review {review_id} has status '{review['status']}', "
                    f"not 'PENDING'. Only PENDING reviews may be resolved."
                )

            resolved = await review_repository.resolve_review(
                conn,
                review_id=review_id,
                team_leader_id=team_leader_id,
                decision=decision,
                decision_reason=decision_reason,
            )

    if not resolved:
        raise ReviewError(f"Failed to resolve review {review_id}")

    log.info(
        f"Review {review_id} resolved as '{decision}' "
        f"by team_leader {team_leader_id}"
    )
    return resolved


async def get_call_reviews(pool, call_id: str) -> list[dict]:
    """List all reviews for a call."""
    return await review_repository.get_reviews_by_call(pool, call_id)


async def get_pending_reviews(pool) -> list[dict]:
    """List all reviews awaiting team leader action."""
    return await review_repository.get_pending_reviews(pool)


async def compute_effective_flags(
    pool,
    call_id: str,
    original_flags: list[dict],
) -> list[dict]:
    """Compute effective status for each flag based on review history.

    Original analysis is never modified. Instead, each flag is annotated
    with a computed `status` derived from the most recent review:

      No review      → ACTIVE
      PENDING review → CONTESTED
      ACCEPTED       → ACTIVE
      OVERTURNED     → OVERTURNED

    Args:
        pool: Database connection pool
        call_id: The call to compute flags for
        original_flags: The original flags array from reports.flags

    Returns:
        A new list of flag dicts, each with a `status` field added.
        The original list is not modified.
    """
    reviews = await review_repository.get_reviews_by_call(pool, call_id)

    # Build a map: flag_id → most recent review
    review_map: dict[str, dict] = {}
    for r in reviews:
        rid = str(r["flag_id"])
        # Keep latest review for each flag
        review_map[rid] = r

    effective = []
    for flag in original_flags:
        flag_copy = dict(flag)
        fid = flag_copy.get("flag_id")

        if fid and fid in review_map:
            r = review_map[fid]
            if r["status"] == "PENDING":
                flag_copy["status"] = "CONTESTED"
            elif r["status"] == "ACCEPTED":
                flag_copy["status"] = "ACTIVE"
            elif r["status"] == "OVERTURNED":
                flag_copy["status"] = "OVERTURNED"
            else:
                flag_copy["status"] = "ACTIVE"
        else:
            flag_copy["status"] = "ACTIVE"

        effective.append(flag_copy)

    return effective
