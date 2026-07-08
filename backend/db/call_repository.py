"""Call repository — SQL for call CRUD operations."""

import json
import uuid
from datetime import datetime, timezone

import asyncpg


async def create_call(
    pool: asyncpg.Pool,
    *,
    organization_id: str,
    advisor_id: str | None,
    audio_path: str,
) -> dict:
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
    completed_at = datetime.now(timezone.utc) if status in ("completed", "failed") else None
    await pool.execute("""
        UPDATE calls SET
            status = $2,
            duration_sec = COALESCE($3, duration_sec),
            language = COALESCE($4, language),
            error_message = $5,
            completed_at = COALESCE($6, completed_at)
        WHERE id = $1
    """, call_id, status, duration_sec, language, error_message, completed_at)


async def get_call(pool: asyncpg.Pool, call_id: str) -> dict | None:
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
            te.name as team_name,
            (SELECT COUNT(*) FROM flag_reviews fr WHERE fr.call_id = c.id) as review_count
        FROM calls c
        LEFT JOIN transcripts t ON t.call_id = c.id
        LEFT JOIN reports r ON r.call_id = c.id
        LEFT JOIN advisors a ON a.id = c.advisor_id
        LEFT JOIN teams te ON te.id = a.team_id
        WHERE c.id = $1
    """, call_id)
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
