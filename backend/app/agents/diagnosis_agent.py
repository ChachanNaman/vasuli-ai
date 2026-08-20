"""Diagnosis + intervention agent (PRD §8).

Thin orchestration layer: builds the prompt, calls the LLM client (Groq
primary / Gemini fallback), validates the structured response against the
§8.3 contract and the §8.2 allowed action set, and returns a typed
Diagnosis. This module never touches the database or executes an action —
that's the guardrail engine's and the recovery executor's job.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from app.agents.llm_client import LLMClientError, call_diagnosis_llm
from app.agents.prompts import (
    ALLOWED_ACTIONS,
    DIAGNOSE_TOOL_SCHEMA,
    SYSTEM_PROMPT,
    build_user_prompt,
)


class DiagnosisValidationError(Exception):
    """Raised when the LLM's structured response fails contract validation."""


@dataclass
class Diagnosis:
    root_cause: str
    confidence: float
    reasoning: str
    recommended_action: str
    action_params: dict
    customer_message: Optional[str]
    llm_provider: str
    llm_fallback_used: bool


def _validate(data: dict) -> None:
    required = {
        "root_cause",
        "confidence",
        "reasoning",
        "recommended_action",
        "action_params",
        "customer_message",
    }
    missing = required - data.keys()
    if missing:
        raise DiagnosisValidationError(f"missing fields in LLM response: {missing}")

    if data["recommended_action"] not in ALLOWED_ACTIONS:
        raise DiagnosisValidationError(
            f"recommended_action {data['recommended_action']!r} is not in the allowed action set"
        )

    confidence = data["confidence"]
    if not isinstance(confidence, (int, float)) or not (0.0 <= confidence <= 1.0):
        raise DiagnosisValidationError(f"confidence {confidence!r} must be a number in [0, 1]")

    if not isinstance(data["action_params"], dict):
        raise DiagnosisValidationError("action_params must be an object")


def diagnose(
    event: dict,
    customer_history: Optional[dict] = None,
    on_fallback: Optional[Callable[[str, str], None]] = None,
) -> Diagnosis:
    """Diagnose one event and recommend one bounded action.

    Raises DiagnosisValidationError if the LLM's structured output doesn't
    satisfy the §8.3 contract, and LLMClientError if both providers fail —
    callers should route those to `flag_for_human_review` rather than
    letting a bad or absent diagnosis silently do nothing.
    """
    user_prompt = build_user_prompt(event, customer_history)

    result = call_diagnosis_llm(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
        tool_schema=DIAGNOSE_TOOL_SCHEMA,
        on_fallback=on_fallback,
    )

    _validate(result.data)

    return Diagnosis(
        root_cause=result.data["root_cause"],
        confidence=float(result.data["confidence"]),
        reasoning=result.data["reasoning"],
        recommended_action=result.data["recommended_action"],
        action_params=result.data["action_params"],
        customer_message=result.data["customer_message"],
        llm_provider=result.provider,
        llm_fallback_used=result.fallback_used,
    )
