"use client";

import { useMutation } from "@tanstack/react-query";
import { Brain, Play } from "lucide-react";
import { runDiagnosisAgreement } from "@/lib/api";
import { formatActionType, formatRootCause } from "@/lib/format";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

export function DiagnosisAgreementCard() {
  const mutation = useMutation({
    mutationFn: () => runDiagnosisAgreement(15, 42),
  });

  const result = mutation.data;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm font-medium flex items-center gap-1.5">
          <Brain className="size-4" />
          LLM vs. heuristic agreement
        </CardTitle>
        <p className="text-xs text-muted-foreground">
          If Groq and Gemini were both down right now, how much would actually be lost by falling
          back to the deterministic heuristic? Runs the live LLM against the same events the
          heuristic sees and compares their independent judgment — not accuracy against a label
          (the heuristic deliberately just echoes the event&apos;s own failure code, so that would
          always read 100% and prove nothing).
        </p>
      </CardHeader>
      <CardContent>
        <button
          onClick={() => mutation.mutate()}
          disabled={mutation.isPending}
          className={cn(
            "inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors",
            mutation.isPending
              ? "bg-processing/15 text-processing cursor-not-allowed"
              : "bg-primary text-primary-foreground hover:bg-primary/90"
          )}
        >
          {mutation.isPending ? (
            "Calling live LLM…"
          ) : (
            <>
              <Play className="size-3.5" />
              Run 15-case check (live API calls)
            </>
          )}
        </button>

        {mutation.isError && (
          <p className="mt-2 text-xs text-destructive">{(mutation.error as Error).message}</p>
        )}

        {result && (
          <div className="mt-3 space-y-3">
            <div className="flex items-center gap-2 flex-wrap">
              <Badge variant="outline" className="font-mono text-[10px]">
                {result.n_evaluated}/{result.n_cases_requested} evaluated
                {result.llm_calls_failed > 0 && `, ${result.llm_calls_failed} LLM calls failed`}
              </Badge>
              {result.action_agreement_pct != null && (
                <Badge className="bg-primary/15 text-primary border-primary/30">
                  {result.action_agreement_pct}% action agreement
                </Badge>
              )}
              {result.root_cause_agreement_pct != null && (
                <Badge className="bg-secondary text-secondary-foreground border-transparent">
                  {result.root_cause_agreement_pct}% root-cause agreement
                </Badge>
              )}
            </div>

            {result.rows.length > 0 && (
              <div className="space-y-1 max-h-64 overflow-y-auto pr-1">
                {result.rows.map((row) => (
                  <div
                    key={row.event_id}
                    className={cn(
                      "flex items-center justify-between gap-2 text-xs rounded-md px-2 py-1.5 border",
                      row.action_agree
                        ? "border-border/50 bg-muted/20"
                        : "border-destructive/40 bg-destructive/10"
                    )}
                  >
                    <span className="font-mono text-muted-foreground shrink-0">
                      {row.event_id.slice(0, 12)}
                    </span>
                    <span className="text-muted-foreground truncate">
                      heuristic: {formatActionType(row.heuristic_action)}
                    </span>
                    <span className="text-muted-foreground shrink-0">→</span>
                    <span
                      className={cn(
                        "truncate font-medium",
                        row.action_agree ? "text-foreground" : "text-destructive"
                      )}
                    >
                      LLM: {formatActionType(row.llm_action)}
                    </span>
                    {!row.root_cause_agree && (
                      <span
                        className="text-muted-foreground shrink-0"
                        title={`heuristic: ${formatRootCause(row.heuristic_root_cause)} / LLM: ${formatRootCause(row.llm_root_cause)}`}
                      >
                        (cause diverged too)
                      </span>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
