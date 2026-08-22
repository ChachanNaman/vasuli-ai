"use client";

import { motion } from "motion/react";
import { cn } from "@/lib/utils";

/** Indeterminate progress line — a bar sweeps back and forth. Uses the
 * `processing` accent (violet-blue) rather than the amber brand color, so
 * "in progress" and "money recovered" never read as the same signal. */
export function LoadingLine({ className }: { className?: string }) {
  return (
    <div className={cn("relative h-0.5 w-full overflow-hidden rounded-full bg-processing/15", className)}>
      <motion.div
        className="absolute inset-y-0 w-1/3 rounded-full bg-processing"
        animate={{ x: ["-100%", "260%"] }}
        transition={{ duration: 1.1, repeat: Infinity, ease: "easeInOut" }}
      />
    </div>
  );
}
