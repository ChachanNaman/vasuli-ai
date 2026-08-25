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
}: {
  decision: { action_status: string; llm_provider: string | null };
  className?: string;
}) {
  const info = decisionSource(decision);
  return (
    <Badge className={cn(VARIANT_CLASS[info.source], className)} title={info.label}>
      <span aria-hidden>{info.icon}</span>
      {info.label}
    </Badge>
  );
}
