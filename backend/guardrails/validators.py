"""Output validators — post-processing verification for every LLM output.

These validators run AFTER LLM calls to catch hallucinations, structural
issues, and data quality problems before results are stored or displayed.

Validator hierarchy:
    Speaker Repair Output → validate_repair_output()
    Analysis Output       → validate_analysis_output()
    Quote Verification    → verify_quote() / verify_all_quotes()
"""

import logging
from dataclasses import dataclass, field

from config import settings
from rapidfuzz import fuzz

log = logging.getLogger("fitnova.guards.validators")


# ═══════════════════════════════════════════════════════════════════════════
# Validation Result
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class ValidationResult:
    """Result of output validation. Collects warnings and errors."""
    ok: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    stats: dict = field(default_factory=dict)

    def add_error(self, msg: str):
        self.errors.append(msg)
        self.ok = False

    def add_warning(self, msg: str):
        self.warnings.append(msg)

    def raise_if_failed(self, prefix: str = ""):
        if not self.ok:
            msg = f"{prefix}: {'; '.join(self.errors)}" if prefix else "; ".join(self.errors)
            raise ValueError(msg)


# ═══════════════════════════════════════════════════════════════════════════
# VALIDATOR 1: Speaker Repair Output
# Runs AFTER Gemini speaker repair
# ═══════════════════════════════════════════════════════════════════════════

VALID_SPEAKERS = {"Advisor", "Customer"}


def validate_repair_output(
    repaired_turns: list,
    original_turns: list,
    max_turn_drift: float = 0.3,
) -> ValidationResult:
    """Validate speaker repair output against the original transcript.

    Checks:
    1. Turn count hasn't changed drastically (LLM didn't merge/split)
    2. Only valid speakers exist (Advisor/Customer — no hallucinated 3rd)
    3. Timestamps are preserved (not invented)
    4. Text is preserved (not rewritten)
    5. At least some speaker diversity exists

    Args:
        repaired_turns: Turns from Gemini speaker repair
        original_turns: Turns from the STT engine (ground truth for text/timestamps)
        max_turn_drift: Max allowed fractional change in turn count (0.3 = 30%)
    """
    result = ValidationResult()

    if not repaired_turns:
        result.add_error("Speaker repair returned 0 turns")
        return result

    # ── Turn count drift ──────────────────────────────────────
    orig_count = len(original_turns)
    repair_count = len(repaired_turns)
    drift = abs(repair_count - orig_count) / max(orig_count, 1)

    result.stats["original_turn_count"] = orig_count
    result.stats["repaired_turn_count"] = repair_count
    result.stats["turn_count_drift"] = round(drift, 3)

    if drift > max_turn_drift:
        result.add_warning(
            f"Turn count changed significantly: {orig_count} → {repair_count} "
            f"(drift={drift:.1%}). LLM may have merged or split turns."
        )

    # ── Speaker validation (NO 3rd speaker) ───────────────────
    speakers = set()
    invalid_speakers = set()
    for t in repaired_turns:
        speaker = getattr(t, 'speaker', None)
        if isinstance(speaker, str):
            s = speaker
        else:
            # Enum type — get value
            s = speaker.value if hasattr(speaker, 'value') else str(speaker)
        speakers.add(s)
        if s not in VALID_SPEAKERS:
            invalid_speakers.add(s)

    result.stats["speakers_found"] = speakers

    if invalid_speakers:
        result.add_error(
            f"Invalid speaker(s) detected: {invalid_speakers}. "
            f"Only {VALID_SPEAKERS} are allowed. LLM hallucinated a 3rd party."
        )

    if len(speakers) == 1:
        result.add_warning(
            f"Only 1 speaker found ({speakers}). "
            f"Speaker repair may not have worked — all turns assigned to same person."
        )

    # ── Text preservation check ───────────────────────────────
    # Spot-check a few turns to ensure text wasn't rewritten
    check_count = min(5, len(repaired_turns), len(original_turns))
    text_changed = 0

    for i in range(check_count):
        orig_text = getattr(original_turns[i], 'text', '').strip()
        repair_text = getattr(repaired_turns[i], 'text', '').strip()

        if orig_text and repair_text:
            similarity = fuzz.ratio(orig_text, repair_text)
            if similarity < 80:
                text_changed += 1

    if text_changed > check_count * 0.5:
        result.add_warning(
            f"Text appears modified in {text_changed}/{check_count} spot-checked turns. "
            f"LLM may have rewritten content instead of just relabeling speakers."
        )

    # ── Timestamp preservation check ──────────────────────────
    if len(repaired_turns) == len(original_turns):
        timestamp_drift = 0
        for orig, rep in zip(original_turns[:check_count], repaired_turns[:check_count]):
            orig_start = getattr(orig, 'start', 0)
            rep_start = getattr(rep, 'start', 0)
            if abs(orig_start - rep_start) > 0.5:
                timestamp_drift += 1

        if timestamp_drift > 0:
            result.add_warning(
                f"Timestamps shifted in {timestamp_drift}/{check_count} spot-checked turns. "
                f"LLM may have invented timestamps."
            )

    # Log
    if result.ok:
        log.info(f"Repair output validated: {repair_count} turns, speakers={speakers} ✓")
    else:
        log.error(f"Repair output validation FAILED: {result.errors}")

    for w in result.warnings:
        log.warning(f"Repair validation warning: {w}")

    return result


