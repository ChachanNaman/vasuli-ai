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
import { InitialLoadOverlay } from "@/components/dashboard/initial-load-overlay";
import { AmbientBackground } from "@/components/motion/ambient-background";
import { useBatchRun } from "@/hooks/use-batch-run";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { DecisionRow } from "@/lib/types";

export default function DashboardPage() {
  const [selectedDecision, setSelectedDecision] = useState<DecisionRow | null>(null);
  const [drillDownOpen, setDrillDownOpen] = useState(false);

  const metricsQuery = useQuery({ queryKey: ["metrics"], queryFn: getMetrics });
  const decisionsQuery = useQuery({
    queryKey: ["decisions"],
    queryFn: () => getDecisions(200),
  });

  const batch = useBatchRun();

  // First paint of the dashboard — metrics/decisions are both fetching for
  // the first time and there's nothing on screen yet. This is what "Run
  // live batch" on the landing page lands on, and the Render backend can
  // take 10-15s to answer, so cover the content area until they land
  // instead of showing empty chart shells. `isLoading` (not `isFetching`)
  // so this never re-triggers on the background refetches a recovery-batch
  // run kicks off — that flow stays inline-only on the button itself, same
  // as it's always been.
  const initialLoading = metricsQuery.isLoading || decisionsQuery.isLoading;

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
        <RunBatchButton batch={batch} />
      </header>

      <div className="relative space-y-6">
        <InitialLoadOverlay loading={initialLoading} />

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
      </div>

      <EventDrillDown
        decision={selectedDecision}
        open={drillDownOpen}
        onOpenChange={setDrillDownOpen}
      />
    </div>
  );
}
