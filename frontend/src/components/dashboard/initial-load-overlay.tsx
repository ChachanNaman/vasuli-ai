"use client";

import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { Sparkles } from "lucide-react";
import { EASE_OUT } from "@/lib/ease";

// The Render backend takes ~10-15s to answer the first fetch after a cold
// start — this paces the ramp against that so it reads as "tracking a real
// wait," not a generic spinner. It eases toward 96% and holds there
// (never claims done before the fetch is); the moment `loading` flips
// false it snaps to 100% and the overlay clears a beat later. One pass,
// no loop — unlike an indeterminate loader, this has a real endpoint.
const ESTIMATED_LOAD_MS = 11000;
const TICK_MS = 60;
const SETTLE_MS = 350;

type Phase = "idle" | "loading" | "settling";

export function InitialLoadOverlay({ loading }: { loading: boolean }) {
  const [percent, setPercent] = useState(0);
  const [phase, setPhase] = useState<Phase>(loading ? "loading" : "idle");
  const [prevLoading, setPrevLoading] = useState(loading);

  // Adjust state during render when `loading` changes, rather than in an
  // effect — this is React's sanctioned pattern for "reset state when a
  // prop changes" and keeps the effect below doing only what effects
  // should: owning the interval/timeout subscriptions.
  if (loading !== prevLoading) {
    setPrevLoading(loading);
    if (loading) {
      setPhase("loading");
      setPercent(0);
    } else if (phase !== "idle") {
      setPhase("settling");
      setPercent(100);
    }
  }

  useEffect(() => {
    if (phase === "loading") {
      const start = Date.now();
      const id = setInterval(() => {
        const elapsed = Date.now() - start;
        const eased = 96 * (1 - Math.exp(-elapsed / (ESTIMATED_LOAD_MS / 2.5)));
        setPercent(Math.min(96, Math.round(eased)));
      }, TICK_MS);
      return () => clearInterval(id);
    }
    if (phase === "settling") {
      const timer = setTimeout(() => setPhase("idle"), SETTLE_MS);
      return () => clearTimeout(timer);
    }
  }, [phase]);

  const show = phase !== "idle";

  return (
    <AnimatePresence>
      {show && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.35, ease: EASE_OUT }}
          className="absolute inset-0 z-30 flex items-center justify-center rounded-2xl bg-background/40 backdrop-blur-sm"
        >
          <motion.div
            initial={{ opacity: 0, y: 8, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -6, scale: 0.98 }}
            transition={{ duration: 0.35, ease: EASE_OUT }}
            className="flex flex-col items-center gap-5 rounded-2xl border border-border/60 bg-background/85 px-14 py-11 text-center shadow-[0_20px_50px_-25px_rgb(0,0,0,0.4)] backdrop-blur-md"
          >
            <span className="flex size-12 items-center justify-center rounded-full bg-primary/10 text-primary">
              <Sparkles className="size-6" />
            </span>

            <div className="flex flex-col items-center gap-3">
              <span
                className="font-mono font-semibold tabular-nums leading-none tracking-tight text-foreground"
                style={{ fontSize: "clamp(3rem, 6vw, 4.5rem)" }}
              >
                {percent}%
              </span>
              <span className="block h-1.5 w-56 overflow-hidden rounded-full bg-foreground/10">
                <motion.span
                  className="block h-full rounded-full bg-primary"
                  animate={{ width: `${percent}%` }}
                  transition={{ duration: 0.2, ease: EASE_OUT }}
                />
              </span>
            </div>

            <p className="font-mono text-sm text-muted-foreground">Loading live data…</p>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
