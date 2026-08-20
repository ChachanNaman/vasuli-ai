-- Vasuli — initial schema
-- events, decisions (audit record, PRD §6.2), and a computed-on-read metrics view.

create extension if not exists "pgcrypto";

-- ---------------------------------------------------------------------------
-- events: raw synthetic loss events (payment_failed, subscription_charge_failed,
-- checkout_abandoned, invoice_overdue). One shared envelope + a jsonb bag for
-- the type-specific fields (schema.py's RevenueEvent.to_dict() output),
-- so we don't need a migration every time the generator's field set changes.
-- ---------------------------------------------------------------------------
create table if not exists events (
    event_id            text primary key,
    event_type          text not null check (event_type in (
                             'payment_failed',
                             'subscription_charge_failed',
                             'checkout_abandoned',
                             'invoice_overdue'
                         )),
    timestamp           timestamptz not null,
    merchant_id         text not null,
    amount              numeric not null default 0,
    currency            text not null default 'INR',
    customer_id         text not null,
    customer            jsonb not null,       -- full CustomerContext
    payload             jsonb not null,       -- full RevenueEvent.to_dict()
    created_at          timestamptz not null default now()
);

create index if not exists idx_events_customer_id on events (customer_id);
create index if not exists idx_events_event_type on events (event_type);
create index if not exists idx_events_timestamp on events (timestamp desc);

-- ---------------------------------------------------------------------------
-- decisions: the audit record. One row per (event, batch-run) decision.
-- Shape matches PRD §6.2 exactly.
-- ---------------------------------------------------------------------------
create table if not exists decisions (
    decision_id          uuid primary key default gen_random_uuid(),
    event_id             text not null references events (event_id) on delete cascade,
    customer_id          text not null,
    timestamp            timestamptz not null default now(),

    -- diagnosis: { root_cause, confidence, reasoning_text }
    root_cause           text not null,
    confidence           numeric not null check (confidence >= 0 and confidence <= 1),
    reasoning_text       text not null,

    -- guardrail_checks: [ { rule_name, passed, detail } ]
    guardrail_checks     jsonb not null default '[]'::jsonb,

    -- action_taken: { type, params }
    action_type          text not null,
    action_params        jsonb not null default '{}'::jsonb,

    action_status        text not null check (action_status in (
                              'executed',
                              'blocked_by_guardrail',
                              'skipped_opt_out'
                          )),

    -- outcome: { recovered, amount_recovered, notes }
    recovered             boolean not null default false,
    amount_recovered      numeric not null default 0,
    outcome_notes          text,

    razorpay_payment_link  text,
    is_live_integration     boolean not null default false, -- true only for real Razorpay test-mode calls
    llm_provider             text,   -- 'groq' | 'gemini' | null (no LLM call, e.g. guardrail pre-block)
    llm_fallback_used        boolean not null default false,

    customer_message        text,

    created_at              timestamptz not null default now()
);

create index if not exists idx_decisions_event_id on decisions (event_id);
create index if not exists idx_decisions_customer_id on decisions (customer_id);
create index if not exists idx_decisions_timestamp on decisions (timestamp desc);
create index if not exists idx_decisions_action_status on decisions (action_status);
create index if not exists idx_decisions_root_cause on decisions (root_cause);

alter table decisions enable row level security;
alter table events enable row level security;

-- Single-merchant demo, no auth system (PRD §3.2) — allow anon read for the
-- dashboard/live feed, restrict writes to the service role (backend only).
create policy "public read events" on events for select using (true);
create policy "public read decisions" on decisions for select using (true);
create policy "service write events" on events for insert to service_role using (true) with check (true);
create policy "service write decisions" on decisions for insert to service_role using (true) with check (true);

-- Enable Supabase Realtime on decisions for the live agent feed (PRD §12.3).
alter publication supabase_realtime add table decisions;

-- ---------------------------------------------------------------------------
-- metrics: computed-on-read aggregate view (PRD §6.3). No redundant storage —
-- recomputed from decisions on every query.
-- ---------------------------------------------------------------------------
create or replace view metrics_overview as
select
    coalesce(sum(e.amount), 0)                                          as total_exposure,
    coalesce(sum(d.amount_recovered) filter (where d.recovered), 0)      as total_recovered,
    count(d.decision_id)                                                 as total_decisions,
    count(d.decision_id) filter (where d.recovered)                      as recovered_count,
    round(
        (count(d.decision_id) filter (where d.recovered))::numeric
        / nullif(count(d.decision_id), 0) * 100,
    2)                                                                   as recovery_rate_pct,
    count(d.decision_id) filter (where d.action_status = 'blocked_by_guardrail') as guardrail_block_count,
    count(d.decision_id) filter (where d.action_status = 'skipped_opt_out')      as opt_out_respected_count,
    count(d.decision_id) filter (
        where d.action_type in ('flag_for_human_review', 'no_action_recommended')
    )                                                                    as exception_count
from decisions d
join events e on e.event_id = d.event_id;

create or replace view metrics_by_root_cause as
select
    d.root_cause,
    count(*)                                                            as decision_count,
    count(*) filter (where d.recovered)                                 as recovered_count,
    round(
        (count(*) filter (where d.recovered))::numeric
        / nullif(count(*), 0) * 100,
    2)                                                                   as recovery_rate_pct,
    coalesce(sum(d.amount_recovered) filter (where d.recovered), 0)      as amount_recovered
from decisions d
group by d.root_cause
order by decision_count desc;

create or replace view metrics_exceptions as
select
    d.decision_id,
    d.event_id,
    d.customer_id,
    d.timestamp,
    d.root_cause,
    d.action_type,
    d.action_status,
    d.reasoning_text,
    d.outcome_notes
from decisions d
where d.action_type in ('flag_for_human_review', 'no_action_recommended')
   or d.action_status in ('blocked_by_guardrail', 'skipped_opt_out')
order by d.timestamp desc;
