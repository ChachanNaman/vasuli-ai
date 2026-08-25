"use client";

import Link from "next/link";
import { motion } from "motion/react";
import { Badge } from "@/components/ui/badge";
import { DecisionSourceBadge } from "@/components/dashboard/decision-source-badge";
import type { ExceptionRow } from "@/lib/types";
import { formatActionType, formatRootCause, formatRelativeTime } from "@/lib/format";

export function ExceptionsTab({ exceptions }: { exceptions: ExceptionRow[] }) {
  if (exceptions.length === 0) {
    return (
      <div className="flex items-center justify-center h-48 text-sm text-muted-foreground border border-dashed rounded-lg">
        No exceptions yet — everything the agent has decided so far was actioned.
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <p className="text-sm text-muted-foreground mb-3">
        Vasuli doesn&apos;t hide what it couldn&apos;t recover — everything flagged for
        human review, opted out, or blocked by a guardrail shows up here honestly.
      </p>
      {exceptions.map((e, i) => (
        <motion.div
          key={e.decision_id}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: Math.min(i * 0.03, 0.3) }}
          className="rounded-lg border border-border/60 bg-card px-4 py-3"
        >
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2 min-w-0">
              <span className="font-mono text-xs text-muted-foreground truncate">
                {e.event_id}
              </span>
              <Link
                href={`/dashboard/customers/${encodeURIComponent(e.customer_id)}`}
                className="font-mono text-xs text-primary underline underline-offset-2 shrink-0"
              >
                {e.customer_id}
              </Link>
            </div>
            <span className="text-xs text-muted-foreground shrink-0">
              {formatRelativeTime(e.timestamp)}
            </span>
          </div>
          <div className="mt-1.5 flex items-center gap-2 flex-wrap">
            <Badge variant="outline">{formatRootCause(e.root_cause)}</Badge>
            <Badge variant="secondary">{formatActionType(e.action_type)}</Badge>
            <Badge variant="outline">{formatActionType(e.action_status)}</Badge>
            <DecisionSourceBadge decision={e} />
          </div>
          <p className="mt-2 text-sm text-muted-foreground">{e.reasoning_text}</p>
          {e.outcome_notes && (
            <p className="mt-1 text-xs text-muted-foreground italic">{e.outcome_notes}</p>
          )}
        </motion.div>
      ))}
    </div>
  );
}
