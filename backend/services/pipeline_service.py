"""PipelineService — orchestrates the end-to-end call processing pipeline.

Routers should simply call:
    result = await pipeline.process_call(file=file, advisor_id=advisor_id)

Idempotency flow:
  Validate Audio → Ingest + Compute Fingerprint → Create or Fetch Call →
  [Completed → reuse] | [Processing → 409] | [Failed → retry] |
  [New/Uploaded/Cancelled → STT → Repair → Analysis → Persist → Complete]
"""

import logging
import time

from fastapi import UploadFile

from config import Settings
from config import settings as app_settings
from db.connection import get_pool
from errors import (
    AudioValidationError, IngestionError, TranscriptionError,
    SpeakerRepairError, ConversationValidationError, AnalysisError,
    PersistenceError, CallConflictError,
)
from guardrails.input_guards import validate_audio_input, validate_stt_output, validate_analysis_input
from guardrails.prompts import PROMPT_VERSIONS
from pipeline.context import PipelineContext, PipelineMetadata
from pipeline.conversation_validator import validate_conversation
from pipeline.evidence_validator import validate_evidence
from schemas.transcript import TranscriptOut
from services.ingestion import FileUploadAdapter
from services.transcription_service import TranscriptionService
from services.speaker_repair_service import repair_speakers
from services.tagging_service import analyze_call
from services import persistence_service
from utils.audio import validate_extension

log = logging.getLogger("fitnova.services.pipeline")

REUSE_STATUSES = frozenset({"completed"})
CONFLICT_STATUSES = frozenset({"processing"})
RETRY_STATUSES = frozenset({"failed", "cancelled"})

# Pipeline stages for failure tracking
FAILED_STAGE_TRANSCRIPTION = "TRANSCRIPTION"
FAILED_STAGE_ANALYSIS = "ANALYSIS"
FAILED_STAGE_SPEAKER_REPAIR = "SPEAKER_REPAIR"
FAILED_STAGE_VALIDATION = "VALIDATION"


