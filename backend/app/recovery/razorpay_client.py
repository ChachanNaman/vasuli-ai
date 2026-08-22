"""Real Razorpay Test Mode integration (PRD §3.1.5, §10).

Used for `smart_retry` (schedules a retry — represented here as a fresh
test-mode payment link the customer can pay immediately, since Razorpay's
API has no "retry the same payment" endpoint) and `generate_payment_link`.
Zero real money ever moves — Test Mode keys only generate sandboxed objects.

If RAZORPAY_KEY_ID/RAZORPAY_KEY_SECRET aren't configured, or the API call
fails, callers fall back to a simulated link — this keeps the demo runnable
before/without Razorpay keys, but every decision honestly records whether
its link was `is_live_integration` or not (PRD §12.4: nothing ambiguous
about what's real).
"""

from __future__ import annotations

import logging
import os
import uuid
from dataclasses import dataclass
from functools import lru_cache

logger = logging.getLogger("vasuli.razorpay")


@dataclass
class PaymentLinkResult:
    url: str
    is_live: bool
    razorpay_payment_link_id: str | None = None


def _has_credentials() -> bool:
    return bool(os.environ.get("RAZORPAY_KEY_ID") and os.environ.get("RAZORPAY_KEY_SECRET"))


@lru_cache(maxsize=1)
def _client():
    import razorpay

    key_id = os.environ["RAZORPAY_KEY_ID"]
    key_secret = os.environ["RAZORPAY_KEY_SECRET"]
    return razorpay.Client(auth=(key_id, key_secret))


def _simulated_link(amount: float, description: str) -> PaymentLinkResult:
    fake_id = f"plink_sim_{uuid.uuid4().hex[:14]}"
    return PaymentLinkResult(
        url=f"https://rzp.io/simulated/{fake_id}",
        is_live=False,
        razorpay_payment_link_id=fake_id,
    )


def create_payment_link(
    amount: float,
    currency: str,
    customer_name: str,
    customer_contact: str | None,
    description: str,
    reference_id: str,
) -> PaymentLinkResult:
    """Create a real Razorpay Test Mode payment link, falling back to a
    clearly-labeled simulated one if credentials are absent or the call
    errors (e.g. rate limit, network issue during a live demo)."""
    if not _has_credentials():
        logger.info("Razorpay credentials not configured; using simulated link for %s", reference_id)
        return _simulated_link(amount, description)

    try:
        client = _client()
        payload = {
            "amount": int(round(amount * 100)),  # paise
            "currency": currency,
            "description": description,
            "customer": {
                "name": customer_name,
                "contact": customer_contact or "",
            },
            "notify": {"sms": False, "email": False},  # no real comms sent (PRD §3.2)
            "reference_id": reference_id[:40],
        }
        response = client.payment_link.create(payload)
        return PaymentLinkResult(
            url=response["short_url"],
            is_live=True,
            razorpay_payment_link_id=response["id"],
        )
    except Exception as e:  # noqa: BLE001 - any Razorpay failure falls back to simulated
        logger.warning("Razorpay payment link creation failed, falling back to simulated: %s", e)
        return _simulated_link(amount, description)
