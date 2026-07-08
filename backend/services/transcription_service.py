"""Transcription engines: WhisperX (local GPU) and Deepgram (cloud API)."""

import asyncio
import json
import logging
import time

from deepgram import DeepgramClient

from schemas.transcript import Turn
from utils.deepgram_retry import is_deepgram_retryable
from utils.retry import retry_async

log = logging.getLogger("fitnova.transcription")


class TranscriptionService:
    """Manages STT engines with proper lifecycle management.

    Instantiated once in FastAPI lifespan, injected via app.state.
    WhisperX model is lazy-loaded on first whisperx request.
    """

    def __init__(self, settings):
        self._settings = settings
        self._whisperx_model = None
        self._torch = None

    def _get_torch(self):
        """Import torch only when WhisperX is actually used."""
        if self._torch is not None:
            return self._torch

        try:
            import torch
        except ImportError as exc:
            raise RuntimeError(
                "WhisperX transcription requested but torch is not installed. "
                "Use the Deepgram path for deployment or install WhisperX dependencies."
            ) from exc

        self._torch = torch
        return torch

    def _whisperx_device(self) -> str:
        torch = self._get_torch()
        return "cuda" if torch.cuda.is_available() else "cpu"

    def _empty_cuda_cache(self) -> None:
        torch = self._get_torch()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    # ── WhisperX (local) ───────────────────────────────────────

    def _load_whisperx_model(self):
        """Lazy-load the WhisperX model (first call only)."""
        if self._whisperx_model is not None:
            return self._whisperx_model

        import whisperx

        device = self._whisperx_device()
        log.info(
            f"Loading WhisperX model={self._settings.whisperx_model} "
            f"device={device} compute={self._settings.whisperx_compute_type}"
        )
        self._whisperx_model = whisperx.load_model(
            self._settings.whisperx_model,
            device,
            compute_type=self._settings.whisperx_compute_type,
        )
        log.info("WhisperX model loaded ✓")
        return self._whisperx_model

    def transcribe_whisperx(self, audio_path: str) -> tuple[list[Turn], float]:
        """Run WhisperX transcription + alignment + pyannote diarization."""
        import whisperx

        device = self._whisperx_device()
        model = self._load_whisperx_model()
        t0 = time.time()

        # 1. Transcribe
        audio = whisperx.load_audio(audio_path)
        result = model.transcribe(audio, batch_size=self._settings.whisperx_batch_size)
        lang = result.get("language", "en")
        log.info(
            f"WhisperX transcribe done in {time.time() - t0:.1f}s — "
            f"lang={lang}, segments={len(result['segments'])}"
        )
        # 2. Align word-level timestamps
        t1 = time.time()
        model_a, metadata = whisperx.load_align_model(language_code=lang, device=device)
        result = whisperx.align(
            result["segments"], model_a, metadata, audio, device,
            return_char_alignments=False,
        )
        log.info(f"WhisperX align done in {time.time() - t1:.1f}s")

        # Free alignment model memory
        del model_a
        self._empty_cuda_cache()

        # 3. Diarize with pyannote
        t2 = time.time()
        hf_token = self._settings.hf_token
        if not hf_token:
            log.warning("HF_TOKEN not set — skipping diarization, all speakers = SPEAKER_00")
            turns = [
                Turn(
                    speaker="SPEAKER_00",
                    start=round(seg["start"], 2),
                    end=round(seg["end"], 2),
                    text=seg["text"].strip(),
                )
                for seg in result["segments"]
            ]
            duration = turns[-1].end if turns else 0.0
            return turns, duration

        from whisperx.diarize import DiarizationPipeline
        diarize_model = DiarizationPipeline(token=hf_token, device=device)
        diarize_segments = diarize_model(audio)
        result = whisperx.assign_word_speakers(diarize_segments, result)
        log.info(f"WhisperX diarize done in {time.time() - t2:.1f}s")
        log.info(f"WhisperX total pipeline: {time.time() - t0:.1f}s")

        turns = [
            Turn(
                speaker=seg.get("speaker", "UNKNOWN"),
                start=round(seg["start"], 2),
                end=round(seg["end"], 2),
                text=seg["text"].strip(),
            )
            for seg in result["segments"]
        ]
        duration = turns[-1].end if turns else 0.0
        return turns, duration

    # ── Deepgram (cloud) ───────────────────────────────────────

    def _extract_detected_language(self, result) -> str | None:
        try:
            if result.channels and result.channels[0].alternatives:
                alt = result.channels[0].alternatives[0]
                detected = getattr(alt, "detected_language", None)
                if detected:
                    return detected
                detected_languages = getattr(alt, "detected_languages", None)
                if detected_languages:
                    return ", ".join(detected_languages)
        except Exception:
            return None
        return None

    def _log_deepgram_output(self, *, turns: list[Turn], duration: float, language: str | None) -> None:
        if not self._settings.log_sensitive_details:
            return

        log.info(
            "Deepgram STT output (model=%s, multilingual=%s, duration=%.2fs, language=%s):\n%s",
            self._settings.deepgram_model,
            bool(self._settings.deepgram_detect_language),
            duration,
            language or "unknown",
            json.dumps([turn.model_dump() for turn in turns], ensure_ascii=False, indent=2),
        )

    async def transcribe_deepgram(self, raw_bytes: bytes) -> tuple[list[Turn], float, object]:
        """Run Deepgram transcription with diarization.

        The Deepgram API call is wrapped in retry logic for transient failures.
        Transcript parsing is excluded from the retry boundary.
        """
        dg = DeepgramClient(api_key=self._settings.deepgram_api_key)

        max_retries = getattr(self._settings, "deepgram_max_retries", 3)
        base_delay = getattr(self._settings, "retry_base_delay_ms", 1000) / 1000.0

        async def _call_deepgram():
            return await asyncio.to_thread(
                dg.listen.v1.media.transcribe_file,
                request=raw_bytes,
                model=self._settings.deepgram_model,
                smart_format=True,
                diarize_model=self._settings.deepgram_diarize_model,
                utterances=True,
                detect_language=self._settings.deepgram_detect_language,
            )

        response = await retry_async(
            operation=_call_deepgram,
            is_retryable=is_deepgram_retryable,
            max_attempts=max_retries,
            base_delay=base_delay,
            vendor="deepgram",
            operation_name="transcription",
        )

        result = response.results

        # Duration from last word
        duration = 0.0
        if result.channels and result.channels[0].alternatives:
            words = result.channels[0].alternatives[0].words
            if words:
                duration = words[-1].end

        # Build turns from utterances
        turns: list[Turn] = []
        if result.utterances:
            for utt in result.utterances:
                turns.append(Turn(
                    speaker=f"speaker_{utt.speaker}",
                    start=utt.start,
                    end=utt.end,
                    text=utt.transcript,
                ))
        else:
            alt = result.channels[0].alternatives[0]
            turns.append(Turn(
                speaker="unknown",
                start=0.0,
                end=duration,
                text=alt.transcript,
            ))

        detected_language = self._extract_detected_language(result)
        self._log_deepgram_output(
            turns=turns,
            duration=duration,
            language=detected_language,
        )

        return turns, duration, response

    # ── Lifecycle ──────────────────────────────────────────────

    def cleanup(self):
        """Release GPU memory on shutdown."""
        if self._whisperx_model is not None:
            del self._whisperx_model
            self._whisperx_model = None
            if self._torch is not None:
                self._empty_cuda_cache()
            log.info("WhisperX model unloaded")
