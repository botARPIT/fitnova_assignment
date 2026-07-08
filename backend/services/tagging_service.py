"""LLM-powered call analysis: scoring, flagging, and quote verification.

All prompts, schemas, and validators are imported from the central
guardrails module — no inline prompt strings or ad-hoc validation here.
"""

import logging

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage

from config import settings
from schemas.transcript import Turn, TranscriptOut

# ── Central guardrails imports ─────────────────────────────────
from guardrails.prompts import build_analysis_system, build_analysis_human
from guardrails.schemas import CallAnalysis, FlaggedFlag
from guardrails.validators import verify_all_quotes, validate_analysis_output
from guardrails.input_guards import validate_analysis_input
from utils.gemini_retry import is_gemini_retryable
from utils.retry import retry_async

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

async def analyze_call(
    transcript: TranscriptOut,
    rubric: dict,
    company_facts: dict,
    google_api_key: str,
    model_name: str,
    quote_match_threshold: float = 0.6,
    gemini_max_retries: int = 2,
    retry_base_delay_ms: int = 1000,
) -> tuple[dict, float, list[FlaggedFlag], list[FlaggedFlag]]:
    """Run the full LLM analysis pipeline on a transcript.

    Pipeline:
        1. Input guard — validate transcript before expensive LLM call
        2. Build prompts — from central guardrails registry
        3. LLM call (retryable) — with structured output schema enforcement
        4. Output validation — structural checks on LLM response  (never retried)
        5. Quote verification — anti-hallucination fuzzy matching  (never retried)

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
        model=model_name,
        temperature=0,
        google_api_key=google_api_key,
    )
    structured_llm = llm.with_structured_output(CallAnalysis)

    base_delay = retry_base_delay_ms / 1000.0

    async def _invoke_llm():
        return await structured_llm.ainvoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=human_prompt),
        ])

    try:
        analysis: CallAnalysis = await retry_async(
            operation=_invoke_llm,
            is_retryable=is_gemini_retryable,
            max_attempts=gemini_max_retries,
            base_delay=base_delay,
            vendor="gemini",
            operation_name="analysis",
        )
    except Exception as e:
        if settings.log_tracebacks:
            log.error("LLM analysis failed after retries: %s", str(e) or type(e).__name__, exc_info=True)
        else:
            log.error("LLM analysis failed after retries: %s", type(e).__name__)
        raise RuntimeError(f"Analysis failed: {e}") from e

    # ── VALIDATOR: Structural checks on LLM output ─────────────
    # NOTE: This runs AFTER the retry block — never retry validation failures.
    output_check = validate_analysis_output(analysis)
    for w in output_check.warnings:
        log.warning(f"Analysis output: {w}")
    if not output_check.ok:
        if settings.log_sensitive_details:
            log.error(f"Analysis output validation failed: {output_check.errors}")
        else:
            log.error(
                "Analysis output validation failed (%d issue(s))",
                len(output_check.errors),
            )
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
