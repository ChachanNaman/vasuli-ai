  # Vasuli — AI Revenue Recovery Agent
### Product Requirements Document (PRD)
Razorpay AI Buildathon — Track 03: AI Revenue Recovery

Version 1.0 — prepared for build in VS Code / local dev

---

## 0. Project name

**Vasuli** (वसूली — Hindi/Hinglish for "recovery" or "collection of dues").

Tagline: **"Vasuli — the AI agent that gets your money back."**

Why this name: it's short, memorable, on-brand for an Indian fintech context, and it directly signals what the product does without needing explanation — which matters when a judge is skimming 200 project names. It also pairs naturally with the Hinglish recovery-message feature (a Vasuli-branded WhatsApp/SMS nudge reads as native, not translated).

If you'd rather not use a Hindi word, backup names considered: **Recoup**, **Rebound**, **Wapas AI**. Vasuli is the strongest of the four for memorability and track fit — go with it unless you have a strong preference otherwise.

Suggested repo name: `vasuli-ai` or `vasuli-recovery-agent`.

---

## 1. One-line pitch

Vasuli is an autonomous agent that watches a merchant's failed payments, abandoned checkouts, failed subscription mandates, and overdue B2B invoices, diagnoses *why* each one is losing money, picks a bounded and explainable recovery action per case, executes it under hard guardrails, and reports exactly how much money it got back — and how much it honestly could not.

---

## 2. Why this track, and why this project wins it

The buildathon brief scores every submission on four things, verbatim from the site: **problem taste** (did you pick something that actually matters), **build quality** (does it run, is it structured, would you trust it), **AI judgment** (the right tool in the right place, and where you chose *not* to use one), and **failure recovery** (what broke, and what you did about it).

Track 03's own bar is explicit: *"Don't just identify the problem. Show measured money recovered across a batch, with compliant escalation, stopping rules, and an audit trail."*

Vasuli is designed so every one of those bar items is a literal, demoable feature rather than a slide:

| Bar requirement | How Vasuli satisfies it |
|---|---|
| Measured money recovered across a batch | A metrics dashboard computed from an 80+ record synthetic batch, showing ₹ recovered, recovery rate by cause, and total exposure |
| Compliant escalation | Escalation path (retry → nudge → human handoff) respects opt-outs and never exceeds contact-frequency caps |
| Stopping rules | Deterministic guardrail engine that runs *before* every agent action — max retries, cool-down windows, spend caps |
| Audit trail | Every decision the agent makes is logged with cause, reasoning, guardrail checks passed, and outcome, and is browsable in the UI |
| Honest exceptions | A dedicated "could not recover" list with reasons, not hidden failures |
| AI judgment (where NOT to use AI) | Guardrails and stopping rules are plain deterministic code, not LLM calls — the LLM is used only for what actually needs judgment: diagnosis and message drafting |
| Failure recovery story | A deliberately engineered failure scenario (Section 11) with a real fix, documented for the application form |

This also happens to be the track least likely to be flooded with lookalike submissions — Track 01 (Agentic Commerce) is the headline everyone will pile onto. Track 03 maps directly onto what Razorpay's business actually is (failed payments, subscriptions, receivables are their bread and butter), which is a strong "problem taste" signal on its own.

---

## 3. Scope

### 3.1 In scope (MVP — this is what must work end-to-end for submission)

