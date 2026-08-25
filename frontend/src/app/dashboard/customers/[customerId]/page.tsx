"use client";

import { use } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { motion } from "motion/react";
import { getCustomerTimeline } from "@/lib/api";
import { DecisionSourceBadge } from "@/components/dashboard/decision-source-badge";
import { AmbientBackground } from "@/components/motion/ambient-background";
import { Badge } from "@/components/ui/badge";
import {
  formatActionType,
  formatCompactINR,
  formatRootCause,
  formatAbsoluteTime,
} from "@/lib/format";
import { cn } from "@/lib/utils";

export default function CustomerTimelinePage({
  params,
}: {
  params: Promise<{ customerId: string }>;
}) {
  const { customerId } = use(params);

  const query = useQuery({
    queryKey: ["customer-timeline", customerId],
    queryFn: () => getCustomerTimeline(customerId),
    retry: false,
  });

  return (
    <div className="relative mx-auto min-h-dvh max-w-3xl px-4 md:px-6 py-8 space-y-6">
      <AmbientBackground />
      <header>
        <Link href="/dashboard" className="text-sm text-muted-foreground hover:text-foreground">
          ← Dashboard
        </Link>
        <h1 className="text-xl font-semibold mt-1">
          {query.data?.customer?.name ?? "Customer"} — recovery journey
        </h1>
        <p className="text-sm text-muted-foreground font-mono mt-0.5">{customerId}</p>
      </header>

      {query.isLoading && (
        <p className="text-sm text-muted-foreground">Loading…</p>
      )}

      {query.isError && (
        <div className="rounded-lg border border-dashed border-border/60 px-4 py-8 text-center text-sm text-muted-foreground">
          No decisions on record for this customer yet.
        </div>
      )}

      {query.data && (
        <ol className="relative border-l border-border/60 pl-6 space-y-6">
          {query.data.steps.map((step, i) => (
            <motion.li
              key={step.decision_id}
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: Math.min(i * 0.05, 0.4) }}
              className="relative"
            >
              <span
                className={cn(
                  "absolute -left-[1.72rem] top-1.5 size-3 rounded-full border-2 border-background",
                  step.recovered
                    ? "bg-primary"
                    : step.action_status === "blocked_by_guardrail"
                      ? "bg-destructive"
                      : "bg-muted-foreground"
                )}
              />
              <div className="rounded-lg border border-border/60 bg-card px-4 py-3">
                <div className="flex items-center justify-between gap-2 flex-wrap">
                  <div className="flex items-center gap-2 flex-wrap">
                    <Badge variant="outline">
                      {step.event_type ? formatActionType(step.event_type) : "unknown event"}
                    </Badge>
                    <span className="text-muted-foreground text-xs">→</span>
                    <Badge>{formatActionType(step.action_type)}</Badge>
                    <DecisionSourceBadge decision={step} />
                  </div>
                  <span className="text-xs text-muted-foreground">
                    {formatAbsoluteTime(step.timestamp)}
                  </span>
                </div>
                <p className="mt-1.5 text-sm text-muted-foreground">
                  {formatRootCause(step.root_cause)}
                  {step.event_amount != null && (
                    <span className="font-mono"> · {formatCompactINR(step.event_amount)}</span>
                  )}
                </p>
                <div className="mt-1.5 flex items-center gap-2">
                  <Badge variant={step.recovered ? "default" : "outline"}>
                    {step.recovered ? "Recovered" : "Not recovered"}
                  </Badge>
                  {step.recovered && (
                    <span className="font-mono text-xs text-primary">
                      +{formatCompactINR(step.amount_recovered)}
                    </span>
                  )}
                </div>
              </div>
            </motion.li>
          ))}
        </ol>
      )}
    </div>
  );
}
