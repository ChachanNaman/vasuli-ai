-- FEATURES.md #1: the decision-source badge needs llm_provider to tell a
-- heuristic-fallback decision apart from an LLM-proposed one, but
-- metrics_exceptions never selected it. Not a new column — llm_provider
-- has existed on `decisions` since 0001_init.sql; this just adds it to the
-- view's projection (CREATE OR REPLACE VIEW may append columns at the end
-- without breaking existing consumers of the earlier columns).
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
    d.outcome_notes,
    d.llm_provider
from decisions d
where d.action_type in ('flag_for_human_review', 'no_action_recommended')
   or d.action_status in ('blocked_by_guardrail', 'skipped_opt_out')
order by d.timestamp desc;
