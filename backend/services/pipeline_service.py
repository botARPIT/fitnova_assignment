"""PipelineService — orchestrates the end-to-end call processing pipeline.

Routers should simply call:
    result = await pipeline.process_call(file=file, advisor_id=advisor_id)

Flow:
  Upload → Audio Validation → Ingestion → STT → Speaker Repair →
  Conversation Validation → Analysis → Evidence Validation →
  Persistence → Response
"""

import logging
import time
import uuid

from fastapi import UploadFile

from config import Settings
from errors import (
    AudioValidationError, IngestionError, TranscriptionError,
    SpeakerRepairError, ConversationValidationError, AnalysisError,
    PersistenceError,
)
from guardrails.input_guards import validate_audio_input, validate_stt_output, validate_analysis_input
from guardrails.prompts import PROMPT_VERSIONS
from pipeline.context import PipelineContext, PipelineMetadata, PipelineTimings
from pipeline.conversation_validator import validate_conversation
from pipeline.evidence_validator import validate_evidence
from services.ingestion import FileUploadAdapter
from services.transcription_service import TranscriptionService
from services.speaker_repair_service import repair_speakers
from services.tagging_service import analyze_call, build_transcript_text
from services import persistence_service
from utils.audio import validate_extension

log = logging.getLogger("fitnova.services.pipeline")


