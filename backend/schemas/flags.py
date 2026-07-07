"""Pydantic models for call flagging request/response.

LLM output schemas (CallAnalysis, Scores, Flag, IssueTag) and post-processing
models (FlaggedFlag) are now defined in guardrails.schemas — the single source
of truth. This file re-exports them for backward compatibility and defines
only the API request/response envelopes.
"""

from typing import Optional

from pydantic import BaseModel

from schemas.transcript import TranscriptOut

# ── Re-exports from central guardrails ─────────────────────────
from guardrails.schemas import (
    IssueTag,
    Severity,
    Flag,
    Scores,
    CallAnalysis,
    FlaggedFlag,
)

__all__ = [
    "IssueTag", "Severity", "Flag", "Scores", "CallAnalysis", "FlaggedFlag",
    "FlagRequest", "FlagResponse",
]


# ---------------------------------------------------------------------------
# Request / Response models (API envelope — NOT LLM schemas)
# ---------------------------------------------------------------------------

class FlagRequest(BaseModel):
    call_id: Optional[str] = None
    transcript: Optional[TranscriptOut] = None


class FlagResponse(BaseModel):
    call_id: str
    scores: dict
    overall_score: float
    flags: list[FlaggedFlag]
    discarded_flags: list[FlaggedFlag]
