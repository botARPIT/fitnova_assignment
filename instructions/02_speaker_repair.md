# Task 02: LLM Speaker Repair Service

## Objective
Create a Gemini-powered speaker repair service that takes raw STT output (from Deepgram) and produces properly diarized turns with correct speaker assignments. This solves the critical problem that Deepgram's diarization is broken on mono/single-channel audio.

## Parallelization
**Group A** — No dependencies. Can be executed immediately.

## Background
From our STT analysis:
- Deepgram outputs `speaker_0` for 90%+ of turns on mono audio
- LLM re-diarization (GPT/Gemini) correctly separates speakers ~90% of the time
- The LLM should assign exactly 2 speakers: "Advisor" and "Customer" (never hallucinate a 3rd)
- Output must be in the same `Turn` schema format the rest of the pipeline expects

## Files to Create

### 1. `backend/services/speaker_repair_service.py`

```python
"""LLM-powered speaker diarization repair using Gemini.

Takes raw STT transcript (often with broken speaker labels on mono audio)
and re-assigns speakers using conversational context.
"""

import json
import logging

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage

from schemas.transcript import Turn

log = logging.getLogger("fitnova.speaker_repair")


SYSTEM_PROMPT = """You are a diarization repair engine for sales call transcripts.

INPUT: A raw transcript from a speech-to-text engine. The speaker labels may be 
wrong, missing, or all assigned to one speaker (common on mono recordings).

YOUR TASK: Re-assign each line to the correct speaker using conversational context.

RULES:
1. There are EXACTLY 2 speakers in every call:
   - "Advisor" — the FitNova sales advisor who initiates the call
   - "Customer" — the person being called (the lead/prospect)
2. NEVER create a 3rd speaker. Even if someone mentions another person, 
   the call is always 2-party.
3. The Advisor typically:
   - Introduces themselves and FitNova
   - Asks discovery questions
   - Explains plans and pricing
   - Tries to book a trial session
4. The Customer typically:
   - Answers questions
   - Asks about pricing/details
   - Raises objections
   - Is initially unfamiliar with the call context
5. Keep the original text EXACTLY as-is. Do NOT modify, translate, or clean the text.
6. Keep the original timestamps EXACTLY as-is.

OUTPUT: Return a JSON array of objects, each with:
- "speaker": either "Advisor" or "Customer" 
- "start": the original start time (float)
- "end": the original end time (float)
- "text": the original text (unchanged)

Adjacent turns by the same speaker should remain separate — do not merge them."""


def repair_speakers(
    raw_turns: list[Turn],
    google_api_key: str,
) -> list[Turn]:
    """Re-diarize a transcript using Gemini.
    
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

    # Build input text
    input_lines = []
    for t in raw_turns:
        input_lines.append(f"[{t.start:.1f}s – {t.end:.1f}s] {t.speaker}: {t.text}")
    
    input_text = "\n".join(input_lines)

    # Call Gemini
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        temperature=0,
        google_api_key=google_api_key,
    )

    try:
        response = llm.invoke([
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=f"Repair the speaker labels in this transcript:\n\n{input_text}"),
        ])
    except Exception as e:
        log.error(f"Gemini speaker repair failed: {e}")
        raise RuntimeError(f"Speaker repair failed: {e}") from e

    # Parse response
    response_text = response.content.strip()
    
    # Strip markdown code fence if present
    if response_text.startswith("```"):
        lines = response_text.split("\n")
        # Remove first line (```json) and last line (```)
        lines = [l for l in lines if not l.strip().startswith("```")]
        response_text = "\n".join(lines)

    try:
        repaired = json.loads(response_text)
    except json.JSONDecodeError as e:
        log.error(f"Failed to parse Gemini response as JSON: {e}")
        log.debug(f"Raw response: {response_text[:500]}")
        raise RuntimeError(f"Speaker repair returned invalid JSON: {e}") from e

    # Validate and convert back to Turn objects
    if not isinstance(repaired, list):
        raise RuntimeError(f"Expected list from Gemini, got {type(repaired)}")

    repaired_turns = []
    valid_speakers = {"Advisor", "Customer"}
    
    for item in repaired:
        speaker = item.get("speaker", "Unknown")
        if speaker not in valid_speakers:
            log.warning(f"Invalid speaker '{speaker}' — mapping to 'Customer'")
            speaker = "Customer"
        
        repaired_turns.append(Turn(
            speaker=speaker,
            start=float(item.get("start", 0)),
            end=float(item.get("end", 0)),
            text=str(item.get("text", "")),
        ))

    log.info(
        f"Speaker repair complete: {len(raw_turns)} → {len(repaired_turns)} turns, "
        f"speakers={set(t.speaker for t in repaired_turns)}"
    )
    return repaired_turns
```

## Key Design Decisions

1. **Exactly 2 speakers**: The system prompt explicitly forbids hallucinating a 3rd speaker (this was a real issue with Gemini in our testing).
2. **Text preservation**: The LLM must NOT modify the text — only reassign speakers. This is critical for downstream quote matching in the flagging engine.
3. **Robust JSON parsing**: Handles markdown code fences that Gemini sometimes wraps around JSON.
4. **Fallback on invalid speaker**: Maps any unexpected speaker name to "Customer" rather than failing.
5. **No structured output**: We use raw JSON parsing instead of `with_structured_output()` because the output is a variable-length array. LangChain's structured output works best with fixed-shape Pydantic models.

## Integration Point

This service is called by the pipeline in `routers/calls.py` (Task 04):

```python
# In the pipeline:
# 1. Transcribe with Deepgram
raw_turns, duration, response = stt.transcribe_deepgram(raw_bytes)

# 2. Repair speakers with Gemini
from services.speaker_repair_service import repair_speakers
diarized_turns = repair_speakers(raw_turns, settings.google_api_key)

# 3. Build transcript with repaired turns for flagging
transcript = TranscriptOut(call_id=call_id, duration_sec=duration, turns=diarized_turns, engine="deepgram")
```

## Acceptance Criteria
1. Function accepts `list[Turn]` and returns `list[Turn]` with speakers labeled as "Advisor" or "Customer"
2. Never produces a 3rd speaker (even if transcript mentions other people)
3. Original text is preserved exactly (byte-for-byte)
4. Original timestamps are preserved exactly
5. Handles Gemini returning markdown-fenced JSON
6. Raises `RuntimeError` on failure with clear error message
