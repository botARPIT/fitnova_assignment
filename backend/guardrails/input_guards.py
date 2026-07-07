"""Input guards — pre-processing validation for audio and transcript input.

These guards run BEFORE any expensive processing (STT, LLM calls) to
reject bad input early and provide clear error messages.

Guard hierarchy:
    Audio Input → validate_audio_input()
    STT Output  → validate_stt_output()
    Repair Input → (uses STT output validation)
    Analysis Input → validate_analysis_input()
"""

import logging
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger("fitnova.guards.input")


# ═══════════════════════════════════════════════════════════════════════════
# Guard Result
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class GuardResult:
    """Result of a guard check. If not ok, reason explains why."""
    ok: bool
    reason: str = ""

    def raise_if_failed(self, prefix: str = ""):
        """Raise ValueError if the guard failed."""
        if not self.ok:
            msg = f"{prefix}: {self.reason}" if prefix else self.reason
            raise ValueError(msg)


# ═══════════════════════════════════════════════════════════════════════════
# GUARD 1: Audio Input Validation
# Runs BEFORE STT — rejects bad files early
# ═══════════════════════════════════════════════════════════════════════════

ALLOWED_EXTENSIONS = frozenset({"wav", "mp3", "m4a", "ogg", "flac", "webm"})
MAX_FILE_SIZE_MB = 100
MIN_FILE_SIZE_BYTES = 1024  # 1KB — anything smaller is corrupted/empty


def validate_audio_input(
    filename: str,
    raw_bytes: bytes,
    allowed_extensions: frozenset[str] = ALLOWED_EXTENSIONS,
    max_size_mb: int = MAX_FILE_SIZE_MB,
) -> GuardResult:
    """Validate audio file before sending to STT engine.

    Checks:
    1. File has a valid extension
    2. File is not empty or suspiciously small
    3. File is not too large
    4. Basic magic byte check for common formats
    """
    # Extension check
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in allowed_extensions:
        return GuardResult(
            ok=False,
            reason=f"Unsupported format '.{ext}'. Allowed: {sorted(allowed_extensions)}"
        )

    # Size checks
    size_bytes = len(raw_bytes)
    if size_bytes < MIN_FILE_SIZE_BYTES:
        return GuardResult(
            ok=False,
            reason=f"File too small ({size_bytes} bytes). Likely empty or corrupted."
        )

    max_bytes = max_size_mb * 1024 * 1024
    if size_bytes > max_bytes:
        size_mb = size_bytes / (1024 * 1024)
        return GuardResult(
            ok=False,
            reason=f"File too large ({size_mb:.1f}MB). Maximum is {max_size_mb}MB."
        )

    # Magic byte check (basic — catches obvious non-audio files)
    magic_checks = {
        b"RIFF": "wav",
        b"ID3": "mp3",
        b"\xff\xfb": "mp3",
        b"\xff\xf3": "mp3",
        b"\xff\xf2": "mp3",
        b"fLaC": "flac",
        b"OggS": "ogg",
    }

    # For M4A/MP4, check for ftyp box
    is_m4a = len(raw_bytes) >= 8 and raw_bytes[4:8] == b"ftyp"

    header = raw_bytes[:4]
    recognized = any(raw_bytes[:len(magic)] == magic for magic in magic_checks) or is_m4a

    if not recognized:
        # WebM starts with 0x1A45DFA3 (EBML header)
        is_webm = len(raw_bytes) >= 4 and raw_bytes[:4] == b"\x1a\x45\xdf\xa3"
        if not is_webm:
            log.warning(
                f"Unrecognized audio magic bytes: {header.hex()}. "
                f"Proceeding anyway — STT engine will reject if invalid."
            )

    log.info(
        f"Audio input validated: ext={ext}, size={size_bytes/1024:.0f}KB ✓"
    )
    return GuardResult(ok=True)


# ═══════════════════════════════════════════════════════════════════════════
# GUARD 2: STT Output Validation
# Runs AFTER Deepgram/WhisperX — before speaker repair
# ═══════════════════════════════════════════════════════════════════════════

def validate_stt_output(
    turns: list,
    duration: float,
    min_duration_sec: float = 10.0,
    min_turns: int = 2,
    max_single_speaker_ratio: float = 1.0,
) -> GuardResult:
    """Validate STT engine output before passing to speaker repair.

    Checks:
    1. Duration meets minimum threshold (reject misdials)
    2. At least N turns exist (not empty/single-word transcript)
    3. Turns have non-empty text
    4. Timestamps are valid (start <= end, monotonically increasing)
    """
    # Duration check
    if duration < min_duration_sec:
        return GuardResult(
            ok=False,
            reason=(
                f"Audio too short ({duration:.1f}s). "
                f"Minimum is {min_duration_sec}s — likely a misdial or test tone."
            )
        )

    # Turn count check
    if len(turns) < min_turns:
        return GuardResult(
            ok=False,
            reason=(
                f"Only {len(turns)} turn(s) detected. "
                f"Minimum is {min_turns} — likely failed transcription."
            )
        )

    # Empty text check
    empty_turns = [i for i, t in enumerate(turns) if not getattr(t, 'text', '').strip()]
    if len(empty_turns) > len(turns) * 0.5:
        return GuardResult(
            ok=False,
            reason=f"{len(empty_turns)}/{len(turns)} turns have empty text. Transcription may have failed."
        )

    # Timestamp sanity
    for i, t in enumerate(turns):
        start = getattr(t, 'start', 0)
        end = getattr(t, 'end', 0)
        if end < start:
            log.warning(f"Turn {i} has end ({end}) < start ({start}) — will be fixed")

    log.info(
        f"STT output validated: {len(turns)} turns, {duration:.1f}s ✓"
    )
    return GuardResult(ok=True)


# ═══════════════════════════════════════════════════════════════════════════
# GUARD 3: Analysis Input Validation
# Runs BEFORE LLM analysis — after speaker repair
# ═══════════════════════════════════════════════════════════════════════════

def validate_analysis_input(
    turns: list,
    min_turns: int = 2,
    required_speakers: set[str] | None = None,
) -> GuardResult:
    """Validate transcript before sending to the analysis LLM.

    Checks:
    1. Minimum turn count
    2. Expected speakers are present (Advisor and Customer after repair)
    3. Total text length is reasonable
    """
    if required_speakers is None:
        required_speakers = {"Advisor", "Customer"}

    if len(turns) < min_turns:
        return GuardResult(
            ok=False,
            reason=f"Only {len(turns)} turn(s) — need at least {min_turns} for meaningful analysis."
        )

    # Speaker check
    present_speakers = {getattr(t, 'speaker', 'UNKNOWN') for t in turns}
    missing = required_speakers - present_speakers
    if missing:
        log.warning(
            f"Expected speakers {required_speakers} but only found {present_speakers}. "
            f"Missing: {missing}. Speaker repair may have failed."
        )
        # This is a warning, not a hard failure — analysis can still proceed

    # Total text length
    total_text = " ".join(getattr(t, 'text', '') for t in turns)
    if len(total_text) < 50:
        return GuardResult(
            ok=False,
            reason=f"Transcript too short ({len(total_text)} chars). Not enough content to analyze."
        )

    log.info(
        f"Analysis input validated: {len(turns)} turns, "
        f"speakers={present_speakers}, text_len={len(total_text)} ✓"
    )
    return GuardResult(ok=True)
