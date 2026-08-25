"use client";

import { useQuery } from "@tanstack/react-query";
import { ShieldCheck, ShieldAlert } from "lucide-react";
import { getFairnessReport } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

export function FairnessCard() {
  const query = useQuery({ queryKey: ["fairness"], queryFn: getFairnessReport });

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm font-medium flex items-center gap-1.5">
          <ShieldCheck className="size-4" />
          Fairness / consistency check
        </CardTitle>
        <p className="text-xs text-muted-foreground">
          Does which action gets proposed differ across customer segments that shouldn&apos;t
          matter? Checks assignment, not outcome — outcomes are properly probabilistic. Honest
          either way; not a claim of proven fairness.
        </p>
      </CardHeader>
      <CardContent>
        {query.isLoading && (
          <p className="text-xs text-muted-foreground">Loading…</p>
        )}
        {query.data && query.data.sample_size < 10 && (
          <p className="text-xs text-muted-foreground">
            Only {query.data.sample_size} decisions on record — run a bigger batch for this
            check to mean anything.
          </p>
        )}
        {query.data && (
          <div className="space-y-3">
            {query.data.dimensions.map((dim) => (
              <div key={dim.dimension} className="space-y-1.5">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-sm font-medium capitalize">{dim.dimension}</span>
                  {dim.max_delta_pp != null && (
                    <Badge
                      className={cn(
                        "gap-1",
                        dim.flagged
                          ? "bg-destructive/15 text-destructive border-destructive/30"
                          : "bg-primary/15 text-primary border-primary/30"
                      )}
                    >
                      {dim.flagged ? (
                        <ShieldAlert className="size-3" />
                      ) : (
                        <ShieldCheck className="size-3" />
                      )}
                      {dim.max_delta_pp}pp gap
                    </Badge>
                  )}
                </div>
                <p className="text-xs text-muted-foreground">{dim.summary}</p>
                <div className="flex flex-wrap gap-1.5">
                  {dim.segments.map((s) => (
                    <span
                      key={s.segment_value}
                      className="text-[11px] font-mono text-muted-foreground bg-muted/40 rounded px-1.5 py-0.5"
                    >
                      {s.segment_value}: {s.restrictive_rate_pct}% flagged (n={s.decision_count})
                    </span>
                  ))}
                </div>
              </div>
            ))}
            <p className="text-[11px] text-muted-foreground/70">
              Threshold: a flag-rate gap over {query.data.threshold_pp} percentage points between
              segments is treated as worth investigating.
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
