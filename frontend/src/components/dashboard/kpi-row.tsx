"use client";

import { motion } from "motion/react";
import NumberFlow from "@number-flow/react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { CashFlowMetrics, MetricsOverview } from "@/lib/types";
import { formatCompactINR } from "@/lib/format";

interface KpiCardProps {
  label: string;
  value: number;
  currency?: boolean;
  suffix?: string;
  subtext?: string;
  cashFlowLine?: string;
  accent?: boolean;
}

function KpiCard({ label, value, currency, suffix, subtext, cashFlowLine, accent }: KpiCardProps) {
  return (
    <motion.div
      whileHover={{ y: -3 }}
      transition={{ type: "spring", stiffness: 300, damping: 24 }}
      className="min-w-0"
    >
      <Card className="border-border/60 min-w-0">
        <CardHeader className="pb-1">
          <CardTitle className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            {label}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div
            className={`font-mono text-2xl md:text-3xl font-semibold tabular-nums ${
              accent ? "text-primary" : "text-foreground"
            }`}
          >
            <NumberFlow
              value={value}
              locales="en-IN"
              suffix={suffix}
              format={
                currency
                  ? { style: "currency", currency: "INR", maximumFractionDigits: 0 }
                  : undefined
              }
            />
          </div>
          {subtext && (
            <p className="mt-1 text-xs text-muted-foreground">{subtext}</p>
          )}
          {cashFlowLine && (
            <p className="mt-0.5 text-[11px] text-muted-foreground/70">{cashFlowLine}</p>
          )}
        </CardContent>
      </Card>
    </motion.div>
  );
}

export function KpiRow({
  overview,
  cashFlow,
}: {
  overview: MetricsOverview | undefined;
  cashFlow?: CashFlowMetrics;
}) {
  const exposure = overview?.total_exposure ?? 0;
  const recovered = overview?.total_recovered ?? 0;
  const rate = overview?.recovery_rate_pct ?? 0;
  const blocks = overview?.guardrail_block_count ?? 0;

  // FEATURES.md #3 — same numbers as the cards above, reframed in
  // cash-flow language a merchant CFO/ops lead would actually use.
  // average_daily_revenue is a stated illustrative constant (no real
  // merchant revenue data exists for this demo), so it's spelled out
  // inline rather than implied.
  const days = cashFlow?.days_of_reduced_receivables;
  const daysLine =
    days != null
      ? `≈ ${days} day${days === 1 ? "" : "s"} of reduced receivables outstanding (illustrative ${formatCompactINR(
          cashFlow!.average_daily_revenue_assumed
        )}/day avg. revenue)`
      : undefined;

  const mrrPct = cashFlow?.pct_at_risk_mrr_prevented;
  const mrrLine =
    mrrPct != null
      ? `Prevented an est. ${mrrPct}% of at-risk subscription MRR from churning`
      : undefined;

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 md:gap-4">
      <KpiCard
        label="Total at risk"
        value={exposure}
        currency
        subtext="Across the current batch"
      />
      <KpiCard
        label="Total recovered"
        value={recovered}
        currency
        subtext="Money actually got back"
        cashFlowLine={daysLine}
        accent
      />
      <KpiCard
        label="Recovery rate"
        value={rate}
        suffix="%"
        subtext="Of all decisions made"
        cashFlowLine={mrrLine}
      />
      <KpiCard
        label="Guardrail blocks"
        value={blocks}
        subtext="Actions the engine stopped"
      />
    </div>
  );
}
