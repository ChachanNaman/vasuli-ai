"use client";

import Link from "next/link";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { DecisionSourceBadge } from "@/components/dashboard/decision-source-badge";
import { CounterfactualSandbox } from "@/components/dashboard/counterfactual-sandbox";
import type { DecisionRow } from "@/lib/types";
import {
  formatActionType,
  formatCompactINR,
  formatRootCause,
  formatAbsoluteTime,
} from "@/lib/format";
import { cn } from "@/lib/utils";

export function EventDrillDown({
  decision,
  open,
  onOpenChange,
}: {
  decision: DecisionRow | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  if (!decision) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <div className="flex items-center gap-2 flex-wrap">
            <DialogTitle className="font-mono text-base">{decision.event_id}</DialogTitle>
            <DecisionSourceBadge decision={decision} />
          </div>
          <DialogDescription className="flex items-center gap-2 flex-wrap">
            <span>Full reasoning trace — diagnosis, guardrail checks, action, and outcome.</span>
            <Link
              href={`/dashboard/customers/${encodeURIComponent(decision.customer_id)}`}
              className="text-primary underline underline-offset-2 font-mono text-xs"
            >
              View {decision.customer_id}&apos;s recovery journey →
            </Link>
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-5">
          <section>
            <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-2">
              Diagnosis
            </h4>
            <div className="flex items-center gap-2 mb-1.5">
              <Badge variant="secondary">{formatRootCause(decision.root_cause)}</Badge>
              <span className="text-xs text-muted-foreground font-mono">
                confidence {Math.round(decision.confidence * 100)}%
              </span>
              {decision.llm_provider && (
                <span className="text-xs text-muted-foreground">
                  via {decision.llm_provider}
                  {decision.llm_fallback_used && " (fallback)"}
                </span>
              )}
            </div>
            <p className="text-sm text-muted-foreground leading-relaxed">
              {decision.reasoning_text}
            </p>
          </section>

          <Separator />

          <section>
            <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-2">
              Guardrail checks
            </h4>
            <div className="space-y-1.5">
              {decision.guardrail_checks.map((check) => (
                <div
                  key={check.rule_name}
                  className={cn(
                    "flex items-start gap-2 text-sm rounded-md px-2.5 py-1.5 border",
                    check.passed
                      ? "border-border/50 bg-muted/20"
                      : "border-destructive/40 bg-destructive/10"
                  )}
                >
                  <span
                    className={cn(
                      "font-mono text-xs mt-0.5",
                      check.passed ? "text-primary" : "text-destructive"
                    )}
                  >
                    {check.passed ? "PASS" : "FAIL"}
                  </span>
                  <div className="min-w-0">
                    <span className="font-medium text-xs">{check.rule_name}</span>
                    <p className="text-xs text-muted-foreground">{check.detail}</p>
                  </div>
                </div>
              ))}
            </div>
          </section>

          <Separator />

          <section>
            <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-2">
              {decision.action_status === "executed" ? "Action taken" : "Action proposed"}
            </h4>
            <div className="flex items-center gap-2">
              <Badge>{formatActionType(decision.action_type)}</Badge>
              <Badge
                variant={decision.action_status === "executed" ? "default" : "outline"}
              >
                {formatActionType(decision.action_status)}
              </Badge>
            </div>
            {decision.action_status === "blocked_by_guardrail" && (
              <p className="mt-1.5 text-xs text-muted-foreground">
                The AI proposed {formatActionType(decision.action_type)}; the guardrail engine
                blocked it before it could run. Nothing was substituted in its place — see
                &ldquo;Guardrail checks&rdquo; above for exactly which rule stopped it.
              </p>
            )}
            {decision.action_status === "skipped_opt_out" && (
              <p className="mt-1.5 text-xs text-muted-foreground">
                The AI proposed {formatActionType(decision.action_type)}; it was never sent
                because this customer opted out of recovery comms.
              </p>
            )}
            {decision.customer_message && (
              <p className="mt-2 text-sm bg-muted/30 rounded-md p-3 italic">
                &ldquo;{decision.customer_message}&rdquo;
              </p>
            )}
            {decision.razorpay_payment_link && (
              <div className="mt-2 flex items-center gap-2">
                <a
                  href={decision.razorpay_payment_link}
                  target="_blank"
                  rel="noreferrer"
                  className="text-sm text-primary underline underline-offset-2 font-mono break-all"
                >
                  {decision.razorpay_payment_link}
                </a>
                <Badge variant={decision.is_live_integration ? "default" : "secondary"}>
                  {decision.is_live_integration ? "Live — Razorpay test mode" : "Simulated — test mode"}
                </Badge>
              </div>
            )}
          </section>

          <Separator />

          <section>
            <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-2">
              Outcome
            </h4>
            <div className="flex items-center gap-2">
              <Badge variant={decision.recovered ? "default" : "outline"}>
                {decision.recovered ? "Recovered" : "Not recovered"}
              </Badge>
              {decision.recovered && (
                <span className="font-mono text-sm text-primary">
                  {formatCompactINR(decision.amount_recovered)}
                </span>
              )}
            </div>
            {decision.outcome_notes && (
              <p className="mt-1.5 text-xs text-muted-foreground">{decision.outcome_notes}</p>
            )}
            <p className="mt-2 text-xs text-muted-foreground">
              {formatAbsoluteTime(decision.timestamp)}
            </p>
          </section>

          <Separator />

          <CounterfactualSandbox eventId={decision.event_id} />
        </div>
      </DialogContent>
    </Dialog>
  );
}
