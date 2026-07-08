"""Deterministic business-rule validation against FitNova company facts."""

from __future__ import annotations

import re

from guardrails.schemas import FlaggedFlag
from schemas.transcript import Turn


_GUARANTEE_PATTERNS = (
    r"\bguarantee(?:d)?\b",
    r"\b100%\b",
    r"\bassured\b",
    r"\bfor sure\b",
    r"\bdefinitely\b",
    r"\bcertain(?:ly)?\b",
    r"\bwithin\s+\d+\s*(?:day|days|week|weeks|month|months)\b",
)

_URGENCY_PATTERNS = (
    r"\btoday only\b",
    r"\blast slot\b",
    r"\blimited time\b",
    r"\boffer expires\b",
    r"\bonly today\b",
    r"\bright now\b",
    r"\bfinal slot\b",
)

_TRIAL_BOOKING_PATTERNS = (
    r"\bbook\b.*\btrial\b",
    r"\bschedule\b.*\btrial\b",
    r"\bfree trial\b",
    r"\btrial session\b",
)

_FEE_DISCLOSURE_PATTERNS = (
    r"\bhidden fee(?:s)?\b",
    r"\bextra charge(?:s)?\b",
    r"\badditional cost(?:s)?\b",
    r"\bjoining fee\b",
    r"\bregistration fee\b",
)


def _normalize(text: str) -> str:
    return " ".join((text or "").lower().split())


def _contains_any(text: str, patterns: tuple[str, ...]) -> bool:
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)


def _extract_plan_prices(company_facts: dict) -> dict[str, int]:
    prices: dict[str, int] = {}
    for plan_key, plan in (company_facts.get("plans") or {}).items():
        price = plan.get("price_monthly")
        if isinstance(price, int):
            prices[plan_key.lower()] = price
            name = str(plan.get("name") or plan_key).strip().lower()
            prices[name] = price
    return prices


def _mentions_correct_plan_price(text: str, company_facts: dict) -> bool:
    prices = _extract_plan_prices(company_facts)
    compact = text.replace(",", "")
    for plan_name, price in prices.items():
        if plan_name in compact and str(price) in compact:
            return True
    return False


def validate_flag_against_company_facts(
    flag: FlaggedFlag,
    matched_turn: Turn,
    prior_turns: list[Turn],
    company_facts: dict,
) -> list[str]:
    """Return discard reasons when a flag contradicts deterministic rules."""

    reasons: list[str] = []
    quote_text = _normalize(flag.quote)
    tag = (flag.tag or "").strip()

    if tag == "overpromising":
        if not _contains_any(quote_text, _GUARANTEE_PATTERNS):
            reasons.append(
                "Quote does not contain a deterministic guarantee/result-claim pattern"
            )

    if tag == "pressure_or_urgency_tactics":
        if not _contains_any(quote_text, _URGENCY_PATTERNS):
            reasons.append(
                "Quote does not contain a deterministic urgency/scarcity pattern"
            )

    if tag == "weak_or_missing_trial_booking":
        if _contains_any(quote_text, _TRIAL_BOOKING_PATTERNS):
            reasons.append(
                "Quote shows an explicit trial-booking attempt, which contradicts this tag"
            )

    if tag == "undisclosed_costs":
        if (
            _mentions_correct_plan_price(quote_text, company_facts)
            and not _contains_any(quote_text, _FEE_DISCLOSURE_PATTERNS)
        ):
            reasons.append(
                "Quote explicitly states a canonical plan price without hidden-fee language"
            )

    if tag == "price_before_value":
        discovery_patterns = ("goal", "routine", "schedule", "budget", "injur", "online", "offline")
        prior_text = _normalize(" ".join(turn.text for turn in prior_turns if turn.speaker == "Advisor"))
        if any(pattern in prior_text for pattern in discovery_patterns):
            reasons.append(
                "Prior advisor turns already contain discovery-language before this quote"
            )

    if tag == "no_needs_discovery":
        joined_prior = _normalize(" ".join(turn.text for turn in prior_turns if turn.speaker == "Advisor"))
        if any(term in joined_prior for term in ("goal", "routine", "schedule", "budget", "injur")):
            reasons.append(
                "Prior advisor turns already include deterministic discovery-topic language"
            )

    return reasons
