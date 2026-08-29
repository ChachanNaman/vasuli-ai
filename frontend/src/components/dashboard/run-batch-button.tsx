"use client";

import { useEffect, useState } from "react";
import { motion } from "motion/react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pause, Play } from "lucide-react";
import { startBatch, pauseBatch, resumeBatch, getBatchStatus } from "@/lib/api";
import { cn } from "@/lib/utils";
import { LoadingLine } from "@/components/motion/loading-line";

const POLL_INTERVAL_MS = 800;

export function RunBatchButton({
  n = 12,
  onRunStart,
}: {
  n?: number;
  onRunStart?: () => void;
}) {
  const queryClient = useQueryClient();
  const [batchId, setBatchId] = useState<string | null>(null);

  const statusQuery = useQuery({
    queryKey: ["batch-status", batchId],
    queryFn: () => getBatchStatus(batchId as string),
    enabled: !!batchId,
    refetchInterval: (query) => {
      const s = query.state.data?.status;
      return s === "completed" || s === "error" ? false : POLL_INTERVAL_MS;
    },
  });

  const status = statusQuery.data;

  // Refresh the dashboard's own stat tiles/feed every time another decision
  // lands, not just once at the very end — otherwise the batch's progress
  // line ticks up for a minute-plus while every card behind it sits frozen,
  // then everything jumps at once. `processed` only ever increases within
  // one batch, so this fires once per new decision, not once per poll.
  useEffect(() => {
    if (status && status.processed > 0) {
      queryClient.invalidateQueries({ queryKey: ["metrics"] });
      queryClient.invalidateQueries({ queryKey: ["decisions"] });
    }
  }, [status?.processed, queryClient]);

  // Batch finished (or died) — refresh everything else once, then stop
  // tracking it so the button resets to its idle state.
  useEffect(() => {
    if (status?.status === "completed" || status?.status === "error") {
      queryClient.invalidateQueries({ queryKey: ["metrics"] });
      queryClient.invalidateQueries({ queryKey: ["decisions"] });
      queryClient.invalidateQueries({ queryKey: ["fairness"] });
      queryClient.invalidateQueries({ queryKey: ["stability"] });
      queryClient.invalidateQueries({ queryKey: ["audit-verify"] });
      queryClient.invalidateQueries({ queryKey: ["eval-comparison"] });
    }
  }, [status?.status, queryClient]);

  const startMutation = useMutation({
    mutationFn: () => startBatch(n),
    onSuccess: (data) => {
      setBatchId(data.batch_id);
      // The backend scopes /api/metrics and /api/decisions to whichever
      // batch_id is newest, so as soon as this run's first event is
      // written it becomes "the latest batch" and every card should
      // switch to describing it instead of the previous run — kick off a
      // refetch right away instead of waiting for the next poll tick.
      queryClient.invalidateQueries({ queryKey: ["metrics"] });
      queryClient.invalidateQueries({ queryKey: ["decisions"] });
    },
  });

  const pauseMutation = useMutation({
    mutationFn: () => pauseBatch(batchId as string),
    onSuccess: () => statusQuery.refetch(),
  });

  const resumeMutation = useMutation({
    mutationFn: () => resumeBatch(batchId as string),
    onSuccess: () => statusQuery.refetch(),
  });

  const isActive = !!status && status.status !== "completed" && status.status !== "error";
  const isPaused = status?.status === "paused";

  if (!isActive) {
    return (
      <div className="flex flex-col items-end gap-1.5">
        <motion.button
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.97 }}
          onClick={() => {
            setBatchId(null);
            onRunStart?.();
            startMutation.mutate();
          }}
          disabled={startMutation.isPending}
          className={cn(
            "inline-flex items-center gap-2 rounded-lg px-5 py-2.5 text-sm font-medium shadow-sm transition-colors",
            startMutation.isPending
              ? "bg-processing/15 text-processing cursor-not-allowed"
              : "bg-primary text-primary-foreground hover:bg-primary/90"
          )}
        >
          {startMutation.isPending ? (
            <>Starting…</>
          ) : (
            <>
              <Play className="size-4" />
              Run recovery batch
            </>
          )}
        </motion.button>
        {status?.status === "error" && (
          <p className="text-xs text-destructive max-w-56 text-right">
            Last batch failed: {status.error}
          </p>
        )}
      </div>
    );
  }

  return (
    <div className="flex flex-col items-end gap-1.5">
      <div className="flex items-center gap-2">
        <span className="text-sm text-muted-foreground font-mono">
          {isPaused
            ? `Paused — ${status.processed} of ${status.total} processed`
            : `Diagnosing — ${status.processed} of ${status.total} processed`}
        </span>
        <motion.button
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.97 }}
          onClick={() =>
            isPaused ? resumeMutation.mutate() : pauseMutation.mutate()
          }
          disabled={pauseMutation.isPending || resumeMutation.isPending}
          className={cn(
            "inline-flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium shadow-sm transition-colors",
            isPaused
              ? "bg-primary text-primary-foreground hover:bg-primary/90"
              : "bg-destructive/15 text-destructive hover:bg-destructive/25"
          )}
        >
          {isPaused ? (
            <>
              <Play className="size-4" />
              Resume
            </>
          ) : (
            <>
              <Pause className="size-4" />
              Pause agent
            </>
          )}
        </motion.button>
      </div>
      {!isPaused && <LoadingLine className="w-40" />}
      {isPaused && status.skipped_paused > 0 && (
        <p className="text-xs text-muted-foreground">
          {status.skipped_paused} event{status.skipped_paused === 1 ? "" : "s"} waiting, none
          dropped
        </p>
      )}
    </div>
  );
}
