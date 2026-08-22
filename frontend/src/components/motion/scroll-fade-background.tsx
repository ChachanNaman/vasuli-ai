"use client";

import { motion, useScroll, useTransform } from "motion/react";
import BeamsBackground from "@/components/kokonutui/beams-background";

/** A page-wide ambient background whose opacity fades as the reader
 * scrolls deeper into the page — pattern adapted from motion.dev's
 * scroll-fade example, applied to a fixed backdrop instead of inline
 * content. */
export function ScrollFadeBackground() {
  const { scrollYProgress } = useScroll();
  const opacity = useTransform(scrollYProgress, [0, 0.15, 0.7, 1], [1, 0.7, 0.35, 0.15]);

  return (
    <motion.div className="fixed inset-0 -z-10" style={{ opacity }}>
      <BeamsBackground className="h-full" intensity="subtle" />
    </motion.div>
  );
}
