export function formatINR(amount: number): string {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(amount);
}

export function formatCompactINR(amount: number): string {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    notation: "compact",
    maximumFractionDigits: 1,
  }).format(amount);
}

export function formatRelativeTime(iso: string): string {
  const then = new Date(iso).getTime();
  const now = Date.now();
  const diffMs = now - then;
  const diffSec = Math.round(diffMs / 1000);

  const divisions: [Intl.RelativeTimeFormatUnit, number][] = [
    ["year", 60 * 60 * 24 * 365],
    ["month", 60 * 60 * 24 * 30],
    ["day", 60 * 60 * 24],
    ["hour", 60 * 60],
    ["minute", 60],
    ["second", 1],
  ];

  const rtf = new Intl.RelativeTimeFormat("en", { numeric: "auto" });
  for (const [unit, secondsInUnit] of divisions) {
    if (Math.abs(diffSec) >= secondsInUnit || unit === "second") {
      const value = Math.round(diffSec / secondsInUnit);
      return rtf.format(-value, unit);
    }
  }
  return "just now";
}

export function formatAbsoluteTime(iso: string): string {
  return new Date(iso).toLocaleString("en-IN", {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

export function formatActionType(action: string): string {
  return action
    .split("_")
    .map((w) => w[0]?.toUpperCase() + w.slice(1))
    .join(" ");
}

export function formatRootCause(cause: string): string {
  return formatActionType(cause);
}

// FEATURES.md #1 — decision-source badge. Derived purely from data already
// on the decision row (action_status, llm_provider); no new fields.
// llm_provider === "heuristic" is the only signal that both LLM providers
// failed — llm_fallback_used alone is *not* that signal, since it's also
// true for a plain Groq -> Gemini fallback (still an LLM call). Priority:
// a heuristic-agent call is the most notable provenance fact about a
// decision regardless of guardrail outcome, so it wins over a
// guardrail-blocked label if both are true (heuristic proposed something
// that also got blocked).
export type DecisionSource = "ai_proposed" | "guardrail_blocked" | "heuristic_fallback";

export interface DecisionSourceInfo {
  source: DecisionSource;
  icon: string;
  label: string;
}

export function decisionSource(decision: {
  action_status: string;
  llm_provider: string | null;
}): DecisionSourceInfo {
  if (decision.llm_provider === "heuristic") {
    return { source: "heuristic_fallback", icon: "📐", label: "Heuristic fallback" };
  }
  if (decision.action_status !== "executed") {
    return { source: "guardrail_blocked", icon: "⚙️", label: "Guardrail blocked" };
  }
  return { source: "ai_proposed", icon: "🤖", label: "AI-proposed" };
}
