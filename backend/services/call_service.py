"""Read-side call service for router-facing call queries."""

from __future__ import annotations

import asyncpg
from pathlib import Path

from db.call_repository import get_call, get_call_status, list_calls
from services import review_service


class CallService:
    """Owns router-facing read operations for calls."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def list_calls(
        self,
        *,
        advisor_id: str | None = None,
        team_id: str | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        calls = await list_calls(
            self._pool,
            advisor_id=advisor_id,
            team_id=team_id,
            status=status,
            limit=limit,
            offset=offset,
        )
        return {"calls": calls, "count": len(calls), "limit": limit, "offset": offset}

    async def get_call_detail(self, call_id: str) -> dict | None:
        call = await get_call(self._pool, call_id)
        if not call:
            return None

        original_flags = call.get("flags") or []
        if original_flags:
            call["effective_flags"] = await review_service.compute_effective_flags(
                self._pool,
                call_id,
                original_flags,
            )
        else:
            call["effective_flags"] = []

        return call

    async def get_call_status(self, call_id: str) -> dict | None:
        call = await get_call_status(self._pool, call_id)
        if not call:
            return None

        return {
            "call_id": str(call["id"]),
            "status": call.get("status"),
            "failed_stage": call.get("failed_stage"),
            "error_message": call.get("error_message"),
            "advisor_id": str(call["advisor_id"]) if call.get("advisor_id") else None,
            "organization_id": str(call["organization_id"]) if call.get("organization_id") else None,
            "created_at": call.get("created_at"),
            "completed_at": call.get("completed_at"),
        }

    async def get_call_audio_path(self, call_id: str) -> Path | None:
        call = await get_call(self._pool, call_id)
        if not call or not call.get("audio_path"):
            return None
        return Path(call["audio_path"])
