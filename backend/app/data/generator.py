"""
Synthetic data generator for the Revenue Recovery Agent.

Produces a batch of RevenueEvent records across all four loss categories
(payment failure, subscription/mandate failure, checkout abandonment,
overdue B2B invoice). Distributions are hand-tuned to be *plausible* for an
Indian merchant on Razorpay rather than uniform-random, so the diagnosis
layer downstream has real signal to work with instead of noise.

Run directly to regenerate backend/app/data/events.json:
    python -m app.data.generator --n 80 --seed 42
"""

from __future__ import annotations

import argparse
import json
import random
from datetime import datetime, timedelta
from pathlib import Path

from app.data.schema import (
    CustomerContext,
    EventType,
    FailureReasonCode,
    RevenueEvent,
)


def _random_hex(n_chars: int) -> str:
    """A hex ID drawn from the seeded `random` module rather than
    `uuid.uuid4()`. uuid4() reads from the OS's CSPRNG and completely
    ignores `random.seed()` — using it here would make `generate_batch(n,
    seed=42)` produce a different set of event/customer IDs on every
    invocation despite the fixed seed, silently breaking reproducibility
    for anything that seeds or keys off those IDs (the evaluation
    harness's common-random-numbers design, app/eval/policies.py, does
    exactly that)."""
    return f"{random.getrandbits(n_chars * 4):0{n_chars}x}"

FIRST_NAMES = [
    "Aarav", "Vivaan", "Aditya", "Vihaan", "Arjun", "Sai", "Reyansh", "Krishna",
    "Ishaan", "Rohan", "Ananya", "Diya", "Saanvi", "Aadhya", "Kiara", "Myra",
    "Pari", "Anika", "Navya", "Riya",
]
LAST_NAMES = [
    "Sharma", "Verma", "Gupta", "Reddy", "Iyer", "Nair", "Khan", "Singh",
    "Patel", "Mehta", "Bose", "Chatterjee", "Rao", "Pillai", "Kulkarni",
]
BUSINESS_NAMES = [
    "Sunrise Traders", "Metro Logistics", "Bluewave Textiles", "Orbit Retail Co",
    "Green Leaf Foods", "Nimbus Electronics", "Coral Craft Studio",
    "Vertex Hardware", "Silverline Apparel", "Pinnacle Packaging",
]
BANKS = ["HDFC Bank", "ICICI Bank", "SBI", "Axis Bank", "Kotak Mahindra", "Yes Bank", "IDFC First"]
PAYMENT_METHODS = ["upi", "credit_card", "debit_card", "netbanking", "wallet"]
DEVICES = ["android_app", "ios_app", "mobile_web", "desktop_web"]
PLANS = ["Starter Monthly", "Pro Monthly", "Pro Annual", "Business Monthly", "Business Annual"]

MERCHANT_ID = "merchant_test_9f31a2"

# Once a payment is disputed/charged back, collection action should stop
# pending resolution (ENHANCEMENTS.md §2.2 dispute-freeze rule) — a small,
# explicit rate so the demo reliably produces a few dispute-frozen cases per
# batch without dominating it.
DISPUTE_RATE = 0.04


def _name() -> str:
    return f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"


def _customer(opt_out_rate: float = 0.08) -> CustomerContext:
    successful = max(0, int(random.gauss(14, 10)))
    failed = max(0, int(random.gauss(1.5, 1.8)))
    return CustomerContext(
        customer_id=f"cust_{_random_hex(10)}",
        name=_name(),
        past_successful_payments=successful,
        past_failed_payments=failed,
        tenure_months=max(0, int(random.gauss(9, 7))),
        opted_out_of_recovery_comms=random.random() < opt_out_rate,
        preferred_channel=random.choices(
            ["whatsapp", "sms", "email", "call"], weights=[0.5, 0.3, 0.15, 0.05]
        )[0],
        language_pref=random.choices(["hinglish", "english"], weights=[0.65, 0.35])[0],
    )


def _ts(days_ago_max: int) -> str:
    dt = datetime.utcnow() - timedelta(
        days=random.uniform(0, days_ago_max), hours=random.uniform(0, 23)
    )
    return dt.replace(microsecond=0).isoformat() + "Z"


# Failure reason distribution tuned to roughly mirror real-world UPI/card
# decline patterns in India: insufficient funds and bank-side timeouts
# dominate, hard declines (expired card, risk) are the minority.
FAILURE_WEIGHTS = {
    FailureReasonCode.INSUFFICIENT_FUNDS: 0.28,
    FailureReasonCode.BANK_SERVER_DOWN: 0.16,
    FailureReasonCode.OTP_TIMEOUT: 0.14,
    FailureReasonCode.OTP_MISMATCH: 0.10,
    FailureReasonCode.NETWORK_ERROR: 0.12,
    FailureReasonCode.CARD_EXPIRED: 0.08,
    FailureReasonCode.RISK_DECLINED: 0.07,
    FailureReasonCode.DAILY_LIMIT_EXCEEDED: 0.05,
}


def _weighted_failure_reason() -> FailureReasonCode:
    reasons, weights = zip(*FAILURE_WEIGHTS.items())
    return random.choices(reasons, weights=weights)[0]


