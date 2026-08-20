# Vasuli — the AI agent that gets your money back

Vasuli (वसूली — Hindi/Hinglish for "recovery") is an autonomous revenue
recovery agent for Razorpay merchants. It watches failed payments, failed
subscription mandates, abandoned checkouts, and overdue B2B invoices,
diagnoses *why* each one is losing money, picks a bounded and explainable
recovery action, executes it under hard deterministic guardrails, and
reports exactly how much money it got back — and how much it honestly
could not.

Built for Razorpay's AI Buildathon, Track 03: AI Revenue Recovery.

## Why this exists

Track 03's bar is explicit: don't just identify the problem — show measured
money recovered across a batch, with compliant escalation, stopping rules,
and an audit trail. Vasuli is built so each of those is a literal feature,
not a slide:

| Bar requirement | How Vasuli satisfies it |
|---|---|
| Measured money recovered across a batch | Metrics computed live from an 80+ record synthetic batch — ₹ recovered, recovery rate by cause, total exposure |
| Compliant escalation | Escalation respects opt-outs and never exceeds contact-frequency caps |
| Stopping rules | A deterministic guardrail engine runs before every agent action — max retries, cool-downs, spend caps |
| Audit trail | Every decision is logged with cause, reasoning, every guardrail check, and outcome — browsable in the UI |
| Honest exceptions | A dedicated "could not recover" list with reasons, never hidden |
| AI judgment | Guardrails and stopping rules are plain deterministic code, never an LLM call — the LLM is used only for what actually needs judgment: diagnosis and message drafting |

**The LLM never touches money directly.** It proposes a diagnosis and an
action; the guardrail engine and the recovery executors are the only things
allowed to actually do something, and both are deterministic code the LLM
cannot argue its way past.

## Architecture

```
Frontend (Next.js, Vercel)
  Dashboard · Live Agent Feed · Event Drill-down · Exceptions Tab
        │ REST (batch trigger, queries)     ▲ Supabase Realtime (live decisions)
        ▼                                   │
Backend (FastAPI, Render)
  Data Generator → Guardrail Engine → Diagnosis + Action Agent (Groq / Gemini)
                                              │
                        Recovery Executors ←→ Razorpay Test Mode API (real, zero-cost)
                                │
                      Audit Trail + Metrics → Supabase Postgres
```

The guardrail engine and recovery executors sit strictly downstream of the
LLM. The agent recommends; deterministic code decides whether it's allowed
to run.

## Guardrail engine (deterministic, no LLM)

Runs before every proposed action, regardless of what the agent recommends.
Every check — pass or fail — is written to the audit trail, not just the
ones that blocked something.

| Rule | Logic |
|---|---|
| Max retry attempts | Block retry if `attempt_number >= 3` for payments, `>= 4` for subscriptions — route to human/manual queue |
| Cool-down window | No repeat contact to the same customer within 4 hours of the last attempt |
| Daily contact cap | Max 2 recovery touches per customer per 24h across all channels |
| Opt-out enforcement | If the customer opted out of recovery comms, no comms action runs — silently routed to "excluded" |
| Spend/amount cap | Invoices over ₹1,00,000 cannot be auto-escalated; flagged for human review only |
| Retry rate limit | No more than 1 retry per payment per 30 minutes — prevents retry storms (see below) |
| Reliability floor (B2B) | `payment_reliability_score < 0.3` → firmer escalation tier; `>= 0.7` → soft reminder only |

Fully covered by unit tests in [`backend/tests/test_guardrails.py`](backend/tests/test_guardrails.py) —
every rule in the table above has both a pass case and a block case.

## The diagnosis + intervention agent

Given one event's full context, the LLM does exactly three things:

1. Confirms or refines the root cause — reasoning over raw signals (attempt
   history, timing, customer history), not just echoing the generator's
   `failure_reason_code` label.
2. Picks exactly one action from a fixed, allow-listed set: `smart_retry`,
   `generate_payment_link`, `send_nudge`, `escalate_b2b_chase`,
   `initiate_mandate_reauth`, `flag_for_human_review`, `no_action_recommended`.
