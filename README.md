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
| Baseline-compared, not just raw recovery | An evaluation harness runs the same cases through do-nothing, naive-dunning, and Vasuli policies with common random numbers and reports **incremental** recovery — the number that matters after netting out the ~15–20% of value that comes back with zero intervention |
| Compliant escalation | Escalation respects opt-outs, contact-frequency caps, and named regulatory constraints (RBI contact hours, e-mandate notice, TRAI DLT templates) |
| Stopping rules | A deterministic guardrail engine — 12 rules — runs before every agent action, including an economic stopping rule that forces restraint when an action costs more than it could plausibly recover |
| Audit trail | Every decision is logged with cause, reasoning, every guardrail check, and outcome — and the whole trail is hash-chained, so tampering with any past record is provably detectable |
| Honest exceptions | A dedicated "could not recover" list with reasons, never hidden |
| AI judgment | Guardrails and stopping rules are plain deterministic code, never an LLM call — the LLM is used only for what actually needs judgment: diagnosis and message drafting. A zero-API-key heuristic agent backs it up if both LLM providers fail |

**The LLM never touches money directly.** It proposes a diagnosis and an
action; the guardrail engine and the recovery executors are the only things
allowed to actually do something, and both are deterministic code the LLM
cannot argue its way past.

## Architecture

```
Frontend (Next.js, Vercel)
  Dashboard · Live Agent Feed · Event Drill-down · Exceptions Tab · vs. Baseline
        │ REST (batch trigger, queries)     ▲ Supabase Realtime (live decisions)
        ▼                                   │
Backend (FastAPI, Render)
  Data Generator → Diagnosis Agent (Groq → Gemini → heuristic) → Guardrail Engine
                                              │
                        Recovery Executors ←→ Razorpay Test Mode API (real, zero-cost)
                                │
                      Audit Trail (hash-chained) + Metrics → Supabase Postgres
```

The guardrail engine and recovery executors sit strictly downstream of the
LLM. The agent recommends; deterministic code decides whether it's allowed
to run. See [`docs/architecture.md`](docs/architecture.md) for the full
request-flow walkthrough, data model, and API reference.

## Guardrail engine (deterministic, no LLM) — 12 rules

Runs before every proposed action, regardless of what the agent recommends.
Every check — pass or fail — is written to the audit trail, not just the
ones that blocked something.

| Rule | Regulatory / policy basis | Logic |
|---|---|---|
| Max retry attempts | Card network rules cap retry attempts on a declined instrument | Block retry if `attempt_number >= 3` for payments, `>= 4` for subscriptions |
| Cool-down window | RBI fair-practice codes | No repeat contact within 4 hours of the last attempt |
| Daily contact cap | RBI fair-practice codes | Max 2 recovery touches per customer per 24h across all channels |
| Opt-out enforcement | TRAI DND registry + customer's own opt-out flag | No comms action if the customer opted out |
| Spend/amount cap | Internal policy cap | Invoices over ₹1,00,000 flagged for human review only, never auto-escalated |
| Retry rate limit | Card network rules (timing dimension) | No more than 1 retry per payment per 30 minutes — prevents retry storms (see below) |
| Reliability floor (B2B) | Internal policy | `payment_reliability_score < 0.3` → firmer tier, `>= 0.7` → soft reminder |
| **Contact window** | RBI recovery-agent guidelines restrict borrower contact to roughly 08:00–19:00 IST | No customer-facing action outside this window; queued instead |
| **E-mandate pre-debit notice** | RBI's e-mandate/recurring-payment framework requires prior notification before an auto-debit | A retry or re-auth against an *active* mandate must carry a confirmed notice period, never fire silently |
| **DLT template compliance** | TRAI mandates pre-registered SMS/WhatsApp content | Comms actions send from a small fixed template set — the LLM's freeform draft is never sent directly |
| **Dispute freeze** | Standard chargeback-handling practice | Any event flagged `dispute_opened` hard-stops all agent action pending resolution |
| **Economic stopping rule** | Stated cost figures in `recovery/cost_model.py` | Forces `no_action_recommended` whenever expected recovery is under 3x the action's cost — a cheap action still isn't free if it's mathematically not worth sending |

We don't cite specific rupee thresholds or notice-period figures for the
e-mandate rule — that figure has changed in 2026 rule updates and we
haven't independently verified the current revision; the code cites the
*existence* of the requirement, not a number pulled from memory.

Fully covered by unit tests in [`backend/tests/test_guardrails.py`](backend/tests/test_guardrails.py) —
every rule has both a pass case and a block case — plus an **adversarial
test** ([`test_guardrails_adversarial.py`](backend/tests/test_guardrails_adversarial.py)):
a stub agent that recommends the single worst legal action for every case
across 3 seeds (240 cases total). 100% blocked, zero disallowed actions
reach the executor layer.

