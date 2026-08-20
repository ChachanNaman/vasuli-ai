"""
Event schema for the Revenue Recovery Agent.

Every event is shaped to look like something that could plausibly come off
Razorpay's webhook stream (payment.failed, subscription.charged.failed) or
be derived from checkout/session analytics and receivables data. Fields are
deliberately rich enough to support genuine root-cause diagnosis rather than
a coin-flip classifier.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional


class EventType(str, Enum):
    PAYMENT_FAILED = "payment_failed"
    SUBSCRIPTION_CHARGE_FAILED = "subscription_charge_failed"
    CHECKOUT_ABANDONED = "checkout_abandoned"
    INVOICE_OVERDUE = "invoice_overdue"


class FailureReasonCode(str, Enum):
    INSUFFICIENT_FUNDS = "insufficient_funds"
    BANK_SERVER_DOWN = "bank_server_down"
    OTP_MISMATCH = "otp_mismatch"
    OTP_TIMEOUT = "otp_timeout"
    CARD_EXPIRED = "card_expired"
    NETWORK_ERROR = "network_error"
    RISK_DECLINED = "risk_declined"
    MANDATE_EXPIRED = "mandate_expired"
    MANDATE_REVOKED = "mandate_revoked"
    DAILY_LIMIT_EXCEEDED = "daily_limit_exceeded"
    UNKNOWN = "unknown"


@dataclass
class CustomerContext:
    customer_id: str
    name: str
    past_successful_payments: int
    past_failed_payments: int
    tenure_months: int
    opted_out_of_recovery_comms: bool = False
    preferred_channel: str = "sms"  # sms | whatsapp | email | call
    language_pref: str = "hinglish"  # hinglish | english


@dataclass
class RevenueEvent:
    event_id: str
    event_type: EventType
    timestamp: str  # ISO8601
    merchant_id: str
    amount: float
    currency: str
    customer: CustomerContext

    # payment_failed / subscription_charge_failed
    failure_reason_code: Optional[FailureReasonCode] = None
    payment_method: Optional[str] = None
    bank_name: Optional[str] = None
    attempt_number: Optional[int] = None

    # subscription specific
    subscription_id: Optional[str] = None
    mandate_id: Optional[str] = None
    mandate_status: Optional[str] = None
    plan_name: Optional[str] = None
    billing_cycle: Optional[str] = None

    # checkout_abandoned specific
    cart_value: Optional[float] = None
    items_count: Optional[int] = None
    checkout_stage_reached: Optional[str] = None
    minutes_since_abandon: Optional[int] = None
    device: Optional[str] = None

    # invoice_overdue specific (B2B receivables)
    invoice_id: Optional[str] = None
    days_overdue: Optional[int] = None
    business_customer_name: Optional[str] = None
    payment_reliability_score: Optional[float] = None  # 0-1, historical

    def to_dict(self) -> dict:
        d = asdict(self)
        d["event_type"] = self.event_type.value
        if self.failure_reason_code:
            d["failure_reason_code"] = self.failure_reason_code.value
        return d