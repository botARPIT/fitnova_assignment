"""Read-side organization service for teams and advisors."""

from __future__ import annotations

import asyncpg

from db import analytics_repository as repo


class OrgService:
    """Owns router-facing org hierarchy queries."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def list_teams(self) -> dict:
        return {"teams": await repo.list_teams(self._pool)}

    async def list_advisors(self, *, team_id: str | None = None) -> dict:
        return {"advisors": await repo.list_advisors(self._pool, team_id=team_id)}
