"""PipelineContext — shared state carried through the entire pipeline."""

from dataclasses import dataclass, field
from typing import Optional

from config import Settings
from schemas.transcript import Turn


@dataclass
class PipelineMetadata:
    transcription_engine: str = "deepgram"
    llm_model: str = ""
    prompt_version: str = ""
    rubric_version: str = ""
    company_facts_version: str = ""
    analysis_version: str = ""


@dataclass
class PipelineTimings:
    stt_ms: int = 0
    repair_ms: int = 0
    analysis_ms: int = 0
    total_ms: int = 0


@dataclass
class PipelineContext:
    call_id: str = ""
    file_sha256: str = ""
    ingestion_fingerprint: str = ""
    source: str = "FILE_UPLOAD"
    external_call_id: Optional[str] = None
    advisor_id: Optional[str] = None
    organization_id: Optional[str] = None
    audio_path: str = ""
    audio_bytes: bytes = b""
    file_extension: str = ""
    duration_sec: float = 0.0
    language: Optional[str] = None

    raw_transcript: list[Turn] = field(default_factory=list)
    repaired_transcript: list[Turn] = field(default_factory=list)

    scores: dict = field(default_factory=dict)
    overall_score: float = 0.0
    verified_flags: list = field(default_factory=list)
    discarded_flags: list = field(default_factory=list)

    metadata: PipelineMetadata = field(default_factory=PipelineMetadata)
    timings: PipelineTimings = field(default_factory=PipelineTimings)
    settings: Optional[Settings] = None
