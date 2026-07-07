"""Source-agnostic ingestion layer.

Abstracts the mechanism for receiving call audio so that the pipeline
works identically regardless of whether audio arrives via:
  - Direct file upload (current prototype)
  - Telephony webhook (Twilio, Exotel, etc.)
  - CRM export (Salesforce, Zoho, etc.)
  - Cloud storage bucket (S3, GCS)

To add a new source, implement the IngestAdapter ABC and register it
in the ADAPTERS dict at the bottom of this file.
"""

import logging
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

log = logging.getLogger("fitnova.ingestion")


# ── Data contract ────────────────────────────────────────────

@dataclass
class CallMetadata:
    """Standardized metadata for an ingested call, regardless of source."""
    call_id: str
    audio_path: str              # Local path where audio was saved
    audio_bytes: bytes           # Raw audio content
    file_extension: str          # e.g. "wav", "mp3", "m4a"
    source: str                  # Which adapter produced this
    advisor_id: Optional[str] = None
    organization_id: Optional[str] = None
    external_call_id: Optional[str] = None  # ID from external system
    language_hint: Optional[str] = None


# ── Abstract adapter ─────────────────────────────────────────

class IngestAdapter(ABC):
    """Base class for all ingestion sources.
    
    Each adapter knows how to receive audio from one source type
    and normalize it into a CallMetadata object.
    """

    @abstractmethod
    async def ingest(self, **kwargs) -> CallMetadata:
        """Receive and process audio from this source.
        
        Returns a CallMetadata with the audio saved to disk.
        """
        ...

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Human-readable name for this source (e.g., 'file_upload', 'twilio')."""
        ...


# ── File Upload Adapter (production) ─────────────────────────

class FileUploadAdapter(IngestAdapter):
    """Handles direct file uploads via the API.
    
    This is the primary adapter for the prototype. Audio arrives as
    a multipart form upload and is saved to the local upload directory.
    """

    def __init__(self, upload_dir: Path):
        self.upload_dir = upload_dir
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    @property
    def source_name(self) -> str:
        return "file_upload"

    async def ingest(
        self,
        *,
        filename: str,
        raw_bytes: bytes,
        advisor_id: str | None = None,
        organization_id: str | None = None,
    ) -> CallMetadata:
        """Save uploaded audio and return standardized metadata."""
        # Validate extension
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext not in ("wav", "mp3", "m4a"):
            raise ValueError(f"Unsupported format '.{ext}'. Use wav, mp3, or m4a.")

        call_id = str(uuid.uuid4())
        audio_path = self.upload_dir / f"{call_id}.{ext}"
        audio_path.write_bytes(raw_bytes)

        log.info(f"[{self.source_name}] Ingested {filename} → {audio_path} ({len(raw_bytes)} bytes)")

        return CallMetadata(
            call_id=call_id,
            audio_path=str(audio_path),
            audio_bytes=raw_bytes,
            file_extension=ext,
            source=self.source_name,
            advisor_id=advisor_id,
            organization_id=organization_id,
        )


# ── Webhook Adapter (stub — for future telephony integration) ──

class WebhookAdapter(IngestAdapter):
    """Handles audio received via telephony webhooks (Twilio, Exotel, etc.).
    
    In production, this would:
    1. Validate the webhook signature
    2. Download the recording URL
    3. Extract metadata (caller ID, duration, agent extension)
    4. Map agent extension → advisor_id
    """

    @property
    def source_name(self) -> str:
        return "webhook"

    async def ingest(self, **kwargs) -> CallMetadata:
        raise NotImplementedError(
            "Webhook ingestion is a stub. In production, this would "
            "download the recording from the telephony provider's URL "
            "and extract call metadata from the webhook payload."
        )


# ── CRM Export Adapter (stub — for future CRM integration) ───

class CRMExportAdapter(IngestAdapter):
    """Handles audio from CRM bulk exports (Salesforce, Zoho, etc.).
    
    In production, this would:
    1. Poll a CRM API or watch an S3 bucket for new recordings
    2. Download audio files
    3. Extract metadata from the CRM record (lead ID, advisor, timestamp)
    4. Match CRM advisor → internal advisor_id
    """

    @property
    def source_name(self) -> str:
        return "crm_export"

    async def ingest(self, **kwargs) -> CallMetadata:
        raise NotImplementedError(
            "CRM export ingestion is a stub. In production, this would "
            "poll a CRM API for new call recordings and map them to advisors."
        )


# ── Adapter Registry ─────────────────────────────────────────

def get_adapter(source: str, upload_dir: Path) -> IngestAdapter:
    """Factory function to get the appropriate ingestion adapter.
    
    New sources can be added by:
    1. Implementing IngestAdapter
    2. Adding to this registry
    
    No other code changes required — the pipeline is source-agnostic.
    """
    adapters = {
        "file_upload": lambda: FileUploadAdapter(upload_dir),
        "webhook": lambda: WebhookAdapter(),
        "crm_export": lambda: CRMExportAdapter(),
    }
    
    if source not in adapters:
        raise ValueError(f"Unknown ingestion source: '{source}'. Available: {list(adapters.keys())}")
    
    return adapters[source]()
