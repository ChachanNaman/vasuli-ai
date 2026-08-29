"use client";

import { useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { motion } from "motion/react";
import { getDecisions, getMetrics } from "@/lib/api";
import { KpiRow } from "@/components/dashboard/kpi-row";
import { RecoveryByCauseChart } from "@/components/dashboard/recovery-by-cause-chart";
import { RecoveryOverTimeChart } from "@/components/dashboard/recovery-over-time-chart";
import { LiveFeed } from "@/components/dashboard/live-feed";
import { ExceptionsTab } from "@/components/dashboard/exceptions-tab";
import { BaselineComparison } from "@/components/dashboard/baseline-comparison";
import { FairnessCard } from "@/components/dashboard/fairness-card";
import { StabilityCard } from "@/components/dashboard/stability-card";
import { DiagnosisAgreementCard } from "@/components/dashboard/diagnosis-agreement-card";
import { EventDrillDown } from "@/components/dashboard/event-drill-down";
import { RunBatchButton } from "@/components/dashboard/run-batch-button";
import { AmbientBackground } from "@/components/motion/ambient-background";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { DecisionRow } from "@/lib/types";

export default function DashboardPage() {
  const [selectedDecision, setSelectedDecision] = useState<DecisionRow | null>(null);
  const [drillDownOpen, setDrillDownOpen] = useState(false);
  // The dashboard opens showing fixed placeholder numbers (see
  // kpi-row.tsx's DEFAULT_OVERVIEW) instead of hitting the backend on
  // mount — the backend can take a while to wake up from a cold start, and
  // a page that hangs on that fetch looks broken. Real data only starts
  // fetching once a batch is actually kicked off.
  const [hasStarted, setHasStarted] = useState(false);

  const metricsQuery = useQuery({
    queryKey: ["metrics"],
    queryFn: getMetrics,
    enabled: hasStarted,
  });
  const decisionsQuery = useQuery({
    queryKey: ["decisions"],
    queryFn: () => getDecisions(200),
    enabled: hasStarted,
  });

  const handleSelect = (decision: DecisionRow) => {
    setSelectedDecision(decision);
    setDrillDownOpen(true);
  };

  return (
    <div className="relative mx-auto max-w-6xl px-4 md:px-6 py-8 space-y-6">
      <AmbientBackground />
      <header className="flex items-center justify-between gap-4 flex-wrap">
        <div>
          <Link href="/" className="text-sm text-muted-foreground hover:text-foreground">
            ← Vasuli
          </Link>
          <h1 className="text-xl font-semibold mt-1">Recovery dashboard</h1>
        </div>
        <RunBatchButton onRunStart={() => setHasStarted(true)} />
      </header>

      <div className="rounded-lg border border-border bg-muted/40 px-4 py-2.5 text-sm text-muted-foreground">
        Live data can take 10–15 seconds to fetch after a batch finishes — please wait for the
        numbers below to update.
      </div>

      <KpiRow overview={metricsQuery.data?.overview} cashFlow={metricsQuery.data?.cash_flow} />

      <Tabs defaultValue="overview" className="w-full">
        <div className="-mx-4 overflow-x-auto px-4 md:mx-0 md:overflow-visible md:px-0">
          <TabsList className="w-max md:w-fit">
            <TabsTrigger value="overview">Overview</TabsTrigger>
            <TabsTrigger value="live-feed">Live agent feed</TabsTrigger>
            <TabsTrigger value="exceptions">
              Exceptions
              {metricsQuery.data && metricsQuery.data.overview.exception_count > 0 && (
                <span className="ml-1.5 text-xs text-muted-foreground">
                  ({metricsQuery.data.overview.exception_count})
                </span>
              )}
            </TabsTrigger>
            <TabsTrigger value="vs-baseline">vs. Baseline</TabsTrigger>
          </TabsList>
        </div>

        <TabsContent value="overview" className="space-y-4 mt-4">
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className="grid grid-cols-1 gap-4"
          >
            <Card>
              <CardHeader>
                <CardTitle className="text-sm font-medium">Recovery by cause</CardTitle>
              </CardHeader>
              <CardContent>
                <RecoveryByCauseChart data={metricsQuery.data?.by_root_cause ?? []} />
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle className="text-sm font-medium">Recovery over time</CardTitle>
              </CardHeader>
              <CardContent>
                <RecoveryOverTimeChart decisions={decisionsQuery.data ?? []} />
              </CardContent>
            </Card>
            <FairnessCard />
          </motion.div>
        </TabsContent>

        <TabsContent value="live-feed" className="mt-4">
          <LiveFeed initialDecisions={decisionsQuery.data ?? []} onSelect={handleSelect} />
        </TabsContent>

        <TabsContent value="exceptions" className="mt-4">
          <ExceptionsTab exceptions={metricsQuery.data?.exceptions ?? []} />
        </TabsContent>

        <TabsContent value="vs-baseline" className="mt-4 space-y-4">
          <BaselineComparison />
          <StabilityCard />
          <DiagnosisAgreementCard />
        </TabsContent>
      </Tabs>

      <EventDrillDown
        decision={selectedDecision}
        open={drillDownOpen}
        onOpenChange={setDrillDownOpen}
      />
    </div>
  );
}
