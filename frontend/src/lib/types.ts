export type EventType =
  | "payment_failed"
  | "subscription_charge_failed"
  | "checkout_abandoned"
  | "invoice_overdue";

export type ActionType =
  | "smart_retry"
  | "generate_payment_link"
  | "send_nudge"
  | "escalate_b2b_chase"
  | "initiate_mandate_reauth"
  | "flag_for_human_review"
  | "no_action_recommended";

export type ActionStatus = "executed" | "blocked_by_guardrail" | "skipped_opt_out";

export interface CustomerContext {
  customer_id: string;
  name: string;
  past_successful_payments: number;
  past_failed_payments: number;
  tenure_months: number;
  opted_out_of_recovery_comms: boolean;
  preferred_channel: string;
  language_pref: string;
}

export interface EventRow {
  event_id: string;
  event_type: EventType;
  timestamp: string;
  merchant_id: string;
  amount: number;
  currency: string;
  customer_id: string;
  customer: CustomerContext;
  payload: Record<string, unknown>;
  created_at: string;
}

export interface GuardrailCheck {
  rule_name: string;
  passed: boolean;
  detail: string;
}

export interface DecisionRow {
  decision_id: string;
  event_id: string;
  customer_id: string;
  timestamp: string;
  root_cause: string;
  confidence: number;
  reasoning_text: string;
  guardrail_checks: GuardrailCheck[];
  action_type: ActionType;
  action_params: Record<string, unknown>;
  action_status: ActionStatus;
  recovered: boolean;
  amount_recovered: number;
  outcome_notes: string | null;
  razorpay_payment_link: string | null;
  is_live_integration: boolean;
  llm_provider: "groq" | "gemini" | null;
  llm_fallback_used: boolean;
  customer_message: string | null;
  created_at: string;
}

export interface MetricsOverview {
  total_exposure: number;
  total_recovered: number;
  total_decisions: number;
  recovered_count: number;
  recovery_rate_pct: number | null;
  guardrail_block_count: number;
  opt_out_respected_count: number;
  exception_count: number;
}

export interface MetricsByRootCause {
  root_cause: string;
  decision_count: number;
  recovered_count: number;
  recovery_rate_pct: number | null;
  amount_recovered: number;
}

export interface ExceptionRow {
  decision_id: string;
  event_id: string;
  customer_id: string;
  timestamp: string;
  root_cause: string;
  action_type: ActionType;
  action_status: ActionStatus;
  reasoning_text: string;
  outcome_notes: string | null;
}

export interface MetricsResponse {
  overview: MetricsOverview;
  by_root_cause: MetricsByRootCause[];
  exceptions: ExceptionRow[];
}

export interface AuditVerifyResponse {
  ok: boolean;
  records_checked: number;
  error: string | null;
}

export type EvalArmName = "do_nothing" | "fixed_dunning" | "vasuli" | "max_pressure";

export interface EvalArmSummary {
  cases: number;
  total_exposure: number;
  raw_recovered: number;
  raw_recovery_rate_pct: number;
  incremental_recovered: number;
  incremental_recovery_rate_pct: number;
  total_cost: number;
  cost_per_rupee_recovered: number | null;
  contacts: number;
  contacts_per_case: number;
  guardrail_violations: number;
  guardrail_violations_per_case: number;
}

export interface EvalComparisonResponse {
  n_cases: number;
  seed: number;
  arms: Record<EvalArmName, EvalArmSummary>;
  recovery_by_cause: Record<EvalArmName, Record<string, { cases: number; recovery_rate_pct: number }>>;
}
