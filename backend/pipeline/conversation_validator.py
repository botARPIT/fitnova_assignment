"""ConversationValidator — runs after speaker repair, before analysis.

Validates that the repaired transcript is structurally sound
enough for meaningful analysis.
"""

import logging

from guardrails.validators import ValidationResult
from schemas.transcript import Turn

log = logging.getLogger("fitnova.pipeline.conversation_validator")

VALID_SPEAKERS = {"Advisor", "Customer"}


def validate_conversation(turns: list[Turn]) -> ValidationResult:
    """Validate a repaired transcript before sending to analysis.

    Checks:
    1. Exactly two speakers (Advisor, Customer)
    2. Chronological timestamps (start <= end, no negative durations)
    3. Valid speaker labels
    4. Non-empty turns
    5. No negative durations

    Args:
        turns: List of Turn objects from speaker repair

    Returns:
        ValidationResult with errors/warnings
    """
    result = ValidationResult()

    if not turns:
        result.add_error("Conversation has zero turns")
        return result

    # ── Speaker validation ──────────────────────────────────────
    speakers = {t.speaker for t in turns}
    invalid = speakers - VALID_SPEAKERS
    if invalid:
        result.add_error(
            f"Invalid speaker(s): {invalid}. Only {VALID_SPEAKERS} allowed."
        )

    if len(speakers) < 2:
        result.add_warning(
            f"Only {len(speakers)} speaker(s) found: {speakers}. "
            "Expected both Advisor and Customer."
        )

    # ── Timestamp validation ────────────────────────────────────
    negative_durations = 0
    non_chronological = 0
    last_end = 0.0

    for i, t in enumerate(turns):
        if t.end < t.start:
            negative_durations += 1
            result.add_warning(f"Turn {i}: negative duration (start={t.start}, end={t.end})")

        if t.start < last_end - 0.01:
            non_chronological += 1

        if t.end > last_end:
            last_end = t.end

    if negative_durations > 0:
        result.add_error(f"{negative_durations} turn(s) have negative duration")

    if non_chronological > len(turns) * 0.5:
        result.add_error(
            f"{non_chronological}/{len(turns)} turns are non-chronological"
        )
    elif non_chronological > 0:
        result.add_warning(f"{non_chronological} turn(s) are non-chronological")

    # ── Non-empty turns ─────────────────────────────────────────
    empty_turns = [i for i, t in enumerate(turns) if not t.text.strip()]
    if empty_turns:
        result.add_warning(f"{len(empty_turns)} turn(s) have empty text: indices {empty_turns}")

    # ── Logging ─────────────────────────────────────────────────
    if result.ok:
        log.info(
            f"Conversation validated: {len(turns)} turns, "
            f"speakers={speakers} ✓"
        )
    else:
        log.error(f"Conversation validation FAILED: {result.errors}")

    for w in result.warnings:
        log.warning(f"Conversation: {w}")

    return result
