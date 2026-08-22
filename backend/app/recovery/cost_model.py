"""Illustrative per-action cost figures (ENHANCEMENTS.md §2.3).

Not real billing data pulled from any provider invoice — a small, explicit,
hand-picked assumption, stated here in one place so any number in a demo or
metrics panel can be traced back to its source and argued with, rather than
being a black-box "cost per recovery" figure. This is the single source of
truth for cost figures used by three consumers: the guardrail engine's
economic stopping rule, the metrics endpoint's cost-per-₹-recovered figure,
and the evaluation harness (backend/app/eval/).

Figures (INR):
  - smart_retry: ~₹0.05 — a retry is a Razorpay API call, effectively free.
  - generate_payment_link: ~₹0.10 — one API call, no SMS/email notify sent
    (recovery/razorpay_client.py explicitly disables Razorpay's own notify).
  - send_nudge / escalate_b2b_chase / initiate_mandate_reauth: ~₹0.40 — a
    blended WhatsApp/SMS/email send cost, since the exact channel varies by
    customer preference (PRD §10 channel weighting).
  - flag_for_human_review: ~₹50 — a human agent's time is the most
    expensive resource in this system by a wide margin.
  - no_action_recommended: ₹0 — nothing runs.

nuisance_cost is a separate, deliberately illustrative constant standing in
for goodwill erosion from over-contacting a customer — it only applies to
actions that actually reach the customer (CONTACT_ACTION_TYPES below).
"""

from __future__ import annotations

ACTION_COST_INR: dict[str, float] = {
    "smart_retry": 0.05,
    "generate_payment_link": 0.10,
    "send_nudge": 0.40,
    "escalate_b2b_chase": 0.40,
    "initiate_mandate_reauth": 0.40,
    "flag_for_human_review": 50.0,
    "no_action_recommended": 0.0,
}

NUISANCE_COST_INR: float = 2.0

# Actions that involve contacting the customer at all — mirrors
# app/guardrails/rules.py::CONTACT_ACTIONS. Duplicated here (not imported)
# to keep this module dependency-free; both sets are kept in sync by the
# guardrail test suite asserting on ALLOWED_ACTIONS coverage.
CONTACT_ACTION_TYPES: frozenset[str] = frozenset(
    {"generate_payment_link", "send_nudge", "escalate_b2b_chase", "initiate_mandate_reauth"}
)


def action_cost(action_type: str) -> float:
    return ACTION_COST_INR.get(action_type, 0.0)


def nuisance_cost(action_type: str) -> float:
    return NUISANCE_COST_INR if action_type in CONTACT_ACTION_TYPES else 0.0


def total_action_cost(action_type: str) -> float:
    """action_cost + nuisance_cost, the figure the economic stopping rule
    compares expected recovery against (ENHANCEMENTS.md §2.3: forced
    no_action_recommended whenever expected_recovery < 3x this)."""
    return action_cost(action_type) + nuisance_cost(action_type)
