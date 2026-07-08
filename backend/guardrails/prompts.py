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

OUTPUT FORMAT: Return a JSON object with this exact shape:
{
  "turns": [
    {
      "speaker": "Advisor" or "Customer",
      "start": <original float>,
      "end": <original float>,
      "text": "<original text, unchanged>"
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
