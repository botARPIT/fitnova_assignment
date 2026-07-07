"""Review repository — SQL for flag_review operations.

Every flag has a stable UUID (flag_id) embedded in the reports.flags JSONB.
Reviews reference flags by flag_id, never by array index.
"""

import uuid

import asyncpg


async def create_review(
    pool: asyncpg.Pool,
    *,
    call_id: str,
    flag_id: str,
    advisor_id: str,
    contest_reason: str,
) -> dict:
    """Create a new PENDING review (advisor contests a flag)."""
    row = await pool.fetchrow("""
        INSERT INTO flag_reviews (call_id, flag_id, advisor_id, status, contest_reason)
        VALUES ($1, $2, $3, 'PENDING', $4)
        RETURNING *
    """, uuid.UUID(call_id), uuid.UUID(flag_id), uuid.UUID(advisor_id), contest_reason)
    return dict(row)


async def get_review(pool: asyncpg.Pool, review_id: str) -> dict | None:
    """Get a single review by its ID."""
    row = await pool.fetchrow("""
        SELECT fr.*,
            a.name as advisor_name,
            tl.name as team_leader_name
        FROM flag_reviews fr
        LEFT JOIN advisors a ON a.id = fr.advisor_id
        LEFT JOIN advisors tl ON tl.id = fr.team_leader_id
        WHERE fr.id = $1
    """, uuid.UUID(review_id))
    return dict(row) if row else None


async def get_reviews_by_call(pool: asyncpg.Pool, call_id: str) -> list[dict]:
    """List all reviews for a given call, ordered by creation time."""
    rows = await pool.fetch("""
        SELECT fr.*,
            a.name as advisor_name,
            tl.name as team_leader_name
        FROM flag_reviews fr
        LEFT JOIN advisors a ON a.id = fr.advisor_id
        LEFT JOIN advisors tl ON tl.id = fr.team_leader_id
        WHERE fr.call_id = $1
        ORDER BY fr.created_at
    """, uuid.UUID(call_id))
    return [dict(r) for r in rows]


async def get_pending_reviews(pool: asyncpg.Pool) -> list[dict]:
    """List all reviews with status PENDING (awaiting team leader action)."""
    rows = await pool.fetch("""
        SELECT fr.*,
            a.name as advisor_name,
            tl.name as team_leader_name,
            c.id as call_id
        FROM flag_reviews fr
        LEFT JOIN advisors a ON a.id = fr.advisor_id
        LEFT JOIN advisors tl ON tl.id = fr.team_leader_id
        JOIN calls c ON c.id = fr.call_id
        WHERE fr.status = 'PENDING'
        ORDER BY fr.created_at
    """)
    return [dict(r) for r in rows]


async def get_pending_review_for_flag(
    pool: asyncpg.Pool,
    flag_id: str,
    call_id: str,
) -> dict | None:
    """Check if a flag already has a PENDING review (prevents duplicates)."""
    row = await pool.fetchrow("""
        SELECT * FROM flag_reviews
        WHERE flag_id = $1 AND call_id = $2 AND status = 'PENDING'
    """, uuid.UUID(flag_id), uuid.UUID(call_id))
    return dict(row) if row else None


async def resolve_review(
    pool: asyncpg.Pool,
    *,
    review_id: str,
    team_leader_id: str,
    decision: str,
    decision_reason: str | None,
) -> dict | None:
    """Resolve a PENDING review (accepted or overturned).

    Must be called inside a transaction to prevent concurrent approvals.
    """
    row = await pool.fetchrow("""
        UPDATE flag_reviews SET
            status = $2,
            team_leader_id = $3,
            decision_reason = $4,
            resolved_at = NOW()
        WHERE id = $1 AND status = 'PENDING'
        RETURNING *
    """, uuid.UUID(review_id), decision, uuid.UUID(team_leader_id), decision_reason)
    return dict(row) if row else None


async def get_flag_by_id(
    pool: asyncpg.Pool,
    call_id: str,
    flag_id: str,
) -> dict | None:
    """Extract a single flag object from the reports.flags JSONB array by flag_id.

    Returns the flag dict if found, along with the report scores and overall_score.
    """
    row = await pool.fetchrow("""
        SELECT f.value as flag, r.scores, r.overall_score
        FROM reports r
        CROSS JOIN jsonb_array_elements(r.flags) AS f
        WHERE r.call_id = $1 AND f->>'flag_id' = $2
    """, uuid.UUID(call_id), str(flag_id))
    if not row:
        return None
    result = dict(row)
    return result
