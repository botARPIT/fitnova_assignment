"""Simple migration runner that auto-applies pending .sql migrations."""

import logging
import os
from pathlib import Path

import asyncpg

log = logging.getLogger("fitnova.db.migrate")

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


async def ensure_migrations_table(pool: asyncpg.Pool) -> None:
    await pool.execute("""
        CREATE TABLE IF NOT EXISTS _migrations (
            filename TEXT PRIMARY KEY,
            applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)


async def get_applied(pool: asyncpg.Pool) -> set[str]:
    rows = await pool.fetch("SELECT filename FROM _migrations ORDER BY filename")
    return {r["filename"] for r in rows}


async def run_migrations(pool: asyncpg.Pool) -> int:
    await ensure_migrations_table(pool)
    applied = await get_applied(pool)

    files = sorted(
        f for f in os.listdir(MIGRATIONS_DIR)
        if f.endswith(".sql") and f not in applied
    )

    if not files:
        log.info("All migrations already applied")
        return 0

    for filename in files:
        path = MIGRATIONS_DIR / filename
        sql = path.read_text()
        async with pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(sql)
                await conn.execute(
                    "INSERT INTO _migrations (filename) VALUES ($1)", filename
                )
        log.info("Applied migration: %s", filename)

    return len(files)
