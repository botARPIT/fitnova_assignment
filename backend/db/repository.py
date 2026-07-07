"""Database repository — all SQL queries in one place."""

import json
import uuid
from datetime import datetime, timezone

import asyncpg


# ── Org Queries ──────────────────────────────────────────────

async def list_teams(pool: asyncpg.Pool) -> list[dict]:
    """List all teams with advisor count."""
    rows = await pool.fetch("""
        SELECT t.id, t.name, t.organization_id, COUNT(a.id) as advisor_count
        FROM teams t
        LEFT JOIN advisors a ON a.team_id = t.id
        GROUP BY t.id, t.name, t.organization_id
        ORDER BY t.name
    """)
    return [dict(r) for r in rows]


async def list_advisors(pool: asyncpg.Pool, team_id: str | None = None) -> list[dict]:
    """List advisors, optionally filtered by team."""
    if team_id:
        rows = await pool.fetch(
            "SELECT * FROM advisors WHERE team_id = $1 ORDER BY name",
            uuid.UUID(team_id),
        )
    else:
        rows = await pool.fetch("SELECT * FROM advisors ORDER BY name")
    return [dict(r) for r in rows]


# ── Call Queries ─────────────────────────────────────────────

async def create_call(
    pool: asyncpg.Pool,
    *,
    organization_id: str,
    advisor_id: str | None,
    audio_path: str,
) -> dict:
    """Insert a new call record with status='processing'."""
    row = await pool.fetchrow("""
        INSERT INTO calls (organization_id, advisor_id, audio_path, status)
        VALUES ($1, $2, $3, 'processing')
        RETURNING *
    """, uuid.UUID(organization_id),
        uuid.UUID(advisor_id) if advisor_id else None,
        audio_path)
    return dict(row)


async def update_call_status(
    pool: asyncpg.Pool,
    call_id: str,
    status: str,
    *,
    duration_sec: float | None = None,
    language: str | None = None,
    error_message: str | None = None,
) -> None:
    """Update a call's status and optional fields."""
    completed_at = datetime.now(timezone.utc) if status in ("completed", "failed") else None
    await pool.execute("""
        UPDATE calls SET
            status = $2,
            duration_sec = COALESCE($3, duration_sec),
            language = COALESCE($4, language),
            error_message = $5,
            completed_at = COALESCE($6, completed_at)
        WHERE id = $1
    """, uuid.UUID(call_id), status, duration_sec, language, error_message, completed_at)


async def get_call(pool: asyncpg.Pool, call_id: str) -> dict | None:
    """Get a single call with its transcript and report."""
    row = await pool.fetchrow("""
        SELECT
            c.*,
            t.raw_transcript,
            t.diarized_transcript,
            t.engine,
            r.scores,
            r.overall_score,
            r.flags,
            r.discarded_flags,
            a.name as advisor_name,
            te.name as team_name
        FROM calls c
        LEFT JOIN transcripts t ON t.call_id = c.id
        LEFT JOIN reports r ON r.call_id = c.id
        LEFT JOIN advisors a ON a.id = c.advisor_id
        LEFT JOIN teams te ON te.id = a.team_id
        WHERE c.id = $1
    """, uuid.UUID(call_id))
    if not row:
        return None
    result = dict(row)
    for key in ('raw_transcript', 'diarized_transcript', 'scores', 'flags', 'discarded_flags'):
        if result.get(key) and isinstance(result[key], str):
            result[key] = json.loads(result[key])
    return result


