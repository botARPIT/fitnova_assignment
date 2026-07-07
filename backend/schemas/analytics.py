"""Pydantic response models for analytics endpoints."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel


class PeriodOut(BaseModel):
    from_: datetime | None = None
    to: datetime | None = None


class ObjectiveMetrics(BaseModel):
    avg_duration_sec: float = 0
    avg_talk_ratio: float = 0
    trial_booking_rate: float = 0
    avg_interruptions: float = 0
    avg_questions_asked: float = 0


class FlagSummary(BaseModel):
    tag: str
    count: int
    percentage: float


class TrendPoint(BaseModel):
    date: str
    avg_score: float


class OrgOverviewSummary(BaseModel):
    total_calls: int = 0
    completed_calls: int = 0
    failed_calls: int = 0
    avg_score: float = 0
    active_advisors: int = 0


class OrgOverviewOut(BaseModel):
    generated_at: datetime = None
    period: PeriodOut = None
    summary: OrgOverviewSummary = None
    objective_metrics: ObjectiveMetrics = None
    top_flags: list[FlagSummary] = []
    score_trend: list[TrendPoint] = []


class AdvisorLeaderboardEntry(BaseModel):
    id: Any
    name: str
    role: str
    call_count: int = 0
    avg_score: float = 0


class TeamAnalyticsOut(BaseModel):
    generated_at: datetime = None
    period: PeriodOut = None
    team_id: Any
    team_name: str
    avg_score: float = 0
    advisor_leaderboard: list[AdvisorLeaderboardEntry] = []
    coaching_opportunities: list[FlagSummary] = []
    score_trend: list[TrendPoint] = []


class AdvisorSummary(BaseModel):
    total_calls: int = 0
    avg_score: float = 0
    min_score: float = 0
    max_score: float = 0


class RecentCallOut(BaseModel):
    id: Any
    duration_sec: float | None = None
    created_at: datetime | None = None
    overall_score: float | None = None


class AdvisorAnalyticsOut(BaseModel):
    generated_at: datetime = None
    period: PeriodOut = None
    advisor_id: Any
    advisor_name: str
    summary: AdvisorSummary = None
    recent_calls: list[RecentCallOut] = []
    flag_frequency: list[FlagSummary] = []
    strengths: list[str] = []
    coaching_opportunities: list[FlagSummary] = []
    score_trend: list[TrendPoint] = []
