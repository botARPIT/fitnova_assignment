"""AnalyticsService — aggregation logic for analytics endpoints.

Owns all derived metrics and transformation of raw repository data
into typed response models. Designed for future caching.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import asyncpg

from db import analytics_repository as repo
from schemas.analytics import (
    AdvisorAnalyticsOut,
    AdvisorLeaderboardEntry,
    AdvisorSummary,
    FlagSummary,
    ObjectiveMetrics,
    OrgOverviewOut,
    OrgOverviewSummary,
    PeriodOut,
    RecentCallOut,
    TeamAnalyticsOut,
    TrendPoint,
)

log = logging.getLogger("fitnova.services.analytics")


class AnalyticsService:
    """Aggregates raw repository data into typed analytics response models.

    Args:
        pool: Database connection pool (from app.state or get_pool()).
        org_id: Default organization ID for the current deployment.
    """

    def __init__(self, pool: asyncpg.Pool, org_id: str) -> None:
        self._pool = pool
        self._org_id = org_id

    # ── Private helpers ─────────────────────────────────────────

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _period(
        from_date: datetime | None,
        to_date: datetime | None,
    ) -> PeriodOut:
        return PeriodOut(from_=from_date, to=to_date)

    @staticmethod
    def _flag_list(
        raw: list[dict],
        total_calls: int = 0,
    ) -> list[FlagSummary]:
        denominator = total_calls or 1
        return [
            FlagSummary(
                tag=f["tag"],
                count=f["count"],
                percentage=round(f["count"] / denominator * 100, 1),
            )
            for f in raw
        ]

    @staticmethod
    def _trend_points(raw: list[dict]) -> list[TrendPoint]:
        return [TrendPoint(date=t["date"], avg_score=t["avg_score"]) for t in raw]

    @staticmethod
    def _safe_float(val: Any) -> float:
        if val is None:
            return 0.0
        return float(val)

    @staticmethod
    def _safe_int(val: Any) -> int:
        if val is None:
            return 0
        return int(val)

    # ── Organization overview ───────────────────────────────────

    async def get_org_overview(
        self,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        team_id: str | None = None,
        advisor_id: str | None = None,
    ) -> OrgOverviewOut:
        data = await repo.get_org_overview(
            self._pool,
            self._org_id,
            from_date=from_date,
            to_date=to_date,
            team_id=team_id,
            advisor_id=advisor_id,
        )
        stats = data["stats"]
        obj = data["objective"]
        trend = await repo.get_score_trends(
            self._pool,
            self._org_id,
            from_date=from_date,
            to_date=to_date,
            team_id=team_id,
            advisor_id=advisor_id,
        )

        total_calls = self._safe_int(stats.get("total_calls"))

        return OrgOverviewOut(
            generated_at=self._now(),
            period=self._period(from_date, to_date),
            summary=OrgOverviewSummary(
                total_calls=total_calls,
                completed_calls=self._safe_int(stats.get("completed_calls")),
                failed_calls=self._safe_int(stats.get("failed_calls")),
                avg_score=self._safe_float(stats.get("avg_score")),
                active_advisors=self._safe_int(stats.get("active_advisors")),
            ),
            objective_metrics=ObjectiveMetrics(
                avg_duration_sec=self._safe_float(obj.get("avg_duration_sec")),
                avg_talk_ratio=self._safe_float(obj.get("avg_talk_ratio")),
                trial_booking_rate=self._safe_float(obj.get("trial_booking_rate")),
                avg_interruptions=self._safe_float(obj.get("avg_interruptions")),
                avg_questions_asked=self._safe_float(obj.get("avg_questions_asked")),
            ),
            top_flags=self._flag_list(data.get("top_flags", []), total_calls),
            score_trend=self._trend_points(trend),
        )

    # ── Team analytics ──────────────────────────────────────────

    async def get_team_analytics(
        self,
        team_id: str,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
    ) -> TeamAnalyticsOut:
        team = await repo.get_team_by_id(self._pool, team_id)
        if not team:
            return TeamAnalyticsOut(
                generated_at=self._now(),
                period=self._period(from_date, to_date),
                team_id=team_id,
                team_name="",
            )

        data = await repo.get_team_stats(
            self._pool, team_id,
            from_date=from_date,
            to_date=to_date,
        )

        trend = await repo.get_score_trends(
            self._pool,
            self._org_id,
            from_date=from_date,
            to_date=to_date,
            team_id=team_id,
        )

        leaderboard = [
            AdvisorLeaderboardEntry(
                id=r["id"],
                name=r["name"],
                role=r["role"],
                call_count=self._safe_int(r.get("call_count")),
                avg_score=self._safe_float(r.get("avg_score")),
            )
            for r in data.get("advisors", [])
        ]

        avg_score = 0.0
        scores = [e.avg_score for e in leaderboard if e.avg_score > 0]
        if scores:
            avg_score = round(sum(scores) / len(scores), 2)

        return TeamAnalyticsOut(
            generated_at=self._now(),
            period=self._period(from_date, to_date),
            team_id=team["id"],
            team_name=team["name"],
            avg_score=avg_score,
            advisor_leaderboard=leaderboard,
            coaching_opportunities=[
                FlagSummary(**f) for f in data.get("flags", [])
            ],
            score_trend=self._trend_points(trend),
        )

    # ── Advisor analytics ───────────────────────────────────────

    async def get_advisor_analytics(
        self,
        advisor_id: str,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
    ) -> AdvisorAnalyticsOut:
        advisor = await repo.get_advisor_by_id(self._pool, advisor_id)
        if not advisor:
            return AdvisorAnalyticsOut(
                generated_at=self._now(),
                period=self._period(from_date, to_date),
                advisor_id=advisor_id,
                advisor_name="",
            )

        data = await repo.get_advisor_stats(
            self._pool, advisor_id,
            from_date=from_date,
            to_date=to_date,
        )

        trend = await repo.get_score_trends(
            self._pool,
            self._org_id,
            from_date=from_date,
            to_date=to_date,
            advisor_id=advisor_id,
        )

        summary_raw = data.get("summary", {})
        flag_freq_raw = data.get("flag_frequency", [])
        total_calls = self._safe_int(summary_raw.get("total_calls"))

        return AdvisorAnalyticsOut(
            generated_at=self._now(),
            period=self._period(from_date, to_date),
            advisor_id=advisor["id"],
            advisor_name=advisor["name"],
            summary=AdvisorSummary(
                total_calls=total_calls,
                avg_score=self._safe_float(summary_raw.get("avg_score")),
                min_score=self._safe_float(summary_raw.get("min_score")),
                max_score=self._safe_float(summary_raw.get("max_score")),
            ),
            recent_calls=[
                RecentCallOut(
                    id=r["id"],
                    duration_sec=r.get("duration_sec"),
                    created_at=r.get("created_at"),
                    overall_score=r.get("overall_score"),
                )
                for r in data.get("recent_calls", [])
            ],
            flag_frequency=self._flag_list(flag_freq_raw, total_calls),
            coaching_opportunities=self._flag_list(flag_freq_raw, total_calls),
            score_trend=self._trend_points(trend),
        )
