"""Analysis repository — SQL for report persistence."""

import json
import uuid

import asyncpg


async def save_report(
    pool: asyncpg.Pool,
    *,
    call_id: str,
    scores: dict,
    overall_score: float,
    flags: list,
    discarded_flags: list,
) -> None:
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
