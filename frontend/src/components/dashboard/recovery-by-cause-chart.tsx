"use client";

import { BarChart } from "@/components/charts/bar-chart";
import { Bar } from "@/components/charts/bar";
import { Grid } from "@/components/charts/grid";
import { BarXAxis } from "@/components/charts/bar-x-axis";
import { ChartTooltip } from "@/components/charts/tooltip/chart-tooltip";
import type { MetricsByRootCause } from "@/lib/types";
import { formatRootCause } from "@/lib/format";

export function RecoveryByCauseChart({ data }: { data: MetricsByRootCause[] }) {
  const chartData: (Record<string, unknown> & { name: string; recovered: number })[] = data.map((d) => ({
    name: formatRootCause(d.root_cause),
    recovered: d.amount_recovered,
  }));

  if (chartData.length === 0) {
    return (
      <div className="flex items-center justify-center h-48 text-sm text-muted-foreground border border-dashed rounded-lg">
        No decisions yet — run a batch to see recovery by cause.
      </div>
    );
  }

  return (
    <BarChart data={chartData} xDataKey="name" status="ready" aspectRatio="3 / 1">
      <Grid horizontal numTicksRows={4} />
      <BarXAxis />
      <Bar dataKey="recovered" fill="var(--chart-1)" />
      <ChartTooltip />
    </BarChart>
  );
}
