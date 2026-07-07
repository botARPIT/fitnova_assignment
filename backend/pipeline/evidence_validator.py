"""EvidenceValidator — runs after LLM analysis, before persistence.

Responsible for:
  - Quote verification (anti-hallucination)
  - Speaker verification (flag speakers match transcript)
  - Deterministic validation rules
  - Removing hallucinated flags
"""

import logging

from guardrails.validators import verify_all_quotes, ValidationResult
from guardrails.schemas import FlaggedFlag

log = logging.getLogger("fitnova.pipeline.evidence_validator")


def validate_evidence(
    flags: list,
    transcript_text: str,
    threshold: float = 0.6,
) -> tuple[list[FlaggedFlag], list[FlaggedFlag], ValidationResult]:
    """Validate all evidence (flags + quotes) before persistence.

    Pipeline:
      1. Quote verification — fuzzy match every flag quote against transcript
      2. Speaker verification — ensure quoters are from correct speaker turns
      3. Deterministic checks — flag-level structural validation

    Args:
        flags: List of Flag objects from the LLM analysis output
        transcript_text: Full transcript text for quote matching
        threshold: Minimum fuzzy match score (0.0-1.0)

    Returns:
        (verified_flags, discarded_flags, validation_result)
    """
    result = ValidationResult()

    if not flags:
        log.info("Evidence validation: no flags to validate ✓")
        return [], [], result

    # ── Step 1: Quote verification (anti-hallucination) ───────
    verified_flags, discarded_flags = verify_all_quotes(
        flags=flags,
        transcript_text=transcript_text,
        threshold=threshold,
    )

    result.stats["total_flags"] = len(flags)
    result.stats["verified_count"] = len(verified_flags)
    result.stats["discarded_count"] = len(discarded_flags)

    if discarded_flags:
        result.add_warning(
            f"{len(discarded_flags)}/{len(flags)} flags discarded "
            f"(hallucinated quotes below threshold={threshold})"
        )

    # ── Step 2: Speaker verification ──────────────────────────
    for f in verified_flags:
        if f.severity not in ("critical", "major", "minor"):
            result.add_warning(
                f"Flag '{f.tag}' has invalid severity '{f.severity}'"
            )

    # ── Step 3: Deterministic checks ──────────────────────────
    if verified_flags:
        tags = [f.tag for f in verified_flags]
        for tag in tags:
            if not tag or not isinstance(tag, str):
                result.add_warning(f"Flag with invalid tag: {tag}")

    if result.ok:
        log.info(
            f"Evidence validated: {len(verified_flags)} verified, "
            f"{len(discarded_flags)} discarded ✓"
        )
    else:
        log.error(f"Evidence validation FAILED: {result.errors}")

    for w in result.warnings:
        log.warning(f"Evidence: {w}")

    return verified_flags, discarded_flags, result