class PipelineService:
    """Orchestrates the full call processing pipeline with idempotency."""

    def __init__(self, settings: Settings, rubric: dict | None = None, company_facts: dict | None = None):
        self.settings = settings
        self._rubric = rubric or {}
        self._company_facts = company_facts or {}
        self.ingestion = FileUploadAdapter(settings.upload_dir)
        self.stt = TranscriptionService(settings)

    async def process_call(
        self,
        file: UploadFile,
        advisor_id: str | None = None,
        organization_id: str | None = None,
    ) -> dict:
        """Run the full pipeline synchronously with idempotency.

        Args:
            file: Uploaded audio file
            advisor_id: Optional advisor UUID
            organization_id: Optional org UUID

        Returns:
            Dict with call details, scores, flags, and metadata

        Raises:
            CallConflictError: if call is currently being processed (HTTP 409)
            PipelineError subclasses on failure at any stage
        """
        ctx = self._build_context(advisor_id, organization_id)
        started_at = time.time()

        try:
            pool = await get_pool()
            self._validate_extension(file.filename)
            raw_bytes = await self._read_and_validate_audio(file)
            await self._ingest_upload(ctx, raw_bytes, file.filename)

            reuse_response = await self._initialize_or_reuse_call(pool, ctx)
            if reuse_response:
                return reuse_response

            await self._run_transcription(pool, ctx, raw_bytes)
            await self._validate_transcription_output(pool, ctx)
            await self._run_speaker_repair(pool, ctx)
            await self._validate_repaired_conversation(pool, ctx)
            await self._validate_analysis_input(pool, ctx)
            await self._run_analysis(pool, ctx)
            self._finalize_flags(ctx)
            self._set_metadata(ctx)

            ctx.timings.total_ms = int((time.time() - started_at) * 1000)
            call_record = await self._persist_results(pool, ctx)
            return self._build_response(call_record, idempotent_reuse=False)

        except CallConflictError:
            raise

        except (AudioValidationError, IngestionError, TranscriptionError,
                SpeakerRepairError, ConversationValidationError, AnalysisError,
                PersistenceError):
            raise

        except Exception as e:
            if app_settings.log_tracebacks:
                log.error("Unexpected pipeline error: %s", str(e) or type(e).__name__, exc_info=True)
            else:
                log.error("Unexpected pipeline error: %s", type(e).__name__)
            raise PersistenceError("Unexpected pipeline failure.") from e

    def _build_context(
        self,
        advisor_id: str | None,
        organization_id: str | None,
    ) -> PipelineContext:
        return PipelineContext(
            advisor_id=advisor_id,
            organization_id=organization_id or self.settings.default_org_id,
            settings=self.settings,
        )

    def _validate_extension(self, filename: str | None) -> None:
        try:
            validate_extension(filename)
        except ValueError as e:
            raise AudioValidationError(str(e)) from e

    async def _read_and_validate_audio(self, file: UploadFile) -> bytes:
        raw_bytes = await file.read()
        audio_check = validate_audio_input(file.filename, raw_bytes)
        if not audio_check.ok:
            raise AudioValidationError(audio_check.reason)
        return raw_bytes

    async def _ingest_upload(
        self,
        ctx: PipelineContext,
        raw_bytes: bytes,
        filename: str | None,
    ) -> None:
        try:
            meta = await self.ingestion.ingest(
                filename=filename or "audio.wav",
                raw_bytes=raw_bytes,
                advisor_id=ctx.advisor_id,
                organization_id=ctx.organization_id,
            )
        except Exception as e:
            raise IngestionError(str(e)) from e

        ctx.audio_path = meta.audio_path
        ctx.audio_bytes = meta.audio_bytes
        ctx.file_extension = meta.file_extension
        ctx.file_sha256 = meta.file_sha256
        ctx.ingestion_fingerprint = meta.ingestion_fingerprint
        ctx.source = meta.source
        ctx.external_call_id = meta.external_call_id

    async def _initialize_or_reuse_call(self, pool, ctx: PipelineContext) -> dict | None:
        call_result = await persistence_service.create_call(pool, ctx)
        existing_status = call_result["status"]
        is_new = call_result["is_new"]

        if existing_status in REUSE_STATUSES and not is_new:
            return await self._reuse_completed(pool, ctx)

        if existing_status in CONFLICT_STATUSES and not is_new:
            raise CallConflictError(
                call_id=ctx.call_id,
                detail=f"Call {ctx.call_id} is currently processing",
            )

        if existing_status in RETRY_STATUSES or existing_status == "uploaded" or is_new:
            await self._mark_processing(pool, ctx.call_id)

        return None

    async def _mark_processing(self, pool, call_id: str) -> None:
        from db.call_repository import update_status
        async with pool.acquire() as conn:
            await update_status(conn, call_id=call_id, status="processing")

    async def _run_transcription(self, pool, ctx: PipelineContext, raw_bytes: bytes) -> None:
        started_at = time.time()
        try:
            turns, duration, _response = await self.stt.transcribe_deepgram(raw_bytes)
        except Exception as e:
            await persistence_service.mark_failed(
                pool,
                ctx,
                str(e),
                failed_stage=FAILED_STAGE_TRANSCRIPTION,
            )
            raise TranscriptionError(str(e)) from e

        ctx.raw_transcript = turns
        ctx.duration_sec = duration
        ctx.timings.stt_ms = int((time.time() - started_at) * 1000)

    async def _validate_transcription_output(self, pool, ctx: PipelineContext) -> None:
        stt_check = validate_stt_output(
            turns=ctx.raw_transcript,
            duration=ctx.duration_sec,
            min_duration_sec=self.settings.min_duration_sec,
        )
        if stt_check.ok:
            return

        await persistence_service.mark_failed(
            pool,
            ctx,
            stt_check.reason,
            failed_stage=FAILED_STAGE_VALIDATION,
        )
        raise AudioValidationError(stt_check.reason)

    async def _run_speaker_repair(self, pool, ctx: PipelineContext) -> None:
        started_at = time.time()
        try:
            ctx.repaired_transcript = repair_speakers(
                raw_turns=ctx.raw_transcript,
                google_api_key=self.settings.google_api_key,
                model_name=self.settings.speaker_repair_model,
            )
        except Exception as e:
            await persistence_service.mark_failed(
                pool,
                ctx,
                str(e),
                failed_stage=FAILED_STAGE_SPEAKER_REPAIR,
            )
            raise SpeakerRepairError(str(e)) from e

        ctx.timings.repair_ms = int((time.time() - started_at) * 1000)

    async def _validate_repaired_conversation(self, pool, ctx: PipelineContext) -> None:
        conv_check = validate_conversation(ctx.repaired_transcript)
        if conv_check.ok:
            return

        reason = "; ".join(conv_check.errors)
        await persistence_service.mark_failed(
            pool,
            ctx,
            reason,
            failed_stage=FAILED_STAGE_VALIDATION,
        )
        raise ConversationValidationError(reason)

    async def _validate_analysis_input(self, pool, ctx: PipelineContext) -> None:
        analysis_input_check = validate_analysis_input(ctx.repaired_transcript)
        if analysis_input_check.ok:
            return

        await persistence_service.mark_failed(
            pool,
            ctx,
            analysis_input_check.reason,
            failed_stage=FAILED_STAGE_VALIDATION,
        )
        raise AnalysisError(analysis_input_check.reason)

    async def _run_analysis(self, pool, ctx: PipelineContext) -> None:
        started_at = time.time()
        transcript_out = TranscriptOut(
            call_id=ctx.call_id,
            duration_sec=ctx.duration_sec,
            turns=ctx.repaired_transcript,
            engine="deepgram",
        )

        try:
            scores, overall, verified, discarded = await analyze_call(
                transcript=transcript_out,
                rubric=self._rubric,
                company_facts=self._company_facts,
                google_api_key=self.settings.google_api_key,
                model_name=self.settings.analysis_model,
                quote_match_threshold=self.settings.quote_match_threshold,
                gemini_max_retries=self.settings.gemini_max_retries,
                retry_base_delay_ms=self.settings.retry_base_delay_ms,
            )
        except Exception as e:
            await persistence_service.mark_failed(
                pool,
                ctx,
                str(e),
                failed_stage=FAILED_STAGE_ANALYSIS,
            )
            raise AnalysisError(str(e)) from e

        ctx.scores = scores
        ctx.overall_score = overall
        ctx.verified_flags = verified
        ctx.discarded_flags = discarded
        ctx.timings.analysis_ms = int((time.time() - started_at) * 1000)

    def _finalize_flags(self, ctx: PipelineContext) -> None:
        verified_flags, discarded_flags, _ev_result = validate_evidence(
            flags=ctx.verified_flags,
            turns=ctx.repaired_transcript,
            company_facts=self._company_facts,
            threshold=self.settings.quote_match_threshold,
        )
        ctx.verified_flags = verified_flags
        ctx.discarded_flags = discarded_flags

    def _set_metadata(self, ctx: PipelineContext) -> None:
        ctx.metadata = PipelineMetadata(
            transcription_engine="deepgram",
            llm_model=self.settings.analysis_model,
            prompt_version=PROMPT_VERSIONS.get("call_analysis", "unknown"),
            rubric_version=getattr(self.settings, "rubric_version", "1.0"),
            company_facts_version=getattr(self.settings, "company_facts_version", "1.0"),
            analysis_version=getattr(self.settings, "analysis_version", "1.0"),
        )

    async def _persist_results(self, pool, ctx: PipelineContext) -> dict:
        try:
            return await persistence_service.persist_results(pool, ctx)
        except Exception as e:
            await persistence_service.mark_failed(
                pool,
                ctx,
                str(e),
                failed_stage=FAILED_STAGE_VALIDATION,
            )
            raise PersistenceError(str(e)) from e

    async def _reuse_completed(self, pool, ctx: PipelineContext) -> dict:
        """Reuse a completed call result — no STT/LLM re-execution."""
        from db.call_repository import get_call
        async with pool.acquire() as conn:
            call_record = await get_call(conn, ctx.call_id)
        if not call_record:
            raise PersistenceError(f"Completed call {ctx.call_id} not found on reuse")

        log.info(f"Reusing completed call {ctx.call_id} — no STT/LLM executed")

        return {
            "call_id": call_record["id"],
            "status": "completed",
            "idempotent_reuse": True,
            "reused": True,
            "duration_sec": round(call_record.get("duration_sec") or 0, 2),
            "scores": call_record.get("scores") or {},
            "overall_score": call_record.get("overall_score") or 0,
            "flags": call_record.get("flags") or [],
            "discarded_flags": call_record.get("discarded_flags") or [],
            "transcript": {
                "raw": call_record.get("raw_transcript") or [],
                "diarized": call_record.get("diarized_transcript") or [],
            },
            "metadata": {
                "engine": call_record.get("engine") or call_record.get("transcript_metadata", {}).get("transcription_engine", "deepgram"),
                "llm_model": call_record.get("transcript_metadata", {}).get("llm_model", self.settings.analysis_model),
                "prompt_version": call_record.get("transcript_metadata", {}).get("prompt_version", PROMPT_VERSIONS.get("call_analysis", "unknown")),
                "rubric_version": call_record.get("transcript_metadata", {}).get("rubric_version", getattr(self.settings, "rubric_version", "1.0")),
                "company_facts_version": call_record.get("transcript_metadata", {}).get("company_facts_version", getattr(self.settings, "company_facts_version", "1.0")),
                "analysis_version": call_record.get("transcript_metadata", {}).get("analysis_version", getattr(self.settings, "analysis_version", "1.0")),
            },
            "timings": call_record.get("timings") or {},
            "created_at": str(call_record.get("created_at", "")),
        }

    def _build_response(self, call_record: dict, *, idempotent_reuse: bool = False) -> dict:
        return {
            "call_id": call_record["id"],
            "status": "completed",
            "idempotent_reuse": idempotent_reuse,
            "reused": idempotent_reuse,
            "duration_sec": round(call_record.get("duration_sec") or 0, 2),
            "scores": call_record.get("scores") or {},
            "overall_score": call_record.get("overall_score") or 0,
            "flags": call_record.get("flags") or [],
            "discarded_flags": call_record.get("discarded_flags") or [],
            "transcript": {
                "raw": call_record.get("raw_transcript") or [],
                "diarized": call_record.get("diarized_transcript") or [],
            },
            "metadata": {
                "engine": call_record.get("engine") or call_record.get("transcript_metadata", {}).get("transcription_engine", "deepgram"),
                "llm_model": call_record.get("transcript_metadata", {}).get("llm_model", self.settings.analysis_model),
                "prompt_version": call_record.get("transcript_metadata", {}).get("prompt_version", PROMPT_VERSIONS.get("call_analysis", "unknown")),
                "rubric_version": call_record.get("transcript_metadata", {}).get("rubric_version", getattr(self.settings, "rubric_version", "1.0")),
                "company_facts_version": call_record.get("transcript_metadata", {}).get("company_facts_version", getattr(self.settings, "company_facts_version", "1.0")),
                "analysis_version": call_record.get("transcript_metadata", {}).get("analysis_version", getattr(self.settings, "analysis_version", "1.0")),
            },
            "timings": call_record.get("timings") or {},
            "created_at": str(call_record.get("created_at", "")),
        }