# ═══════════════════════════════════════════════════════════════════════════
# VALIDATOR 2: Quote Verification (Anti-Hallucination)
# Runs AFTER analysis, before flags are stored
# ═══════════════════════════════════════════════════════════════════════════

def verify_quote(quote: str, full_text: str) -> float:
    """Fuzzy-match a quoted line against every line in the transcript.

    Uses rapidfuzz partial_ratio for substring matching.
    Returns the best score (0.0–1.0).

    Args:
        quote: The LLM-generated quote from a flag
        full_text: The complete transcript text to match against
    """
    if not quote or not full_text:
        return 0.0

    lines = full_text.split("\n")
    best = 0.0
    for line in lines:
        score = fuzz.partial_ratio(quote.lower(), line.lower()) / 100.0
        best = max(best, score)
        if best >= 0.95:  # Early exit on near-perfect match
            break
    return best


def match_quote_to_turn(quote: str, turns: list) -> tuple[int | None, float]:
    """Find the best matching transcript turn for a quoted excerpt."""
    if not quote or not turns:
        return None, 0.0

    best_index: int | None = None
    best_score = 0.0

    for index, turn in enumerate(turns):
        text = getattr(turn, "text", "") or ""
        if not text:
            continue
        score = fuzz.partial_ratio(quote.lower(), text.lower()) / 100.0
        if score > best_score:
            best_index = index
            best_score = score
            if best_score >= 0.98:
                break

    return best_index, best_score


def verify_all_quotes(
    flags: list,
    transcript_text: str,
    threshold: float = 0.6,
) -> tuple[list, list]:
    """Verify all flag quotes against the transcript.

    Splits flags into verified (quote found) and discarded (hallucinated).

    Args:
        flags: List of Flag objects from LLM analysis
        transcript_text: Full transcript text for matching
        threshold: Minimum fuzzy match score (0.0-1.0) to accept a quote

    Returns:
        (verified_flags, discarded_flags) — both as FlaggedFlag lists
    """
    from guardrails.schemas import FlaggedFlag

    verified = []
    discarded = []

    for f in flags:
        quoted = getattr(f, 'quote', '')
        match_score = verify_quote(quoted, transcript_text)

        flagged = FlaggedFlag(
            tag=f.tag.value if hasattr(f.tag, 'value') else str(f.tag),
            severity=f.severity.value if hasattr(f.severity, 'value') else str(f.severity),
            quote=f.quote,
            explanation=f.explanation,
            timestamp=f.timestamp,
            match_score=round(match_score, 2),
        )

        if match_score >= threshold:
            verified.append(flagged)
        else:
            flagged.discard_reason = (
                f"Quote match score {match_score:.2f} below threshold {threshold:.2f}"
            )
            if settings.log_sensitive_details:
                log.warning(
                    f"DISCARDED hallucinated flag: tag={flagged.tag}, "
                    f"match={match_score:.0%} < {threshold:.0%}"
                )
            else:
                log.warning(
                    "Discarded unsupported flag: tag=%s match=%s threshold=%s",
                    flagged.tag,
                    f"{match_score:.0%}",
                    f"{threshold:.0%}",
                )
            discarded.append(flagged)

    log.info(
        f"Quote verification: {len(verified)} verified, "
        f"{len(discarded)} discarded (threshold={threshold:.0%})"
    )
    return verified, discarded


