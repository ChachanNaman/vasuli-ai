"use client";

import { cn } from "@/lib/utils";
import Grainient from "@/components/reactbits/Grainient";

/**
 * Ambient site-wide backdrop — the real react-bits Grainient (WebGL/ogl
 * shader: warped noise + film grain), tuned to a soft grey-to-blue
 * diagonal in Vasuli's brand blue. Stays fixed behind the whole page (not
 * just the hero) so cards read as opaque islands floating over a living,
 * animated gradient instead of a flat white page.
 */
export function GrainientBackground({ className }: { className?: string }) {
  return (
    <div className={cn("pointer-events-none absolute inset-0 overflow-hidden", className)}>
      <Grainient
        color1="#b1bbbd"
        color2="#5d8ad1"
        color3="#4c86e4"
        timeSpeed={1.15}
        colorBalance={0}
        warpStrength={1}
        warpFrequency={5}
        warpSpeed={2}
        warpAmplitude={50}
        blendAngle={0}
        blendSoftness={0.05}
        rotationAmount={500}
        noiseScale={2}
        grainAmount={0.1}
        grainScale={2}
        grainAnimated={false}
        contrast={1.5}
        gamma={1}
        saturation={1}
        centerX={0}
        centerY={0}
        zoom={0.9}
        className="h-full w-full"
      />
    </div>
  );
}
