"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { AnimatePresence, motion } from "motion/react";
import { supabase } from "@/lib/supabase";
import type { DecisionRow } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { DecisionSourceBadge } from "@/components/dashboard/decision-source-badge";
import { formatActionType, formatCompactINR, formatRootCause, formatRelativeTime } from "@/lib/format";
import { cn } from "@/lib/utils";

const MAX_FEED_ITEMS = 30;

function statusStyles(status: DecisionRow["action_status"]) {
  switch (status) {
    case "executed":
      return "border-l-primary";
    case "blocked_by_guardrail":
      return "border-l-destructive bg-destructive/5";
    case "skipped_opt_out":
      return "border-l-muted-foreground bg-muted/30";
  }
}

function StatusBadge({ status }: { status: DecisionRow["action_status"] }) {
  if (status === "executed") {
    return <Badge className="bg-primary/15 text-primary border-primary/30">Executed</Badge>;
  }
  if (status === "blocked_by_guardrail") {
    return (
      <Badge variant="destructive" className="bg-destructive/15 text-destructive border-destructive/30">
        Guardrail blocked
      </Badge>
    );
  }
  return <Badge variant="secondary">Opt-out respected</Badge>;
}

export function LiveFeed({
  initialDecisions,
  onSelect,
}: {
  initialDecisions: DecisionRow[];
  onSelect: (decision: DecisionRow) => void;
}) {
  const [feed, setFeed] = useState<DecisionRow[]>(initialDecisions.slice(0, MAX_FEED_ITEMS));
  const seenIds = useRef(new Set(initialDecisions.map((d) => d.decision_id)));

  useEffect(() => {
    setFeed(initialDecisions.slice(0, MAX_FEED_ITEMS));
    seenIds.current = new Set(initialDecisions.map((d) => d.decision_id));
  }, [initialDecisions]);

  useEffect(() => {
    const channel = supabase
      .channel("decisions-live-feed")
      .on(
        "postgres_changes",
        { event: "INSERT", schema: "public", table: "decisions" },
        (payload) => {
          const row = payload.new as DecisionRow;
          if (seenIds.current.has(row.decision_id)) return;
          seenIds.current.add(row.decision_id);
          setFeed((prev) => [row, ...prev].slice(0, MAX_FEED_ITEMS));
        }
      )
      .subscribe();

    return () => {
      supabase.removeChannel(channel);
    };
  }, []);

  if (feed.length === 0) {
    return (
      <div className="flex items-center justify-center h-64 text-sm text-muted-foreground border border-dashed rounded-lg">
        No decisions yet — run a batch to watch the agent work.
      </div>
    );
  }

  return (
    <div className="space-y-2 max-h-[560px] overflow-y-auto pr-1">
      <AnimatePresence initial={false}>
        {feed.map((d) => {
          const blocked = d.action_status === "blocked_by_guardrail";
          return (
            <motion.div
              key={d.decision_id}
              layout
              role="button"
              tabIndex={0}
              initial={{ opacity: 0, y: -12, scale: 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, scale: 0.96 }}
              transition={
                blocked
                  ? { duration: 0.6, ease: "easeOut" }
                  : { type: "spring", stiffness: 320, damping: 28 }
              }
              onClick={() => onSelect(d)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") onSelect(d);
              }}
              className={cn(
                "w-full text-left rounded-lg border border-border/60 border-l-4 bg-card px-4 py-3 hover:bg-accent/50 transition-colors cursor-pointer",
                statusStyles(d.action_status)
              )}
            >
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2 min-w-0">
                  <span className="font-mono text-xs text-muted-foreground truncate">
                    {d.event_id}
                  </span>
                  <Link
                    href={`/dashboard/customers/${encodeURIComponent(d.customer_id)}`}
                    onClick={(e) => e.stopPropagation()}
                    className="font-mono text-xs text-primary underline underline-offset-2 shrink-0"
                  >
                    {d.customer_id}
                  </Link>
                  <StatusBadge status={d.action_status} />
                  <DecisionSourceBadge decision={d} hideIfRedundant />
                </div>
                <span className="text-xs text-muted-foreground shrink-0">
                  {formatRelativeTime(d.timestamp)}
                </span>
              </div>
              <div className="mt-1.5 flex items-center gap-2 text-sm">
                <span className="text-muted-foreground">{formatRootCause(d.root_cause)}</span>
                <span className="text-muted-foreground">→</span>
                <span className="font-medium">{formatActionType(d.action_type)}</span>
                {d.recovered && (
                  <span className="ml-auto font-mono text-primary font-medium">
                    +{formatCompactINR(d.amount_recovered)}
                  </span>
                )}
              </div>
              {d.llm_fallback_used && (
                <p className="mt-1 text-[11px] text-muted-foreground">
                  Groq unavailable — Gemini fallback used
                </p>
              )}
            </motion.div>
          );
        })}
      </AnimatePresence>
    </div>
  );
}
