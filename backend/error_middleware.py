"""Sanitized error wrapper — returns just {status_code, component} to clients.

Full error details (reason, traceback) are logged server-side only.
"""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from errors import (
    PipelineError,
    AudioValidationError,
    IngestionError,
    TranscriptionError,
    SpeakerRepairError,
    ConversationValidationError,
    AnalysisError,
    PersistenceError,
    CallConflictError,
    ReviewError,
    ReviewPermissionError,
    ReviewNotFoundError,
)

log = logging.getLogger("fitnova.error_middleware")

# ---------------------------------------------------------------------------
# Component mapping — each PipelineError subclass → short component name
# ---------------------------------------------------------------------------

ERROR_COMPONENT: dict[type[PipelineError], str] = {
    AudioValidationError: "audio_validation",
    IngestionError: "ingestion",
    TranscriptionError: "transcription",
    SpeakerRepairError: "speaker_repair",
    ConversationValidationError: "conversation_validation",
    AnalysisError: "analysis",
    PersistenceError: "persistence",
    CallConflictError: "call_conflict",
    ReviewError: "review",
    ReviewPermissionError: "review_permission",
    ReviewNotFoundError: "review_not_found",
}

ERROR_STATUS: dict[type[PipelineError], int] = {
    AudioValidationError: 422,
    IngestionError: 500,
    TranscriptionError: 502,
    SpeakerRepairError: 502,
    ConversationValidationError: 422,
    AnalysisError: 502,
    PersistenceError: 500,
    CallConflictError: 409,
    ReviewError: 400,
    ReviewPermissionError: 403,
    ReviewNotFoundError: 404,
}


def _sanitized_response(status_code: int, component: str, **extra) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"status_code": status_code, "component": component, **extra},
    )


def _get_component(exc: PipelineError) -> str:
    for exc_type, component in ERROR_COMPONENT.items():
        if isinstance(exc, exc_type):
            return component
    return "unknown"


def register_error_handlers(app: FastAPI, settings) -> None:
    """Register sanitized exception handlers for all known error types.

    Every handler returns ``{"status_code": …, "component": …}``.
    The full error reason / traceback is logged server-side only.
    """

    # ── Pipeline error handlers ─────────────────────────────────
    for exc_cls in ERROR_COMPONENT:

        def _make_handler(exc_type: type[PipelineError]) -> callable:
            component = ERROR_COMPONENT[exc_type]
            status = ERROR_STATUS[exc_type]

            def handler(_request: Request, exc: PipelineError) -> JSONResponse:
                reason = getattr(exc, "reason", None) or str(exc.detail)
                log.error("Pipeline error [%s]: %s", component, reason)

                extra = {}
                if isinstance(exc, CallConflictError):
                    extra["call_id"] = exc.call_id

                return _sanitized_response(status, component, **extra)

            return handler

        app.add_exception_handler(exc_cls, _make_handler(exc_cls))

    # ── Request validation ─────────────────────────────────────
    @app.exception_handler(RequestValidationError)
    async def handle_request_validation_error(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        if settings.log_validation_payloads:
            log.warning("Request validation failed: %s", exc.errors())
        else:
            log.warning("Request validation failed")
        return _sanitized_response(422, "request_validation")

    # ── Catch-all for any unhandled exception ──────────────────
    @app.exception_handler(Exception)
    async def handle_unexpected_error(
        _request: Request, exc: Exception
    ) -> JSONResponse:
        component = _get_component(exc) if isinstance(exc, PipelineError) else "unknown"
        status = getattr(exc, "status_code", 500)
        if not isinstance(status, int) or status < 100:
            status = 500

        if settings.log_tracebacks:
            log.error(
                "Unhandled error [%s]: %s",
                component,
                str(exc) or type(exc).__name__,
                exc_info=True,
            )
        else:
            log.error(
                "Unhandled error [%s]: %s",
                component,
                type(exc).__name__,
            )

        return _sanitized_response(status, component)
