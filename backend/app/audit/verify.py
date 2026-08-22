"""Audit-chain integrity verifier (ENHANCEMENTS.md §2.4).

Walks the `decisions` table in chain order and recomputes each row's hash
from its own content plus the previous row's hash, failing loudly at the
first mismatch. A mismatch means a row was altered or deleted after it was
written — the chain can only be extended, never edited, without detection.

Usage:
    python -m app.audit.verify
"""

from __future__ import annotations

import sys

from app.audit.hash_chain import GENESIS_HASH, compute_hash
from app.audit.supabase_client import get_supabase


def verify_chain() -> tuple[bool, int, str | None]:
    """Returns (ok, records_checked, error_message)."""
    supabase = get_supabase()
    response = supabase.table("decisions").select("*").order("chain_seq").execute()
    rows = response.data or []

    previous_hash = GENESIS_HASH
    for i, row in enumerate(rows):
        stored_hash = row.get("record_hash")
        expected_hash = compute_hash(previous_hash, row)

        if not stored_hash:
            return False, i, (
                f"position {i} (decision_id={row.get('decision_id')}): "
                "record_hash is missing — write may have been interrupted "
                "before the hash was committed, or the column was cleared"
            )
        if stored_hash != expected_hash:
            return False, i, (
                f"position {i} (decision_id={row.get('decision_id')}): "
                f"expected hash {expected_hash[:16]}..., found {stored_hash[:16]}... "
                "— this record or an earlier one has been altered"
            )
        previous_hash = stored_hash

    return True, len(rows), None


def main() -> int:
    ok, count, error = verify_chain()
    if ok:
        print(f"✅ {count} records verified, chain intact")
        return 0
    print(f"❌ chain broken at {error}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
