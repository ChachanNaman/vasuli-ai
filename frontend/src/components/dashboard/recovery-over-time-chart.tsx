"use client";

import { AreaChart } from "@/components/charts/area-chart";
import { Area } from "@/components/charts/area";
import { Grid } from "@/components/charts/grid";
import { XAxis } from "@/components/charts/x-axis";
import { ChartTooltip } from "@/components/charts/tooltip/chart-tooltip";
import type { DecisionRow } from "@/lib/types";

interface CumulativePoint extends Record<string, unknown> {
  date: string;
  recovered: number;
}

// Cumulative running total, one point per decision. Demo batches complete
// within seconds/minutes, so day-level bucketing would collapse an entire
// run into a single flat point — a cumulative series is what actually
// reads as "money recovered over time" for a single live batch.
function cumulativeByDecision(decisions: DecisionRow[]): CumulativePoint[] {
  const sorted = [...decisions].sort(
    (a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
  );

  let running = 0;
  return sorted.map((d) => {
    running += d.amount_recovered;
    return { date: d.timestamp, recovered: running };
  });
}

export function RecoveryOverTimeChart({ decisions }: { decisions: DecisionRow[] }) {
  const data = cumulativeByDecision(decisions);

  if (data.length === 0) {
    return (
      <div className="flex items-center justify-center h-48 text-sm text-muted-foreground border border-dashed rounded-lg">
        No decisions yet — run a batch to see recovery accumulate.
      </div>
    );
  }

  return (
    <AreaChart data={data} xDataKey="date" status="ready" aspectRatio="3 / 1">
      <Grid horizontal numTicksRows={4} />
      <XAxis />
      <Area
        dataKey="recovered"
        fill="var(--chart-1)"
        stroke="var(--chart-1)"
      />
      <ChartTooltip />
    </AreaChart>
  );
}