class PipelineService:
    """Orchestrates the full call processing pipeline."""

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
        """Run the full pipeline synchronously.

        Args:
            file: Uploaded audio file
            advisor_id: Optional advisor UUID
            organization_id: Optional org UUID (defaults to FitNova)

        Returns:
            Dict with call details, scores, flags, and metadata

        Raises:
            PipelineError subclasses on failure at any stage
        """
        ctx = PipelineContext(
            call_id=str(uuid.uuid4()),
            advisor_id=advisor_id,
            organization_id=organization_id or "00000000-0000-0000-0000-000000000001",
            settings=self.settings,
        )

        t_start = time.time()

        try:
            # ── Stage 1: Validate extension ─────────────────────
            try:
                ext = validate_extension(file.filename)
            except ValueError as e:
                raise AudioValidationError(str(e))

            # ── Stage 2: Read + validate audio ──────────────────
            raw_bytes = await file.read()
            audio_check = validate_audio_input(file.filename, raw_bytes)
            if not audio_check.ok:
                raise AudioValidationError(audio_check.reason)

            # ── Stage 3: Ingestion ──────────────────────────────
            try:
                meta = await self.ingestion.ingest(
                    filename=file.filename or f"{ctx.call_id}.wav",
                    raw_bytes=raw_bytes,
                    advisor_id=advisor_id,
                    organization_id=ctx.organization_id,
                )
                ctx.audio_path = meta.audio_path
                ctx.audio_bytes = meta.audio_bytes
                ctx.file_extension = meta.file_extension
            except Exception as e:
                raise IngestionError(str(e))

            # ── Stage 4: STT (Deepgram) ─────────────────────────
            t_stt = time.time()
            try:
                turns, duration, response = self.stt.transcribe_deepgram(raw_bytes)
                ctx.raw_transcript = turns
                ctx.duration_sec = duration
            except Exception as e:
                raise TranscriptionError(str(e))
            ctx.timings.stt_ms = int((time.time() - t_stt) * 1000)

            # ── Stage 5: STT output validation ──────────────────
            stt_check = validate_stt_output(
                turns=turns,
                duration=duration,
                min_duration_sec=self.settings.min_duration_sec,
            )
            if not stt_check.ok:
                raise AudioValidationError(stt_check.reason)

            # ── Stage 6: Speaker repair ─────────────────────────
            t_repair = time.time()
            try:
                repaired = repair_speakers(
                    raw_turns=turns,
                    google_api_key=self.settings.google_api_key,
                )
                ctx.repaired_transcript = repaired
            except Exception as e:
                raise SpeakerRepairError(str(e))
            ctx.timings.repair_ms = int((time.time() - t_repair) * 1000)

            # ── Stage 7: Conversation validation ────────────────
            conv_check = validate_conversation(repaired)
            if not conv_check.ok:
                raise ConversationValidationError(
                    "; ".join(conv_check.errors)
                )

            # ── Stage 8: Analysis input guard ───────────────────
            analysis_input_check = validate_analysis_input(repaired)
            if not analysis_input_check.ok:
                raise AnalysisError(analysis_input_check.reason)

            # ── Stage 9: LLM Analysis ───────────────────────────
            t_analysis = time.time()
            try:
                from schemas.transcript import TranscriptOut
                transcript_out = TranscriptOut(
                    call_id=ctx.call_id,
                    duration_sec=ctx.duration_sec,
                    turns=repaired,
                    engine="deepgram",
                )
                scores, overall, verified, discarded = analyze_call(
                    transcript=transcript_out,
                    rubric=self._rubric,
                    company_facts=self._company_facts,
                    google_api_key=self.settings.google_api_key,
                    quote_match_threshold=self.settings.quote_match_threshold,
                )
                ctx.scores = scores
                ctx.overall_score = overall
            except Exception as e:
                raise AnalysisError(str(e))
            ctx.timings.analysis_ms = int((time.time() - t_analysis) * 1000)

            # ── Stage 10: Evidence validation ───────────────────
            full_text = build_transcript_text(repaired)
            verified_flags, discarded_flags, ev_result = validate_evidence(
                flags=verified,  # already partially verified by analyze_call
                transcript_text=full_text,
                threshold=self.settings.quote_match_threshold,
            )
            ctx.verified_flags = verified_flags
            ctx.discarded_flags = discarded_flags

            # ── Stage 11: Set metadata ──────────────────────────
            ctx.metadata = PipelineMetadata(
                transcription_engine="deepgram",
                llm_model="gemini-2.5-flash",
                prompt_version=PROMPT_VERSIONS.get("call_analysis", "unknown"),
                rubric_version=getattr(self.settings, "rubric_version", "1.0"),
                company_facts_version=getattr(self.settings, "company_facts_version", "1.0"),
                analysis_version=getattr(self.settings, "analysis_version", "1.0"),
            )

            # ── Stage 12: Persistence ───────────────────────────
            ctx.timings.total_ms = int((time.time() - t_start) * 1000)
            try:
                from db.connection import get_pool
                pool = await get_pool()
                call_record = await persistence_service.persist_call(pool, ctx)
            except Exception as e:
                raise PersistenceError(str(e))

            # ── Build response ──────────────────────────────────
            return self._build_response(ctx, call_record)

        except (AudioValidationError, IngestionError, TranscriptionError,
                SpeakerRepairError, ConversationValidationError, AnalysisError,
                PersistenceError):
            raise

        except Exception as e:
            log.error(f"Unexpected pipeline error: {e}", exc_info=True)
            raise PersistenceError(f"Unexpected error: {e}") from e

    def _build_response(self, ctx: PipelineContext, call_record: dict) -> dict:
        return {
            "call_id": call_record["id"],
            "status": "completed",
            "duration_sec": round(ctx.duration_sec, 2),
            "scores": ctx.scores,
            "overall_score": ctx.overall_score,
            "flags": [f.model_dump() for f in ctx.verified_flags],
            "discarded_flags": [f.model_dump() for f in ctx.discarded_flags],
            "transcript": {
                "raw": [t.model_dump() for t in ctx.raw_transcript],
                "diarized": [t.model_dump() for t in ctx.repaired_transcript],
            },
            "metadata": {
                "engine": ctx.metadata.transcription_engine,
                "llm_model": ctx.metadata.llm_model,
                "prompt_version": ctx.metadata.prompt_version,
                "rubric_version": ctx.metadata.rubric_version,
                "company_facts_version": ctx.metadata.company_facts_version,
                "analysis_version": ctx.metadata.analysis_version,
            },
            "timings": {
                "stt_ms": ctx.timings.stt_ms,
                "repair_ms": ctx.timings.repair_ms,
                "analysis_ms": ctx.timings.analysis_ms,
                "total_ms": ctx.timings.total_ms,
            },
            "created_at": str(call_record.get("created_at", "")),
        }
