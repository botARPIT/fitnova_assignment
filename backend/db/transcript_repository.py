"""Transcript repository — SQL for transcript persistence."""

import json
import uuid

import asyncpg


async def save_transcript(
    pool: asyncpg.Pool,
    *,
    call_id: str,
    raw_transcript: dict | list,
    diarized_transcript: dict | list,
    engine: str,
    metadata: dict | None = None,
    timings: dict | None = None,
) -> None:
    await pool.execute("""
        INSERT INTO transcripts (call_id, raw_transcript, diarized_transcript, engine, metadata, timings)
        VALUES ($1::uuid, $2::jsonb, $3::jsonb, $4, $5::jsonb, $6::jsonb)
        ON CONFLICT (call_id) DO UPDATE SET
            raw_transcript = EXCLUDED.raw_transcript,
            diarized_transcript = EXCLUDED.diarized_transcript,
            engine = EXCLUDED.engine,
            metadata = EXCLUDED.metadata,
            timings = EXCLUDED.timings
    """, call_id,
        json.dumps(raw_transcript),
        json.dumps(diarized_transcript),
        engine,
        json.dumps(metadata or {}),
        json.dumps(timings or {}))
