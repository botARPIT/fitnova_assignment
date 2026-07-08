"""Analytics repository — SQL for org-wide stats and team/advisors analytics."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import asyncpg


def _uuid(val: str | Any) -> Any:
    import uuid
    return uuid.UUID(val) if isinstance(val, str) else val


def _time_condition(
    idx: int,
    from_date: datetime | None,
    to_date: datetime | None,
) -> tuple[str, list]:
    clauses = []
    params = []
    if from_date:
        clauses.append(f"c.created_at >= ${idx}")
        params.append(from_date)
        idx += 1
    if to_date:
        clauses.append(f"c.created_at <= ${idx}")
        params.append(to_date)
        idx += 1
    clause = " AND ".join(clauses) if clauses else "TRUE"
    return clause, params


async def list_teams(pool: asyncpg.Pool) -> list[dict]:
    rows = await pool.fetch("""
        SELECT t.id, t.name, t.organization_id, COUNT(a.id) as advisor_count
        FROM teams t
        LEFT JOIN advisors a ON a.team_id = t.id
        GROUP BY t.id, t.name, t.organization_id
        ORDER BY t.name
    """)
    return [dict(r) for r in rows]


async def list_advisors(pool: asyncpg.Pool, team_id: str | None = None) -> list[dict]:
    if team_id:
        rows = await pool.fetch(
            "SELECT * FROM advisors WHERE team_id = $1 ORDER BY name",
            _uuid(team_id),
        )
    else:
        rows = await pool.fetch("SELECT * FROM advisors ORDER BY name")
    return [dict(r) for r in rows]


async def get_team_by_id(pool: asyncpg.Pool, team_id: str) -> dict | None:
    row = await pool.fetchrow(
        "SELECT * FROM teams WHERE id = $1", _uuid(team_id),
    )
    return dict(row) if row else None


async def get_advisor_by_id(pool: asyncpg.Pool, advisor_id: str) -> dict | None:
    row = await pool.fetchrow(
        "SELECT * FROM advisors WHERE id = $1", _uuid(advisor_id),
    )
    return dict(row) if row else None


async def get_org_overview(
    pool: asyncpg.Pool,
    org_id: str,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    team_id: str | None = None,
    advisor_id: str | None = None,
) -> dict:
    time_clause, time_params = _time_condition(1, from_date, to_date)
    team_clause = ""
    advisor_clause = ""
    params = time_params[:]
    idx = len(params) + 1

    if team_id:
        team_clause = f" AND a.team_id = ${idx}"
        params.append(_uuid(team_id))
        idx += 1
    if advisor_id:
        advisor_clause = f" AND c.advisor_id = ${idx}"
        params.append(_uuid(advisor_id))
        idx += 1

    stats = await pool.fetchrow(
        f"""
        SELECT
            COUNT(*)::int as total_calls,
            COUNT(*) FILTER (WHERE c.status = 'completed')::int as completed_calls,
            COUNT(*) FILTER (WHERE c.status = 'failed')::int as failed_calls,
            ROUND(AVG(r.overall_score)::numeric, 2)::float as avg_score,
            COUNT(DISTINCT c.advisor_id)::int as active_advisors
        FROM calls c
        LEFT JOIN advisors a ON a.id = c.advisor_id
        LEFT JOIN reports r ON r.call_id = c.id
        WHERE c.organization_id = ${idx} AND {time_clause} {team_clause} {advisor_clause}
        """,
        *params, _uuid(org_id),
    )

    obj_idx = idx
    obj_params = params[:]
    objective = await pool.fetchrow(
        f"""
        SELECT
            ROUND(AVG(c.duration_sec)::numeric, 2)::float as avg_duration_sec,
            ROUND(AVG((r.scores->>'talk_ratio')::numeric)::numeric, 4)::float as avg_talk_ratio,
            ROUND(
                (COUNT(*) FILTER (
                    WHERE r.flags @> '[{{"tag": "weak_or_missing_trial_booking"}}]'::jsonb
                ))::numeric / NULLIF(COUNT(*), 0) * 100, 2
            )::float as trial_booking_rate,
            ROUND(AVG((r.scores->>'interruptions')::numeric)::numeric, 2)::float as avg_interruptions,
            ROUND(AVG((r.scores->>'questions_asked')::numeric)::numeric, 2)::float as avg_questions_asked
        FROM calls c
        JOIN reports r ON r.call_id = c.id
        LEFT JOIN advisors a ON a.id = c.advisor_id
        WHERE c.organization_id = ${obj_idx} AND {time_clause} {team_clause} {advisor_clause}
          AND c.status = 'completed'
        """,
        *obj_params, _uuid(org_id),
    )

    flag_idx = idx
    flag_params = obj_params[:]
    flags = await pool.fetch(
        f"""
        SELECT flag->>'tag' as tag, COUNT(*)::int as count
        FROM reports r
        JOIN calls c ON c.id = r.call_id
        LEFT JOIN advisors a ON a.id = c.advisor_id,
        jsonb_array_elements(r.flags) as flag
        WHERE c.organization_id = ${flag_idx} AND {time_clause} {team_clause} {advisor_clause}
        GROUP BY flag->>'tag'
        ORDER BY count DESC
        LIMIT 5
        """,
        *flag_params, _uuid(org_id),
    )

    return {
        "stats": dict(stats),
        "objective": dict(objective) if objective else {},
        "top_flags": [dict(r) for r in flags],
    }


async def get_team_stats(
    pool: asyncpg.Pool,
    team_id: str,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
) -> dict:
    time_clause, time_params = _time_condition(1, from_date, to_date)
    idx = len(time_params) + 1

    advisors = await pool.fetch(
        f"""
        SELECT
            a.id, a.name, a.role,
            COUNT(c.id)::int as call_count,
            ROUND(AVG(r.overall_score)::numeric, 2)::float as avg_score
        FROM advisors a
        LEFT JOIN calls c ON c.advisor_id = a.id AND {time_clause}
        LEFT JOIN reports r ON r.call_id = c.id AND c.status = 'completed'
        WHERE a.team_id = ${idx}
        GROUP BY a.id, a.name, a.role
        ORDER BY avg_score DESC NULLS LAST, call_count DESC, a.name ASC
        """,
        *time_params, _uuid(team_id),
    )

    flags_time_clause, _ = _time_condition(2, from_date, to_date)
    flags = await pool.fetch(
        f"""
        SELECT flag->>'tag' as tag, COUNT(*)::int as count
        FROM reports r
        JOIN calls c ON c.id = r.call_id
        JOIN advisors a ON a.id = c.advisor_id,
        jsonb_array_elements(r.flags) as flag
        WHERE a.team_id = $1 AND {flags_time_clause}
        GROUP BY flag->>'tag'
        ORDER BY count DESC
        LIMIT 5
        """,
        _uuid(team_id), *time_params,
    )

    total_calls = sum(r["call_count"] for r in advisors) or 1
    return {
        "advisors": [dict(r) for r in advisors],
        "flags": [{"tag": r["tag"], "count": r["count"],
                    "percentage": round(r["count"] / total_calls * 100, 1)}
                  for r in flags],
    }


async def get_advisor_stats(
    pool: asyncpg.Pool,
    advisor_id: str,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
) -> dict:
    time_clause, time_params = _time_condition(1, from_date, to_date)
    idx = len(time_params) + 1

    summary = await pool.fetchrow(
        f"""
        SELECT
            COUNT(*)::int as total_calls,
            ROUND(AVG(r.overall_score)::numeric, 2)::float as avg_score,
            ROUND(MIN(r.overall_score)::numeric, 2)::float as min_score,
            ROUND(MAX(r.overall_score)::numeric, 2)::float as max_score
        FROM calls c
        LEFT JOIN reports r ON r.call_id = c.id
        WHERE c.advisor_id = ${idx} AND c.status = 'completed'
          AND {time_clause}
        """,
        *time_params, _uuid(advisor_id),
    )

    recent = await pool.fetch(
        f"""
        SELECT c.id, c.duration_sec, c.created_at, r.overall_score
        FROM calls c
        LEFT JOIN reports r ON r.call_id = c.id
        WHERE c.advisor_id = ${idx} AND c.status = 'completed'
          AND {time_clause}
        ORDER BY c.created_at DESC
        LIMIT 20
        """,
        *time_params, _uuid(advisor_id),
    )

    flag_freq = await pool.fetch(
        f"""
        SELECT flag->>'tag' as tag, COUNT(*)::int as count
        FROM reports r
        JOIN calls c ON c.id = r.call_id,
        jsonb_array_elements(r.flags) as flag
        WHERE c.advisor_id = ${idx} AND {time_clause}
        GROUP BY flag->>'tag'
        ORDER BY count DESC
        LIMIT 10
        """,
        *time_params, _uuid(advisor_id),
    )

    return {
        "summary": dict(summary) if summary else {},
        "recent_calls": [dict(r) for r in recent],
        "flag_frequency": [dict(r) for r in flag_freq],
    }


async def get_score_trends(
    pool: asyncpg.Pool,
    org_id: str,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    team_id: str | None = None,
    advisor_id: str | None = None,
) -> list[dict]:
    time_clause, time_params = _time_condition(1, from_date, to_date)
    idx = len(time_params) + 1
    conditions = [f"c.organization_id = ${idx}"]
    params = [*time_params, _uuid(org_id)]
    idx += 1

    if team_id:
        conditions.append(f"a.team_id = ${idx}")
        params.append(_uuid(team_id))
        idx += 1
    if advisor_id:
        conditions.append(f"c.advisor_id = ${idx}")
        params.append(_uuid(advisor_id))
        idx += 1

    where = " AND ".join(conditions)
    rows = await pool.fetch(
        f"""
        SELECT
            c.created_at::date as date,
            ROUND(AVG(r.overall_score)::numeric, 2)::float as avg_score
        FROM calls c
        LEFT JOIN advisors a ON a.id = c.advisor_id
        JOIN reports r ON r.call_id = c.id
        WHERE c.status = 'completed' AND {where} AND {time_clause}
        GROUP BY c.created_at::date
        ORDER BY date ASC
        """,
        *params,
    )
    return [{"date": str(r["date"]), "avg_score": r["avg_score"]} for r in rows]
