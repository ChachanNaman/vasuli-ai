"""Prompt construction for the diagnosis + intervention agent (PRD §8).

The LLM's job is narrow: (a) confirm/refine the root cause using the raw
event as one signal among several — not just echo failure_reason_code — (b)
pick exactly one action from the fixed allow-list, and (c) draft the
customer message if the action involves contact. It never decides whether
an action is allowed to execute; the guardrail engine (app/guardrails/rules.py)
applies after the LLM proposes.
"""

from __future__ import annotations

import json

ALLOWED_ACTIONS = {
    "smart_retry": "Schedule a payment retry at a model-recommended time window. "
    "Best for transient failures (network_error, bank_server_down) or "
    "insufficient_funds if retried after a delay. Rarely helps card_expired.",
    "generate_payment_link": "Generate a real Razorpay test-mode payment link for the "
    "customer to complete manually with a different method. Best when the same "
    "payment method is unlikely to succeed again (card_expired, repeated hard declines).",
    "send_nudge": "Simulated WhatsApp/SMS/email nudge in the customer's preferred "
    "language/channel. Best for checkout_abandoned or low-value reminders.",
    "escalate_b2b_chase": "Structured reminder sequence for overdue invoices, tiered "
    "by the customer's payment_reliability_score. Only for invoice_overdue events.",
    "initiate_mandate_reauth": "Simulated re-authorization link for an expired or "
    "revoked subscription mandate. Only when mandate_status is expired/revoked.",
    "flag_for_human_review": "The honest 'I can't safely automate this' outcome. Use "
    "when confidence is low, signals conflict, or the case looks like fraud review "
    "rather than a payment problem.",
    "no_action_recommended": "Use when intervention would likely backfire, e.g. "
    "contacting a customer mid genuine fraud review, or when there is no real "
    "recovery lever left.",
}

CONFIDENCE_FLOOR = 0.55

SYSTEM_PROMPT = f"""You are Vasuli, a revenue recovery diagnosis agent for an Indian \
payments merchant on Razorpay. You are given one loss event with full context. \
Your job has three parts:

1. Confirm or refine the root cause. The event carries a generator-tagged \
`failure_reason_code` where applicable — treat it as one signal among several, \
not a given. Reason over attempt history, timing, and customer history too.
2. Pick exactly one action from this fixed menu — never invent an action:
{json.dumps(ALLOWED_ACTIONS, indent=2)}
3. If the chosen action involves customer contact (generate_payment_link, \
send_nudge, escalate_b2b_chase, initiate_mandate_reauth), draft the exact \
message text in the customer's preferred language (hinglish or english). \
Otherwise customer_message must be null.

You do NOT decide whether the action is actually allowed to run — a separate \
deterministic guardrail layer does that after you respond. Your job is only to \
recommend.

If your confidence in the diagnosis is below {CONFIDENCE_FLOOR}, or the signals \
conflict, or this looks like it could be a genuine fraud case, prefer \
`flag_for_human_review` or `no_action_recommended` over guessing. A system that \
says "I don't know" is more trustworthy than one that always confidently retries.

Respond ONLY by calling the `diagnose_and_recommend` tool with the structured \
output. Do not respond in free text.
"""


def build_user_prompt(event: dict, customer_history: dict | None = None) -> str:
    parts = [
        "Event to diagnose:",
        json.dumps(event, indent=2, default=str),
    ]
    if customer_history:
        parts.append("Recent customer decision history (for context, do not re-decide these):")
        parts.append(json.dumps(customer_history, indent=2, default=str))
    return "\n\n".join(parts)


# Shared JSON schema used to build both Groq's and Gemini's tool/function spec
# (PRD §8.3 — both providers support tool-calling on this exact shape).
DIAGNOSE_TOOL_SCHEMA = {
    "name": "diagnose_and_recommend",
    "description": "Report the diagnosed root cause and recommended recovery action for one event.",
    "parameters": {
        "type": "object",
        "properties": {
            "root_cause": {
                "type": "string",
                "description": "The diagnosed root cause code, e.g. bank_server_down, insufficient_funds.",
            },
            "confidence": {
                "type": "number",
                "description": "Confidence in this diagnosis, 0.0 to 1.0.",
            },
            "reasoning": {
                "type": "string",
                "description": "Two-sentence plain-language explanation of the diagnosis and action choice.",
            },
            "recommended_action": {
                "type": "string",
                "enum": list(ALLOWED_ACTIONS.keys()),
            },
            "action_params": {
                "type": "object",
                "description": "Parameters for the recommended action, e.g. {\"retry_window_minutes\": 45}.",
            },
            "customer_message": {
                "type": ["string", "null"],
                "description": "Message text to send the customer, or null if the action has no message.",
            },
        },
        "required": [
            "root_cause",
            "confidence",
            "reasoning",
            "recommended_action",
            "action_params",
            "customer_message",
        ],
    },
}