## The diagnosis agent — three-way degradation

Given one event's full context, the diagnosis layer does exactly three
things: confirms/refines the root cause (reasoning over attempt history,
timing, and customer history, not just echoing the generator's label),
picks exactly one action from a fixed allow-listed set, and drafts the
customer-facing message if the action involves contact. It never decides
whether the action is *allowed* to run — that's the guardrail engine's job,
applied after the agent proposes.

Output is structured via tool-calling against a fixed JSON schema — never
free text — so every decision is auditable and machine-checkable.

**Resilience — Groq → Gemini → heuristic.** Groq is the primary LLM (fast
inference, free tier). On any Groq error or rate-limit, the agent
automatically falls back to Gemini. If *both* LLM providers fail, the
pipeline degrades to [`app/agents/heuristic_agent.py`](backend/app/agents/heuristic_agent.py)
— a small, explicit, zero-API-key rule-based diagnosis function that picks
from the exact same allowed action set. Every fallback event is logged,
whichever level it happens at. This has already fired for real during
development: Groq briefly emitted malformed tool-call JSON, Gemini's
free-tier daily quota was exhausted, and the pipeline correctly degraded
all the way to a valid, guardrail-checked heuristic decision instead of
failing the batch.

The heuristic agent also powers the `vasuli` arm of the evaluation harness
below — evaluating hundreds of cases against a live LLM would be slow,
rate-limited, and non-reproducible, which would defeat the point of a
rigorous comparison.

## The evaluation harness — incremental recovery, not raw

`backend/app/eval/` runs the same batch of synthetic cases through four
policies — `do_nothing`, `fixed_dunning` (a naive fixed action for every
case, no guardrails checked), `vasuli` (heuristic diagnosis + the real
guardrail engine), and `max_pressure` (most aggressive action possible,
guardrails ignored entirely) — using **common random numbers**: every case
gets one pre-drawn seed used identically across all four arms, so a case
that "gets lucky" gets lucky in every arm, and differences between arms are
attributable to policy, not noise.

The headline number is **incremental recovery** —
`recovered_under_policy - recovered_under_do_nothing` — not raw recovery.
Roughly 15–20% of at-risk value in this dataset comes back on its own with
*zero* intervention (a customer retries themselves, a reliable business
customer pays late anyway); counting that as the agent's own win is the
easiest way for a recovery product to flatter itself.

Actual output, 500 cases, seed 42, reproducible run-to-run:

| Policy | Incremental recovered | Raw recovery | Contacts/case | Guardrail violations | Cost |
|---|---|---|---|---|---|
| do_nothing | ₹0 | 15.80% | 0.00 | 0 | ₹0 |
| fixed_dunning | ₹49.6L | 56.05% | 0.35 | **175** | ₹85.55 |
| **vasuli** | **₹10.0L** | 23.91% | 0.26 | **47** | ₹55.80 |
| max_pressure | ₹49.6L | 56.05% | 0.35 | 175 | ₹85.55 |

The honest reading: a policy that acts on every case regardless of
guardrails recovers more raw ₹, but at ~3.7x the compliance violations.
Vasuli's guardrails trade some raw recovery for a large, quantified
reduction in violations and lower cost per case — that trade-off is
reported plainly, not hidden behind a single "recovery rate" number.

`fixed_dunning` and `max_pressure` land on identical figures — worth being
upfront about why, rather than manufacturing a fake difference: this
harness evaluates each case independently with no cross-case history, so
the guardrail rules that most separate "one naive retry" from "retry as
often as technically possible" (cool-down, daily contact cap, retry-storm
rate limit) need a multi-touch sequential simulation to diverge, which is
out of scope for this harness's design.

Cost figures (`recovery/cost_model.py`) and outcome probabilities
(`recovery/outcome_model.py`) are hand-picked and stated explicitly in code
comments, not derived from any real billing data — every number here can be
traced to its source and argued with.

Reproduce it: `python -m app.eval.run_comparison --cases 500 --seed 42`, or
via the dashboard's **vs. Baseline** tab, which calls the same harness
through `GET /api/eval/comparison`.

## Hash-chained audit trail

Each `decisions` row stores `record_hash = sha256(previous_hash +
canonical_json(this_row))`. Altering or deleting any past row breaks every
hash after it. `python -m app.audit.verify` walks the chain and prints
`✅ N records verified, chain intact`, or fails loudly at the first broken
link — proven both by unit tests (`test_hash_chain.py`) that construct a
tamper and confirm it's caught, and live against real Supabase data.

The dashboard's **vs. Baseline** tab surfaces this as an
"audit integrity: verified ✅" badge, sourced from `GET /api/audit/verify`.

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

