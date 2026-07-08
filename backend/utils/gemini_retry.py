"""Gemini-specific retry classification.

Knows only about Google API exceptions and LangChain invocation errors.
"""

import logging

log = logging.getLogger("fitnova.retry.gemini")

# ── Retryable Google API error codes ────────────────────────────

RETRYABLE_CODES = frozenset({
    429,  # rate limit / quota exhausted
    500,  # internal server error
    502,  # bad gateway
    503,  # service unavailable
    504,  # gateway timeout
})

RETRYABLE_GOOGLE_ERRORS = (
    "DeadlineExceeded",
    "ServiceUnavailable",
    "TooManyRequests",
    "InternalServerError",
    "BadGateway",
    "GatewayTimeout",
    "RetryError",
)


def is_gemini_retryable(exc: Exception) -> bool:
    """Return True if *exc* is a transient Gemini failure worth retrying.

    Retryable:
        - Transport/network failures (connection, timeout)
        - Google API errors with retryable status codes (429, 5xx)
        - Deadline exceeded
        - Rate limiting

    Non-retryable:
        - Pydantic/schema validation errors (happen after LLM response)
        - Authentication errors (401/403)
        - InvalidArgument (400) — indicates bad request
        - Quote/evidence validation errors (deterministic logic)
        - JSON decode errors from parsing LLM output
    """
    # ── Pydantic / schema errors — NEVER retry ─────────────────
    if _is_validation_error(exc):
        return False

    # ── Network / transport errors — always retryable ──────────
    if _is_transport_error(exc):
        return True

    # ── Google API errors — check status code ──────────────────
    status = _extract_google_status(exc)
    if status is not None:
        if status in RETRYABLE_CODES:
            log.debug("Retryable Google API error (status=%s)", status)
            return True
        # 400, 401, 403, 404 → permanent
        log.debug("Non-retryable Google API error (status=%s)", status)
        return False

    # ── Try matching by error class name ───────────────────────
    exc_name = type(exc).__name__
    for retryable in RETRYABLE_GOOGLE_ERRORS:
        if retryable in exc_name:
            return True

    return False


def _is_validation_error(exc: Exception) -> bool:
    """Detect Pydantic / schema / deterministic validation errors."""
    exc_name = type(exc).__name__
    # Pydantic
    if "ValidationError" in exc_name:
        return True
    # LangChain output parser
    if "OutputParserException" in exc_name:
        return True
    # JSON decoding
    if isinstance(exc, (ValueError, TypeError, KeyError)):
        return True
    return False


def _is_transport_error(exc: Exception) -> bool:
    """Detect network-level transport failures."""
    import httpx

    return isinstance(exc, (
        httpx.TimeoutException,
        httpx.ConnectError,
        httpx.RemoteProtocolError,
        ConnectionResetError,
        TimeoutError,
        ConnectionError,
        OSError,
    ))


def _extract_google_status(exc: Exception) -> int | None:
    """Extract HTTP status code from a Google API exception."""
    status = getattr(exc, "status_code", None) or getattr(exc, "code", None)
    if isinstance(status, int):
        return status

    # google.api_core.exceptions wrap a `grpc.StatusCode` or similar
    if hasattr(exc, "grpc_status_code") and exc.grpc_status_code is not None:
        from grpc import StatusCode as GrpcStatusCode
        mapping = {
            GrpcStatusCode.DEADLINE_EXCEEDED: 504,
            GrpcStatusCode.UNAVAILABLE: 503,
            GrpcStatusCode.RESOURCE_EXHAUSTED: 429,
            GrpcStatusCode.INTERNAL: 500,
            GrpcStatusCode.UNAUTHENTICATED: 401,
            GrpcStatusCode.PERMISSION_DENIED: 403,
            GrpcStatusCode.INVALID_ARGUMENT: 400,
        }
        return mapping.get(exc.grpc_status_code)

    return None
