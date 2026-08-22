"""Unit tests for the hash-chain primitives (ENHANCEMENTS.md §2.4).

Pure-function tests — no Supabase, no mocks. `get_last_hash` (the one
function that talks to the database) is covered indirectly by the
pipeline integration tests in test_pipeline_integration.py.
"""

from __future__ import annotations

from app.audit.hash_chain import GENESIS_HASH, canonical_json, compute_hash


def test_genesis_hash_is_stable():
    assert GENESIS_HASH == "f22c40ad87831b7e8e7522c299eef57a2ca28fd0161a0a90ff7815aec5a4c42e"
    assert len(GENESIS_HASH) == 64


def test_canonical_json_excludes_hash_bookkeeping_fields():
    record = {"event_id": "evt_1", "record_hash": "abc", "chain_seq": 5}
    serialized = canonical_json(record)
    assert "record_hash" not in serialized
    assert "chain_seq" not in serialized
    assert "evt_1" in serialized


def test_canonical_json_is_order_independent():
    a = canonical_json({"b": 1, "a": 2})
    b = canonical_json({"a": 2, "b": 1})
    assert a == b


def test_compute_hash_is_deterministic():
    record = {"event_id": "evt_1", "amount": 999.0}
    h1 = compute_hash(GENESIS_HASH, record)
    h2 = compute_hash(GENESIS_HASH, record)
    assert h1 == h2
    assert len(h1) == 64  # sha256 hex digest


def test_compute_hash_changes_if_record_changes():
    base = {"event_id": "evt_1", "amount": 999.0}
    mutated = {"event_id": "evt_1", "amount": 1000.0}
    assert compute_hash(GENESIS_HASH, base) != compute_hash(GENESIS_HASH, mutated)


def test_compute_hash_changes_if_previous_hash_changes():
    record = {"event_id": "evt_1", "amount": 999.0}
    h1 = compute_hash(GENESIS_HASH, record)
    h2 = compute_hash("some_other_previous_hash", record)
    assert h1 != h2


def test_compute_hash_ignores_bookkeeping_fields_in_input():
    """record_hash/chain_seq on the input record itself shouldn't affect
    the computed hash — they're excluded by canonical_json before hashing."""
    record_a = {"event_id": "evt_1", "amount": 999.0, "record_hash": "x", "chain_seq": 1}
    record_b = {"event_id": "evt_1", "amount": 999.0, "record_hash": "y", "chain_seq": 2}
    assert compute_hash(GENESIS_HASH, record_a) == compute_hash(GENESIS_HASH, record_b)
