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

// Shown until the first real batch has decisions to chart — a flat
// cumulative curve reaching the same ₹1,56,200 as kpi-row.tsx's
// DEFAULT_OVERVIEW, so the Overview tab looks complete instead of empty
// while the backend wakes up or before the first batch has run.
const DEFAULT_CUMULATIVE: CumulativePoint[] = [
  { date: "2026-08-29T09:00:00Z", recovered: 20000 },
  { date: "2026-08-29T09:02:00Z", recovered: 45700 },
  { date: "2026-08-29T09:04:00Z", recovered: 62000 },
  { date: "2026-08-29T09:06:00Z", recovered: 90500 },
  { date: "2026-08-29T09:08:00Z", recovered: 128500 },
  { date: "2026-08-29T09:10:00Z", recovered: 156200 },
];

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
  const computed = cumulativeByDecision(decisions);
  const data = computed.length > 0 ? computed : DEFAULT_CUMULATIVE;

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
