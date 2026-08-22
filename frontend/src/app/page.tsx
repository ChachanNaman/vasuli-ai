"use client";

import Link from "next/link";
import { motion } from "motion/react";
import { ShieldCheck, Brain, Wallet, ScrollText } from "lucide-react";
import CurrencyTransfer from "@/components/kokonutui/currency-transfer";
import CardStackExample from "@/components/kokonutui/card-stack";
import SlideTextButton from "@/components/kokonutui/slide-text-button";
import { SplitText } from "@/components/motion/split-text";
import { ScrollReveal } from "@/components/motion/scroll-reveal";
import { ScrollZoom } from "@/components/motion/scroll-zoom";
import { ScrollFadeBackground } from "@/components/motion/scroll-fade-background";
import { StickyStack } from "@/components/motion/sticky-stack";
import { Card, CardContent } from "@/components/ui/card";

const architectureLayers = [
  {
    icon: Brain,
    title: "Diagnosis agent",
    body: "Groq primary, Gemini automatic fallback. Given one event's full context, it confirms the root cause and picks exactly one action from a fixed menu — never freeform. Below a confidence threshold, it's told to flag for human review instead of guessing.",
    tag: "LLM · proposes only",
  },
  {
    icon: ShieldCheck,
    title: "Guardrail engine",
    body: "Plain deterministic code — no LLM involved. Retry caps, cool-downs, contact caps, opt-out enforcement, spend caps on invoices, and the retry rate limit that fixed a real retry-storm bug. Every check is logged, pass or fail.",
    tag: "Deterministic · decides",
  },
  {
    icon: Wallet,
    title: "Recovery executors",
    body: "Runs the action once it's cleared. Real Razorpay test-mode payment links for smart_retry and generate_payment_link; everything else is simulated and clearly labeled as such in the UI.",
    tag: "Executes · zero real money",
  },
  {
    icon: ScrollText,
    title: "Audit trail",
    body: "Every decision — executed, blocked, or skipped — is written with its full reasoning, every guardrail check, and the outcome. Nothing is swept under the rug, including what couldn't be recovered.",
    tag: "Supabase · full history",
  },
];

export default function LandingPage() {
  return (
    <div className="relative flex-1">
      <ScrollFadeBackground />

      {/* Hero */}
      <section className="relative flex min-h-screen items-center overflow-hidden">
        <div className="relative z-10 mx-auto grid w-full max-w-6xl grid-cols-1 items-center gap-12 px-6 py-20 lg:grid-cols-2">
          <div>
            <motion.span
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5 }}
              className="mb-6 inline-block rounded-full border border-primary/30 px-3 py-1 text-xs font-medium uppercase tracking-wide text-primary"
            >
              Razorpay AI Buildathon — Track 03
            </motion.span>

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
              className="mt-5 max-w-lg text-base leading-relaxed text-muted-foreground md:text-lg"
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
              className="mt-6 max-w-md text-xs text-muted-foreground"
            >
              The LLM never touches money directly — a deterministic guardrail
              engine and recovery executors are the only things allowed to act.
            </motion.p>
          </div>

          <ScrollZoom scaleRange={[0.94, 1.05]}>
            <motion.div
              initial={{ opacity: 0, scale: 0.96 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ duration: 0.6, delay: 0.3, ease: "easeOut" }}
            >
              <CurrencyTransfer />
            </motion.div>
          </ScrollZoom>
        </div>
      </section>

      {/* Architecture — sticky stack */}
      <section className="relative mx-auto max-w-3xl px-6 pb-20">
        <ScrollReveal className="mb-4 text-center">
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
              <Card key={layer.title} className="border-border/60 shadow-xl">
                <CardContent className="p-8 md:p-10">
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
                </CardContent>
              </Card>
            );
          })}
        </StickyStack>
      </section>

      {/* Recovery actions — fan-out card stack */}
      <section className="relative mx-auto max-w-6xl px-6 pb-28">
        <ScrollReveal className="mb-10 text-center">
          <p className="text-xs font-medium uppercase tracking-wide text-primary">
            The allowed action set
          </p>
          <h2 className="mt-2 text-2xl font-semibold md:text-3xl">
            A fixed menu — never a freeform action.
          </h2>
          <p className="mx-auto mt-2 max-w-md text-sm text-muted-foreground">
            Click the stack to see all four.
          </p>
        </ScrollReveal>
        <CardStackExample />
      </section>

      {/* Closing CTA */}
      <ScrollReveal className="relative mx-auto max-w-2xl px-6 pb-28 text-center">
        <h2 className="text-2xl font-semibold md:text-3xl">
          See it diagnose, decide, and recover — live.
        </h2>
        <p className="mx-auto mt-3 max-w-md text-sm text-muted-foreground">
          One click runs a real batch through the full pipeline: guardrails,
          the diagnosis agent, and the executors.
        </p>
        <div className="mt-6 flex justify-center">
          <SlideTextButton href="/dashboard" text="Run live batch" hoverText="Let's go →" />
        </div>
      </ScrollReveal>
    </div>
  );
}
