"""LLM-powered speaker diarization repair using OpenAI with Gemini fallback.

Takes raw STT transcript (often with broken speaker labels on mono audio)
and re-assigns speakers using conversational context.

All prompts and schemas are imported from the central guardrails module.
"""

import logging
import json

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage

from config import settings
from schemas.transcript import Turn

# ── Central guardrails imports ─────────────────────────────────
from guardrails.prompts import SPEAKER_REPAIR_SYSTEM, build_speaker_repair_human
from guardrails.schemas import RepairedTurn, SpeakerRepairOutput
from guardrails.validators import validate_repair_output

log = logging.getLogger("fitnova.speaker_repair")


def _build_messages(input_text: str):
    return [
        SystemMessage(content=SPEAKER_REPAIR_SYSTEM),
        HumanMessage(content=build_speaker_repair_human(input_text)),
    ]


def _invoke_openai_speaker_repair(input_text: str) -> SpeakerRepairOutput:
    try:
        from langchain_openai import ChatOpenAI
    except ImportError as exc:
        raise RuntimeError(
            "OpenAI speaker repair requested but langchain_openai is not installed in the backend environment"
        ) from exc

    llm = ChatOpenAI(
        model=settings.speaker_repair_primary_model,
        temperature=0,
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
    )
    structured_llm = llm.with_structured_output(SpeakerRepairOutput)
    return structured_llm.invoke(_build_messages(input_text))


def _invoke_gemini_speaker_repair(
    input_text: str,
    google_api_key: str,
    model_name: str,
) -> SpeakerRepairOutput:
    llm = ChatGoogleGenerativeAI(
        model=model_name,
        temperature=0,
        google_api_key=google_api_key,
    )
    structured_llm = llm.with_structured_output(SpeakerRepairOutput)
    return structured_llm.invoke(_build_messages(input_text))


def repair_speakers(
    raw_turns: list[Turn],
    google_api_key: str,
    model_name: str,
) -> list[Turn]:
    """Re-diarize a transcript using Gemini.

    Pipeline:
        1. Format input turns for LLM
        2. Call Gemini with centralized prompt
        3. Parse JSON response into schema-validated RepairedTurn objects
        4. Run output validator (3rd speaker detection, text preservation, etc.)
        5. Convert back to Turn objects for downstream consumption

    Args:
        raw_turns: List of Turn objects from the STT engine (possibly with
                   broken speaker labels).
        google_api_key: Google API key for Gemini.
        model_name: Configured Gemini model for speaker repair.

    Returns:
        List of Turn objects with corrected speaker labels ("Advisor"/"Customer").

    Raises:
        RuntimeError: If Gemini returns invalid output.
    """
    if not raw_turns:
        return []

    # ── Build input text ───────────────────────────────────────
    input_lines = []
    for t in raw_turns:
        input_lines.append(f"[{t.start:.1f}s – {t.end:.1f}s] {t.speaker}: {t.text}")

    input_text = "\n".join(input_lines)

    provider_used = "gemini"
    try:
        if settings.openai_api_key:
            provider_used = "openai"
            response = _invoke_openai_speaker_repair(input_text)
            log.info(
                "Speaker repair completed with primary provider: OpenAI (%s)",
                settings.speaker_repair_primary_model,
            )
        else:
            response = _invoke_gemini_speaker_repair(
                input_text=input_text,
                google_api_key=google_api_key,
                model_name=model_name,
            )
            log.info("Speaker repair completed with fallback-only provider: Gemini (%s)", model_name)
    except Exception as e:
        if settings.openai_api_key:
            if settings.log_tracebacks:
                log.warning(
                    "OpenAI speaker repair failed, falling back to Gemini: %s",
                    str(e) or type(e).__name__,
                    exc_info=True,
                )
            else:
                log.warning(
                    "OpenAI speaker repair failed, falling back to Gemini: %s",
                    type(e).__name__,
                )
            provider_used = "gemini"
            try:
                response = _invoke_gemini_speaker_repair(
                    input_text=input_text,
                    google_api_key=google_api_key,
                    model_name=model_name,
                )
                log.info("Speaker repair fallback succeeded with Gemini (%s)", model_name)
            except Exception as fallback_exc:
                if settings.log_tracebacks:
                    log.error(
                        "Gemini speaker repair fallback failed: %s",
                        str(fallback_exc) or type(fallback_exc).__name__,
                        exc_info=True,
                    )
                else:
                    log.error(
                        "Gemini speaker repair fallback failed: %s",
                        type(fallback_exc).__name__,
                    )
                raise RuntimeError(f"Speaker repair failed: {fallback_exc}") from fallback_exc
        else:
            if settings.log_tracebacks:
                log.error("Gemini speaker repair failed: %s", str(e) or type(e).__name__, exc_info=True)
            else:
                log.error("Gemini speaker repair failed: %s", type(e).__name__)
            raise RuntimeError(f"Speaker repair failed: {e}") from e

    repaired_turns = []
    for i, validated in enumerate(response.turns):
        # Map invalid speakers to "Customer" before schema validation
        speaker = validated.speaker.value if hasattr(validated.speaker, "value") else str(validated.speaker)
        if speaker not in ("Advisor", "Customer"):
            log.warning(f"Turn {i}: invalid speaker '{speaker}' → mapping to 'Customer'")
            repaired_turns.append(RepairedTurn(
                speaker="Customer",
                start=validated.start,
                end=max(validated.end, validated.start),
                text=validated.text or "[empty]",
            ))
            continue

        repaired_turns.append(validated)

    # ── Output validator ───────────────────────────────────────
    validation = validate_repair_output(
        repaired_turns=repaired_turns,
        original_turns=raw_turns,
    )

    # Log validation results (warnings don't block, errors are logged)
    for w in validation.warnings:
        log.warning(f"Repair validation: {w}")
    if not validation.ok:
        log.error(f"Repair validation FAILED: {validation.errors}")
        # Don't hard-fail — the repaired output may still be usable
        # The validator catches issues like 3rd-speaker hallucination

    # ── Convert back to Turn objects ───────────────────────────
    result_turns = []
    for rt in repaired_turns:
        speaker_str = rt.speaker.value if hasattr(rt.speaker, 'value') else str(rt.speaker)
        result_turns.append(Turn(
            speaker=speaker_str,
            start=rt.start,
            end=rt.end,
            text=rt.text,
        ))

    if settings.log_sensitive_details:
        log.info(
            "LLM-corrected diarization output:\n%s",
            json.dumps(
                [turn.model_dump() for turn in result_turns],
                ensure_ascii=False,
                indent=2,
            ),
        )

    log.info(
        f"Speaker repair complete: {len(raw_turns)} → {len(result_turns)} turns, "
        f"speakers={set(t.speaker for t in result_turns)}, "
        f"provider={provider_used}, "
        f"validation={'✓' if validation.ok else '⚠ (see warnings)'}"
    )
    return result_turns
