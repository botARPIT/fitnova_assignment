"""Call repository — SQL for idempotent call CRUD.

All methods accept an asyncpg.Connection so callers can participate
in transactions managed by PersistenceService.
"""

import json
import uuid
from datetime import datetime, timezone

import asyncpg


async def create_if_absent(
    conn: asyncpg.Connection,
    *,
    organization_id: str,
    ingestion_fingerprint: str,
    source: str = "FILE_UPLOAD",
    external_call_id: str | None = None,
    advisor_id: str | None = None,
    audio_path: str | None = None,
) -> dict:
    """Atomically insert a call row if it doesn't exist, or return existing.

    Uses INSERT … ON CONFLICT DO NOTHING RETURNING to avoid race conditions.
    Never performs a separate SELECT-then-INSERT.

    Returns:
        Dict with keys: id, status, is_new
    """
    row = await conn.fetchrow("""
        INSERT INTO calls (
            organization_id,
            advisor_id,
            audio_path,
            source,
            external_call_id,
            ingestion_fingerprint,
            status
        )
        VALUES ($1, $2, $3, $4, $5, $6, 'uploaded')
        ON CONFLICT (ingestion_fingerprint) WHERE ingestion_fingerprint IS NOT NULL
        DO NOTHING
        RETURNING id, status
    """,
        uuid.UUID(organization_id),
        uuid.UUID(advisor_id) if advisor_id else None,
        audio_path,
        source,
        external_call_id,
        ingestion_fingerprint,
    )

    if row:
        return {"id": str(row["id"]), "status": row["status"], "is_new": True}

    # Race lost — another request inserted the row first
    existing = await conn.fetchrow("""
        SELECT id, status FROM calls
        WHERE ingestion_fingerprint = $1
    """,
        ingestion_fingerprint,
    )
    if not existing:
        raise RuntimeError(
            f"Idempotency invariant violated: no row for "
            f"(org={organization_id}, fingerprint={ingestion_fingerprint}) after INSERT attempt"
        )

    return {"id": str(existing["id"]), "status": existing["status"], "is_new": False}


async def get_by_ingestion_fingerprint(
    conn: asyncpg.Connection,
    ingestion_fingerprint: str,
) -> dict | None:
    """Look up a call by its ingestion fingerprint.

    Returns full call record or None.
    """
    row = await conn.fetchrow("""
        SELECT * FROM calls
        WHERE ingestion_fingerprint = $1
    """,
        ingestion_fingerprint,
    )
    return dict(row) if row else None


async def update_status(
    conn: asyncpg.Connection,
    call_id: str,
    status: str,
    *,
    duration_sec: float | None = None,
    language: str | None = None,
    error_message: str | None = None,
    failed_stage: str | None = None,
) -> None:
    """Update a call's status and optional fields."""
    completed_at = datetime.now(timezone.utc) if status in ("completed", "failed") else None
    await conn.execute("""
        UPDATE calls SET
            status = $2,
            duration_sec = COALESCE($3, duration_sec),
            language = COALESCE($4, language),
            error_message = $5,
            failed_stage = COALESCE($7, failed_stage),
            completed_at = COALESCE($6, completed_at)
        WHERE id = $1
    """, uuid.UUID(call_id), status, duration_sec, language, error_message, completed_at, failed_stage)


async def get_call(
    conn: asyncpg.Connection,
    call_id: str,
) -> dict | None:
    """Get a single call with its transcript and report (full result for reuse)."""
    row = await conn.fetchrow("""
        SELECT
            c.*,
            t.raw_transcript,
            t.diarized_transcript,
            t.engine,
            t.metadata AS transcript_metadata,
            t.timings,
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
    """, uuid.UUID(call_id))
    if not row:
        return None
    result = dict(row)
    for key in ('raw_transcript', 'diarized_transcript', 'scores', 'flags', 'discarded_flags', 'transcript_metadata', 'timings'):
        if result.get(key) and isinstance(result[key], str):
            result[key] = json.loads(result[key])
    return result


async def get_call_status(
    conn: asyncpg.Connection,
    call_id: str,
) -> dict | None:
    """Get lightweight status metadata for polling upload/job progress."""
    row = await conn.fetchrow("""
        SELECT
            c.id,
            c.status,
            c.failed_stage,
            c.error_message,
            c.created_at,
            c.completed_at,
            c.advisor_id,
            c.organization_id
        FROM calls c
        WHERE c.id = $1
    """, uuid.UUID(call_id))
    return dict(row) if row else None


async def list_calls(
    conn: asyncpg.Connection,
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
    rows = await conn.fetch(f"""
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
