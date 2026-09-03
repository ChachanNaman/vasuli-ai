"use client";

import { motion } from "motion/react";
import { Pause, Play } from "lucide-react";
import { cn } from "@/lib/utils";
import { LoadingLine } from "@/components/motion/loading-line";
import type { UseBatchRun } from "@/hooks/use-batch-run";

export function RunBatchButton({ batch }: { batch: UseBatchRun }) {
  const { status, isActive, isPaused, startMutation, pauseMutation, resumeMutation, setBatchId } =
    batch;

  if (!isActive || !status) {
    return (
      <div className="flex flex-col items-end gap-1.5">
        <motion.button
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.97 }}
          onClick={() => {
            setBatchId(null);
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
