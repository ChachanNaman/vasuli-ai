-- Every click of "Run recovery batch" writes into the same shared events/
-- decisions tables, and metrics_overview sums the whole table with no
-- notion of "this run" vs "everyone's runs so far" — so the dashboard's
-- headline numbers only ever grow across every demo click anyone has ever
-- made, instead of describing the batch that just ran. Tagging each row
-- with the batch_id that produced it lets the API scope reads to "the
-- latest batch" without deleting or touching any historical data.
alter table events add column if not exists batch_id text;
alter table decisions add column if not exists batch_id text;

create index if not exists idx_events_batch_id on events (batch_id);
create index if not exists idx_decisions_batch_id on decisions (batch_id);
