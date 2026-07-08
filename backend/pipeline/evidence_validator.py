"""EvidenceValidator — runs after LLM analysis, before persistence."""

import logging

from guardrails.validators import ValidationResult, match_quote_to_turn
from guardrails.schemas import FlaggedFlag
from pipeline.company_facts_validator import validate_flag_against_company_facts
from schemas.transcript import Turn

log = logging.getLogger("fitnova.pipeline.evidence_validator")


def _flag_attr(flag, name: str, default=None):
    value = getattr(flag, name, default)
    return value.value if hasattr(value, "value") else value


def _to_flagged_flag(
    flag,
    *,
    match_score: float,
    discard_reason: str | None = None,
    matched_turn_index: int | None = None,
    matched_turn_speaker: str | None = None,
    matched_turn_start: float | None = None,
) -> FlaggedFlag:
    data = {
        "tag": _flag_attr(flag, "tag", ""),
        "severity": _flag_attr(flag, "severity", ""),
        "quote": _flag_attr(flag, "quote", ""),
        "explanation": _flag_attr(flag, "explanation", ""),
        "timestamp": _flag_attr(flag, "timestamp", 0.0),
        "match_score": round(match_score, 2),
        "discard_reason": discard_reason or _flag_attr(flag, "discard_reason"),
        "matched_turn_index": matched_turn_index,
        "matched_turn_speaker": matched_turn_speaker,
        "matched_turn_start": matched_turn_start,
    }
    flag_id = _flag_attr(flag, "flag_id")
    if flag_id:
        data["flag_id"] = flag_id
    return FlaggedFlag(**data)


def validate_evidence(
    flags: list,
    turns: list[Turn],
    company_facts: dict,
    threshold: float = 0.6,
    timestamp_tolerance_sec: float = 1.5,
) -> tuple[list[FlaggedFlag], list[FlaggedFlag], ValidationResult]:
    """Validate all evidence (flags + quotes) before persistence.

    Pipeline:
      1. Quote-to-turn resolution — fuzzy match every flag quote to a transcript turn
      2. Speaker verification — all current policy flags must match advisor turns
      3. Timestamp verification — LLM timestamp should align to the matched turn
      4. Company-facts checks — deterministic contradictions discard unsupported flags

    Args:
        flags: List of Flag objects from the LLM analysis output
        turns: Repaired transcript turns with speaker labels
        company_facts: Parsed company-facts registry used for deterministic checks
        threshold: Minimum fuzzy match score (0.0-1.0)

    Returns:
        (verified_flags, discarded_flags, validation_result)
    """
    result = ValidationResult()

    if not flags:
        log.info("Evidence validation: no flags to validate ✓")
        return [], [], result

    result.stats["total_flags"] = len(flags)
    verified_flags: list[FlaggedFlag] = []
    discarded_flags: list[FlaggedFlag] = []

    for flag in flags:
        quote = _flag_attr(flag, "quote", "")
        matched_turn_index, match_score = match_quote_to_turn(quote, turns)

        if matched_turn_index is None or match_score < threshold:
            discarded_flags.append(
                _to_flagged_flag(
                    flag,
                    match_score=match_score,
                    discard_reason=(
                        f"Quote match score {match_score:.2f} below threshold {threshold:.2f}"
                    ),
                )
            )
            continue

        matched_turn = turns[matched_turn_index]
        normalized_flag = _to_flagged_flag(
            flag,
            match_score=match_score,
            matched_turn_index=matched_turn_index,
            matched_turn_speaker=matched_turn.speaker,
            matched_turn_start=matched_turn.start,
        )

        if matched_turn.speaker != "Advisor":
            normalized_flag.discard_reason = (
                f"Matched quote belongs to speaker '{matched_turn.speaker}', not Advisor"
            )
            discarded_flags.append(normalized_flag)
            continue

        if abs(normalized_flag.timestamp - matched_turn.start) > timestamp_tolerance_sec:
            normalized_flag.discard_reason = (
                f"Flag timestamp {normalized_flag.timestamp:.2f}s does not align with "
                f"matched turn start {matched_turn.start:.2f}s"
            )
            discarded_flags.append(normalized_flag)
            continue

        company_reasons = validate_flag_against_company_facts(
            normalized_flag,
            matched_turn=matched_turn,
            prior_turns=turns[:matched_turn_index],
            company_facts=company_facts,
        )
        if company_reasons:
            normalized_flag.discard_reason = "; ".join(company_reasons)
            discarded_flags.append(normalized_flag)
            continue

        if normalized_flag.severity not in ("critical", "major", "minor"):
            result.add_warning(
                f"Flag '{normalized_flag.tag}' has invalid severity '{normalized_flag.severity}'"
            )

        if not normalized_flag.tag or not isinstance(normalized_flag.tag, str):
            result.add_warning(f"Flag with invalid tag: {normalized_flag.tag}")

        verified_flags.append(normalized_flag)

    result.stats["verified_count"] = len(verified_flags)
    result.stats["discarded_count"] = len(discarded_flags)

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
