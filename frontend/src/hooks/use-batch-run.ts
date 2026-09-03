"use client";

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { startBatch, pauseBatch, resumeBatch, getBatchStatus } from "@/lib/api";

const POLL_INTERVAL_MS = 800;

export function useBatchRun(n = 12) {
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

  return {
    batchId,
    setBatchId,
    status,
    isActive,
    isPaused,
    startMutation,
    pauseMutation,
    resumeMutation,
  };
}

export type UseBatchRun = ReturnType<typeof useBatchRun>;
