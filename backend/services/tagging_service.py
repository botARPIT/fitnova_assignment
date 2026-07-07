"""LLM-powered call analysis: scoring, flagging, and quote verification."""

import logging

from rapidfuzz import fuzz
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage

from schemas.transcript import Turn, TranscriptOut
from schemas.flags import CallAnalysis, FlaggedFlag

log = logging.getLogger("fitnova.tagging")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def build_transcript_text(turns: list[Turn]) -> str:
    """Flatten turns into a single string for LLM input and quote matching."""
    return "\n".join(
        f"[{t.start:.1f}s] {t.speaker}: {t.text}" for t in turns
    )


def verify_quote(quote: str, full_text: str) -> float:
    """Fuzzy-match a quoted line against every line in the transcript.

    Returns the best partial_ratio score (0–100).
    """
    lines = full_text.split("\n")
    best = 0.0
    for line in lines:
        score = fuzz.partial_ratio(quote.lower(), line.lower())
        best = max(best, score)
    return best


def build_rubric_prompt(rubric: dict) -> str:
    """Format the rubric YAML dict into a readable prompt section."""
    parts = []
    for dim, info in rubric["dimensions"].items():
        parts.append(f"\n### {dim}")
        parts.append(info["description"])
        parts.append("Scoring guide:")
        for score, desc in info["scoring"].items():
            parts.append(f"  {score}: {desc}")
        if "example_good" in info:
            parts.append(f"Good example:\n{info['example_good'].strip()}")
        if "example_bad" in info:
            parts.append(f"Bad example:\n{info['example_bad'].strip()}")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Main analysis
# ---------------------------------------------------------------------------

def analyze_call(
    transcript: TranscriptOut,
    rubric: dict,
    company_facts: str,
    google_api_key: str,
    quote_match_threshold: int,
) -> tuple[dict, float, list[FlaggedFlag], list[FlaggedFlag]]:
    """Run the full LLM analysis pipeline on a transcript.

    Returns (scores_dict, overall_score, verified_flags, discarded_flags).
    Raises RuntimeError on LLM failure.
    """
    full_text = build_transcript_text(transcript.turns)

    # ── Build prompt ───────────────────────────────────────────
    system_prompt = f"""You are a quality analyst for FitNova, a fitness coaching company.
You will analyze a sales call transcript and:
1. Score the call on 5 rubric dimensions (0-5 each)
2. Flag any issues from the FIXED taxonomy — do NOT invent new tags

COMPANY FACTS (use this as ground truth for accuracy checks):
{company_facts}

SCORING RUBRIC:
{build_rubric_prompt(rubric)}

ISSUE TAG TAXONOMY (only these tags are valid):
- no_needs_discovery: Advisor didn't ask about customer needs/goals before pitching
- overpromising: Advisor made guarantees about results (e.g. "guaranteed weight loss")
- pressure_or_urgency_tactics: Advisor used artificial urgency or pressure to close
- price_before_value: Advisor discussed pricing before establishing value/needs
- undisclosed_costs: Advisor hid or failed to mention relevant costs
- weak_or_missing_trial_booking: Advisor didn't attempt to book the free trial
- talking_over_customer: Advisor interrupted or didn't let the customer speak

CRITICAL RULES:
- quoted_line MUST be an exact verbatim quote from the transcript — copy-paste, do not paraphrase
- timestamp must match the turn's start time from the transcript
- Only flag issues you can directly support with a quote from the transcript
- If the call is clean, return an empty flags list — do not force flags"""

    human_prompt = f"""Analyze this sales call transcript:

{full_text}"""

    # ── LLM call ───────────────────────────────────────────────
    llm = ChatGoogleGenerativeAI(
        model="gemini-3.5-flash",
        temperature=0,
        google_api_key=google_api_key,
    )
    structured_llm = llm.with_structured_output(CallAnalysis)

    try:
        analysis: CallAnalysis = structured_llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=human_prompt),
        ])
    except Exception as e:
        log.error(f"LLM error: {e}")
        raise RuntimeError(f"Analysis failed: {e}") from e

    # ── Post-processing: verify quotes ─────────────────────────
    verified_flags: list[FlaggedFlag] = []
    discarded_flags: list[FlaggedFlag] = []

    for f in analysis.flags:
        match_score = verify_quote(f.quoted_line, full_text)
        flagged = FlaggedFlag(
            tag=f.tag.value,
            severity=f.severity,
            quoted_line=f.quoted_line,
            reason=f.reason,
            timestamp=f.timestamp,
            match_score=round(match_score, 1),
        )

        if match_score >= quote_match_threshold:
            verified_flags.append(flagged)
        else:
            log.warning(
                f"Discarded hallucinated flag: tag={f.tag.value}, "
                f"match_score={match_score:.1f}, quote='{f.quoted_line[:60]}...'"
            )
            discarded_flags.append(flagged)

    # ── Compute overall score ──────────────────────────────────
    scores_dict = analysis.scores.model_dump()
    overall = sum(scores_dict.values()) / len(scores_dict)

    return scores_dict, round(overall, 2), verified_flags, discarded_flags
