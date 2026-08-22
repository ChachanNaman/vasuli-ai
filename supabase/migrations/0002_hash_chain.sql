-- Vasuli — hash-chained audit trail (ENHANCEMENTS.md §2.4).
--
-- Each decisions row gets a record_hash = sha256(previous_row's record_hash
-- + canonical_json(this row, hash fields excluded)). chain_seq is a plain
-- auto-incrementing sequence used only to establish "what's the previous
-- row" unambiguously — it carries no other meaning and isn't exposed
-- outside the audit/verify module.
--
-- This assumes a single sequential writer (true today: the batch pipeline
-- writes one decision at a time). A concurrent writer would need a
-- DB-side trigger or transaction to keep the chain atomic — out of scope
-- for this demo's minimal version, and noted as such in docs/architecture.md.

alter table decisions add column if not exists chain_seq bigserial;
alter table decisions add column if not exists record_hash text;

create index if not exists idx_decisions_chain_seq on decisions (chain_seq);
