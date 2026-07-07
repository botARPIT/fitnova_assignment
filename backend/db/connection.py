"""Async PostgreSQL connection pool using asyncpg."""

import asyncpg
import logging

log = logging.getLogger("fitnova.db")

_pool: asyncpg.Pool | None = None


async def init_pool(dsn: str) -> asyncpg.Pool:
    """Create and cache the connection pool. Called once during app startup."""
    global _pool
    if _pool is not None:
        return _pool
    _pool = await asyncpg.create_pool(dsn, min_size=2, max_size=10)
    log.info("Database pool created ✓")
    return _pool


async def get_pool() -> asyncpg.Pool:
    """Get the cached pool. Raises if init_pool hasn't been called."""
    if _pool is None:
        raise RuntimeError("Database pool not initialized. Call init_pool() first.")
    return _pool


async def close_pool():
    """Close the pool on shutdown."""
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
        log.info("Database pool closed")
