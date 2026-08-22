"use client";

import Link from "next/link";
import { motion } from "motion/react";
import { ArrowRight } from "lucide-react";
import BeamsBackground from "@/components/kokonutui/beams-background";
import CurrencyTransfer from "@/components/kokonutui/currency-transfer";

export default function LandingPage() {
  return (
    <div className="relative flex-1 flex items-center overflow-hidden">
      <BeamsBackground className="absolute inset-0" intensity="medium" />

      <div className="relative z-10 mx-auto max-w-6xl w-full px-6 py-20 grid lg:grid-cols-2 gap-12 items-center">
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, ease: "easeOut" }}
        >
          <span className="inline-block text-xs font-medium tracking-wide uppercase text-primary border border-primary/30 rounded-full px-3 py-1 mb-6">
            Razorpay AI Buildathon — Track 03
          </span>
          <h1 className="text-4xl md:text-5xl font-semibold tracking-tight leading-[1.1]">
            Vasuli — the AI agent that{" "}
            <span className="text-primary">gets your money back.</span>
          </h1>
          <p className="mt-5 text-base md:text-lg text-muted-foreground max-w-lg leading-relaxed">
            It watches failed payments, abandoned checkouts, failed mandates,
            and overdue invoices — diagnoses why each one is losing money,
            picks a bounded action, executes it under hard guardrails, and
            reports exactly how much it got back. And what it honestly
            couldn&apos;t.
          </p>

          <div className="mt-8 flex items-center gap-4">
            <motion.div whileHover={{ scale: 1.03 }} whileTap={{ scale: 0.97 }}>
              <Link
                href="/dashboard"
                className="inline-flex items-center gap-2 rounded-lg bg-primary text-primary-foreground px-6 py-3 text-sm font-medium shadow-sm hover:bg-primary/90 transition-colors"
              >
                Run live batch
                <ArrowRight className="size-4" />
              </Link>
            </motion.div>
            <a
              href="https://github.com/ChachanNaman/vasuli-ai"
              target="_blank"
              rel="noreferrer"
              className="text-sm text-muted-foreground hover:text-foreground transition-colors"
            >
              View source →
            </a>
          </div>

          <p className="mt-6 text-xs text-muted-foreground max-w-md">
            The LLM never touches money directly — a deterministic guardrail
            engine and recovery executors are the only things allowed to act.
          </p>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, scale: 0.96 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.6, delay: 0.15, ease: "easeOut" }}
        >
          <CurrencyTransfer />
        </motion.div>
      </div>
    </div>
  );
}
