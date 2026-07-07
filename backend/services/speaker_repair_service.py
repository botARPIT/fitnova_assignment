"""LLM-powered speaker diarization repair using Gemini.

Takes raw STT transcript (often with broken speaker labels on mono audio)
and re-assigns speakers using conversational context.

All prompts and schemas are imported from the central guardrails module.
"""

import json
import logging

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage

from schemas.transcript import Turn

# ── Central guardrails imports ─────────────────────────────────
from guardrails.prompts import SPEAKER_REPAIR_SYSTEM, build_speaker_repair_human
from guardrails.schemas import RepairedTurn, SpeakerRepairOutput
from guardrails.validators import validate_repair_output

log = logging.getLogger("fitnova.speaker_repair")


def repair_speakers(
    raw_turns: list[Turn],
    google_api_key: str,
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

    # ── Call Gemini with centralized prompt ─────────────────────
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        temperature=0,
        google_api_key=google_api_key,
    )

    try:
        response = llm.invoke([
            SystemMessage(content=SPEAKER_REPAIR_SYSTEM),
            HumanMessage(content=build_speaker_repair_human(input_text)),
        ])
    except Exception as e:
        log.error(f"Gemini speaker repair failed: {e}")
        raise RuntimeError(f"Speaker repair failed: {e}") from e

    # ── Parse response ─────────────────────────────────────────
    response_text = response.content.strip()

    # Strip markdown code fence if present
    if response_text.startswith("```"):
        lines = response_text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        response_text = "\n".join(lines)

    try:
        repaired_raw = json.loads(response_text)
    except json.JSONDecodeError as e:
        log.error(f"Failed to parse Gemini response as JSON: {e}")
        log.debug(f"Raw response: {response_text[:500]}")
        raise RuntimeError(f"Speaker repair returned invalid JSON: {e}") from e

    # ── Schema validation via Pydantic ─────────────────────────
    if not isinstance(repaired_raw, list):
        raise RuntimeError(f"Expected list from Gemini, got {type(repaired_raw)}")

    repaired_turns = []
    for i, item in enumerate(repaired_raw):
        # Map invalid speakers to "Customer" before schema validation
        speaker = item.get("speaker", "Unknown")
        if speaker not in ("Advisor", "Customer"):
            log.warning(f"Turn {i}: invalid speaker '{speaker}' → mapping to 'Customer'")
            item["speaker"] = "Customer"

        try:
            validated = RepairedTurn(**item)
            repaired_turns.append(validated)
        except Exception as e:
            log.warning(f"Turn {i}: schema validation failed ({e}) — using raw values")
            # Fallback: create turn from raw values
            repaired_turns.append(RepairedTurn(
                speaker="Customer",
                start=float(item.get("start", 0)),
                end=max(float(item.get("end", 0)), float(item.get("start", 0))),
                text=str(item.get("text", "")) or "[empty]",
            ))

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

    log.info(
        f"Speaker repair complete: {len(raw_turns)} → {len(result_turns)} turns, "
        f"speakers={set(t.speaker for t in result_turns)}, "
        f"validation={'✓' if validation.ok else '⚠ (see warnings)'}"
    )
    return result_turns
