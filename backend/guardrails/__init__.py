"""Centralized guardrails: prompts, output schemas, validators, and input guards.

This module is the single source of truth for all LLM prompts, structured output
schemas, and validation logic. All services import from here — no inline prompts
or ad-hoc validation anywhere else in the codebase.

Structure:
    prompts.py      — All LLM system/human prompt templates (versioned)
    schemas.py      — Pydantic models for LLM structured output
    validators.py   — Post-processing validators for every pipeline stage
    input_guards.py — Pre-processing validators for audio/transcript input
"""
