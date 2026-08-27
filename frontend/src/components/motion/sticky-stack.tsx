"use client";

import { useEffect, useRef, useState } from "react";
import { motion, useScroll, useTransform } from "motion/react";
import { cn } from "@/lib/utils";

interface StackCardProps {
  children: React.ReactNode;
  index: number;
  className?: string;
}

/** One card in the stack — sticks at a fixed offset, then scales/dims down
 * as the next card scrolls over it. Each card tracks its own scroll
 * range independently, so only one card is ever "stuck" onscreen at a
 * time (no overlap-ghosting) — the sticky window is sized close to the
 * card's own height to keep the hand-off snappy instead of leaving dead
 * scroll space. Pattern from razorpay.com's product sections.
 *
 * This pinning/scaling animation assumes a desktop-sized viewport and a
 * hover-capable pointer; on narrow mobile viewports the fixed 58vh sticky
 * window is shorter than the cards' actual (image + copy) height, so cards
 * pile up with only slivers visible. Below the `md` breakpoint we skip the
 * sticky/scale mechanics entirely and render a plain vertical stack. */
function StackCard({ children, index, className }: StackCardProps) {
  const ref = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ["start start", "end start"],
  });
  const scale = useTransform(scrollYProgress, [0, 0.7], [1, 0.94]);
  const opacity = useTransform(scrollYProgress, [0, 0.7], [1, 0.55]);

  return (
    <div
      ref={ref}
      className="sticky top-20 flex h-[58vh] items-start justify-center pt-6"
      style={{ zIndex: index + 1 }}
    >
      <motion.div style={{ scale, opacity }} className={cn("w-full", className)}>
        {children}
      </motion.div>
    </div>
  );
}

function useIsMobile(breakpoint = 768) {
  const [isMobile, setIsMobile] = useState<boolean | null>(null);

  useEffect(() => {
    const mql = window.matchMedia(`(max-width: ${breakpoint - 1}px)`);
    const update = () => setIsMobile(mql.matches);
    update();
    mql.addEventListener("change", update);
    return () => mql.removeEventListener("change", update);
  }, [breakpoint]);

  return isMobile;
}

export function StickyStack({
  children,
  className,
}: {
  children: React.ReactNode[];
  className?: string;
}) {
  const isMobile = useIsMobile();

  // Avoid the pinning animation until we know the viewport isn't mobile —
  // defaulting to the plain stack means there's no flash of broken layout
  // on mobile while matchMedia resolves, and desktop upgrades in on mount.
  if (isMobile !== false) {
    return (
      <div className={cn("relative flex flex-col gap-6", className)}>
        {children.map((child, i) => (
          <div key={i}>{child}</div>
        ))}
      </div>
    );
  }

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
