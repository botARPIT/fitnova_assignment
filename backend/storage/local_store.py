"""Local filesystem store for uploads and transcripts.

This is the default storage backend. Swap for S3Store or MinIOStore
later by implementing the same interface.
"""

import logging
from pathlib import Path

from schemas.transcript import Turn, TranscriptOut
from utils.pii import redact_text

log = logging.getLogger("fitnova.storage")


class LocalStore:
    """Read/write helpers for /tmp-based file storage."""

    def __init__(self, upload_dir: Path, transcripts_dir: Path):
        self.upload_dir = upload_dir
        self.transcripts_dir = transcripts_dir
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.transcripts_dir.mkdir(parents=True, exist_ok=True)

    # ── Uploads ────────────────────────────────────────────────

    def save_upload(self, call_id: str, ext: str, raw_bytes: bytes) -> Path:
        """Persist raw audio bytes to disk. Returns the saved path."""
        path = self.upload_dir / f"{call_id}.{ext}"
        path.write_bytes(raw_bytes)
        log.info(f"Saved upload → {path} ({len(raw_bytes)} bytes)")
        return path

    # ── Transcripts ────────────────────────────────────────────

    def save_transcript(self, transcript: TranscriptOut) -> Path:
        """Save transcript as JSON. Returns the saved path."""
        out_path = self.transcripts_dir / f"{transcript.call_id}.json"
        redacted = transcript.model_copy(
            update={
                "turns": [
                    Turn(
                        speaker=t.speaker,
                        start=t.start,
                        end=t.end,
                        text=redact_text(t.text),
                    )
                    for t in transcript.turns
                ]
            }
        )
        out_path.write_text(redacted.model_dump_json(indent=2))
        log.info(f"Transcript saved → {out_path}")
        return out_path

    def save_transcript_txt(self, transcript: TranscriptOut) -> Path:
        """Save a human-readable .txt version of the transcript."""
        txt_path = self.transcripts_dir / f"{transcript.call_id}.txt"
        lines = [
            f"Call ID: {transcript.call_id}",
            f"Duration: {transcript.duration_sec:.1f}s",
            f"Engine: {transcript.engine}",
            "",
        ]
        for t in transcript.turns:
            lines.append(f"[{t.start:.1f}s – {t.end:.1f}s] {t.speaker}: {redact_text(t.text)}")
        txt_path.write_text("\n".join(lines))
        log.info(f"Readable transcript → {txt_path}")
        return txt_path

    def read_transcript(self, call_id: str) -> TranscriptOut | None:
        """Load a transcript by call_id. Returns None if not found."""
        path = self.transcripts_dir / f"{call_id}.json"
        if not path.exists():
            return None
        return TranscriptOut.model_validate_json(path.read_text())
