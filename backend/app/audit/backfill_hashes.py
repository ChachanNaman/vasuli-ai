"""One-off repair for the decisions hash chain after a row's record_hash
failed to commit (the two-phase-write gap that verify.py's "record_hash is
missing" error guards against).

Filling in just the missing row isn't enough: get_last_hash() skips null
hashes when picking a "previous hash" to chain off of, so every row
written *after* the gap was already linked to the hash before the gap,
not to it. Backfilling the gap alone leaves the very next row's stored
hash pointing at the wrong previous link. So this walks the whole chain
in order from the first broken position and recomputes every hash from
there forward using each row's now-correct predecessor — re-linking the
chain, not changing any decision's content.

Usage:
    python -m app.audit.backfill_hashes
"""

from __future__ import annotations

import sys

from app.audit.hash_chain import GENESIS_HASH, compute_hash
from app.audit.supabase_client import get_supabase


def backfill() -> tuple[int, int]:
    """Returns (rows_checked, rows_repaired)."""
    supabase = get_supabase()
    response = supabase.table("decisions").select("*").order("chain_seq").execute()
    rows = response.data or []

    previous_hash = GENESIS_HASH
    repaired = 0
    for row in rows:
        stored_hash = row.get("record_hash")
        expected_hash = compute_hash(previous_hash, row)
        if stored_hash != expected_hash:
            supabase.table("decisions").update({"record_hash": expected_hash}).eq(
                "decision_id", row["decision_id"]
            ).execute()
            print(f"repaired decision_id={row['decision_id']} chain_seq={row.get('chain_seq')}")
            stored_hash = expected_hash
            repaired += 1
        previous_hash = stored_hash

    return len(rows), repaired


def main() -> int:
    checked, repaired = backfill()
    print(f"checked {checked} records, repaired {repaired}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
