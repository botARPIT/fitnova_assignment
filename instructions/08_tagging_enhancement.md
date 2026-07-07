# Task 08: Tagging Service Enhancement + Company Facts

## Objective
Enhance the existing tagging/analysis service to produce per-dimension scores, use the full rubric, verify quotes against the diarized transcript, and integrate company facts for compliance checking.

## Parallelization
**Group A** — No dependencies on new code. Modifies existing service.

## Context
The current `tagging_service.py` uses a basic prompt. We need to:
1. Score each rubric dimension (0-5 scale with evidence)
2. Verify every flagged quote exists in the transcript (anti-hallucination)
3. Provide company facts context so the LLM can detect pricing errors and false guarantees
4. Return structured output matching our DB schema

## Files to Create

### 1. `backend/config/company_facts.yaml`

```yaml
# FitNova Company Facts — ground truth for compliance checking
# These facts are injected into the LLM context to detect inaccuracies

company:
  name: "FitNova"
  tagline: "AI-Powered Fitness Transformation"
  type: "Online and Offline Fitness Coaching Platform"

plans:
  basic:
    name: "Basic"
    price_monthly: 4999  # INR
    sessions_per_week: 3
    features:
      - "Group workout sessions (max 10 per batch)"
      - "Basic nutrition guidelines"
      - "Weekly progress check-in"
    coach_type: "Shared group coach"
    trial: "7-day free trial available"

  pro:
    name: "Pro"
    price_monthly: 9999  # INR
    sessions_per_week: 5
    features:
      - "1-on-1 dedicated coach"
      - "Custom nutrition plan"
      - "Progress tracking dashboard"
      - "WhatsApp support from coach"
    coach_type: "Dedicated 1-on-1 coach"
    trial: "7-day free trial available"

  elite:
    name: "Elite"
    price_monthly: 17999  # INR
    sessions_per_week: 7
    features:
      - "Daily 1-on-1 sessions"
      - "Dedicated nutritionist"
      - "Physiotherapy consultation"
      - "Priority support 24/7"
      - "Body composition analysis monthly"
    coach_type: "Dedicated coach + nutritionist"
    trial: "7-day free trial available"

policies:
  - "All plans come with a 7-day free trial — no credit card required"
  - "No long-term contracts — month-to-month billing"
  - "EMI options available on Pro and Elite plans (3 or 6 months)"
  - "Results vary — advisors must NOT guarantee specific weight loss numbers"
  - "No guaranteed results claims allowed"
  - "Refund available within 48 hours of subscription start"
  - "Session recordings are stored for quality assurance"

locations:
  - "Koramangala, Bangalore"
  - "Indiranagar, Bangalore"
  - "Online (pan-India)"

working_hours:
  weekdays: "6 AM – 10 PM"
  weekends: "7 AM – 8 PM"
  timezone: "IST"
```

## Files to Modify

### 2. `backend/services/tagging_service.py`

Major rewrite of the `analyze_call` function. The key changes:

1. **Enhanced system prompt** that includes:
   - Full rubric (loaded from `rubric.yaml`)
   - Company facts (loaded from `company_facts.yaml`)
   - Strict JSON output format

2. **Per-dimension scoring**: Return a score and evidence for each of the 5 dimensions

3. **Quote verification**: Every flag must include a quote. After LLM returns flags, verify each quote exists in the transcript text (fuzzy match with threshold).

4. **Discarded flags**: Flags whose quotes don't match get discarded with a reason.

Updated function signature:
```python
def analyze_call(
    transcript: TranscriptOut,
    rubric: dict,
    company_facts: dict,
    google_api_key: str,
    quote_match_threshold: float = 0.6,
) -> tuple[dict, float, list[FlaggedIssue], list[FlaggedIssue]]:
    """Analyze a sales call transcript.
    
    Returns:
        (scores_dict, overall_score, verified_flags, discarded_flags)
    """
```

Key implementation details:

```python
# The LLM prompt should include:
ANALYSIS_PROMPT = """You are a sales call quality analyst for FitNova.

COMPANY FACTS:
{company_facts_text}

RUBRIC — score each dimension 0-5:
{rubric_text}

ISSUE TAGS to flag:
{issue_tags}

TRANSCRIPT:
{transcript_text}

Return a JSON object with:
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
      "quote": "<exact quote from transcript>",
      "explanation": "..."
    }}
  ]
}}

RULES:
1. Score EVERY dimension. Use the rubric descriptions to calibrate.
2. Every flag MUST include an exact quote from the transcript.
3. Check pricing against company facts — flag inaccuracies.
4. Check for false guarantees against company policies.
5. Be fair — only flag genuine issues, not nitpicks.
"""

# After getting LLM response, verify quotes:
def _verify_quote(quote: str, transcript_text: str, threshold: float) -> bool:
    """Check if a quote approximately exists in the transcript."""
    from difflib import SequenceMatcher
    # Normalize
    quote_lower = quote.lower().strip()
    text_lower = transcript_text.lower()
    
    # Exact substring match
    if quote_lower in text_lower:
        return True
    
    # Sliding window fuzzy match
    words = quote_lower.split()
    window_size = len(words)
    text_words = text_lower.split()
    
    for i in range(len(text_words) - window_size + 1):
        window = " ".join(text_words[i:i + window_size])
        ratio = SequenceMatcher(None, quote_lower, window).ratio()
        if ratio >= threshold:
            return True
    
    return False
```

### 3. `backend/main.py`

In the lifespan function, load company facts:

```python
import yaml

# Load company facts
company_facts_path = Path(__file__).parent / "config" / "company_facts.yaml"
if company_facts_path.exists():
    with open(company_facts_path) as f:
        app.state.company_facts = yaml.safe_load(f)
else:
    app.state.company_facts = {}
```

### 4. `backend/config.py`

Add setting:
```python
quote_match_threshold: float = float(os.getenv("QUOTE_MATCH_THRESHOLD", "0.6"))
min_duration_sec: float = float(os.getenv("MIN_DURATION_SEC", "10"))
```

## Acceptance Criteria
1. Analysis returns per-dimension scores (5 dimensions, each 0-5)
2. Overall score is the mean of dimension scores
3. Every flag includes a quote from the transcript
4. Quotes are verified against the actual transcript text (fuzzy match)
5. Unverified quotes result in flags being moved to `discarded_flags` with reason
6. Company facts are loaded and injected into the LLM prompt
7. Pricing errors are detected (e.g., advisor says Basic is ₹3,000 instead of ₹4,999)
8. False guarantee claims are detected (e.g., "guaranteed 10kg weight loss")
