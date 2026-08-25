"use client";

import { GrainientBackground } from "@/components/motion/grainient-background";
import { cn } from "@/lib/utils";

/**
 * Same shader backdrop as the landing page (blue in light mode, near-black
 * in dark mode, theme-synced automatically), held at a low constant
 * opacity instead of the landing page's scroll-linked fade — this sits
 * behind data-heavy pages (dashboard, batch runs) where the charts/stats
 * are the point, not the backdrop, so it only needs to read as ambient
 * texture in the gaps between opaque cards.
 */
export function AmbientBackground({ className }: { className?: string }) {
  return (
    <div className={cn("fixed inset-0 -z-10 bg-background", className)}>
      <GrainientBackground className="h-full opacity-[0.12] dark:opacity-[0.14]" />
    </div>
  );
}