1. Synthetic dataset generator producing 80+ realistic loss events across four categories: payment failures, subscription/mandate failures, checkout abandonment, overdue B2B invoices.
2. Deterministic guardrail engine gating every agent action (retry caps, cool-downs, spend caps, opt-out enforcement).
3. LLM-powered diagnosis + intervention agent: classifies root cause per event, selects a bounded action from an allowed set, and produces an explainable reasoning trace.
4. Recovery execution simulators that produce realistic, probabilistic outcomes per intervention type (not hand-picked wins).
5. **Real Razorpay Test Mode integration** for the retry path: the agent actually generates a live (test-mode, zero-cost) Razorpay Payment Link via the Razorpay API for "smart retry" and "checkout recovery" interventions. This is the single highest-leverage authenticity feature in the whole build — it proves the agent isn't just narrating, it's touching real (sandboxed) payment infrastructure.
6. Audit trail store: every decision, with full reasoning and guardrail check results.
7. Dashboard UI: batch overview, live "agent working" feed, per-event drill-down, aggregate recovery metrics, and an honest exceptions list.
8. One engineered failure scenario with a documented fix (for the application's "what broke" field).
9. Public GitHub repo, README, architecture doc, 5-minute pitch video.

### 3.2 Explicitly out of scope (do not build, do not apologize for not building)

- Real WhatsApp/SMS/email delivery (Meta/Twilio/etc. require paid accounts or business verification) — these are **simulated** in-UI as "what would be sent," clearly labeled. This mirrors the brief's own language ("Razorpay test-mode APIs") — simulation of comms channels is expected, not a shortcut.
- Real bank-side payment processing beyond Razorpay's test mode (no real money ever moves).
- Multi-tenant merchant accounts, auth/login system, billing. This is a single-merchant demo.
- Mobile app. Web-responsive is enough.
- Fine-tuned/custom ML models. A well-prompted LLM with structured output plus a small deterministic scoring function is sufficient and is *more* defensible under "AI judgment" than an undertrained custom classifier.

---

## 4. Users and the judging journey

There is really one user (the merchant's finance/growth team, represented by the dashboard) and one critical journey (the judge's 15 minutes with the repo, video, and live app). Design every screen for the judge's path:

1. Land on the dashboard → immediately see the headline number: total ₹ at risk vs. ₹ recovered, with a batch just run.
2. Click "Run recovery batch" → watch the agent process the batch live (streamed decisions, not a spinner-then-done) — this is the single most important UX moment, it's the "prove it's real" moment.
3. Click into any individual event → see the full reasoning trace: what data it saw, what it concluded, which guardrails it checked, what it did, what happened.
4. View the exceptions tab → see the honest list of what could not be recovered and why.
5. Click a "smart retry" event → see (or click through to) an actual live Razorpay test-mode payment link that the agent generated.

If a judge can complete that path in under 5 minutes without you narrating, the UI has done its job.

---

## 5. System architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Frontend (Next.js)                       │
│  Dashboard · Live Agent Feed · Event Drill-down · Exceptions Tab │
│  hosted free on Vercel                                           │
└───────────────┬───────────────────────────────▲──────────────────┘
                │ REST (batch trigger, queries)  │ Supabase Realtime
                ▼                                │ (live decision stream)
┌─────────────────────────────────────────────────────────────────┐
│                    Backend (Python, FastAPI)                     │
│                                                                    │
│  ┌───────────────┐  ┌──────────────────┐  ┌────────────────────┐ │
│  │ Data Generator │→ │ Guardrail Engine  │→ │ Diagnosis + Action │ │
│  │ (synthetic     │  │ (deterministic,   │  │ Agent (LLM tool-   │ │
│  │  events)       │  │  pre-LLM gate)    │  │  calling, Groq/    │ │
│  └───────────────┘  └──────────────────┘  │  Gemini)            │ │
│                                             └─────────┬──────────┘ │
│                                                        ▼            │
│  ┌──────────────────────┐   ┌───────────────────────────────────┐ │
│  │ Recovery Executors     │←→│ Razorpay Test Mode API (real,     │ │
│  │ (retry sim, nudge sim, │   │ zero-cost payment links)         │ │
│  │ chase sim, mandate     │   └───────────────────────────────────┘ │
│  │ re-auth sim)           │                                         │
│  └───────────┬────────────┘                                         │
│              ▼                                                      │
│  ┌────────────────────────┐                                         │
│  │ Audit Trail + Metrics   │──────────► Supabase Postgres            │
│  │ Logger                  │           (events, decisions, outcomes) │
│  └────────────────────────┘                                         │
│  hosted free on Render (Web Service, free tier)                     │
└───────────────────────────────────────────────────────────────────┘
```

Design principle worth stating explicitly in the README (judges will look for exactly this): **the LLM never touches money directly.** It proposes a diagnosis and an action; the guardrail engine and the executor layer are the only things allowed to actually do something, and both are deterministic code the LLM cannot argue its way past. That separation is the whole "AI judgment" answer.

---

## 6. Data model

### 6.1 Event schema (four event types, one shared envelope)

Shared fields: `event_id`, `event_type`, `timestamp`, `merchant_id`, `amount`, `currency`, `customer` (id, name, past successful/failed payment counts, tenure, opt-out flag, preferred channel, language preference).

Type-specific fields:

- **payment_failed** — `failure_reason_code` (insufficient_funds, bank_server_down, otp_mismatch, otp_timeout, card_expired, network_error, risk_declined, daily_limit_exceeded), `payment_method`, `bank_name`, `attempt_number`.
- **subscription_charge_failed** — all payment_failed fields plus `subscription_id`, `mandate_id`, `mandate_status` (active/expired/revoked), `plan_name`, `billing_cycle`.
- **checkout_abandoned** — `cart_value`, `items_count`, `checkout_stage_reached` (cart/address/payment_method_select/otp_pending), `minutes_since_abandon`, `device`.
- **invoice_overdue** — `invoice_id`, `days_overdue`, `business_customer_name`, `payment_reliability_score` (0–1, historical).

This schema is already implemented and the generator already produces realistic, non-uniform distributions (e.g. insufficient funds and bank timeouts dominate over hard declines, mirroring real UPI/card decline patterns in India). Bring the existing `schema.py` and `generator.py` into the VS Code project as-is — they don't need rework, just porting.

### 6.2 Decision / audit record

```
decision_id, event_id, timestamp,
diagnosis: { root_cause, confidence, reasoning_text },
guardrail_checks: [ { rule_name, passed: bool, detail } ],
action_taken: { type, params },
action_status: "executed" | "blocked_by_guardrail" | "skipped_opt_out",
outcome: { recovered: bool, amount_recovered, notes },
razorpay_payment_link: string | null
```

### 6.3 Aggregate metrics (computed, not stored redundantly)

Total exposure (₹), total recovered (₹), recovery rate overall and by root cause, guardrail-block count, opt-out-respected count, average time-to-recovery, exception count with reasons.

---

## 7. Guardrail engine (deterministic — no LLM involved)

This runs **before** any action is allowed to execute, regardless of what the agent recommends.

| Rule | Logic |
|---|---|
| Max retry attempts | Block retry if `attempt_number >= 3` for payments, `>= 4` for subscriptions — route to human/manual queue instead |
| Cool-down window | No repeat contact to the same customer within 4 hours of the last attempt |
| Daily contact cap | Max 2 recovery touches per customer per 24h across all channels |
| Opt-out enforcement | If `customer.opted_out_of_recovery_comms == true`, no comms action is permitted — silently route to "excluded" bucket |
| Spend/amount cap for auto-action | Invoices over ₹1,00,000 cannot be auto-escalated; they're flagged for human review only (this is the "compliant escalation" the bar asks for) |
| Rate limiting for retries | No more than 1 retry attempt per payment per 30 minutes (prevents the retry-storm failure mode — see Section 11) |
| Reliability floor for B2B chase tone | `payment_reliability_score < 0.3` routes to a firmer escalation tier; `>= 0.7` gets a soft reminder only |

Every rule check — pass or fail — is written to the audit trail whether or not it blocked anything. This is what makes the audit trail actually meaningful instead of just a log of successes.

---

## 8. The diagnosis + intervention agent

### 8.1 What the LLM is actually for

The LLM's job is narrow and well-defined: given one event's full context, (a) confirm/refine the root cause (the generator already tags a ground-truth reason, but the agent should reason over the raw signals, not just echo the label — use `failure_reason_code` as one signal among several, not a given), (b) pick one action from a fixed, allow-listed action set (never a freeform action), and (c) draft the actual recovery message text if the chosen action involves customer contact. It does **not** decide whether an action is allowed to execute — that's the guardrail engine's job, applied after the LLM proposes.

### 8.2 Allowed action set (the only actions the agent may ever choose)

`smart_retry` (schedule a payment retry at a model-recommended time window), `generate_payment_link` (real Razorpay test-mode link for the customer to complete manually), `send_nudge` (simulated WhatsApp/SMS/email in customer's preferred language/channel), `escalate_b2b_chase` (structured reminder sequence for overdue invoices, tiered by reliability score), `initiate_mandate_reauth` (for expired/revoked mandates), `flag_for_human_review` (the honest "I can't safely automate this" outcome), `no_action_recommended` (for cases where intervention would likely backfire — e.g. contacting someone mid-genuine-fraud-review).

### 8.3 Structured output contract

Use tool-calling / function-calling (both Groq and Gemini support this) so the model returns a strict JSON object matching a schema, not free text — this is what makes the reasoning auditable and the pipeline reliable. Example shape:

```json
{
  "root_cause": "bank_server_down",
  "confidence": 0.82,
  "reasoning": "Two-sentence plain-language explanation",
  "recommended_action": "smart_retry",
  "action_params": { "retry_window_minutes": 45 },
  "customer_message": "Hinglish or English message text, or null if action has no message"
}
```

### 8.4 Prompt design notes

Give the model the full event context, the customer's history, and — critically — the *allowed action list with one-line descriptions of when each is appropriate*, so it's choosing from a menu rather than inventing behavior. Explicitly instruct it to prefer `flag_for_human_review` or `no_action_recommended` over guessing when confidence is low; a system that recommends "no action" when it doesn't know is more trustworthy than one that always confidently retries, and this restraint is a direct, gradeable answer to "AI judgment... and where you chose not to use one."

---

## 9. Recovery execution layer

Each action type has a simulated (or, for retries, real) execution step that produces a probabilistic outcome — not a hard-coded win, since "one cherry-picked match proves nothing" per the brief.

| Action | Execution | Outcome model |
|---|---|---|
| `smart_retry` | Real Razorpay test-mode payment link generated via API | Recovery probability weighted by root cause (e.g. insufficient_funds retried next day ≈ 55%, bank_server_down retried in 45 min ≈ 70%, card_expired retry ≈ 5% — should basically always fail retry and instead need `generate_payment_link` with a new method, which is itself a good "AI judgment" branch to show) |
| `send_nudge` | Simulated, UI shows the exact message that would go out | Recovery probability weighted by channel (WhatsApp > SMS > email), language match, and days-since-abandon decay |
| `escalate_b2b_chase` | Simulated multi-touch sequence with promise-to-pay tracking | Probability weighted by `payment_reliability_score` and `days_overdue` |
| `initiate_mandate_reauth` | Simulated re-authorization link | Lower baseline probability, reflects real-world mandate churn |
| `flag_for_human_review` / `no_action_recommended` | No execution | Counted honestly as "not recovered by the agent," shown in the exceptions tab, not swept under the rug |

Keep the probability model in one clearly-commented module (`recovery/outcome_model.py`) so you can show judges the exact assumptions rather than a black box — this is a place where being transparent about "this is a simulation, here's the model" scores better than pretending it's real.

---

## 10. Tech stack — 100% free tier, no paid signups required anywhere

| Layer | Choice | Why / free-tier notes |
|---|---|---|
| Frontend framework | **Next.js 14 (App Router) + TypeScript** | Industry standard, free, huge ecosystem, deploys natively to Vercel |
| Styling | **Tailwind CSS** | Free, fast to build a polished look |
| UI components | **shadcn/ui** | Free, open-source, copy-paste components (tables, tabs, dialogs, badges) — not a locked-in dependency |
| Dashboard/metrics components | **Tremor (tremor.so)** | Free, open-source, purpose-built for exactly this "KPI cards + area charts + metrics dashboard" use case — this will save you huge amounts of design time and looks professional out of the box |
| Landing/hero flourish | **Aceternity UI** or **Magic UI** (both free, copy-paste, Tailwind + Framer Motion based) | Use sparingly for the hero/landing section only — animated gradient backgrounds, spotlight cards — this is what makes the first 5 seconds look expensive |
| Animation | **Framer Motion** | Free, pairs with the above |
| Charts (if you outgrow Tremor's built-ins) | **Recharts** | Free, what Tremor is built on anyway |
| State/data fetching | **TanStack Query (React Query)** | Free |
| Backend framework | **FastAPI (Python 3.11+)** | Free, async, great fit for the agent pipeline, auto-generates OpenAPI docs (nice to show judges) |
| LLM — primary | **Groq API** (Llama 3.3 70B or similar, function-calling) | Free tier, no credit card required at signup, extremely fast inference (good for the "live agent feed" demo effect) |
| LLM — fallback | **Google Gemini API (Gemini 2.x Flash)** via Google AI Studio | Free tier, no credit card required, also supports function-calling |
| Why two LLMs | Wire a genuine fallback: if Groq rate-limits or errors, fall back to Gemini automatically, log the fallback event | This is a built-in, real resilience feature — and doubles as a legitimate answer to the "what broke and how you fixed it" field if you don't want to engineer a separate incident |
| Database | **Supabase (Postgres, free tier)** | Free, no card required, 500MB is far more than enough, and gives you Realtime out of the box |
| Real-time updates | **Supabase Realtime** (Postgres change subscriptions) | Free, avoids having to run and scale your own WebSocket server — the frontend just subscribes to the `decisions` table and gets the live agent feed for free |
| Payments (the one live integration) | **Razorpay Test Mode API** (Node or Python SDK) | Free — test mode requires only a free Razorpay account, no business verification, no real money ever moves, generates real payment link objects |
| Backend hosting | **Render (free Web Service tier)** | Free; note it cold-starts after ~15 min idle — mention this in your README as a known limitation, or ping it right before your demo/judging slot |
| Frontend hosting | **Vercel (Hobby/free tier)** | Free, effectively instant deploys from GitHub |
| Voice (optional wow-factor) | **Web Speech API** (browser-native `speechSynthesis`) | Zero cost, zero signup, client-side only — use it to actually *read aloud* a generated Hinglish recovery message in the demo video, ties directly to the brief's "Hinglish voice recovery" example direction without needing any paid TTS |
| Error tracking (optional, adds polish) | **Sentry (free developer tier)** | Free tier is enough for a hackathon project, shows operational maturity if a judge digs into your repo |
| Background scheduling (optional stretch) | **APScheduler** (in-process, Python) | Free, no external queue infra needed, sufficient to simulate "the agent runs every N minutes" without standing up Redis/Celery |

Nothing above requires a credit card at signup. If any provider changes its free-tier policy between now and build time, the fallback is always "simulate that layer" — the architecture is designed so every external dependency is swappable behind a clean interface for exactly this reason.

---

## 11. The failure story (for the application's "what broke" field)

Don't leave this to chance — engineer it on purpose, then document it honestly. Recommended scenario, already anticipated by the guardrail rule in Section 7:

**What broke:** An early version of the retry executor had no rate limit — a customer whose `insufficient_funds` payment failed would get retried on every batch run, including runs seconds apart during testing. Real payment networks (and Razorpay's own docs) treat rapid repeat retries as suspicious and soft-decline them, which meant the *retry itself* was making recovery worse, not better — a retry storm.

**How it was found:** the audit trail's `guardrail_checks` log showed `passed: true` on every attempt with no rate-limit rule to catch it, and the outcome log showed a recovering payment flipping to a *new* decline reason (`risk_declined`) after multiple rapid retries against the same customer.

**The fix:** added the 30-minute per-payment retry rate limit and the 4-hour cross-channel cool-down (Section 7), moved retry timing to be root-cause-aware (immediate retry only for `network_error`/`bank_server_down`; next-day retry for `insufficient_funds`), and added an explicit guardrail-block reason (`rate_limited`) to the audit trail so this class of failure is visible rather than silent.

This is a genuinely good failure story because it's true-to-domain (retry storms are a real, well-known payments failure mode), it's caught *by the system's own audit trail* (which is a nice self-referential proof that the audit trail works), and the fix is a guardrail, not a prompt tweak — showing the guardrail layer, not the LLM, is what you trust for correctness.

---

## 12. UI/UX specification

### 12.1 Design direction

Dark, high-contrast fintech dashboard aesthetic — think Stripe Dashboard / Linear / Vercel, not a generic admin template. Deep charcoal/near-black background, one confident accent color (recommend a warm amber/gold — it nods to the "money recovered" theme without being the expected green-for-money cliché, and it's distinctive against the sea of blue/purple SaaS dashboards judges will see all day), generous whitespace, monospace font for numbers/IDs (reinforces "this is real infrastructure, not a mockup").

### 12.2 Reference templates to pull from

You asked where to find a template to hand me — here's where to look, in priority order:

1. **Tremor Blocks** (`tremor.so/blocks`) — free, prebuilt dashboard sections (KPI rows, area charts, tables) built exactly for this financial-metrics use case. Start here for the main dashboard.
2. **shadcn/ui examples** (`ui.shadcn.com/examples/dashboard`) — free, the canonical modern dashboard reference layout (sidebar + top bar + content grid). Use this for overall page structure.
3. **Aceternity UI** (`ui.aceternity.com`) — free, copy-paste animated components (spotlight, glowing borders, bento grids). Use *only* for the landing/hero section and maybe the live-agent-feed panel, where a bit of motion sells "this is alive."
4. **Magic UI** (`magicui.design`) — free, similar to Aceternity, has a nice animated list component that's a near-perfect fit for the "live agent decision feed."

Pick components from these, screenshot or link the specific ones you like, and I'll adapt them into the actual pages when we're in VS Code together.

### 12.3 Pages/screens

1. **Landing / hero** — one screen, the pitch in one sentence, a "Run live batch" CTA. This is what plays first in your video.
2. **Dashboard (main)** — KPI row (Total at risk, Total recovered, Recovery rate, Guardrail blocks) using Tremor cards; a recovery-by-cause bar chart; a recovery-over-time area chart.
3. **Live agent feed** — a scrolling, animated list (Magic UI's animated list is ideal) showing each decision as it's made in real time via Supabase Realtime: event → diagnosis → guardrail check → action → outcome, appearing one at a time like a real operations feed.
4. **Event drill-down** (modal or side panel) — full reasoning trace for one event: raw event data, the LLM's diagnosis and confidence, every guardrail check with pass/fail, the action taken, the outcome, and — for `generate_payment_link` actions — a real clickable Razorpay test-mode link.
5. **Exceptions tab** — the honest list: everything flagged for human review or explicitly not actioned, with reasons, styled distinctly (not hidden in shame, presented as a feature).
6. **Architecture/"How it works" tab** — a simple diagram (can literally be the Section 5 diagram, styled) plus the guardrail rule table, so a judge who wants to verify rigor doesn't have to leave the app to read your README.

### 12.4 Non-negotiable UI details that read as "trustworthy" to a judge

Every ₹ amount formatted properly (₹1,24,500 not $124500 — this is an Indian merchant); every timestamp relative *and* absolute on hover; every simulated action explicitly labeled "Simulated — test mode" or "Live — Razorpay test mode" so nothing is ambiguous about what's real; loading and empty states designed, not left default; the live feed should visibly slow down for guardrail-blocked actions (a beat of red/amber) so blocking reads as a deliberate safety feature, not a bug.

---

## 13. Project structure (monorepo)

```
vasuli-ai/
├── PRD.md
├── README.md
├── .gitignore
├── .env.example
├── backend/
│   ├── app/
│   │   ├── data/           # schema.py, generator.py, events.json
│   │   ├── guardrails/     # rules.py — deterministic checks
│   │   ├── agents/         # diagnosis_agent.py, prompts.py, llm_client.py (Groq + Gemini fallback)
│   │   ├── recovery/       # executors.py, outcome_model.py, razorpay_client.py
│   │   ├── audit/          # logger.py, metrics.py
│   │   └── api/            # FastAPI routes
│   ├── tests/
│   └── requirements.txt
├── frontend/
│   ├── app/                # Next.js App Router pages
│   ├── components/         # shadcn + Tremor + custom components
│   ├── lib/                # supabase client, api client
│   └── package.json
└── docs/
    ├── architecture.md
    └── demo-script.md
```

---

## 14. Timeline (today: Aug 20 → application deadline: Sept 5)

| Days | Focus |
|---|---|
| Day 1–2 | Port existing data schema/generator into the VS Code project; set up Supabase project and schema; scaffold FastAPI + Next.js skeletons |
| Day 3–4 | Build guardrail engine fully, with tests; build audit logging |
| Day 5–7 | Build the LLM diagnosis agent (Groq primary, Gemini fallback), structured output, prompt iteration |
| Day 8–9 | Build recovery executors + outcome model; wire real Razorpay test-mode payment link generation |
| Day 10–12 | Build the full frontend: dashboard, live feed (Supabase Realtime), drill-down, exceptions tab |
| Day 13 | Deliberately trigger and fix the retry-storm failure scenario; capture it for the write-up |
| Day 14 | Deploy (Vercel + Render), polish UI pass, write README/architecture doc |
| Day 15 (buffer) | Record the 5-minute pitch video, final QA pass, submit |

---

## 15. Submission checklist (mapped to the form's 12 fields)

About you: full name, college, graduation year, in-person availability from September, 6 or 12 month preference, resume file — these are yours to fill in directly.

About the build: track = **AI Revenue Recovery**; project name = **Vasuli**; what it solves = one paragraph pulled straight from Section 1–2 of this PRD; GitHub repo URL (public); 5-minute pitch video (unlisted is fine) following the journey in Section 4; "what broke and how you got out" = Section 11, verbatim or lightly edited.

---

## 16. Git and attribution policy

**Do not list Claude, Anthropic, or any AI tool as a contributor, co-author, or credited party anywhere in this repository.** Specifically:

- Do not add `Co-Authored-By: Claude` (or similar) trailers to any commit message.
- Do not add an AI attribution footer, badge, or acknowledgment section to the README.
- Configure git locally with only your own name and email (`git config user.name` / `user.email`) before making any commits.
- Do not include any generated-with-AI metadata in `package.json`, `pyproject.toml`, or elsewhere.
- Commit messages should read as your own work in your own voice.

This is a firm instruction for however you or any tooling assist in writing code for this repo going forward — the repository history and README should show only you (and any real teammates) as contributors.

---

## 17. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Render free tier cold-starts right when a judge clicks the live link | Ping the backend a few minutes before any judging/demo window; mention the limitation proactively in the README rather than hoping no one notices |
| Groq/Gemini free-tier rate limits hit during a live demo | The Groq→Gemini fallback (Section 10) covers this; also pre-run and cache a "known good" batch result as a fallback dataset if live LLM calls fail entirely during judging |
| Razorpay test-mode account setup friction | Test mode signup is free and takes minutes with no business verification; do this on Day 1, not Day 8 |
| Scope creep across all 7 example directions in the brief | Section 3 deliberately narrows to 4 of the 7 directions built deeply, rather than 7 built shallowly — resist the urge to add more during the build |
| UI looking like "a hackathon project" rather than a product | Section 12's template references exist specifically to avoid this — don't freehand the design, start from Tremor/shadcn blocks and customize |

---

*End of PRD. Bring this file and the `backend/app/data/schema.py` + `generator.py` already generated in this session into your VS Code project as the starting point — everything else in the plan above builds outward from that data model.*
