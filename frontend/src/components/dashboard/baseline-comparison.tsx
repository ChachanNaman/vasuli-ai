"use client";

import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, XCircle, Loader2 } from "lucide-react";
import { getAuditVerify, getEvalComparison } from "@/lib/api";
import { formatCompactINR } from "@/lib/format";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import type { EvalArmName } from "@/lib/types";

const ARM_LABELS: Record<EvalArmName, string> = {
  do_nothing: "Do nothing",
  fixed_dunning: "Fixed dunning",
  vasuli: "Vasuli",
  max_pressure: "Max pressure",
};

const ARM_NOTES: Record<EvalArmName, string> = {
  do_nothing: "Organic recovery baseline — zero intervention",
  fixed_dunning: "Same fixed action for every case, no guardrails checked",
  vasuli: "Heuristic diagnosis + the real guardrail engine",
  max_pressure: "Most aggressive action possible, guardrails ignored entirely",
};

const ARM_ORDER: EvalArmName[] = ["do_nothing", "fixed_dunning", "vasuli", "max_pressure"];

function AuditIntegrityBadge() {
  const { data, isLoading } = useQuery({
    queryKey: ["audit-verify"],
    queryFn: getAuditVerify,
    refetchInterval: 30_000,
  });

  if (isLoading) {
    return (
      <Badge variant="outline" className="gap-1.5">
        <Loader2 className="size-3 animate-spin" />
        Checking audit chain…
      </Badge>
    );
  }

  if (!data) return null;

  if (data.ok) {
    return (
      <Badge variant="outline" className="gap-1.5 border-primary/30 text-primary">
        <CheckCircle2 className="size-3" />
        Audit integrity: verified — {data.records_checked.toLocaleString("en-IN")} records
      </Badge>
    );
  }

  return (
    <Badge variant="destructive" className="gap-1.5">
      <XCircle className="size-3" />
      Audit integrity: broken — {data.error}
    </Badge>
  );
}

export function BaselineComparison({ cases = 300 }: { cases?: number }) {
  const { data, isLoading } = useQuery({
    queryKey: ["eval-comparison", cases],
    queryFn: () => getEvalComparison(cases, 42),
  });

  return (
    <Card className="border-border/60">
      <CardHeader className="flex-row items-start justify-between gap-4 flex-wrap">
        <div>
          <CardTitle className="text-sm font-medium">Vasuli vs. baseline policies</CardTitle>
          <p className="mt-1 text-xs text-muted-foreground">
            Same {cases.toLocaleString("en-IN")} synthetic cases run through four policies with
            common random numbers — incremental recovery nets out the ~15–20% of value that
            recovers on its own with zero intervention.
          </p>
        </div>
        <AuditIntegrityBadge />
      </CardHeader>
      <CardContent>
        {isLoading || !data ? (
          <div className="space-y-2">
            <Skeleton className="h-8 w-full" />
            <Skeleton className="h-8 w-full" />
            <Skeleton className="h-8 w-full" />
            <Skeleton className="h-8 w-full" />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border/60 text-left text-xs uppercase tracking-wide text-muted-foreground">
                  <th className="py-2 pr-3 font-medium">Policy</th>
                  <th className="py-2 pr-3 font-medium">Incremental recovered</th>
                  <th className="py-2 pr-3 font-medium">Raw recovery</th>
                  <th className="py-2 pr-3 font-medium">Contacts/case</th>
                  <th className="py-2 pr-3 font-medium">Guardrail violations</th>
                  <th className="py-2 font-medium">Cost</th>
                </tr>
              </thead>
              <tbody>
                {ARM_ORDER.map((arm) => {
                  const summary = data.arms[arm];
                  const isVasuli = arm === "vasuli";
                  return (
                    <tr
                      key={arm}
                      className={
                        isVasuli
                          ? "border-b border-border/40 bg-primary/5"
                          : "border-b border-border/40"
                      }
                    >
                      <td className="py-2.5 pr-3">
                        <div className={isVasuli ? "font-semibold text-primary" : "font-medium"}>
                          {ARM_LABELS[arm]}
                        </div>
                        <div className="text-xs text-muted-foreground">{ARM_NOTES[arm]}</div>
                      </td>
                      <td className="py-2.5 pr-3 font-mono tabular-nums">
                        {formatCompactINR(summary.incremental_recovered)}
                        <span className="ml-1 text-xs text-muted-foreground">
                          ({summary.incremental_recovery_rate_pct.toFixed(1)}%)
                        </span>
                      </td>
                      <td className="py-2.5 pr-3 font-mono tabular-nums text-muted-foreground">
                        {formatCompactINR(summary.raw_recovered)} (
                        {summary.raw_recovery_rate_pct.toFixed(1)}%)
                      </td>
                      <td className="py-2.5 pr-3 font-mono tabular-nums">
                        {summary.contacts_per_case.toFixed(2)}
                      </td>
                      <td className="py-2.5 pr-3 font-mono tabular-nums">
                        <span
                          className={
                            isVasuli && summary.guardrail_violations > 0
                              ? "text-primary"
                              : summary.guardrail_violations > 0
                                ? "text-destructive"
                                : ""
                          }
                        >
                          {summary.guardrail_violations}
                        </span>
                      </td>
                      <td className="py-2.5 font-mono tabular-nums text-muted-foreground">
                        {formatCompactINR(summary.total_cost)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
        {data && (
          <p className="mt-4 text-xs text-muted-foreground">
            fixed_dunning and max_pressure land on identical figures here — this harness evaluates
            each case independently with no cross-case history, so the guardrail rules that most
            separate &quot;one naive retry&quot; from &quot;retry as often as technically
            possible&quot; (cool-down, daily contact cap, retry-storm rate limit) need a
            multi-touch sequential simulation to diverge. Stated plainly rather than hidden.
          </p>
        )}
      </CardContent>
    </Card>
  );
}
