# Task 06: Analytics API Endpoints

## Objective
Implement aggregate scoring and analytics endpoints that provide org-wide, team-level, and advisor-level visibility into call quality metrics.

## Parallelization
**Group B** — Depends on Task 01 (database) and Task 04 (pipeline).

## Context
From the requirements:
- *"Aggregate scores across the org — by team, by advisor, over time"*
- *"Surface team-wide coaching opportunities based on recurring flag patterns"*
- *"Which issues crop up most often across the org?"*

## Files to Create

### 1. `backend/routers/analytics.py`

```python
"""Analytics endpoints for org-wide, team-level, and advisor-level insights."""

import logging

from fastapi import APIRouter, HTTPException, Request

from db.connection import get_pool
from db import repository as repo

log = logging.getLogger("fitnova.routes.analytics")
router = APIRouter(prefix="/api/analytics", tags=["analytics"])

DEFAULT_ORG_ID = "00000000-0000-0000-0000-000000000001"


@router.get("/overview")
async def org_overview(request: Request):
    """Get org-wide statistics.
    
    Returns:
    - Total/completed/failed call counts
    - Average overall score
    - Active advisor count
    - Top 5 most frequent flags (coaching opportunities)
    """
    pool = await get_pool()
    overview = await repo.get_org_overview(pool, DEFAULT_ORG_ID)
    
    # Convert types for JSON serialization
    result = {}
    for key, val in overview.items():
        if hasattr(val, 'hex'):
            result[key] = str(val)
        elif isinstance(val, float) and val is not None:
            result[key] = round(val, 2)
        elif isinstance(val, list):
            result[key] = [
                {k: (str(v) if hasattr(v, 'hex') else v) for k, v in item.items()}
                for item in val
            ]
        else:
            result[key] = val
    
    return result


@router.get("/teams/{team_id}")
async def team_stats(request: Request, team_id: str):
    """Get team-level statistics with per-advisor breakdown.
    
    Returns advisor leaderboard sorted by average score.
    """
    pool = await get_pool()
    stats = await repo.get_team_stats(pool, team_id)
    
    # Serialize
    for advisor in stats.get("advisors", []):
        for key in advisor:
            if hasattr(advisor[key], 'hex'):
                advisor[key] = str(advisor[key])
            elif isinstance(advisor[key], float) and advisor[key] is not None:
                advisor[key] = round(advisor[key], 2)
    
    return stats


@router.get("/advisors/{advisor_id}")
async def advisor_stats(request: Request, advisor_id: str):
    """Get advisor-level statistics.
    
    Returns:
    - Summary (total calls, avg/min/max score)
    - Recent call history (last 20)
    - Flag frequency (which issues they trigger most)
    """
    pool = await get_pool()
    stats = await repo.get_advisor_stats(pool, advisor_id)
    
    # Serialize
    result = {}
    for key, val in stats.items():
        if hasattr(val, 'hex'):
            result[key] = str(val)
        elif isinstance(val, float) and val is not None:
            result[key] = round(val, 2)
        elif isinstance(val, list):
            serialized = []
            for item in val:
                s = {}
                for k, v in item.items():
                    if hasattr(v, 'hex'):
                        s[k] = str(v)
                    elif hasattr(v, 'isoformat'):
                        s[k] = v.isoformat()
                    elif isinstance(v, float) and v is not None:
                        s[k] = round(v, 2)
                    else:
                        s[k] = v
                serialized.append(s)
            result[key] = serialized
        else:
            result[key] = val
    
    return result
```

## Files to Modify

### 2. `backend/main.py`
Add to imports:
```python
from routers import analytics
```

Add router registration:
```python
app.include_router(analytics.router)
```

## API Response Examples

### `GET /api/analytics/overview`
```json
{
  "total_calls": 47,
  "completed_calls": 42,
  "failed_calls": 3,
  "avg_score": 3.24,
  "active_advisors": 6,
  "top_flags": [
    {"tag": "weak_or_missing_trial_booking", "count": 18},
    {"tag": "no_needs_discovery", "count": 12},
    {"tag": "price_before_value", "count": 9},
    {"tag": "overpromising", "count": 7},
    {"tag": "pressure_or_urgency_tactics", "count": 4}
  ]
}
```

### `GET /api/analytics/teams/{team_id}`
```json
{
  "advisors": [
    {"id": "...", "name": "Priya Sharma", "role": "senior", "call_count": 12, "avg_score": 4.1},
    {"id": "...", "name": "Arjun Mehta", "role": "junior", "call_count": 8, "avg_score": 3.5},
    {"id": "...", "name": "Vikram Patel", "role": "junior", "call_count": 5, "avg_score": 2.8}
  ]
}
```

### `GET /api/analytics/advisors/{advisor_id}`
```json
{
  "total_calls": 12,
  "avg_score": 4.1,
  "min_score": 2.8,
  "max_score": 4.9,
  "recent_calls": [
    {"id": "...", "duration_sec": 340, "created_at": "2024-01-15T10:30:00", "overall_score": 4.5}
  ],
  "flag_frequency": [
    {"tag": "weak_or_missing_trial_booking", "count": 3},
    {"tag": "no_needs_discovery", "count": 1}
  ]
}
```

## Acceptance Criteria
1. `GET /api/analytics/overview` returns org-wide metrics with top flags
2. `GET /api/analytics/teams/{team_id}` returns advisor leaderboard sorted by score
3. `GET /api/analytics/advisors/{advisor_id}` returns individual stats with flag frequency
4. All numeric values are properly rounded to 2 decimal places
5. All UUIDs and datetimes are serialized to strings
6. Empty results (no calls yet) return sensible defaults (0 counts, null scores)
