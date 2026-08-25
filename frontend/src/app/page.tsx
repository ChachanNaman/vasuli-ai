"use client";

import Image from "next/image";
import { motion } from "motion/react";
import { ShieldCheck, Brain, Wallet, ScrollText } from "lucide-react";
import CurrencyTransfer from "@/components/kokonutui/currency-transfer";
import SlideTextButton from "@/components/kokonutui/slide-text-button";
import { SplitText } from "@/components/motion/split-text";
import { ScrollReveal } from "@/components/motion/scroll-reveal";
import { ScrollZoom } from "@/components/motion/scroll-zoom";
import { ScrollFadeBackground } from "@/components/motion/scroll-fade-background";
import { StickyStack } from "@/components/motion/sticky-stack";
import { Card, CardContent } from "@/components/ui/card";
import LineSidebar from "@/components/reactbits/LineSidebar";
import ScrollExpand from "@/components/reactbits/ScrollExpand";
import ShapeBlur from "@/components/reactbits/ShapeBlur";
import AccordionGallery from "@/components/reactbits/AccordionGallery";

const SECTIONS = ["Overview", "How it works", "Action set", "Live demo"];
const SECTION_IDS = ["hero", "how-it-works", "actions", "cta"];

const architectureLayers = [
  {
    icon: Brain,
    title: "Diagnosis agent",
    body: "Groq primary, Gemini automatic fallback. Given one event's full context, it confirms the root cause and picks exactly one action from a fixed menu — never freeform. Below a confidence threshold, it's told to flag for human review instead of guessing.",
    tag: "LLM · proposes only",
    image: null as string | null,
  },
  {
    icon: ShieldCheck,
    title: "Guardrail engine",
    body: "Plain deterministic code — no LLM involved. Retry caps, cool-downs, contact caps, opt-out enforcement, spend caps on invoices, and the retry rate limit that fixed a real retry-storm bug. Every check is logged, pass or fail.",
    tag: "Deterministic · decides",
    image: null as string | null,
  },
  {
    icon: Wallet,
    title: "Recovery executors",
    body: "Runs the action once it's cleared. Real Razorpay test-mode payment links for smart_retry and generate_payment_link; everything else is simulated and clearly labeled as such in the UI.",
    tag: "Executes · zero real money",
    image: "/illustrations/recovery-executors.jpg",
  },
  {
    icon: ScrollText,
    title: "Audit trail",
    body: "Every decision — executed, blocked, or skipped — is written with its full reasoning, every guardrail check, and the outcome. Nothing is swept under the rug, including what couldn't be recovered.",
    tag: "Supabase · full history",
    image: null as string | null,
  },
];

const recoveryActions = [
  {
    image: "/illustrations/gallery-smart-retry.jpg",
    label: "Smart Retry",
    description: [
      "Real Razorpay test-mode retry link",
      "Capped at 3 attempts per payment",
      "Rate-limited to 1 per 30 min",
      "Blocked instantly if a dispute opens",
      "Economic rule vetoes low-value retries",
    ],
  },
  {
    image: "/illustrations/gallery-payment-link.jpg",
    label: "Payment Link",
    description: [
      "Fresh Razorpay test-mode link",
      "For abandoned checkouts + invoices",
      "Customer pays on their own time",
      "No repeat contact within 4 hours",
      "Max 2 touches per customer per day",
    ],
  },
  {
    image: "/illustrations/gallery-send-nudge.jpg",
    label: "Send Nudge",
    description: [
      "Pre-registered DLT template only",
      "08:00–19:00 IST contact window",
      "Respects the daily contact cap",
      "Skipped entirely if opted out",
      "Never sends freeform LLM text",
    ],
  },
  {
    image: "/illustrations/gallery-b2b-chase.jpg",
    label: "B2B Chase",
    description: [
      "Tiered by reliability score",
      "Firmer tone for overdue invoices",
      "Never auto-escalates above ₹1L",
      "Flagged for human review above cap",
      "Full reasoning logged to audit trail",
    ],
  },
];

