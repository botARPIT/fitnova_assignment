"""Central output schemas — Pydantic models for all LLM structured output.

These models define the EXACT shape that LLM responses must conform to.
Used with LangChain's `with_structured_output()` for type-safe parsing.

Every LLM call in the pipeline must output into one of these schemas.
"""

import uuid
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


# ═══════════════════════════════════════════════════════════════════════════
# Shared Enums
# ═══════════════════════════════════════════════════════════════════════════

class SpeakerLabel(str, Enum):
    """Valid speaker labels — exactly 2 parties in every call."""
    advisor = "Advisor"
    customer = "Customer"


class IssueTag(str, Enum):
    """Fixed taxonomy of flaggable issues. LLM cannot invent new tags."""
    no_needs_discovery = "no_needs_discovery"
    overpromising = "overpromising"
    pressure_or_urgency_tactics = "pressure_or_urgency_tactics"
    price_before_value = "price_before_value"
    undisclosed_costs = "undisclosed_costs"
    weak_or_missing_trial_booking = "weak_or_missing_trial_booking"
    talking_over_customer = "talking_over_customer"


class Severity(str, Enum):
    """Flag severity levels."""
    minor = "minor"
    major = "major"
    critical = "critical"


# ═══════════════════════════════════════════════════════════════════════════
# STAGE 1: Speaker Repair Output Schema
# ═══════════════════════════════════════════════════════════════════════════

class RepairedTurn(BaseModel):
    """A single turn after speaker repair.

    Used to parse raw JSON from the LLM speaker repair stage.
    Enforces that speaker is one of the valid SpeakerLabel values.
    """
    speaker: SpeakerLabel = Field(
        description="Must be 'Advisor' or 'Customer' — no other values"
    )
    start: float = Field(ge=0, description="Start time in seconds (from original STT)")
    end: float = Field(ge=0, description="End time in seconds (from original STT)")
    text: str = Field(min_length=1, description="Original text — must not be empty or modified")

    @field_validator("end")
    @classmethod
    def end_after_start(cls, v, info):
        start = info.data.get("start", 0)
        if v < start:
            raise ValueError(f"end ({v}) must be >= start ({start})")
        return v


class SpeakerRepairOutput(BaseModel):
    """Complete output from speaker repair stage.

    Wraps the list of repaired turns for schema-level validation.
    """
    turns: list[RepairedTurn] = Field(min_length=1)

    @field_validator("turns")
    @classmethod
    def check_speakers(cls, v):
        """Ensure exactly 2 speakers exist — no more, no less."""
        speakers = {t.speaker for t in v}
        if len(speakers) < 1:
            raise ValueError("Transcript has no speakers")
        # Allow 1 speaker (monologue) but warn — validator logs this
        return v


# ═══════════════════════════════════════════════════════════════════════════
# STAGE 2: Call Analysis Output Schema
# ═══════════════════════════════════════════════════════════════════════════

class DimensionScore(BaseModel):
    """Score for a single rubric dimension with supporting evidence."""
    score: float = Field(
        ge=0,
        le=5,
        description="Score 0-5 per rubric definition. Fractional scores like 0.5 or 1.5 are allowed."
    )
    evidence: str = Field(
        min_length=1,
        description="Brief justification — reference specific moments from the call"
    )


class Scores(BaseModel):
    """Call quality scores across 5 rubric dimensions, each with score + evidence."""
    needs_discovery: DimensionScore
    product_knowledge: DimensionScore
    objection_handling: DimensionScore
    compliance: DimensionScore
    next_step_booking: DimensionScore


class Flag(BaseModel):
    """A single issue flag extracted from the call transcript.

    The quote MUST be a verbatim excerpt — LLMs sometimes paraphrase,
    which is caught by the post-processing quote verifier.
    """
    tag: IssueTag = Field(description="Issue type — must be from the fixed taxonomy")
    severity: Severity = Field(description="How serious this issue is")
    quote: str = Field(
        min_length=1,
        description="Exact verbatim quote from the transcript that shows this issue"
    )
    explanation: str = Field(
        min_length=5,
        description="One-sentence explanation of why this is flagged"
    )
    timestamp: float = Field(
        ge=0,
        description="Start time (seconds) of the turn containing this quote"
    )

    @field_validator("quote", "explanation", mode="before")
    @classmethod
    def strip_text_fields(cls, value):
        if isinstance(value, str):
            return value.strip()
        return value


class CallAnalysis(BaseModel):
    """Complete structured analysis of a sales call (LLM output shape).

    Used with `llm.with_structured_output(CallAnalysis)` to ensure
    the LLM produces valid, type-safe output.
    """
    scores: Scores = Field(description="Quality scores per rubric dimension")
    flags: list[Flag] = Field(
        description="Issues found in the call — only from the fixed taxonomy"
    )


# ═══════════════════════════════════════════════════════════════════════════
# Post-Processing Models (not LLM output — used after validation)
# ═══════════════════════════════════════════════════════════════════════════

class FlaggedFlag(BaseModel):
    """A flag after post-processing (with match score from quote verification).

    Every flag receives a stable UUID at creation time. This flag_id is
    used by the contestation workflow to reference flags without relying
    on array indices.
    """
    flag_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tag: str
    severity: str
    quote: str
    explanation: str
    timestamp: float
    match_score: Optional[float] = None
    discard_reason: Optional[str] = None
    matched_turn_index: Optional[int] = None
    matched_turn_speaker: Optional[str] = None
    matched_turn_start: Optional[float] = None
