"use client";

import { AnimatePresence, motion } from "motion/react";
import { Sparkles } from "lucide-react";
import { EASE_OUT } from "@/lib/ease";
import type { BatchStatus } from "@/lib/types";

interface BatchLoadingOverlayProps {
  visible: boolean;
  status: BatchStatus | undefined;
  starting: boolean;
}

export function BatchLoadingOverlay({ visible, status, starting }: BatchLoadingOverlayProps) {
  const total = status?.total ?? 0;
  const processed = status?.processed ?? 0;
  const isComplete = status?.status === "completed";
  const percent = isComplete
    ? 100
    : total > 0
      ? Math.min(99, Math.round((processed / total) * 100))
      : 0;

  const caption = starting
    ? "Starting the batch…"
    : isComplete
      ? "Wrapping up…"
      : status?.status === "paused"
        ? `Paused — ${processed} of ${total} events`
        : total > 0
          ? `Diagnosing ${processed} of ${total} events`
          : "Diagnosing…";

  return (
    <AnimatePresence>
      {visible && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.45, ease: EASE_OUT }}
          className="fixed inset-0 z-40 flex items-center justify-center bg-background/55 backdrop-blur-xl"
        >
          <motion.div
            initial={{ opacity: 0, y: 10, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -6, scale: 0.98 }}
            transition={{ duration: 0.4, ease: EASE_OUT }}
            className="flex flex-col items-center gap-6 px-6 text-center"
          >
            <span className="flex size-11 items-center justify-center rounded-full bg-primary/10 text-primary">
              <Sparkles className="size-5" />
            </span>

            <div className="flex flex-col items-center gap-4">
              <span
                className="font-mono font-semibold tabular-nums leading-none tracking-tight text-foreground"
                style={{ fontSize: "clamp(3.5rem, 9vw, 6rem)" }}
              >
                {percent}%
              </span>

              <span className="block h-1 w-64 max-w-[60vw] overflow-hidden rounded-full bg-foreground/10">
                <motion.span
                  className="block h-full rounded-full bg-primary"
                  animate={{ width: `${percent}%` }}
                  transition={{ duration: 0.35, ease: EASE_OUT }}
                />
              </span>
            </div>

            <p className="font-mono text-sm text-muted-foreground">{caption}</p>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
