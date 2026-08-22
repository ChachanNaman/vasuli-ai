"use client";

import { motion } from "motion/react";
import NumberFlow from "@number-flow/react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { MetricsOverview } from "@/lib/types";

interface KpiCardProps {
  label: string;
  value: number;
  currency?: boolean;
  suffix?: string;
  subtext?: string;
  accent?: boolean;
}

function KpiCard({ label, value, currency, suffix, subtext, accent }: KpiCardProps) {
  return (
    <motion.div
      whileHover={{ y: -3 }}
      transition={{ type: "spring", stiffness: 300, damping: 24 }}
    >
      <Card className="border-border/60">
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
        </CardContent>
      </Card>
    </motion.div>
  );
}

export function KpiRow({ overview }: { overview: MetricsOverview | undefined }) {
  const exposure = overview?.total_exposure ?? 0;
  const recovered = overview?.total_recovered ?? 0;
  const rate = overview?.recovery_rate_pct ?? 0;
  const blocks = overview?.guardrail_block_count ?? 0;

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
        accent
      />
      <KpiCard
        label="Recovery rate"
        value={rate}
        suffix="%"
        subtext="Of all decisions made"
      />
      <KpiCard
        label="Guardrail blocks"
        value={blocks}
        subtext="Actions the engine stopped"
      />
    </div>
  );
}
