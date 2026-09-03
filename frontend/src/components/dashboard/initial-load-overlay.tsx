"use client";

import { AnimatePresence, motion } from "motion/react";
import { Loader } from "@/components/motion/loader";
import { EASE_OUT } from "@/lib/ease";

/**
 * Covers the dashboard while the first metrics/decisions fetch is in
 * flight — the Render backend can take 10-15s to answer, and a bare page
 * of empty chart shells reads as broken rather than loading. Deliberately
 * lighter than BatchLoadingOverlay (no progress %, thinner blur): this is
 * "the page behind me is about to appear," not "a multi-step job is
 * running," and it should disappear the instant the queries resolve.
 */
export function InitialLoadOverlay({ visible }: { visible: boolean }) {
  return (
    <AnimatePresence>
      {visible && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.3, ease: EASE_OUT }}
          className="fixed inset-0 z-40 flex items-center justify-center bg-background/30 backdrop-blur-sm"
        >
          <motion.div
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            transition={{ duration: 0.3, ease: EASE_OUT }}
            className="flex flex-col items-center gap-3 rounded-2xl border border-border/60 bg-background/70 px-8 py-6 text-primary shadow-[0_20px_50px_-25px_rgb(0,0,0,0.4)] backdrop-blur-md"
          >
            <Loader variant="percent" size={44} speed={1.3} label="Loading live data" />
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
