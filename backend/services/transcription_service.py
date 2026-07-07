"""Transcription engines: WhisperX (local GPU) and Deepgram (cloud API)."""

import logging
import time

import torch
from deepgram import DeepgramClient

from schemas.transcript import Turn

log = logging.getLogger("fitnova.transcription")


class TranscriptionService:
    """Manages STT engines with proper lifecycle management.

    Instantiated once in FastAPI lifespan, injected via app.state.
    WhisperX model is lazy-loaded on first whisperx request.
    """

    def __init__(self, settings):
        self._settings = settings
        self._whisperx_model = None

    # ── WhisperX (local) ───────────────────────────────────────

    def _load_whisperx_model(self):
        """Lazy-load the WhisperX model (first call only)."""
        if self._whisperx_model is not None:
            return self._whisperx_model

        import whisperx

        device = "cuda" if torch.cuda.is_available() else "cpu"
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

        device = "cuda" if torch.cuda.is_available() else "cpu"
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
        torch.cuda.empty_cache()

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

        diarize_model = whisperx.DiarizationPipeline(use_auth_token=hf_token, device=device)
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

    def transcribe_deepgram(self, raw_bytes: bytes) -> tuple[list[Turn], float, object]:
        """Run Deepgram Nova-2-phonecall transcription with diarization."""
        dg = DeepgramClient(api_key=self._settings.deepgram_api_key)

        response = dg.listen.v1.media.transcribe_file(
            request=raw_bytes,
            model="nova-2-phonecall",
            smart_format=True,
            diarize_model="latest",
            utterances=True,
            language="en",
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

        return turns, duration, response

    # ── Lifecycle ──────────────────────────────────────────────

    def cleanup(self):
        """Release GPU memory on shutdown."""
        if self._whisperx_model is not None:
            del self._whisperx_model
            self._whisperx_model = None
            torch.cuda.empty_cache()
            log.info("WhisperX model unloaded")