async def list_calls(
    pool: asyncpg.Pool,
    *,
    advisor_id: str | None = None,
    team_id: str | None = None,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    """List calls with pagination and filtering."""
    conditions = []
    params = []
    idx = 1

    if advisor_id:
        conditions.append(f"c.advisor_id = ${idx}")
        params.append(uuid.UUID(advisor_id))
        idx += 1
    if team_id:
        conditions.append(f"a.team_id = ${idx}")
        params.append(uuid.UUID(team_id))
        idx += 1
    if status:
        conditions.append(f"c.status = ${idx}")
        params.append(status)
        idx += 1

    where = " AND ".join(conditions) if conditions else "TRUE"

    params.extend([limit, offset])
    rows = await pool.fetch(f"""
        SELECT
            c.id, c.status, c.duration_sec, c.language, c.created_at, c.completed_at,
            a.name as advisor_name,
            te.name as team_name,
            r.overall_score,
            (SELECT COUNT(*) FROM flag_reviews fr WHERE fr.call_id = c.id) as review_count
        FROM calls c
        LEFT JOIN advisors a ON a.id = c.advisor_id
        LEFT JOIN teams te ON te.id = a.team_id
        LEFT JOIN reports r ON r.call_id = c.id
        WHERE {where}
        ORDER BY c.created_at DESC
        LIMIT ${idx} OFFSET ${idx + 1}
    """, *params)
    return [dict(r) for r in rows]


# ── Transcript Queries ───────────────────────────────────────

async def save_transcript(
    pool: asyncpg.Pool,
    *,
    call_id: str,
    raw_transcript: dict | list,
    diarized_transcript: dict | list,
    engine: str,
) -> None:
    """Insert or update the transcript record for a call."""
    await pool.execute("""
        INSERT INTO transcripts (call_id, raw_transcript, diarized_transcript, engine)
        VALUES ($1, $2::jsonb, $3::jsonb, $4)
        ON CONFLICT (call_id) DO UPDATE SET
            raw_transcript = EXCLUDED.raw_transcript,
            diarized_transcript = EXCLUDED.diarized_transcript,
            engine = EXCLUDED.engine
    """, uuid.UUID(call_id),
        json.dumps(raw_transcript),
        json.dumps(diarized_transcript),
        engine)


# ── Report Queries ───────────────────────────────────────────

async def save_report(
    pool: asyncpg.Pool,
    *,
    call_id: str,
    scores: dict,
    overall_score: float,
    flags: list,
    discarded_flags: list,
) -> None:
    """Insert or update the report for a call."""
    await pool.execute("""
        INSERT INTO reports (call_id, scores, overall_score, flags, discarded_flags)
        VALUES ($1, $2::jsonb, $3, $4::jsonb, $5::jsonb)
        ON CONFLICT (call_id) DO UPDATE SET
            scores = EXCLUDED.scores,
            overall_score = EXCLUDED.overall_score,
            flags = EXCLUDED.flags,
            discarded_flags = EXCLUDED.discarded_flags
    """, uuid.UUID(call_id),
        json.dumps(scores),
        overall_score,
        json.dumps(flags),
        json.dumps(discarded_flags))


# ── Flag Review Queries ──────────────────────────────────────

async def create_flag_review(
    pool: asyncpg.Pool,
    *,
    call_id: str,
    flag_index: int,
    reviewer_id: str | None,
    decision: str,
    reason: str | None,
) -> dict:
    """Create a flag review (contest/accept/overturn)."""
    row = await pool.fetchrow("""
        INSERT INTO flag_reviews (call_id, flag_index, reviewer_id, decision, reason)
        VALUES ($1, $2, $3, $4, $5)
        RETURNING *
    """, uuid.UUID(call_id), flag_index,
        uuid.UUID(reviewer_id) if reviewer_id else None,
        decision, reason)
    return dict(row)


async def list_flag_reviews(pool: asyncpg.Pool, call_id: str) -> list[dict]:
    """Get all flag reviews for a call."""
    rows = await pool.fetch("""
        SELECT fr.*, a.name as reviewer_name
        FROM flag_reviews fr
        LEFT JOIN advisors a ON a.id = fr.reviewer_id
        WHERE fr.call_id = $1
        ORDER BY fr.reviewed_at
    """, uuid.UUID(call_id))
    return [dict(r) for r in rows]


async def update_flag_review(
    pool: asyncpg.Pool,
    review_id: str,
    decision: str,
) -> dict | None:
    """Update a flag review's decision (team leader resolving a contest)."""
    row = await pool.fetchrow("""
        UPDATE flag_reviews SET decision = $2
        WHERE id = $1
        RETURNING *
    """, uuid.UUID(review_id), decision)
    return dict(row) if row else None


# ── Analytics Queries ────────────────────────────────────────

async def get_org_overview(pool: asyncpg.Pool, org_id: str) -> dict:
    """Get org-wide stats."""
    stats = await pool.fetchrow("""
        SELECT
            COUNT(*) as total_calls,
            COUNT(*) FILTER (WHERE c.status = 'completed') as completed_calls,
            COUNT(*) FILTER (WHERE c.status = 'failed') as failed_calls,
            AVG(r.overall_score) as avg_score,
            COUNT(DISTINCT c.advisor_id) as active_advisors
        FROM calls c
        LEFT JOIN reports r ON r.call_id = c.id
        WHERE c.organization_id = $1
    """, uuid.UUID(org_id))

    top_flags = await pool.fetch("""
        SELECT flag->>'tag' as tag, COUNT(*) as count
        FROM reports r
        JOIN calls c ON c.id = r.call_id,
        jsonb_array_elements(r.flags) as flag
        WHERE c.organization_id = $1
        GROUP BY flag->>'tag'
        ORDER BY count DESC
        LIMIT 5
    """, uuid.UUID(org_id))

    return {
        **dict(stats),
        "top_flags": [dict(r) for r in top_flags],
    }


async def get_team_stats(pool: asyncpg.Pool, team_id: str) -> dict:
    """Get team-level stats with per-advisor breakdown."""
    advisors = await pool.fetch("""
        SELECT
            a.id, a.name, a.role,
            COUNT(c.id) as call_count,
            AVG(r.overall_score) as avg_score
        FROM advisors a
        LEFT JOIN calls c ON c.advisor_id = a.id
        LEFT JOIN reports r ON r.call_id = c.id
        WHERE a.team_id = $1
        GROUP BY a.id, a.name, a.role
        ORDER BY avg_score DESC NULLS LAST
    """, uuid.UUID(team_id))

    return {"advisors": [dict(r) for r in advisors]}


async def get_advisor_stats(pool: asyncpg.Pool, advisor_id: str) -> dict:
    """Get advisor-level stats with recent call history."""
    summary = await pool.fetchrow("""
        SELECT
            COUNT(c.id) as total_calls,
            AVG(r.overall_score) as avg_score,
            MIN(r.overall_score) as min_score,
            MAX(r.overall_score) as max_score
        FROM calls c
        LEFT JOIN reports r ON r.call_id = c.id
        WHERE c.advisor_id = $1 AND c.status = 'completed'
    """, uuid.UUID(advisor_id))

    recent = await pool.fetch("""
        SELECT c.id, c.duration_sec, c.created_at, r.overall_score
        FROM calls c
        LEFT JOIN reports r ON r.call_id = c.id
        WHERE c.advisor_id = $1 AND c.status = 'completed'
        ORDER BY c.created_at DESC
        LIMIT 20
    """, uuid.UUID(advisor_id))

    flag_freq = await pool.fetch("""
        SELECT flag->>'tag' as tag, COUNT(*) as count
        FROM reports r
        JOIN calls c ON c.id = r.call_id,
        jsonb_array_elements(r.flags) as flag
        WHERE c.advisor_id = $1
        GROUP BY flag->>'tag'
        ORDER BY count DESC
    """, uuid.UUID(advisor_id))

    return {
        **dict(summary),
        "recent_calls": [dict(r) for r in recent],
        "flag_frequency": [dict(r) for r in flag_freq],
    }
