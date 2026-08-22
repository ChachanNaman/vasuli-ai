"""Hash-chained audit trail (ENHANCEMENTS.md §2.4).

Each `decisions` row's `record_hash` is `sha256(previous_hash +
canonical_json(this_row))`, where `canonical_json` excludes the hash/chain
bookkeeping fields themselves. Any edit or deletion of a past row breaks
every hash after it — `python -m app.audit.verify` walks the chain and
proves whether that's happened.

Design note on why writes are two-phase (insert, then update with the
hash) rather than computing the hash before inserting: Postgres reformats
values on the way in (numeric precision, timestamptz string format,
JSONB key ordering). If we hashed the pre-insert Python dict, a later
verification pass would recompute the hash from the *post-insert*
representation and never match, even with nothing tampered. Hashing the
row exactly as the database hands it back — both at write time and at
verify time — means the two are always working from the same
representation.
"""

from __future__ import annotations

import hashlib
import json

from app.audit.supabase_client import get_supabase

GENESIS_HASH = hashlib.sha256(b"vasuli-genesis").hexdigest()

# Fields excluded from the hashed payload: chain_seq and record_hash are
# bookkeeping about the chain itself, not part of the decision it records.
HASH_EXCLUDED_FIELDS = {"record_hash", "chain_seq"}


def canonical_json(record: dict) -> str:
    """Deterministic JSON serialization: sorted keys, no incidental
    whitespace, so the same logical record always hashes identically
    regardless of dict insertion order."""
    payload = {k: v for k, v in record.items() if k not in HASH_EXCLUDED_FIELDS}
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def compute_hash(previous_hash: str, record: dict) -> str:
    return hashlib.sha256((previous_hash + canonical_json(record)).encode("utf-8")).hexdigest()


def get_last_hash() -> str:
    """The most recent record's hash, or GENESIS_HASH if the chain is
    empty. Reads a small batch ordered by chain_seq rather than assuming
    the very last row already has its hash committed (the two-phase write
    means there's a brief window, within one write, where the newest row
    has chain_seq set but record_hash still null)."""
    supabase = get_supabase()
    response = (
        supabase.table("decisions")
        .select("record_hash")
        .order("chain_seq", desc=True)
        .limit(20)
        .execute()
    )
    for row in response.data or []:
        if row.get("record_hash"):
            return row["record_hash"]
    return GENESIS_HASH
