"use client";

import { BarChart } from "@/components/charts/bar-chart";
import { Bar } from "@/components/charts/bar";
import { Grid } from "@/components/charts/grid";
import { BarXAxis } from "@/components/charts/bar-x-axis";
import { ChartTooltip } from "@/components/charts/tooltip/chart-tooltip";
import type { MetricsByRootCause } from "@/lib/types";
import { formatRootCause } from "@/lib/format";

const AXIS_LABEL_MAX_CHARS = 20;

// Shown until the first real batch has decisions to chart — matches
// kpi-row.tsx's DEFAULT_OVERVIEW so the Overview tab doesn't look empty
// underneath already-populated KPI cards while the backend is still
// waking up or before anyone has clicked "Run recovery batch".
const DEFAULT_BY_ROOT_CAUSE: MetricsByRootCause[] = [
  { root_cause: "insufficient_funds", decision_count: 4, recovered_count: 2, recovery_rate_pct: 50, amount_recovered: 62000 },
  { root_cause: "card_expired", decision_count: 3, recovered_count: 1, recovery_rate_pct: 33.3, amount_recovered: 28500 },
  { root_cause: "bank_server_down", decision_count: 3, recovered_count: 2, recovery_rate_pct: 66.7, amount_recovered: 45700 },
  { root_cause: "checkout_abandoned", decision_count: 2, recovered_count: 0, recovery_rate_pct: 0, amount_recovered: 20000 },
];

function shortenForAxis(label: string): string {
  return label.length > AXIS_LABEL_MAX_CHARS
    ? `${label.slice(0, AXIS_LABEL_MAX_CHARS - 1)}…`
    : label;
}

export function RecoveryByCauseChart({ data }: { data: MetricsByRootCause[] }) {
  const source = data.length > 0 ? data : DEFAULT_BY_ROOT_CAUSE;

  // Root causes can run long ("Insufficient Funds", "Daily Limit Exceeded")
  // and up to 11 distinct values appear in one batch — shorten for the axis
  // so rotated labels always fit regardless of exact margin math.
  const chartData: (Record<string, unknown> & { name: string; recovered: number })[] = source.map((d) => ({
    name: shortenForAxis(formatRootCause(d.root_cause)),
    recovered: d.amount_recovered,
  }));

  return (
    <BarChart data={chartData} xDataKey="name" status="ready" aspectRatio="2.4 / 1">
      <Grid horizontal numTicksRows={4} />
      {/* No hard cap here — up to 11 categories can appear in one batch, and
          the axis's every-Nth-label skip logic (when a cap forces skipping)
          can drop the label for the tallest bar while keeping a shorter
          neighbor's, which reads as a mislabeled chart. Let the axis's own
          container-width-based spacing decide how many labels fit. */}
      <BarXAxis />
      <Bar dataKey="recovered" fill="var(--chart-1)" />
      <ChartTooltip showDatePill={false} />
    </BarChart>
  );
}
