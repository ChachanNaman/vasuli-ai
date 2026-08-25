-- metrics_overview.exception_count and metrics_exceptions used different
-- filters: the count only checked action_type in (flag_for_human_review,
-- no_action_recommended), while the view a judge actually sees also
-- includes action_status in (blocked_by_guardrail, skipped_opt_out) via
-- an OR. Result: the "Exceptions (N)" tab badge undercounted the list
-- rendered below it (e.g. badge said 1, list showed 2, because a
-- guardrail-blocked decision was in the list but not the count). Making
-- the count's filter match the view's WHERE clause exactly.
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
           or d.action_status in ('blocked_by_guardrail', 'skipped_opt_out')
    )                                                                    as exception_count
from decisions d
join events e on e.event_id = d.event_id;
