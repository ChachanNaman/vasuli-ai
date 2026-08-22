import { NextRequest, NextResponse } from "next/server";

const GROQ_MODEL = "openai/gpt-oss-120b";

const SYSTEM_PROMPT = `You are the help assistant embedded in Vasuli, an AI revenue recovery agent \
for Razorpay merchants. Answer questions about how Vasuli works, using only the facts below. \
Keep answers short (2-4 sentences), plain language, no markdown headers.

WHAT VASULI DOES: watches failed payments, failed subscription mandates, abandoned checkouts, \
and overdue B2B invoices. For each one it diagnoses the root cause, picks one bounded recovery \
action, executes it under deterministic guardrails, and logs the outcome honestly (including \
when it could not recover something).

ARCHITECTURE: a synthetic data generator produces events -> a deterministic guardrail engine \
(plain code, no LLM) checks whether an action is allowed -> an LLM diagnosis agent (Groq primary, \
Gemini automatic fallback) proposes a root cause and one action from a fixed menu -> recovery \
executors run the action (real Razorpay test-mode payment links for smart_retry and \
generate_payment_link; everything else is simulated and labeled as such) -> every decision is \
logged to Supabase with full reasoning, every guardrail check, and the outcome.

KEY PRINCIPLE: the LLM never touches money directly. It only proposes; the guardrail engine and \
executors are deterministic code that decide what's actually allowed to run.

GUARDRAIL RULES: max retry attempts (3 for payments, 4 for subscriptions) routes to human review; \
4-hour cool-down between contacts to the same customer; max 2 contacts per customer per 24h; \
opted-out customers get zero comms; invoices over ₹1,00,000 can't be auto-escalated, human review \
only; retries are capped at 1 per payment per 30 minutes (this is the fix for a real retry-storm \
bug the team found and documents in the README); B2B chase tone is tiered by the customer's \
payment reliability score.

ALLOWED ACTIONS: smart_retry, generate_payment_link, send_nudge, escalate_b2b_chase, \
initiate_mandate_reauth, flag_for_human_review, no_action_recommended. The agent is told to prefer \
flagging for human review over guessing when confidence is low.

DASHBOARD SCREENS: Overview (KPI row + recovery-by-cause and recovery-over-time charts), Live \
agent feed (real-time decisions via Supabase Realtime, guardrail-blocked actions show in red), \
Exceptions (everything flagged, opted-out, or blocked — shown honestly, not hidden). Clicking any \
decision opens its full reasoning trace.

If asked something outside this scope, say you only know about Vasuli's own recovery flow.`;

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export async function POST(req: NextRequest) {
  const apiKey = process.env.GROQ_API_KEY;
  if (!apiKey) {
    return NextResponse.json({ error: "Chat is not configured." }, { status: 503 });
  }

  const body = await req.json();
  const messages: ChatMessage[] = body.messages ?? [];
  if (messages.length === 0) {
    return NextResponse.json({ error: "No messages provided." }, { status: 400 });
  }

  const response = await fetch("https://api.groq.com/openai/v1/chat/completions", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${apiKey}`,
    },
    body: JSON.stringify({
      model: GROQ_MODEL,
      messages: [{ role: "system", content: SYSTEM_PROMPT }, ...messages],
      temperature: 0.3,
      max_tokens: 300,
    }),
  });

  if (!response.ok) {
    const text = await response.text();
    return NextResponse.json({ error: `Groq error: ${text}` }, { status: 502 });
  }

  const data = await response.json();
  const reply: string = data.choices?.[0]?.message?.content ?? "Sorry, I couldn't generate a reply.";

  return NextResponse.json({ reply });
}
