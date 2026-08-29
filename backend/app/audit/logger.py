"""Audit trail writer. Every decision — executed, blocked, or skipped — goes
through here so the audit trail is complete by construction, not by
convention (PRD §6.2, §7).
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from app.audit import hash_chain
from app.audit.supabase_client import get_supabase
from app.guardrails.rules import GuardrailResult

logger = logging.getLogger("vasuli.audit")


@dataclass
class DecisionRecord:
    event_id: str
    customer_id: str
    root_cause: str
    confidence: float
    reasoning_text: str
    guardrail_result: GuardrailResult
    action_type: str
    action_params: dict
    recovered: bool
    amount_recovered: float
    outcome_notes: Optional[str]
    razorpay_payment_link: Optional[str]
    is_live_integration: bool
    llm_provider: Optional[str]
    llm_fallback_used: bool
    customer_message: Optional[str]
    batch_id: Optional[str] = None

    def to_row(self) -> dict:
        return {
            "event_id": self.event_id,
            "customer_id": self.customer_id,
            "batch_id": self.batch_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "root_cause": self.root_cause,
            "confidence": self.confidence,
            "reasoning_text": self.reasoning_text,
            "guardrail_checks": [c.to_dict() for c in self.guardrail_result.checks],
            "action_type": self.action_type,
            "action_params": self.action_params,
            "action_status": self.guardrail_result.action_status,
            "recovered": self.recovered,
            "amount_recovered": self.amount_recovered,
            "outcome_notes": self.outcome_notes,
            "razorpay_payment_link": self.razorpay_payment_link,
            "is_live_integration": self.is_live_integration,
            "llm_provider": self.llm_provider,
            "llm_fallback_used": self.llm_fallback_used,
            "customer_message": self.customer_message,
        }


def _write_hash_with_retry(
    decision_id: str, record_hash: str, fallback: dict, attempts: int = 3
) -> dict:
    """The insert already committed by the time we get here, so a failed
    hash update leaves a permanently unhashed row (verify.py reports it as
    a broken chain forever, indistinguishable from tampering). Retry with
    backoff to ride out transient Supabase errors before giving up."""
    supabase = get_supabase()
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            update_response = (
                supabase.table("decisions")
                .update({"record_hash": record_hash})
                .eq("decision_id", decision_id)
                .execute()
            )
            if update_response.data:
                return update_response.data[0]
            return fallback
        except Exception as exc:  # noqa: BLE001 - retrying any transient failure
            last_error = exc
            if attempt < attempts - 1:
                time.sleep(0.5 * (2**attempt))
    logger.error(
        "record_hash update failed after %d attempts for decision_id=%s: %s",
        attempts,
        decision_id,
        last_error,
    )
    return fallback


def write_event(event_row: dict) -> None:
    supabase = get_supabase()
    supabase.table("events").upsert(event_row, on_conflict="event_id").execute()


def write_decision(record: DecisionRecord) -> dict:
    """Write one decision row, then chain it (ENHANCEMENTS.md §2.4): insert
    first so Postgres assigns decision_id/chain_seq/timestamp formatting,
    then hash *that* returned representation and write the hash back. See
    hash_chain.py's module docstring for why this is two round-trips
    instead of one."""
    supabase = get_supabase()
    insert_response = supabase.table("decisions").insert(record.to_row()).execute()
    inserted = insert_response.data[0] if insert_response.data else record.to_row()

    previous_hash = hash_chain.get_last_hash()
    record_hash = hash_chain.compute_hash(previous_hash, inserted)

    decision_id = inserted.get("decision_id")
    final = {**inserted, "record_hash": record_hash}
    if decision_id:
        final = _write_hash_with_retry(decision_id, record_hash, fallback=final)

    logger.info(
        "decision written: event=%s action=%s status=%s recovered=%s hash=%s",
        record.event_id,
        record.action_type,
        record.guardrail_result.action_status,
        record.recovered,
        record_hash[:12],
    )
    return final


def write_llm_fallback_event(event_id: str, reason: str, from_provider: str) -> None:
    """Not a separate table (kept in scope for the 3-day build) — logged
    loudly so it's visible in server logs and can be surfaced in the
    reasoning_text/outcome_notes of the resulting decision."""
    logger.warning(
        "LLM FALLBACK: event=%s from_provider=%s reason=%s", event_id, from_provider, reason
    )