def gen_payment_failed() -> RevenueEvent:
    reason = _weighted_failure_reason()
    method = random.choice(PAYMENT_METHODS)
    return RevenueEvent(
        event_id=f"evt_{_random_hex(12)}",
        event_type=EventType.PAYMENT_FAILED,
        timestamp=_ts(7),
        merchant_id=MERCHANT_ID,
        amount=round(random.uniform(199, 24999), 2),
        currency="INR",
        customer=_customer(),
        failure_reason_code=reason,
        payment_method=method,
        bank_name=random.choice(BANKS) if method in ("upi", "netbanking", "debit_card") else None,
        attempt_number=random.choices([1, 2, 3], weights=[0.7, 0.22, 0.08])[0],
        dispute_opened=random.random() < DISPUTE_RATE,
    )


def gen_subscription_failed() -> RevenueEvent:
    reason = random.choices(
        [
            FailureReasonCode.INSUFFICIENT_FUNDS,
            FailureReasonCode.MANDATE_EXPIRED,
            FailureReasonCode.MANDATE_REVOKED,
            FailureReasonCode.BANK_SERVER_DOWN,
            FailureReasonCode.DAILY_LIMIT_EXCEEDED,
        ],
        weights=[0.35, 0.22, 0.10, 0.18, 0.15],
    )[0]
    mandate_status = {
        FailureReasonCode.MANDATE_EXPIRED: "expired",
        FailureReasonCode.MANDATE_REVOKED: "revoked",
    }.get(reason, "active")
    return RevenueEvent(
        event_id=f"evt_{_random_hex(12)}",
        event_type=EventType.SUBSCRIPTION_CHARGE_FAILED,
        timestamp=_ts(10),
        merchant_id=MERCHANT_ID,
        amount=round(random.choice([299, 499, 999, 1999, 4999, 9999]), 2),
        currency="INR",
        customer=_customer(),
        failure_reason_code=reason,
        subscription_id=f"sub_{_random_hex(10)}",
        mandate_id=f"mandate_{_random_hex(10)}",
        mandate_status=mandate_status,
        plan_name=random.choice(PLANS),
        billing_cycle=random.choice(["monthly", "annual"]),
        attempt_number=random.choices([1, 2, 3, 4], weights=[0.55, 0.25, 0.13, 0.07])[0],
        dispute_opened=random.random() < DISPUTE_RATE,
    )


def gen_checkout_abandoned() -> RevenueEvent:
    stage = random.choices(
        ["cart", "address", "payment_method_select", "otp_pending"],
        weights=[0.3, 0.2, 0.25, 0.25],
    )[0]
    return RevenueEvent(
        event_id=f"evt_{_random_hex(12)}",
        event_type=EventType.CHECKOUT_ABANDONED,
        timestamp=_ts(3),
        merchant_id=MERCHANT_ID,
        amount=0.0,
        currency="INR",
        customer=_customer(opt_out_rate=0.05),
        cart_value=round(random.uniform(299, 15999), 2),
        items_count=random.randint(1, 6),
        checkout_stage_reached=stage,
        minutes_since_abandon=random.randint(5, 2880),
        device=random.choice(DEVICES),
    )


def gen_invoice_overdue() -> RevenueEvent:
    days_overdue = random.choices(
        [random.randint(1, 15), random.randint(16, 45), random.randint(46, 120)],
        weights=[0.55, 0.3, 0.15],
    )[0]
    return RevenueEvent(
        event_id=f"evt_{_random_hex(12)}",
        event_type=EventType.INVOICE_OVERDUE,
        timestamp=_ts(days_overdue),
        merchant_id=MERCHANT_ID,
        amount=round(random.uniform(5000, 350000), 2),
        currency="INR",
        customer=_customer(opt_out_rate=0.03),
        invoice_id=f"inv_{_random_hex(10)}",
        days_overdue=days_overdue,
        business_customer_name=random.choice(BUSINESS_NAMES),
        payment_reliability_score=round(random.betavariate(5, 2), 2),
    )


GENERATORS = {
    EventType.PAYMENT_FAILED: gen_payment_failed,
    EventType.SUBSCRIPTION_CHARGE_FAILED: gen_subscription_failed,
    EventType.CHECKOUT_ABANDONED: gen_checkout_abandoned,
    EventType.INVOICE_OVERDUE: gen_invoice_overdue,
}

# Realistic-ish mix: payment failures are the most frequent event, invoices
# are rarer but highest value.
EVENT_MIX_WEIGHTS = {
    EventType.PAYMENT_FAILED: 0.40,
    EventType.SUBSCRIPTION_CHARGE_FAILED: 0.25,
    EventType.CHECKOUT_ABANDONED: 0.25,
    EventType.INVOICE_OVERDUE: 0.10,
}


def generate_batch(n: int, seed: int | None = None) -> list[RevenueEvent]:
    if seed is not None:
        random.seed(seed)
    types, weights = zip(*EVENT_MIX_WEIGHTS.items())
    events = []
    for _ in range(n):
        etype = random.choices(types, weights=weights)[0]
        events.append(GENERATORS[etype]())
    events.sort(key=lambda e: e.timestamp)
    return events


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=80)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--out",
        type=str,
        default=str(Path(__file__).parent / "events.json"),
    )
    args = parser.parse_args()

    events = generate_batch(args.n, seed=args.seed)
    out_path = Path(args.out)
    out_path.write_text(json.dumps([e.to_dict() for e in events], indent=2))
    print(f"Wrote {len(events)} events to {out_path}")

    # quick sanity breakdown
    from collections import Counter
    counts = Counter(e.event_type.value for e in events)
    for k, v in counts.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()