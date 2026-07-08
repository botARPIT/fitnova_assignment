"""Deepgram-specific retry classification.

Knows only about Deepgram SDK exceptions and HTTP transport errors.
"""

import logging

from httpx import ConnectError, RemoteProtocolError, TimeoutException

log = logging.getLogger("fitnova.retry.deepgram")

# ── Retryable transport errors ──────────────────────────────────

TRANSPORT_ERRORS = (
    TimeoutException,
    ConnectError,
    RemoteProtocolError,
    ConnectionResetError,
    TimeoutError,
)


def is_deepgram_retryable(exc: Exception) -> bool:
    """Return True if *exc* is a transient Deepgram failure worth retrying.

    Retryable categories (in order of likelihood):
        1. HTTP transport errors (timeout, connection reset, DNS failure)
        2. HTTP 429 (rate limited)
        3. HTTP 5xx (server-side outage)
        4. Generic network/IO errors

    Non-retryable (fail immediately):
        - 4xx except 429 (invalid API key, bad request, auth failure)
        - Any non-Deepgram, non-transport exception
        - Validation/contract errors
    """
    # ── Transport / network errors (always retryable) ──────────
    if isinstance(exc, TRANSPORT_ERRORS):
        log.debug("Retryable transport error: %s", type(exc).__name__)
        return True

    # ── Deepgram SDK errors with HTTP status codes ─────────────
    status = _extract_status_code(exc)
    if status is not None:
        if status == 429 or status >= 500:
            log.debug("Retryable HTTP %s", status)
            return True
        # 4xx except 429 is permanent
        log.debug("Non-retryable HTTP %s", status)
        return False

    # ── IO / network errors (fallback) ─────────────────────────
    if isinstance(exc, (OSError, ConnectionError)):
        log.debug("Retryable network error: %s", type(exc).__name__)
        return True

    return False


def _extract_status_code(exc: Exception) -> int | None:
    """Try to extract an HTTP status code from a Deepgram SDK exception."""
    status = getattr(exc, "status", None) or getattr(exc, "status_code", None)
    if isinstance(status, int):
        return status

    # Some SDKs nest the status code deeper
    if hasattr(exc, "response") and hasattr(exc.response, "status_code"):
        return exc.response.status_code

    return None
