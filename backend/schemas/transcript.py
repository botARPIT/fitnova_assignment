"""Pydantic models for transcription data."""

from pydantic import BaseModel


class Turn(BaseModel):
    """A single speaker turn in a transcript."""
    speaker: str
    start: float
    end: float
    text: str


class TranscriptOut(BaseModel):
    """Complete transcript output from either STT engine."""
    call_id: str
    duration_sec: float
    turns: list[Turn]
    engine: str = "deepgram"