# ═══════════════════════════════════════════════════════════════════════════
# VALIDATOR 3: Analysis Output Structural Validation
# Runs AFTER LLM structured output parsing
# ═══════════════════════════════════════════════════════════════════════════

VALID_DIMENSIONS = {
    "needs_discovery", "product_knowledge", "objection_handling",
    "compliance", "next_step_booking",
}


def validate_analysis_output(analysis) -> ValidationResult:
    """Validate the structural integrity of the LLM analysis output.

    Checks:
    1. All 5 dimensions are scored
    2. Scores are within 0-5 range (Pydantic handles this, but double-check)
    3. Flags use valid tags from the taxonomy
    4. Flags have non-empty quotes and reasons
    5. Overall score is reasonable

    Args:
        analysis: CallAnalysis Pydantic model from LLM
    """
    result = ValidationResult()

    # ── Scores validation ─────────────────────────────────────
    scores_dict = analysis.scores.model_dump() if hasattr(analysis.scores, 'model_dump') else {}
    scored_dims = set(scores_dict.keys())
    missing_dims = VALID_DIMENSIONS - scored_dims

    if missing_dims:
        result.add_error(f"Missing dimension scores: {missing_dims}")

    for dim, entry in scores_dict.items():
        if isinstance(entry, dict):
            score = entry.get("score", -1)
            evidence = entry.get("evidence", "")
            if not isinstance(score, (int, float)):
                result.add_error(f"Score for '{dim}' is not numeric: {score}")
            elif score < 0 or score > 5:
                result.add_error(f"Score for '{dim}' out of range: {score} (must be 0-5)")
            if not evidence:
                result.add_warning(f"Dimension '{dim}' has no evidence text")
        else:
            result.add_error(f"Score for '{dim}' is not a dict: {entry}")

    # Overall score check
    if scores_dict:
        values = []
        for entry in scores_dict.values():
            if isinstance(entry, dict):
                s = entry.get("score", -1)
                if isinstance(s, (int, float)):
                    values.append(float(s))
        if values:
            overall = sum(values) / len(values)
            result.stats["computed_overall"] = round(overall, 2)

            # Sanity: if all scores are 5 but there are flags, something's wrong
            if overall >= 4.5 and len(analysis.flags) > 2:
                result.add_warning(
                    f"High score ({overall:.1f}) with {len(analysis.flags)} flags — "
                    f"scores and flags may be inconsistent."
                )

    # ── Flag validation ───────────────────────────────────────
    from guardrails.schemas import IssueTag
    valid_tags = {t.value for t in IssueTag}

    for i, flag in enumerate(analysis.flags):
        tag_value = flag.tag.value if hasattr(flag.tag, 'value') else str(flag.tag)

        if tag_value not in valid_tags:
            result.add_error(f"Flag {i}: invalid tag '{tag_value}'. Valid: {valid_tags}")

        if not flag.quote or len(flag.quote.strip()) < 5:
            result.add_error(f"Flag {i} ({tag_value}): quote is empty or too short")

        if not flag.explanation or len(flag.explanation.strip()) < 5:
            result.add_warning(f"Flag {i} ({tag_value}): explanation is empty or too short")

    result.stats["flag_count"] = len(analysis.flags)
    result.stats["dimension_count"] = len(scored_dims)

    if result.ok:
        log.info(
            f"Analysis output validated: {len(scored_dims)} dims, "
            f"{len(analysis.flags)} flags ✓"
        )
    else:
        log.error(f"Analysis output validation FAILED: {result.errors}")

    for w in result.warnings:
        log.warning(f"Analysis validation warning: {w}")

    return result
