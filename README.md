<div align="center">

# Vasuli — the AI agent that gets your money back

**वसूली** (Hindi/Hinglish for *"recovery"*) — an autonomous revenue recovery
agent for Razorpay merchants. It watches failed payments, abandoned
checkouts, failed subscription mandates, and overdue invoices, diagnoses
*why* each one is losing money, picks a bounded action, executes it under
guardrails it can't argue its way past, and reports exactly how much it
got back — and how much it honestly couldn't.

Built for **Razorpay's AI Buildathon, Track 03: AI Revenue Recovery.**

**[Live demo →](https://vasuli-ai.vercel.app)** · [Architecture deep-dive](docs/architecture.md) · [How it was built (blog)](BLOG.md) · [Quick setup](#get-it-running)

> The backend is on Render's free tier, which spins down after ~15
> minutes idle — the first request after a gap can take ~50s to wake up.
> If the dashboard looks empty at first, give it a moment and refresh.

![Vasuli landing page](docs/images/hero.jpg)

</div>

---

## What it actually does

One sentence a judge should walk away with: **the LLM never touches money
directly.** It only ever gets to *propose*. A separate, 100% deterministic
layer — 13 plain Python rules, zero AI — decides whether that proposal is
allowed to run, and a third layer is the only thing allowed to actually run
it. Every decision, blocked or executed, is written to a tamper-evident
audit trail.

```mermaid
flowchart LR
    A["Loss event\npayment_failed · checkout_abandoned\nsubscription_charge_failed · invoice_overdue"] --> B["Diagnosis Agent\nGroq → Gemini → heuristic"]
    B -- "proposes ONE action\nfrom a fixed menu" --> C{{"Guardrail Engine\n13 deterministic rules"}}
    C -- "blocked" --> D["Audit Trail\nreason logged"]
    C -- "cleared" --> E["Recovery Executor\nreal Razorpay Test Mode"]
    E --> D
    style C fill:#2563eb,color:#fff,stroke:#1e3a8a,stroke-width:2px
```

## See it working

| | |
|---|---|
| ![Live agent feed](docs/images/live-feed.jpg) **Live agent feed** — every decision streams in as it happens, badged by source (🤖 AI-proposed / ⚙️ guardrail-blocked / 📐 heuristic-fallback) | ![Full reasoning trace](docs/images/drill-down.jpg) **Full reasoning trace** — root cause, confidence, every guardrail check pass/fail, action, outcome |
| ![Counterfactual sandbox](docs/images/counterfactual.jpg) **Counterfactual sandbox** — pick a *different* action and watch the real guardrail engine judge it live (here: caught a repeat retry that would've violated the 30-minute rate limit) | ![vs. Baseline](docs/images/vs-baseline.jpg) **vs. Baseline** — the same batch run through 4 policies with common random numbers, headline number is *incremental* recovery, plus a live hash-chain integrity badge |
| ![Seed stability check](docs/images/stability-check.jpg) **Seed stability check** — the same comparison re-run across 20 seeds; rupee totals flagged noisy, rates and counts confirmed stable, computed and labeled automatically | ![LLM vs. heuristic agreement](docs/images/diagnosis-agreement.jpg) **LLM vs. heuristic agreement** — a real run: 7/15 evaluated (8 rate-limited), 42.9% action agreement, 100% root-cause agreement — shown honestly, not cherry-picked |

Full walkthrough with narration: **[BLOG.md](BLOG.md)**.

## Why this exists — the track's actual bar

Track 03 is explicit: *"don't just identify the problem — show measured
money recovered across a batch, with compliant escalation, stopping rules,
and an audit trail."* Every clause of that is a literal feature here, not a
slide:

| Bar requirement | How Vasuli satisfies it |
|---|---|
| Measured money recovered across a batch | KPI row computed live from the current batch — ₹ recovered, recovery rate, exposure |
| Baseline-compared, not just raw recovery | Evaluation harness: `do_nothing` / `fixed_dunning` / `vasuli` / `max_pressure`, common random numbers, **incremental** recovery is the headline |
| Compliant escalation | Opt-outs, contact-frequency caps, and named regulatory constraints (RBI contact hours, e-mandate notice, TRAI DLT templates) |
| Stopping rules | 13-rule guardrail engine, including an economic stopping rule that forces restraint when an action costs more than it could plausibly recover |
| Audit trail | Every decision hash-chained — tampering with any past record is provably detectable, not just logged |
| Honest exceptions | A dedicated "could not recover" list with reasons, never hidden |

## What makes this different from a typical hackathon agent

Nine things beyond the baseline, each a real feature, not a README claim:

- **Decision-source badges** — every single decision, everywhere it renders, is labeled 🤖 AI-proposed / ⚙️ guardrail-blocked / 📐 heuristic-fallback, so the "LLM never touches money" claim is visible by scrolling, not something you have to take on faith.
- **Live pause/resume kill switch** — a batch run can be paused *between* events mid-run, with a visible "Paused — N of M processed" state and nothing silently dropped.
- **Cash-flow framing** — recovered ₹ translated into "≈N days of reduced receivables outstanding" and "% of at-risk subscription MRR prevented from churning," the language a CFO actually uses.
- **Per-customer recovery journey** — click any customer and see their whole story as a timeline, not a flat table row.
- **Counterfactual override sandbox** — try a different action than the one the agent picked, live, against the real guardrail engine — screenshot above.
- **Fairness/consistency check** — a statistical check comparing action-assignment rates across language, channel, and tenure segments, reported honestly either way. None of the comparable projects in this track check for this at all.
- **Promise-to-pay guardrail** — a logged customer commitment defers B2B invoice escalation, but a *broken* promise explicitly re-allows it rather than pausing forever — asymmetric, not a blunt mute button.
- **Seed-stability check** — the vs. Baseline comparison re-run across 20 seeds, auto-flagging any metric whose seed-to-seed swing exceeds a stated threshold instead of presenting one point estimate as gospel.
- **LLM-vs-heuristic agreement** — a live, on-demand check of how often the real LLM's judgment matches the zero-AI fallback's, answering "how much would we actually lose if both providers went down" with data instead of a guess.

## Architecture

```mermaid
flowchart TB
    subgraph FE["Frontend — Next.js (Vercel)"]
        UI["Dashboard · Live Feed · Drill-down\nExceptions · vs. Baseline · Customer Timeline"]
    end
    subgraph BE["Backend — FastAPI (Render)"]
        GEN["Data Generator"] --> DIAG["Diagnosis Agent"]
        DIAG --> GUARD{{"Guardrail Engine\n13 rules"}}
        GUARD --> EXEC["Recovery Executors"]
        EXEC --> AUDIT["Audit Trail\nhash-chained"]
    end
    RZP[("Razorpay\nTest Mode")]
    DB[("Supabase\nPostgres")]
    UI <-- "REST + Realtime" --> BE
    EXEC <--> RZP
    AUDIT --> DB
    style GUARD fill:#2563eb,color:#fff,stroke:#1e3a8a,stroke-width:2px
```

Full request-flow walkthrough, sequence diagram, data model, and API
reference: **[docs/architecture.md](docs/architecture.md)**.

## The guardrail engine — 13 rules, zero LLM calls

Every rule runs on every proposed action — pass or fail, both get written
to the audit trail.

| Rule | Regulatory / policy basis |
|---|---|
| Max retry attempts | Card network rules cap retries on a declined instrument |
| Cool-down window | RBI fair-practice codes — no repeat contact within 4h |
| Daily contact cap | RBI fair-practice codes — max 2 touches/customer/24h |
| Opt-out enforcement | TRAI DND registry + the customer's own opt-out flag |
| Spend/amount cap | Invoices over ₹1,00,000 flagged for human review only |
| Promise-to-pay | A logged customer commitment defers escalation until the date passes — a broken promise then *allows* escalation, it never blocks forever |
| Retry rate limit | Prevents retry storms — see [the failure story](BLOG.md#the-2am-bug) |
| Reliability floor (B2B) | Chase tone tiered by historical payment reliability |
| Contact window | RBI recovery-agent guidelines — 08:00–19:00 IST only |
| E-mandate pre-debit notice | RBI e-mandate framework — no silent auto-debit retries |
| DLT template compliance | TRAI-mandated pre-registered SMS/WhatsApp templates only |
| Dispute freeze | Any disputed payment hard-stops all further action |
| Economic stopping rule | Forces restraint when expected recovery < 3× action cost |

Covered by [`test_guardrails.py`](backend/tests/test_guardrails.py) (every
rule, pass + block case) and an **adversarial test**
([`test_guardrails_adversarial.py`](backend/tests/test_guardrails_adversarial.py)):
a stub agent recommending the worst legal action for every case across 3
seeds — 240/240 blocked, zero disallowed actions ever reach the executor.

## Proof, not claims

- **Three-way LLM degradation** — Groq (primary) → Gemini (auto-fallback) → a zero-API-key deterministic heuristic agent if both fail. This has fired for real during development, not just in theory.
- **Incremental recovery, not raw** — ~15–20% of at-risk value in this dataset comes back with *zero* intervention; counting that as the agent's win is the easiest way for a recovery product to flatter itself. The evaluation harness nets it out. Reproduce: `python -m app.eval.run_comparison --cases 500 --seed 42`.
- **A seed-stability check on that number** — one seed's comparison could just be lucky. `GET /api/eval/stability` re-runs the full 4-arm comparison across 20 independent seeds and reports mean/std/coefficient-of-variation per metric, auto-flagging anything whose seed-to-seed swing exceeds 25% as noisy instead of presenting one point estimate with false precision. Visible live on the dashboard's vs. Baseline tab.
- **LLM-vs-heuristic agreement, not accuracy-against-a-label** — a naive "diagnosis accuracy" eval is meaningless here (the heuristic fallback deliberately just echoes the event's failure code, so it would trivially score 100%). Instead, `POST /api/eval/diagnosis-agreement` runs the *live* LLM against the same events the heuristic sees and reports how often their independent judgment actually agrees — answering "if both LLM providers went down right now, how much would really be lost?" Also live on the dashboard, button-triggered since it costs real API calls.
- **Hash-chained audit trail** — `python -m app.audit.verify` walks the chain and fails loudly at the first tampered record. Proven by a test that tampers with a row on purpose and confirms it's caught at the exact position.
- **A real 2am bug, found and fixed** — an early retry executor with no rate limit made recovery *worse*, not better, caught by the system's own audit trail. Full story: [BLOG.md](BLOG.md#the-2am-bug).

## Tech stack

100% free tier, no paid signups anywhere.

| Layer | Choice |
|---|---|
| Frontend | Next.js (App Router) + TypeScript, Tailwind, shadcn/ui |
| Backend | FastAPI (Python 3.11+) |
| LLM | Groq (primary) → Gemini (fallback) → deterministic heuristic (last resort) |
| Database | Supabase Postgres + Realtime |
| Payments | Razorpay Test Mode API — real payment links, zero cost |
| Hosting | Vercel (frontend), Render free tier (backend) |

## Get it running

```bash
# Backend
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example ../.env      # fill in Supabase / Groq / Gemini / Razorpay keys
python -m pytest -q             # 136 tests, all deterministic — no live keys needed
uvicorn app.api.main:app --reload
```

```bash
# Frontend, in a second terminal
cd frontend
npm install
cp ../.env.example .env.local   # fill in NEXT_PUBLIC_* Supabase + API base URL
npm run dev
```

**Database:** run the migrations in `supabase/migrations/` in order, against
a free Supabase project (SQL editor or `supabase db push`). See
[`.env.example`](.env.example) for the full environment variable list — all
four providers are free tier, no credit card required.

## Repo layout

```
vasuli-ai/
├── README.md
├── BLOG.md                  # how it was built, with screenshots
├── docs/
│   ├── architecture.md      # full system walkthrough, sequence diagram, API reference
│   └── images/               # screenshots used in this README + the blog
├── backend/app/
│   ├── data/                 # event schema + synthetic generator
│   ├── guardrails/            # deterministic rule engine — 13 rules
│   ├── agents/                 # diagnosis agent, heuristic fallback, Groq/Gemini client
│   ├── recovery/                # executors, outcome model, cost model, Razorpay client
│   ├── audit/                    # decision logger, hash chain, verify CLI, metrics
│   ├── eval/                      # baseline-comparison harness + fairness check
│   └── api/                        # FastAPI routes + batch pipeline
├── backend/tests/                  # 136 tests
├── supabase/migrations/            # SQL schema — events, decisions, hash chain, metrics views
└── frontend/                       # dashboard, live feed, drill-down, exceptions, vs. baseline
```

## Status & known limits

The full pipeline runs end-to-end against real infrastructure: generate →
diagnose (with three-way degradation) → guardrail-check (13 rules) →
execute (real Razorpay Test Mode links, not placeholders) → write a
hash-chained decision → push to the live feed over Supabase Realtime.
Covered by 136 passing tests including an adversarial guardrail test and a
full hash-chain tamper-detection test.

- Render's free tier cold-starts after ~15 minutes idle — hit `/health` a few minutes before judging.
- All comms channels (WhatsApp/SMS/email) are simulated in-UI, clearly labeled as such.
- Single-merchant demo: no auth/multi-tenancy.
- The hash chain and the evaluation harness both assume a single sequential writer — a stated scope cut, not an oversight (see `docs/architecture.md`).

## What to read next

- **[docs/architecture.md](docs/architecture.md)** — the full technical walkthrough: request flow, data model, API surface, sequence diagram.
- **[BLOG.md](BLOG.md)** — the build story, with screenshots and the honest failure-and-fix narrative.
