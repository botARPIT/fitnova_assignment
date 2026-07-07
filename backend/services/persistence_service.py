"""PersistenceService — owns every database write.

Routers never call repositories directly. All persistence goes
through this service, wrapped in a single database transaction.
"""

import json
import logging

import asyncpg

from db import call_repository, transcript_repository, analysis_repository
from errors import PersistenceError
from pipeline.context import PipelineContext

log = logging.getLogger("fitnova.services.persistence")


def _build_metadata_dict(ctx: PipelineContext) -> dict:
    return {
        "transcription_engine": ctx.metadata.transcription_engine,
        "llm_model": ctx.metadata.llm_model,
        "prompt_version": ctx.metadata.prompt_version,
        "rubric_version": ctx.metadata.rubric_version,
        "company_facts_version": ctx.metadata.company_facts_version,
        "analysis_version": ctx.metadata.analysis_version,
    }


def _build_timings_dict(ctx: PipelineContext) -> dict:
    return {
        "stt_ms": ctx.timings.stt_ms,
        "repair_ms": ctx.timings.repair_ms,
        "analysis_ms": ctx.timings.analysis_ms,
        "total_ms": ctx.timings.total_ms,
    }


async def persist_call(pool: asyncpg.Pool, ctx: PipelineContext) -> dict:
    """Persist the full pipeline result in a single transaction.

    Args:
        pool: Database connection pool
        ctx: PipelineContext with all pipeline outputs

    Returns:
        The created/updated call record as a dict

    Raises:
        PersistenceError: if any DB operation fails
    """
    async with pool.acquire() as conn:
        async with conn.transaction():
            try:
                # 1. Create call record
                call = await call_repository.create_call(
                    conn,
                    organization_id=ctx.organization_id or "00000000-0000-0000-0000-000000000001",
                    advisor_id=ctx.advisor_id,
                    audio_path=ctx.audio_path,
                )

                # 2. Save raw transcript
                raw_data = [t.model_dump() for t in ctx.raw_transcript]
                diarized_data = [t.model_dump() for t in ctx.repaired_transcript]

                await transcript_repository.save_transcript(
                    conn,
                    call_id=call["id"],
                    raw_transcript=raw_data,
                    diarized_transcript=diarized_data,
                    engine=ctx.metadata.transcription_engine,
                    metadata=_build_metadata_dict(ctx),
                    timings=_build_timings_dict(ctx),
                )

                # 3. Save report (scores + verified flags + discarded)
                flags_data = [f.model_dump() for f in ctx.verified_flags]
                discarded_data = [f.model_dump() for f in ctx.discarded_flags]

                await analysis_repository.save_report(
                    conn,
                    call_id=call["id"],
                    scores=ctx.scores,
                    overall_score=ctx.overall_score,
                    flags=flags_data,
                    discarded_flags=discarded_data,
                )

                # 4. Update call status to completed
                await call_repository.update_call_status(
                    conn,
                    call_id=call["id"],
                    status="completed",
                    duration_sec=ctx.duration_sec,
                    language=ctx.language,
                )

                log.info(
                    f"Call {call['id']} persisted: "
                    f"{len(ctx.raw_transcript)} raw turns, "
                    f"{len(ctx.repaired_transcript)} repaired turns, "
                    f"{len(ctx.verified_flags)} flags, "
                    f"{len(ctx.discarded_flags)} discarded ✓"
                )

                return call

            except Exception as e:
                log.error(f"Persistence failed for call {ctx.call_id}: {e}", exc_info=True)
                raise PersistenceError(str(e)) from e