export default function LandingPage() {
  return (
    <div className="relative flex-1">
      <ScrollFadeBackground />

      <div className="pointer-events-none fixed left-8 top-1/2 z-40 hidden -translate-y-1/2 min-[1620px]:block">
        <div className="pointer-events-auto">
          <LineSidebar
            items={SECTIONS}
            accentColor="var(--primary)"
            textColor="var(--foreground)"
            markerColor="var(--muted-foreground)"
            showIndex
            showMarker
            proximityRadius={90}
            maxShift={22}
            falloff="smooth"
            markerLength={40}
            tickScale={0.5}
            scaleTick
            itemGap={18}
            fontSize={0.85}
            smoothing={90}
            defaultActive={0}
            onItemClick={(index) =>
              document.getElementById(SECTION_IDS[index])?.scrollIntoView({ behavior: "smooth" })
            }
          />
        </div>
      </div>

      {/* Hero */}
      <section id="hero" className="relative flex min-h-screen items-center overflow-hidden">
        <div className="relative z-10 mx-auto grid w-full max-w-6xl grid-cols-1 items-center gap-12 px-6 py-20 lg:grid-cols-2 min-[1620px]:pl-56">
          <div>
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5 }}
              className="mb-6 inline-flex items-center gap-2 rounded-full border border-primary/30 py-1 pl-1.5 pr-3 text-xs font-medium uppercase tracking-wide text-primary"
            >
              <span className="flex size-5 items-center justify-center overflow-hidden rounded-full bg-white">
                <Image
                  src="/illustrations/razorpay-logo.jpg"
                  alt="Razorpay"
                  width={40}
                  height={40}
                  className="scale-150 object-contain opacity-95"
                />
              </span>
              Razorpay AI Buildathon — Track 03
            </motion.div>

            <h1 className="text-4xl font-semibold leading-[1.1] tracking-tight md:text-5xl">
              <SplitText text="Vasuli — the AI agent that" />
              <br />
              <SplitText
                text="gets your money back."
                wordClassName="text-primary"
                delay={0.35}
              />
            </h1>

            <motion.p
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.9 }}
              className="mt-5 max-w-lg text-base leading-relaxed text-foreground/80 md:text-lg"
            >
              It watches failed payments, abandoned checkouts, failed mandates,
              and overdue invoices — diagnoses why each one is losing money,
              picks a bounded action, executes it under hard guardrails, and
              reports exactly how much it got back. And what it honestly
              couldn&apos;t.
            </motion.p>

            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 1.05 }}
              className="mt-8 flex items-center gap-3"
            >
              <SlideTextButton href="/dashboard" text="Run live batch" hoverText="Let's go →" />
              <SlideTextButton
                href="https://github.com/ChachanNaman/vasuli-ai"
                text="View source"
                hoverText="On GitHub →"
                variant="ghost"
              />
            </motion.div>

            <motion.p
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.6, delay: 1.2 }}
              className="mt-6 max-w-md text-xs text-foreground/80"
            >
              The LLM never touches money directly — a deterministic guardrail
              engine and recovery executors are the only things allowed to act.
            </motion.p>
          </div>

          <div className="relative">
            <div className="pointer-events-none absolute inset-[-18%] opacity-60">
              <ShapeBlur variation={2} shapeSize={1.1} roundness={0.5} borderSize={0.03} circleSize={0.3} circleEdge={0.7} />
            </div>
            <ScrollZoom scaleRange={[0.94, 1.05]}>
              <motion.div
                className="relative dark:grayscale dark:contrast-125"
                initial={{ opacity: 0, scale: 0.96 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ duration: 0.6, delay: 0.3, ease: "easeOut" }}
              >
                <CurrencyTransfer />
              </motion.div>
            </ScrollZoom>
          </div>
        </div>
      </section>

      {/* Scroll transition into the next section — frame expands to full-bleed */}
      <ScrollExpand
        src="/illustrations/razorpay-wordmark.jpg"
        alt="Razorpay"
        title="Diagnose. Decide. Recover."
        scrollHint="Scroll to see how"
        useWindowScroll
        startWidth={44}
        startHeight={56}
        startRadius={28}
        endRadius={0}
        mediaZoom={1.15}
        scrollDistance={1}
        holdDistance={0.15}
        smoothing={0.08}
        overlayScrim={0.65}
        mediaClassName="opacity-[0.22] blur-lg grayscale"
      />

      {/* Architecture — sticky stack */}
      <section id="how-it-works" className="relative mx-auto max-w-4xl px-6 pb-20 pt-20 md:pt-28">
        <ScrollReveal className="mb-4 text-center" y={-56}>
          <p className="text-xs font-medium uppercase tracking-wide text-primary">
            How it works
          </p>
          <h2 className="mt-2 text-2xl font-semibold md:text-3xl">
            Four layers, one rule: the LLM proposes, code decides.
          </h2>
        </ScrollReveal>

        <StickyStack>
          {architectureLayers.map((layer) => {
            const Icon = layer.icon;
            return (
              <Card
                key={layer.title}
                className="overflow-hidden border-border/60 shadow-[0_30px_60px_-25px_rgb(0,0,0,0.35)] !py-0"
              >
                <CardContent
                  className={
                    layer.image
                      ? "grid min-h-[280px] grid-cols-1 gap-0 !px-0 md:grid-cols-5"
                      : "flex min-h-[280px] flex-col !px-0"
                  }
                >
                  <div
                    className={
                      layer.image
                        ? "flex flex-col justify-center p-8 md:col-span-3 md:p-10"
                        : "flex flex-1 flex-col justify-center p-8 md:p-10"
                    }
                  >
                    <div className="mb-4 flex items-center gap-3">
                      <div className="flex size-10 items-center justify-center rounded-lg bg-primary/10">
                        <Icon className="size-5 text-primary" />
                      </div>
                      <span className="text-xs font-mono text-muted-foreground">{layer.tag}</span>
                    </div>
                    <h3 className="text-xl font-semibold md:text-2xl">{layer.title}</h3>
                    <p className="mt-3 text-sm leading-relaxed text-muted-foreground md:text-base">
                      {layer.body}
                    </p>
                  </div>
                  {layer.image && (
                    <div className="relative min-h-[200px] overflow-hidden bg-gradient-to-br from-accent to-secondary md:col-span-2">
                      <Image
                        src={layer.image}
                        alt=""
                        fill
                        sizes="400px"
                        className="object-cover opacity-80 blur-[1px]"
                      />
                    </div>
                  )}
                </CardContent>
              </Card>
            );
          })}
        </StickyStack>
      </section>

      {/* Recovery actions — fan-out card stack */}
      <section id="actions" className="relative mx-auto max-w-6xl px-6 pb-28">
        <ScrollReveal className="mb-10 text-center">
          <p className="text-xs font-medium uppercase tracking-wide text-primary">
            The allowed action set
          </p>
          <h2 className="mt-2 text-2xl font-semibold md:text-3xl">
            A fixed menu — never a freeform action.
          </h2>
          <p className="mx-auto mt-2 max-w-md text-sm text-muted-foreground">
            Hover a panel to bring it forward.
          </p>
        </ScrollReveal>
        <ScrollReveal>
          <div className="vasuli-gallery">
            <AccordionGallery
              items={recoveryActions}
              defaultIndex={0}
              expandRatio={0.48}
              trigger="hover"
              accentColor="oklch(0.55 0.21 262)"
              overlayColor="oklch(0.16 0.03 262)"
              textColor="#ffffff"
              grayscale
              showLabels
              duration={0.6}
              ease="power3.out"
              parallax={0.5}
              tilt={8}
              stagger={0.06}
              height={420}
              gap={10}
              radius={20}
              orientation="horizontal"
            />
          </div>
        </ScrollReveal>
      </section>

      {/* Closing CTA */}
      <section id="cta" className="relative overflow-hidden">
        <div className="absolute inset-0">
          <Image
            src="/illustrations/cta-growth.jpg"
            alt=""
            fill
            sizes="100vw"
            className="object-cover opacity-35 blur-[1px] dark:grayscale"
          />
          <div className="absolute inset-0 bg-gradient-to-t from-[oklch(0.2_0.05_262)] via-[oklch(0.25_0.09_262/0.9)] to-[oklch(0.3_0.1_262/0.75)] dark:from-[oklch(0.2_0_0)] dark:via-[oklch(0.25_0_0/0.9)] dark:to-[oklch(0.3_0_0/0.75)]" />
        </div>
        <ScrollReveal className="relative mx-auto max-w-2xl px-6 py-32 text-center">
          <h2 className="text-2xl font-semibold text-white md:text-3xl">
            See it diagnose, decide, and recover — live.
          </h2>
          <p className="mx-auto mt-3 max-w-md text-sm text-white/80">
            One click runs a real batch through the full pipeline: guardrails,
            the diagnosis agent, and the executors.
          </p>
          <div className="mt-6 flex justify-center">
            <SlideTextButton href="/dashboard" text="Run live batch" hoverText="Let's go →" />
          </div>
        </ScrollReveal>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src="/illustrations/rocket-launch.gif"
          alt=""
          className="pointer-events-none absolute bottom-0 left-8 hidden h-44 w-auto opacity-25 blur-[0.5px] dark:grayscale md:block"
        />
      </section>
    </div>
  );
}
