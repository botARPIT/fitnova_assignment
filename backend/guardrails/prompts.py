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

SPEAKER_REPAIR_SYSTEM = """You are a diarization repair engine for FitNova sales call transcripts.

INPUT

You will receive a transcript produced by a speech-to-text system.

Each transcript entry contains:
- speaker (may be incorrect)
- start timestamp
- end timestamp
- text

The speech recognizer may have:
- assigned the wrong speaker
- assigned every turn to the same speaker
- merged speech from both speakers into a single segment
- produced inconsistent speaker labels

YOUR TASK

Repair the speaker diarization using conversational context.

There are ALWAYS exactly two speakers:

- Advisor — the FitNova sales advisor who initiated the call
- Customer — the lead/prospect receiving the call

Do not invent any additional speakers.

RULES

1. Preserve every spoken word exactly as provided.
   - Do NOT rewrite.
   - Do NOT paraphrase.
   - Do NOT translate.
   - Do NOT remove filler words.
   - Do NOT correct grammar.

2. Assign every output turn to either:
   - "Advisor"
   - "Customer"

3. If an input segment already contains speech from only one speaker:
   - keep it as a single output turn
   - preserve its original start and end timestamps exactly.

4. If an input segment contains speech from BOTH speakers:
   - split it into multiple turns.
   - Each output turn must contain speech from only one speaker.

5. When splitting a segment:
   - Preserve the original words exactly.
   - Do NOT reorder words.
   - Do NOT omit words.
   - Do NOT duplicate words.

6. Timestamp rules:
   - Never change the overall timing of the conversation.
   - If a segment is NOT split, keep its timestamps exactly.
   - If a segment IS split, assign timestamps that:
     - stay within the original start/end interval,
     - are chronological,
     - do not overlap,
     - completely cover the original interval with no gaps,
     - are proportional to the amount of speech in each split whenever exact boundaries are unknown.

7. Do NOT merge adjacent turns, even if they belong to the same speaker.

8. Use conversational context to determine the speaker.
   Typical Advisor behavior:
   - greets the customer
   - introduces themselves
   - mentions FitNova
   - explains plans
   - discusses pricing
   - answers questions
   - asks discovery questions
   - attempts to close the sale

   Typical Customer behavior:
   - answers questions
   - asks for clarification
   - discusses goals or budget
   - raises objections
   - requests time to think
   - asks about trials or coaches

9. Return ONLY valid JSON.

OUTPUT FORMAT

{
  "turns": [
    {
      "speaker": "Advisor",
      "start": <float>,
      "end": <float>,
      "text": "<original text>"
    }
  ]
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
1a. Fractional scores in 0.5 increments are allowed when performance falls between rubric bands.
1b. Reserve a score of 0 for complete absence of the behavior or a severe failure/violation. If there was any meaningful partial attempt, prefer 0.5 or 1+ instead of defaulting to 0.
2. Every flag MUST include an exact verbatim quote from the transcript — copy-paste, do not paraphrase.
2a. Prefer substantive quotes that actually demonstrate the issue. Avoid trivial closers or fillers such as "okay", "thanks", or "bye" unless they are the only direct evidence.
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
    if co.get("headquarters"):
        lines.append(f"Headquarters: {co.get('headquarters')}")
    for item in co.get("operating_model", []):
        lines.append(f"  • {item}")
    lines.append("")

    customer_profile = facts.get("customer_profile", {})
    if customer_profile:
        lines.append("Customer Profile:")
        for segment in customer_profile.get("primary_segments", []):
            lines.append(f"  • Segment: {segment}")
        for goal in customer_profile.get("common_goals", []):
            lines.append(f"  • Common goal: {goal}")
        for constraint in customer_profile.get("common_constraints", []):
            lines.append(f"  • Common constraint: {constraint}")
        lines.append("")

    lines.append("Plans & Pricing:")
    for plan_key, plan in facts.get("plans", {}).items():
        lines.append(f"  - {plan.get('name')}: ₹{plan.get('price_monthly')}/mo, "
                     f"{plan.get('sessions_per_week')} sessions/week, "
                     f"coach: {plan.get('coach_type')}")
        if plan.get("session_format"):
            lines.append(f"    Format: {plan.get('session_format')}")
        for feat in plan.get("features", []):
            lines.append(f"    • {feat}")
        for support in plan.get("support", []):
            lines.append(f"    Support: {support}")
        for missing in plan.get("not_included", []):
            lines.append(f"    Not included: {missing}")
        lines.append(f"    Trial: {plan.get('trial', 'N/A')}")
    lines.append("")

    sales_process = facts.get("sales_process", {})
    if sales_process:
        lines.append("Sales Process:")
        for topic in sales_process.get("required_discovery_topics", []):
            lines.append(f"  • Required discovery topic: {topic}")
        for step in sales_process.get("expected_flow", []):
            lines.append(f"  • Expected flow: {step}")
        lines.append("")

    policies = facts.get("policies", {})
    if isinstance(policies, dict):
        lines.append("Policies:")
        for section, entries in policies.items():
            lines.append(f"  {section.replace('_', ' ').title()}:")
            for entry in entries:
                lines.append(f"    • {entry}")
        lines.append("")
    elif isinstance(policies, list):
        lines.append("Policies:")
        for policy in policies:
            lines.append(f"  • {policy}")
        lines.append("")

    allowed_claims = facts.get("allowed_claims", [])
    if allowed_claims:
        lines.append("Allowed Claims:")
        for claim in allowed_claims:
            lines.append(f"  • {claim}")
        lines.append("")

    disallowed_claims = facts.get("disallowed_claims", [])
    if disallowed_claims:
        lines.append("Disallowed Claims:")
        for claim in disallowed_claims:
            lines.append(f"  • {claim}")
        lines.append("")

    objections = facts.get("common_objections", {})
    if objections:
        lines.append("Common Objections:")
        for key, value in objections.items():
            lines.append(f"  {key.title()}: {value.get('customer_signal', '')}")
            for response in value.get("acceptable_response", []):
                lines.append(f"    • {response}")
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