A second, smaller failure surfaced later, caught the same way the harness
is supposed to catch things: the evaluation harness's own reproducibility
depended on event/customer IDs, which were generated with `uuid.uuid4()` —
a call that reads from the OS's CSPRNG and completely ignores
`random.seed()`. Running the same `--seed 42` comparison twice silently
produced two different reports. Fixed by drawing IDs from the seeded
`random` module instead (`app/data/generator.py::_random_hex`); verified
two separate CLI invocations with the same seed now produce byte-identical
output.

## Tech stack

100% free tier, no paid signups anywhere.

| Layer | Choice |
|---|---|
| Frontend | Next.js 14 (App Router) + TypeScript, Tailwind, shadcn/ui, Tremor |
| Backend | FastAPI (Python 3.11+) |
| LLM | Groq (primary) → Gemini (automatic fallback) → deterministic heuristic (last resort) |
| Database | Supabase Postgres + Realtime |
| Payments | Razorpay Test Mode API (real payment links, zero cost — live and verified) |
| Hosting | Vercel (frontend), Render free tier (backend) |

## Repo layout

```
vasuli-ai/
├── README.md
├── docs/
│   ├── architecture.md      # full system walkthrough, data model, API surface
│   └── demo-script.md       # 5-minute pitch script mapped to the judging journey
├── backend/
│   └── app/
│       ├── data/           # event schema + synthetic generator
│       ├── guardrails/      # deterministic rule engine — 12 rules, adversarial test
│       ├── agents/          # diagnosis agent, heuristic fallback, prompts, Groq/Gemini client
│       ├── recovery/         # executors, outcome model, cost model, Razorpay Test Mode client
│       ├── audit/             # decision logger, hash chain, verify CLI, metrics
│       ├── eval/               # baseline-comparison evaluation harness
│       └── api/                 # FastAPI routes + batch pipeline
├── backend/tests/                # 110 tests
├── supabase/migrations/          # SQL schema (events, decisions + hash chain, metrics views)
└── frontend/                     # dashboard, live feed, drill-down, exceptions, vs. baseline
```

See [`docs/architecture.md`](docs/architecture.md) for the full request-flow
walkthrough and API reference, and [`docs/demo-script.md`](docs/demo-script.md)
for the pitch-video script mapped to the judging journey.

## Setup

### Backend

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example ../.env   # fill in Supabase / Groq / Gemini / Razorpay keys
python -m pytest -q          # 110 tests, all deterministic — no live keys needed
uvicorn app.api.main:app --reload
```

Useful one-off commands once `.env` is populated:

```bash
python -m app.eval.run_comparison --cases 500 --seed 42   # evaluation harness
python -m app.audit.verify                                 # hash-chain integrity check
```

### Frontend

```bash
cd frontend
npm install
cp ../.env.example .env.local   # fill in NEXT_PUBLIC_* Supabase + API base URL
npm run dev
```

### Database

Run both migrations, in order, against a free Supabase project (SQL editor
or `supabase db push`):

1. [`supabase/migrations/0001_init.sql`](supabase/migrations/0001_init.sql) — events, decisions, metrics views.
2. [`supabase/migrations/0002_hash_chain.sql`](supabase/migrations/0002_hash_chain.sql) — `record_hash`/`chain_seq` for the hash-chained audit trail.

### Environment variables

See [`.env.example`](.env.example) for the full list — Supabase, Groq,
Gemini, and Razorpay Test Mode keys. All four are free tier, no credit card
required at signup.

## Current status

The full pipeline is built and verified end-to-end against real
infrastructure: generate → diagnose (Groq → Gemini → heuristic
degradation) → guardrail-check (12 rules) → execute (real Razorpay Test
Mode links for `smart_retry`/`generate_payment_link` — live and verified,
not a placeholder) → write a hash-chained decision → Supabase Realtime
pushes it to the live feed. Covered by 110 passing unit/integration tests,
including an adversarial guardrail test and a full hash-chain
tamper-detection test.

The evaluation harness, hash-chain verification, and the dashboard's
"vs. Baseline" panel (incremental-recovery comparison + audit-integrity
badge) are built and wired end-to-end.

**Still open:** deployment to Vercel/Render, and recording the 5-minute
pitch video — both need a live decision on hosting/voice rather than
further code changes.

## Known limitations

- Render's free tier cold-starts after ~15 minutes idle.
- All comms channels (WhatsApp/SMS/email) are simulated in-UI, clearly
  labeled as such — no paid delivery provider is wired up.
- Single-merchant demo: no auth/login system, no multi-tenancy.
- `POST /api/run-batch` runs synchronously with a small delay between LLM
  calls to stay inside Groq's free-tier rate limit, so larger batches take
  proportionally longer to return (the live feed still updates in real
  time throughout, independent of when the HTTP response completes).
- The evaluation harness's hash-chain and its `vasuli` arm both assume a
  single sequential writer/evaluator — documented as a deliberate scope cut
  in `docs/architecture.md`, not an oversight.
