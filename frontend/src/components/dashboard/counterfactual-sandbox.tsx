"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { FlaskConical } from "lucide-react";
import { runCounterfactual } from "@/lib/api";
import { formatActionType, formatCompactINR } from "@/lib/format";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { ActionType } from "@/lib/types";

// FEATURES.md #5 — the fixed allowed-action set (PRD 8.2), mirrored from
// backend/app/agents/prompts.py's ALLOWED_ACTIONS. The endpoint itself is
// the source of truth (it validates against ALLOWED_ACTIONS server-side)
// — this list is just what populates the dropdown.
const ACTIONS: ActionType[] = [
  "smart_retry",
  "generate_payment_link",
  "send_nudge",
  "escalate_b2b_chase",
  "initiate_mandate_reauth",
  "flag_for_human_review",
  "no_action_recommended",
];

export function CounterfactualSandbox({ eventId }: { eventId: string }) {
  const [selectedAction, setSelectedAction] = useState<ActionType>("smart_retry");

  const mutation = useMutation({
    mutationFn: () => runCounterfactual(eventId, selectedAction),
  });

  const result = mutation.data;

  return (
    <section>
      <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-2 flex items-center gap-1.5">
        <FlaskConical className="size-3.5" />
        Try a different action
      </h4>
      <p className="text-xs text-muted-foreground mb-2">
        Runs the action you pick through the real guardrail engine for this event&apos;s actual
        state — live, not a canned example. Nothing is ever sent for real from here.
      </p>
      <div className="flex items-center gap-2">
        <select
          value={selectedAction}
          onChange={(e) => setSelectedAction(e.target.value as ActionType)}
          className="text-sm rounded-md border border-border bg-background px-2 py-1.5"
        >
          {ACTIONS.map((action) => (
            <option key={action} value={action}>
              {formatActionType(action)}
            </option>
          ))}
        </select>
        <button
          onClick={() => mutation.mutate()}
          disabled={mutation.isPending}
          className={cn(
            "inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors",
            mutation.isPending
              ? "bg-processing/15 text-processing cursor-not-allowed"
              : "bg-primary text-primary-foreground hover:bg-primary/90"
          )}
        >
          {mutation.isPending ? "Running guardrails…" : "Run through guardrails"}
        </button>
      </div>

      {mutation.isError && (
        <p className="mt-2 text-xs text-destructive">
          {(mutation.error as Error).message}
        </p>
      )}

      {result && (
        <div className="mt-3 space-y-2">
          <div className="flex items-center gap-2 flex-wrap">
            <Badge variant="outline" className="font-mono text-[10px]">
              simulated projection
            </Badge>
            <Badge
              className={
                result.action_status === "executed"
                  ? "bg-primary/15 text-primary border-primary/30"
                  : "bg-destructive/15 text-destructive border-destructive/30"
              }
            >
              {result.action_status === "executed" ? "Cleared" : "Blocked"}
            </Badge>
          </div>

          <div className="space-y-1">
            {result.checks.map((check) => (
              <div
                key={check.rule_name}
                className={cn(
                  "flex items-start gap-2 text-xs rounded-md px-2 py-1 border",
                  check.passed
                    ? "border-border/50 bg-muted/20"
                    : "border-destructive/40 bg-destructive/10"
                )}
              >
                <span
                  className={cn(
                    "font-mono mt-0.5",
                    check.passed ? "text-primary" : "text-destructive"
                  )}
                >
                  {check.passed ? "PASS" : "FAIL"}
                </span>
                <div className="min-w-0">
                  <span className="font-medium">{check.rule_name}</span>
                  <p className="text-muted-foreground">{check.detail}</p>
                </div>
              </div>
            ))}
          </div>

          {result.action_status === "executed" &&
            result.simulated_recovery_probability != null && (
              <p className="text-xs text-muted-foreground">
                Simulated recovery probability:{" "}
                <span className="font-mono text-foreground">
                  {Math.round(result.simulated_recovery_probability * 100)}%
                </span>{" "}
                (expected ≈{" "}
                {formatCompactINR(result.simulated_expected_recovery_amount ?? 0)} if executed —
                not a real Razorpay call)
              </p>
            )}

          {result.action_status !== "executed" && result.block_reason && (
            <p className="text-xs text-muted-foreground">{result.block_reason}</p>
          )}
        </div>
      )}
    </section>
  );
}
