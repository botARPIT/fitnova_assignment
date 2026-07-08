"""PII redaction helpers for transcript persistence."""

from __future__ import annotations

import re

from schemas.transcript import Turn

PHONE_RE = re.compile(r"(?<!\w)(?:\+91[-\s]?)?[6-9]\d{9}(?!\w)")
EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
AADHAAR_RE = re.compile(r"(?<!\w)\d{4}[\s-]?\d{4}[\s-]?\d{4}(?!\w)")
PAN_RE = re.compile(r"(?<!\w)[A-Z]{5}\d{4}[A-Z](?!\w)")


def redact_text(text: str) -> str:
    """Redact common PII patterns from free text."""
    redacted = PHONE_RE.sub("[REDACTED_PHONE]", text)
    redacted = EMAIL_RE.sub("[REDACTED_EMAIL]", redacted)
    redacted = AADHAAR_RE.sub("[REDACTED_AADHAAR]", redacted)
    redacted = PAN_RE.sub("[REDACTED_PAN]", redacted)
    return redacted


def redact_turns(turns: list[Turn]) -> list[Turn]:
    """Return redacted copies of transcript turns."""
    return [
        Turn(
            speaker=t.speaker,
            start=t.start,
            end=t.end,
            text=redact_text(t.text),
        )
        for t in turns
    ]
