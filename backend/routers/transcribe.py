"""POST /transcribe — Upload audio and get a diarized transcript."""

import json
import logging
import uuid

from fastapi import APIRouter, UploadFile, Query, HTTPException, Request

from schemas.transcript import TranscriptOut
from utils.audio import validate_extension
from guardrails.input_guards import validate_audio_input, validate_stt_output

log = logging.getLogger("fitnova.routes.transcribe")

router = APIRouter()


@router.post("/transcribe", response_model=TranscriptOut)
async def transcribe(
    request: Request,
    file: UploadFile,
    engine: str = Query("deepgram", enum=["deepgram", "whisperx"]),
):
    # ── Resolve dependencies from app.state ────────────────────
    settings = request.app.state.settings
    store = request.app.state.store
    stt = request.app.state.transcription_service

    # ── Validate extension ─────────────────────────────────────
    try:
        ext = validate_extension(file.filename)
    except ValueError as e:
        raise HTTPException(400, str(e))

    # ── Save upload ────────────────────────────────────────────
    call_id = str(uuid.uuid4())
    raw_bytes = await file.read()

    # ── GUARD: Validate audio input (size, magic bytes) ────────
    audio_check = validate_audio_input(file.filename, raw_bytes)
    if not audio_check.ok:
        raise HTTPException(422, audio_check.reason)
    upload_path = store.save_upload(call_id, ext, raw_bytes)

    # ── Route to engine ────────────────────────────────────────
    if engine == "whisperx":
        log.info("Using WhisperX engine")
        try:
            turns, duration = stt.transcribe_whisperx(str(upload_path))
        except Exception as e:
            log.error(f"WhisperX error: {e}", exc_info=True)
            raise HTTPException(502, f"WhisperX transcription failed: {e}")
    else:
        log.info("Using Deepgram engine")
        try:
            turns, duration, response = stt.transcribe_deepgram(raw_bytes)
        except Exception as e:
            log.error(f"Deepgram error: {e}")
            raise HTTPException(502, f"Transcription failed: {e}")

        # Log raw Deepgram response
        log.info("═" * 60)
        log.info("DEEPGRAM RAW RESPONSE:")
        log.info("═" * 60)
        try:
            raw_json = response.to_dict() if hasattr(response, "to_dict") else response.__dict__
            log.info(json.dumps(raw_json, indent=2, default=str))
        except Exception:
            log.info(str(response))
        log.info("═" * 60)

    # ── GUARD: Validate STT output ──────────────────────────────
    stt_check = validate_stt_output(
        turns=turns,
        duration=duration,
        min_duration_sec=settings.min_duration_sec,
    )
    if not stt_check.ok:
        raise HTTPException(422, stt_check.reason)

    transcript = TranscriptOut(
        call_id=call_id,
        duration_sec=round(duration, 2),
        turns=turns,
        engine=engine,
    )

    # ── Persist ────────────────────────────────────────────────
    store.save_transcript(transcript)
    store.save_transcript_txt(transcript)

    return transcript