3. Drafts the customer-facing message (Hinglish or English) if the action
   involves contact.

It never decides whether the action is *allowed* to run — that's the
guardrail engine's job, applied after the LLM proposes. Below a confidence
threshold, the system prompt explicitly steers the model toward
`flag_for_human_review` or `no_action_recommended` rather than guessing.

Output is structured via tool-calling against a fixed JSON schema — never
free text — so every decision is auditable and machine-checkable.

**Resilience:** Groq is the primary LLM (fast inference, free tier). On any
Groq error or rate-limit, the agent automatically falls back to Gemini, and
every fallback event is logged. If both providers fail on a given event, the
pipeline routes it to `flag_for_human_review` rather than silently doing
nothing — an honest failure, not a hidden one.

## The failure story: the retry storm

**What broke:** an early version of the retry path had no rate limit — a
customer whose payment failed with `insufficient_funds` would get retried on
every batch run, including runs seconds apart during testing. Real payment
networks treat rapid repeat retries as suspicious and soft-decline them,
which means the retry itself was making recovery *worse*, not better.

**How it was caught:** the audit trail's guardrail checks showed `passed:
true` on every retry with no rule in place to catch the pattern, and the
outcome log showed a recovering payment flipping to a new decline reason
after multiple rapid retries against the same customer — the system's own
audit trail surfaced the bug.

**The fix:** added the 30-minute per-payment retry rate limit and the
4-hour cross-channel cool-down (`retry_rate_limit` and `cool_down_window` in
the guardrail table above), and gave the audit trail an explicit
`rate_limited` block reason so this class of failure is visible, not silent.
The fix is a guardrail, not a prompt tweak — the guardrail layer is what's
trusted for correctness, not the LLM.

## Tech stack

100% free tier, no paid signups anywhere.

| Layer | Choice |
|---|---|
| Frontend | Next.js 14 (App Router) + TypeScript, Tailwind, shadcn/ui, Tremor |
| Backend | FastAPI (Python 3.11+) |
| LLM | Groq (primary) → Gemini (automatic fallback) |
| Database | Supabase Postgres + Realtime |
| Payments | Razorpay Test Mode API (real payment links, zero cost) |
| Hosting | Vercel (frontend), Render free tier (backend) |

## Repo layout

```
vasuli-ai/
├── PRD_1.md
├── README.md
├── backend/
│   └── app/
│       ├── data/          # event schema + synthetic generator
│       ├── guardrails/     # deterministic rule engine
│       ├── agents/         # diagnosis agent, prompts, Groq/Gemini client
│       ├── recovery/        # executors + outcome model (Day 2)
│       ├── audit/            # Supabase-backed decision logger + metrics
│       └── api/               # FastAPI routes + batch pipeline
├── backend/tests/
├── supabase/migrations/     # SQL schema (events, decisions, metrics views)
└── frontend/                 # Next.js dashboard (Day 2)
```

## Setup

### Backend

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example ../.env   # fill in Supabase / Groq / Gemini / Razorpay keys
python -m pytest -q          # 36 tests, all deterministic — no live keys needed
uvicorn app.api.main:app --reload
```

### Database

Run [`supabase/migrations/0001_init.sql`](supabase/migrations/0001_init.sql)
against a free Supabase project (SQL editor or `supabase db push`).

### Environment variables

See [`.env.example`](.env.example) for the full list — Supabase, Groq,
Gemini, and Razorpay Test Mode keys. All four are free tier, no credit card
required at signup.

## Current status

Day 1 (data model, guardrail engine, diagnosis agent, FastAPI wiring) is
complete and covered by 36 passing unit/integration tests. The full
pipeline — generate → guardrail-check → diagnose → write decision — is
proven correct against a mocked Supabase + LLM; a live run against real
Supabase/Groq/Gemini is next. Recovery executors, the Razorpay Test Mode
integration, and the frontend dashboard are in progress.

## Known limitations

- Render's free tier cold-starts after ~15 minutes idle.
- All comms channels (WhatsApp/SMS/email) are simulated in-UI, clearly
  labeled as such — no paid delivery provider is wired up.
- Single-merchant demo: no auth/login system, no multi-tenancy.
