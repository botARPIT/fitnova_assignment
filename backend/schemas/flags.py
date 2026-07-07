"""Pydantic models for call flagging and quality analysis."""

from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field

from schemas.transcript import TranscriptOut


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class IssueTag(str, Enum):
    no_needs_discovery = "no_needs_discovery"
    overpromising = "overpromising"
    pressure_or_urgency_tactics = "pressure_or_urgency_tactics"
    price_before_value = "price_before_value"
    undisclosed_costs = "undisclosed_costs"
    weak_or_missing_trial_booking = "weak_or_missing_trial_booking"
    talking_over_customer = "talking_over_customer"


# ---------------------------------------------------------------------------
# LLM structured output schema
# ---------------------------------------------------------------------------

class Flag(BaseModel):
    """A single issue flag extracted from the call transcript."""
    tag: IssueTag = Field(description="Issue type — must be from the fixed taxonomy")
    severity: Literal["low", "medium", "high"] = Field(description="How serious this issue is")
    quoted_line: str = Field(description="Exact verbatim quote from the transcript that shows this issue")
    reason: str = Field(description="One-sentence explanation of why this is flagged")
    timestamp: float = Field(description="Start time (seconds) of the turn containing this quote")


class Scores(BaseModel):
    """Call quality scores across 5 rubric dimensions, each 0-5."""
    needs_discovery: int = Field(ge=0, le=5)
    product_knowledge: int = Field(ge=0, le=5)
    objection_handling: int = Field(ge=0, le=5)
    compliance: int = Field(ge=0, le=5)
    next_step_booking: int = Field(ge=0, le=5)


class CallAnalysis(BaseModel):
    """Complete structured analysis of a sales call (LLM output shape)."""
    scores: Scores = Field(description="Quality scores per rubric dimension")
    flags: list[Flag] = Field(description="Issues found in the call — only from the fixed taxonomy")


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class FlagRequest(BaseModel):
    call_id: Optional[str] = None
    transcript: Optional[TranscriptOut] = None


class FlaggedFlag(BaseModel):
    """A flag after post-processing (with match score from quote verification)."""
    tag: str
    severity: str
    quoted_line: str
    reason: str
    timestamp: float
    match_score: Optional[float] = None


class FlagResponse(BaseModel):
    call_id: str
    scores: dict
    overall_score: float
    flags: list[FlaggedFlag]
    discarded_flags: list[FlaggedFlag]
