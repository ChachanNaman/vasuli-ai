"use client";

import { useRef } from "react";
import { motion, useScroll, useTransform } from "motion/react";
import { cn } from "@/lib/utils";

interface StackCardProps {
  children: React.ReactNode;
  index: number;
  className?: string;
}

/** One card in the stack — sticks at a fixed offset, then scales/dims down
 * as the next card scrolls over it. This is the "cards stacking as you
 * scroll" pattern from razorpay.com's product sections. */
function StackCard({ children, index, className }: StackCardProps) {
  const ref = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ["start start", "end start"],
  });
  const scale = useTransform(scrollYProgress, [0, 1], [1, 0.92]);
  const opacity = useTransform(scrollYProgress, [0, 1], [1, 0.5]);

  return (
    <div
      ref={ref}
      className="sticky top-20 flex h-[80vh] items-center justify-center"
      style={{ zIndex: index + 1 }}
    >
      <motion.div style={{ scale, opacity }} className={cn("w-full", className)}>
        {children}
      </motion.div>
    </div>
  );
}

export function StickyStack({ children, className }: { children: React.ReactNode[]; className?: string }) {
  return (
    <div className={cn("relative", className)}>
      {children.map((child, i) => (
        <StackCard key={i} index={i}>
          {child}
        </StackCard>
      ))}
    </div>
  );
}
