"""Pipeline error types — every failure mode has a dedicated exception."""

from fastapi import HTTPException


class PipelineError(HTTPException):
    """Base for all pipeline errors. Maps to HTTP error responses."""

    def __init__(self, status_code: int = 500, detail: str = "Pipeline error"):
        super().__init__(status_code=status_code, detail=detail)


class AudioValidationError(PipelineError):
    def __init__(self, reason: str):
        super().__init__(status_code=422, detail="Audio input failed validation.")
        self.reason = reason


class IngestionError(PipelineError):
    def __init__(self, reason: str):
        super().__init__(status_code=500, detail="Unable to ingest the uploaded file.")
        self.reason = reason


class TranscriptionError(PipelineError):
    def __init__(self, reason: str):
        super().__init__(status_code=502, detail="Transcription provider request failed.")
        self.reason = reason


class SpeakerRepairError(PipelineError):
    def __init__(self, reason: str):
        super().__init__(status_code=502, detail="Speaker attribution step failed.")
        self.reason = reason


class ConversationValidationError(PipelineError):
    def __init__(self, reason: str):
        super().__init__(status_code=422, detail="Transcript content failed validation.")
        self.reason = reason


class AnalysisError(PipelineError):
    def __init__(self, reason: str):
        super().__init__(status_code=502, detail="Analysis provider request failed.")
        self.reason = reason


class PersistenceError(PipelineError):
    def __init__(self, reason: str):
        super().__init__(status_code=500, detail="Unable to persist call results.")
        self.reason = reason


class ReviewError(PipelineError):
    """Raised when a review operation fails (duplicate contest, invalid flag, etc)."""
    def __init__(self, reason: str):
        super().__init__(status_code=400, detail=reason)


class ReviewPermissionError(PipelineError):
    """Raised when an advisor lacks permission for a review action."""
    def __init__(self, reason: str = "Insufficient permissions"):
        super().__init__(status_code=403, detail=reason)


class ReviewNotFoundError(PipelineError):
    """Raised when a review or flag is not found."""
    def __init__(self, reason: str = "Review not found"):
        super().__init__(status_code=404, detail=reason)


class CallConflictError(PipelineError):
    """Raised when a call is already being processed."""
    def __init__(self, call_id: str, detail: str = "Call is already being processed"):
        super().__init__(status_code=409, detail=detail)
        self.call_id = call_id
