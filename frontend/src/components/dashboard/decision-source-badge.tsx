"use client";

import { Badge } from "@/components/ui/badge";
import { decisionSource } from "@/lib/format";
import { cn } from "@/lib/utils";

const VARIANT_CLASS: Record<string, string> = {
  ai_proposed: "bg-primary/15 text-primary border-primary/30",
  guardrail_blocked: "bg-destructive/15 text-destructive border-destructive/30",
  heuristic_fallback: "bg-secondary text-secondary-foreground border-transparent",
};

export function DecisionSourceBadge({
  decision,
  className,
  hideIfRedundant = false,
}: {
  decision: { action_status: string; llm_provider: string | null };
  className?: string;
  /** In the live feed and exceptions tab, a "guardrail_blocked" source
   * badge repeats text already shown by an adjacent action_status badge —
   * pass true there to suppress it. Everywhere else (event drill-down,
   * customer timeline) this badge is the *only* per-decision-source
   * indicator, so it must always render — never set this true globally. */
  hideIfRedundant?: boolean;
}) {
  const info = decisionSource(decision);
  if (hideIfRedundant && info.source === "guardrail_blocked") {
    return null;
  }
  return (
    <Badge className={cn(VARIANT_CLASS[info.source], className)} title={info.label}>
      <span aria-hidden>{info.icon}</span>
      {info.label}
    </Badge>
  );
}
