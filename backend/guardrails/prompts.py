"""Central prompt registry — all LLM prompts in one place.

Every prompt is:
- Versioned (PROMPT_VERSION dict)
- Tagged with its pipeline stage
- Documented with expected input/output

To modify a prompt: edit HERE, not in service files.
To A/B test: add a new version key and switch via config.
"""

# ─── Version tracking ─────────────────────────────────────────────────────
PROMPT_VERSIONS = {
    "speaker_repair": "v2.0",
    "call_analysis": "v2.0",
}


# ═══════════════════════════════════════════════════════════════════════════
# STAGE 1: Speaker Repair (Post-Deepgram, Pre-Analysis)
# ═══════════════════════════════════════════════════════════════════════════

SPEAKER_REPAIR_SYSTEM = """You are a diarization repair engine for sales call transcripts.

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
   - Answers questions about their situation
   - Asks about pricing/details
   - Raises objections
   - Is initially unfamiliar with the call context
5. Keep the original text EXACTLY as-is. Do NOT modify, translate, or clean the text.
6. Keep the original timestamps EXACTLY as-is.
7. Do NOT merge adjacent turns — keep them as separate entries even if same speaker.

OUTPUT FORMAT: Return a JSON array. Each element:
{
  "speaker": "Advisor" or "Customer",
  "start": <original float>,
  "end": <original float>,
  "text": "<original text, unchanged>"
}"""


def build_speaker_repair_human(raw_turns_text: str) -> str:
    """Build the human message for speaker repair.

    Args:
        raw_turns_text: Formatted transcript lines like
                        "[0.0s – 2.1s] speaker_0: Hello ..."
    """
    return f"Repair the speaker labels in this transcript:\n\n{raw_turns_text}"


# ═══════════════════════════════════════════════════════════════════════════
# STAGE 2: Call Quality Analysis (Post-Repair, Final Stage)
# ═══════════════════════════════════════════════════════════════════════════

CALL_ANALYSIS_SYSTEM_TEMPLATE = """You are a quality analyst for FitNova, a fitness coaching company.
You will analyze a sales call transcript and:
1. Score the call on 5 rubric dimensions (0-5 each) with evidence
2. Flag any issues from the FIXED taxonomy — do NOT invent new tags

COMPANY FACTS (use this as ground truth for accuracy checks):
{company_facts}

SCORING RUBRIC:
{rubric_text}

ISSUE TAG TAXONOMY (only these tags are valid):
- no_needs_discovery: Advisor didn't ask about customer needs/goals before pitching
- overpromising: Advisor made guarantees about results (e.g. "guaranteed weight loss")
- pressure_or_urgency_tactics: Advisor used artificial urgency or pressure to close
- price_before_value: Advisor discussed pricing before establishing value/needs
- undisclosed_costs: Advisor hid or failed to mention relevant costs
- weak_or_missing_trial_booking: Advisor didn't attempt to book the free trial
- talking_over_customer: Advisor interrupted or didn't let the customer speak

Return a JSON object matching this EXACT schema:
{{
  "scores": {{
    "needs_discovery": {{"score": <0-5>, "evidence": "..."}},
    "product_knowledge": {{"score": <0-5>, "evidence": "..."}},
    "objection_handling": {{"score": <0-5>, "evidence": "..."}},
    "compliance": {{"score": <0-5>, "evidence": "..."}},
    "next_step_booking": {{"score": <0-5>, "evidence": "..."}}
  }},
  "flags": [
    {{
      "tag": "<from issue_tags list>",
      "severity": "critical|major|minor",
      "quote": "<exact verbatim quote from transcript>",
      "explanation": "...",
      "timestamp": <start_time_of_turn>
    }}
  ]
}}

CRITICAL RULES:
1. Score EVERY dimension. Use the rubric descriptions to calibrate.
2. Every flag MUST include an exact verbatim quote from the transcript — copy-paste, do not paraphrase.
3. timestamp must match the turn's start time from the transcript.
4. Only flag issues you can directly support with a quote from the transcript.
5. If the call is clean, return an empty flags list — do not force flags.
6. Check pricing against Company Facts — flag any inaccurate pricing claims.
7. Check for guarantees against policies — flag any result guarantees.
8. Be fair — only flag genuine issues, not nitpicks."""


def build_analysis_system(company_facts: dict, rubric_text: str) -> str:
    """Build the system prompt for call analysis.

    Args:
        company_facts: Parsed dict from company_facts.yaml
        rubric_text: Formatted rubric from build_rubric_prompt()
    """
    return CALL_ANALYSIS_SYSTEM_TEMPLATE.format(
        company_facts=_format_company_facts(company_facts),
        rubric_text=rubric_text,
    )


def _format_company_facts(facts: dict) -> str:
    """Format the company facts dict into a readable prompt block."""
    if not facts:
        return "(No company facts available)"

    lines = []
    co = facts.get("company", {})
    lines.append(f"Company: {co.get('name', 'N/A')} — {co.get('tagline', '')}")
    lines.append(f"Type: {co.get('type', 'N/A')}")
    lines.append("")

    lines.append("Plans & Pricing:")
    for plan_key, plan in facts.get("plans", {}).items():
        lines.append(f"  - {plan.get('name')}: ₹{plan.get('price_monthly')}/mo, "
                     f"{plan.get('sessions_per_week')} sessions/week, "
                     f"coach: {plan.get('coach_type')}")
        for feat in plan.get("features", []):
            lines.append(f"    • {feat}")
        lines.append(f"    Trial: {plan.get('trial', 'N/A')}")
    lines.append("")

    lines.append("Policies:")
    for policy in facts.get("policies", []):
        lines.append(f"  • {policy}")
    lines.append("")

    lines.append("Locations: " + ", ".join(facts.get("locations", [])))
    wh = facts.get("working_hours", {})
    lines.append(f"Hours: Weekdays {wh.get('weekdays', 'N/A')}, "
                 f"Weekends {wh.get('weekends', 'N/A')} ({wh.get('timezone', 'IST')})")

    return "\n".join(lines)


def build_analysis_human(transcript_text: str) -> str:
    """Build the human message for call analysis.

    Args:
        transcript_text: Formatted transcript like
                         "[0.0s] Advisor: Hello ..."
    """
    return f"Analyze this sales call transcript:\n\n{transcript_text}"
