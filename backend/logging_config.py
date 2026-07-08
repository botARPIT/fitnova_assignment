"""Centralized application logging configuration."""

from __future__ import annotations

import logging


def configure_logging(settings) -> None:
    """Configure root/app logging based on environment."""
    level_name = (settings.log_level or ("DEBUG" if settings.is_dev else "INFO")).upper()
    level = getattr(logging, level_name, logging.INFO)

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(level)

    handler = logging.StreamHandler()
    if settings.is_dev:
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
        )
    else:
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
        )
    handler.setFormatter(formatter)
    root.addHandler(handler)

    if not settings.is_dev:
        logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
        logging.getLogger("uvicorn.error").setLevel(logging.INFO)
        logging.getLogger("asyncpg").setLevel(logging.WARNING)
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)
        logging.getLogger("google").setLevel(logging.WARNING)
        logging.getLogger("deepgram").setLevel(logging.WARNING)


def safe_exception_text(exc: Exception, settings) -> str:
    """Return a verbose exception string only in development."""
    if settings.log_sensitive_details:
        text = str(exc).strip()
        return text or type(exc).__name__
    return type(exc).__name__
