"""Pipeline error types — every failure mode has a dedicated exception."""

from fastapi import HTTPException


class PipelineError(HTTPException):
    """Base for all pipeline errors. Maps to HTTP error responses."""

    def __init__(self, status_code: int = 500, detail: str = "Pipeline error"):
        super().__init__(status_code=status_code, detail=detail)


class AudioValidationError(PipelineError):
    def __init__(self, reason: str):
        super().__init__(status_code=422, detail=f"Audio validation failed: {reason}")


class IngestionError(PipelineError):
    def __init__(self, reason: str):
        super().__init__(status_code=500, detail=f"Ingestion failed: {reason}")


class TranscriptionError(PipelineError):
    def __init__(self, reason: str):
        super().__init__(status_code=502, detail=f"Transcription failed: {reason}")


class SpeakerRepairError(PipelineError):
    def __init__(self, reason: str):
        super().__init__(status_code=502, detail=f"Speaker repair failed: {reason}")


class ConversationValidationError(PipelineError):
    def __init__(self, reason: str):
        super().__init__(status_code=422, detail=f"Conversation validation failed: {reason}")


class AnalysisError(PipelineError):
    def __init__(self, reason: str):
        super().__init__(status_code=502, detail=f"Analysis failed: {reason}")


class PersistenceError(PipelineError):
    def __init__(self, reason: str):
        super().__init__(status_code=500, detail=f"Persistence failed: {reason}")


class ReviewError(PipelineError):
    """Raised when a review operation fails (duplicate contest, invalid flag, etc)."""
    def __init__(self, reason: str):
        super().__init__(status_code=400, detail=f"Review error: {reason}")


class ReviewPermissionError(PipelineError):
    """Raised when an advisor lacks permission for a review action."""
    def __init__(self, reason: str = "Insufficient permissions"):
        super().__init__(status_code=403, detail=reason)


class ReviewNotFoundError(PipelineError):
    """Raised when a review or flag is not found."""
    def __init__(self, reason: str = "Review not found"):
        super().__init__(status_code=404, detail=reason)
