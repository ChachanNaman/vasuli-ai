"use client";

import { useRef } from "react";
import { motion, useScroll, useTransform } from "motion/react";

interface ScrollZoomProps {
  children: React.ReactNode;
  className?: string;
  /** Scale range across the scroll distance. Default: [0.92, 1.04] */
  scaleRange?: [number, number];
}

/** Scales an element up slightly as the page scrolls it through the
 * viewport — pattern adapted from motion.dev's scroll-zoom-hero example. */
export function ScrollZoom({ children, className, scaleRange = [0.92, 1.04] }: ScrollZoomProps) {
  const ref = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ["start end", "end start"],
  });
  const scale = useTransform(scrollYProgress, [0, 0.5, 1], [scaleRange[0], scaleRange[1], scaleRange[0]]);

  return (
    <div ref={ref} className={className}>
      <motion.div style={{ scale }}>{children}</motion.div>
    </div>
  );
}
