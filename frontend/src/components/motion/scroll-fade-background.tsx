"use client";

import { motion, useScroll, useTransform } from "motion/react";
import { GrainientBackground } from "@/components/motion/grainient-background";

/** A page-wide ambient background whose opacity fades as the reader
 * scrolls deeper into the page — pattern adapted from motion.dev's
 * scroll-fade example, applied to a fixed backdrop instead of inline
 * content. */
export function ScrollFadeBackground() {
  const { scrollYProgress } = useScroll();
  // Stays present the whole way down the page (per-page cards float over
  // it as opaque islands) — only a gentle taper, never fading to flat.
  const opacity = useTransform(scrollYProgress, [0, 0.5, 1], [1, 0.82, 0.7]);

  return (
    <motion.div className="fixed inset-0 -z-10 bg-background" style={{ opacity }}>
      <GrainientBackground className="h-full" />
    </motion.div>
  );
}
