"""LLM-powered call analysis: scoring, flagging, and quote verification.

All prompts, schemas, and validators are imported from the central
guardrails module — no inline prompt strings or ad-hoc validation here.
"""

import logging

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage

from schemas.transcript import Turn, TranscriptOut

# ── Central guardrails imports ─────────────────────────────────
from guardrails.prompts import build_analysis_system, build_analysis_human
from guardrails.schemas import CallAnalysis, FlaggedFlag
from guardrails.validators import verify_all_quotes, validate_analysis_output
from guardrails.input_guards import validate_analysis_input

log = logging.getLogger("fitnova.tagging")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def build_transcript_text(turns: list[Turn]) -> str:
    """Flatten turns into a single string for LLM input and quote matching."""
    return "\n".join(
        f"[{t.start:.1f}s] {t.speaker}: {t.text}" for t in turns
    )


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
    company_facts: dict,
    google_api_key: str,
    quote_match_threshold: float = 0.6,
) -> tuple[dict, float, list[FlaggedFlag], list[FlaggedFlag]]:
    """Run the full LLM analysis pipeline on a transcript.

    Pipeline:
        1. Input guard — validate transcript before expensive LLM call
        2. Build prompts — from central guardrails registry
        3. LLM call — with structured output schema enforcement
        4. Output validation — structural checks on LLM response
        5. Quote verification — anti-hallucination fuzzy matching

    Returns (scores_dict, overall_score, verified_flags, discarded_flags).
    Raises RuntimeError on LLM failure, ValueError on input guard failure.
    """
    # ── GUARD: Validate analysis input ─────────────────────────
    input_check = validate_analysis_input(transcript.turns)
    input_check.raise_if_failed("Analysis input guard")

    full_text = build_transcript_text(transcript.turns)

    # ── Build prompts from central registry ────────────────────
    rubric_text = build_rubric_prompt(rubric)
    system_prompt = build_analysis_system(
        company_facts=company_facts,
        rubric_text=rubric_text,
    )
    human_prompt = build_analysis_human(full_text)

    # ── LLM call with structured output enforcement ────────────
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
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

    # ── VALIDATOR: Structural checks on LLM output ─────────────
    output_check = validate_analysis_output(analysis)
    for w in output_check.warnings:
        log.warning(f"Analysis output: {w}")
    if not output_check.ok:
        log.error(f"Analysis output validation failed: {output_check.errors}")
        # Don't hard-fail — log errors but proceed with what we have

    # ── VALIDATOR: Quote verification (anti-hallucination) ─────
    verified_flags, discarded_flags = verify_all_quotes(
        flags=analysis.flags,
        transcript_text=full_text,
        threshold=quote_match_threshold,
    )

    # ── Compute overall score ──────────────────────────────────
    scores_dict = analysis.scores.model_dump()
    overall = sum(s["score"] for s in scores_dict.values()) / len(scores_dict)

    return scores_dict, round(overall, 2), verified_flags, discarded_flags
