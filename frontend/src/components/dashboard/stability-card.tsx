"use client";

import { useQuery } from "@tanstack/react-query";
import { ShieldCheck, ShieldAlert } from "lucide-react";
import { getStabilityReport } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import type { EvalArmNameForStability, StabilityMetricStats } from "@/lib/types";

const ARM_LABELS: Record<EvalArmNameForStability, string> = {
  do_nothing: "Do nothing",
  fixed_dunning: "Fixed dunning",
  vasuli: "Vasuli",
  max_pressure: "Max pressure",
};

const METRIC_LABELS: Record<string, string> = {
  incremental_recovered: "Incremental ₹",
  incremental_recovery_rate_pct: "Incremental %",
  guardrail_violations: "Violations",
  contacts_per_case: "Contacts/case",
};

function MetricPill({ label, stats }: { label: string; stats: StabilityMetricStats }) {
  return (
    <div
      className={cn(
        "rounded-md border px-2 py-1.5 text-[11px]",
        stats.stable ? "border-border/50 bg-muted/20" : "border-destructive/40 bg-destructive/10"
      )}
    >
      <div className="flex items-center justify-between gap-1">
        <span className="text-muted-foreground">{label}</span>
        {stats.cv_pct != null && (
          <span className={stats.stable ? "text-primary" : "text-destructive"}>
            CV {stats.cv_pct}%
          </span>
        )}
      </div>
      <div className="font-mono text-foreground">
        {stats.mean.toLocaleString("en-IN")} ± {stats.std.toLocaleString("en-IN")}
      </div>
    </div>
  );
}

export function StabilityCard() {
  const query = useQuery({
    queryKey: ["stability"],
    queryFn: () => getStabilityReport(200, 20, 42),
    staleTime: 5 * 60_000,
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm font-medium flex items-center gap-1.5">
          <ShieldCheck className="size-4" />
          Seed stability check
        </CardTitle>
        <p className="text-xs text-muted-foreground">
          Would the vs.-Baseline numbers still say the same thing on a different seed? Runs the
          full 4-arm comparison across {query.data?.n_seeds ?? 20} independent seeds and flags any
          metric whose seed-to-seed swing exceeds {query.data?.noise_threshold_cv_pct ?? 25}% —
          an honest number stays honest even when re-run.
        </p>
      </CardHeader>
      <CardContent>
        {query.isLoading && (
          <div className="space-y-2">
            <Skeleton className="h-16 w-full" />
            <Skeleton className="h-16 w-full" />
          </div>
        )}
        {query.data && (
          <div className="space-y-3">
            {(Object.keys(ARM_LABELS) as EvalArmNameForStability[]).map((arm) => {
              const armStats = query.data!.arms[arm];
              const anyUnstable = Object.values(armStats).some((s) => !s.stable);
              return (
                <div key={arm} className="space-y-1.5">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium">{ARM_LABELS[arm]}</span>
                    <Badge
                      className={cn(
                        "gap-1",
                        anyUnstable
                          ? "bg-destructive/15 text-destructive border-destructive/30"
                          : "bg-primary/15 text-primary border-primary/30"
                      )}
                    >
                      {anyUnstable ? (
                        <ShieldAlert className="size-3" />
                      ) : (
                        <ShieldCheck className="size-3" />
                      )}
                      {anyUnstable ? "some metrics noisy" : "all stable"}
                    </Badge>
                  </div>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-1.5">
                    {Object.entries(METRIC_LABELS).map(([key, label]) => (
                      <MetricPill
                        key={key}
                        label={label}
                        stats={armStats[key as keyof typeof armStats]}
                      />
                    ))}
                  </div>
                </div>
              );
            })}
            <p className="text-[11px] text-muted-foreground/70">
              {query.data.cases_per_seed} cases × {query.data.n_seeds} seeds, base seed{" "}
              {query.data.base_seed} — rupee-denominated metrics are typically noisier than
              count/rate metrics for a small batch (a few large invoices can swing a total); that
              asymmetry is expected, not a bug.
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
