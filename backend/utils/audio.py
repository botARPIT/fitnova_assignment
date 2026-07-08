"""Audio utilities: format validation, channel detection, and splitting."""

import json
import logging
import subprocess
import wave
from dataclasses import dataclass
from pathlib import Path

from config import settings

log = logging.getLogger("fitnova.audio")

ALLOWED_EXTENSIONS = frozenset({"wav", "mp3", "m4a"})


# ---------------------------------------------------------------------------
# Format validation
# ---------------------------------------------------------------------------

def validate_extension(filename: str | None) -> str:
    """Extract and validate audio file extension.

    Returns the lowercase extension string.
    Raises ValueError if the format is unsupported.
    """
    if not filename:
        raise ValueError("No filename provided")
    ext = filename.rsplit(".", 1)[-1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(
            f"Unsupported format '.{ext}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )
    return ext


# ---------------------------------------------------------------------------
# Channel detection
# ---------------------------------------------------------------------------

@dataclass
class AudioInfo:
    """Metadata about an audio file."""
    channels: int
    sample_rate: int
    duration_sec: float
    format: str  # wav, mp3, m4a


def detect_channels(audio_path: str) -> AudioInfo:
    """Detect channel count and basic audio metadata.

    Uses stdlib `wave` for WAV files, falls back to ffprobe for mp3/m4a.
    """
    path = Path(audio_path)
    ext = path.suffix.lower().lstrip(".")

    if ext == "wav":
        return _detect_wav(audio_path)
    return _detect_ffprobe(audio_path, ext)


def _detect_wav(audio_path: str) -> AudioInfo:
    """Use stdlib wave module for WAV files."""
    with wave.open(audio_path, "rb") as wf:
        channels = wf.getnchannels()
        sample_rate = wf.getframerate()
        frames = wf.getnframes()
        duration = frames / sample_rate
        return AudioInfo(
            channels=channels,
            sample_rate=sample_rate,
            duration_sec=round(duration, 2),
            format="wav",
        )


def _detect_ffprobe(audio_path: str, ext: str) -> AudioInfo:
    """Use ffprobe for non-WAV formats (mp3, m4a)."""
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "quiet",
                "-print_format", "json",
                "-show_streams", "-show_format",
                audio_path,
            ],
            capture_output=True, text=True, timeout=10,
        )
        data = json.loads(result.stdout)

        # Find the audio stream
        audio_stream = next(
            (s for s in data.get("streams", []) if s.get("codec_type") == "audio"),
            None,
        )
        if not audio_stream:
            raise ValueError(f"No audio stream found in {audio_path}")

        return AudioInfo(
            channels=int(audio_stream.get("channels", 1)),
            sample_rate=int(audio_stream.get("sample_rate", 44100)),
            duration_sec=round(float(data.get("format", {}).get("duration", 0)), 2),
            format=ext,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        if settings.log_sensitive_details:
            log.warning(f"ffprobe unavailable or timed out: {e} — returning defaults")
        else:
            log.warning("ffprobe unavailable or timed out — returning defaults")
        return AudioInfo(channels=1, sample_rate=44100, duration_sec=0.0, format=ext)


# ---------------------------------------------------------------------------
# Channel splitting
# ---------------------------------------------------------------------------

def split_channels(audio_path: str, output_dir: str | None = None) -> list[str]:
    """Split a multi-channel audio file into separate mono WAV files.

    Returns a list of output file paths (one per channel).
    For mono files, returns a single-element list with the original path.

    Requires ffmpeg to be installed.
    """
    info = detect_channels(audio_path)

    if info.channels <= 1:
        log.info("Audio is already mono — no splitting needed")
        return [audio_path]

    path = Path(audio_path)
    out_dir = Path(output_dir) if output_dir else path.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    output_paths = []
    for ch in range(info.channels):
        out_file = out_dir / f"{path.stem}_ch{ch}.wav"
        try:
            subprocess.run(
                [
                    "ffmpeg", "-y", "-i", audio_path,
                    "-af", f"pan=mono|c0=c{ch}",
                    str(out_file),
                ],
                capture_output=True, text=True, timeout=60, check=True,
            )
            output_paths.append(str(out_file))
            log.info(f"Split channel {ch} → {out_file}")
        except subprocess.CalledProcessError as e:
            if settings.log_sensitive_details:
                log.error(f"Failed to split channel {ch}: {e.stderr}")
            else:
                log.error("Failed to split channel %s", ch)
            raise RuntimeError(f"Channel splitting failed for channel {ch}") from e

    return output_paths
