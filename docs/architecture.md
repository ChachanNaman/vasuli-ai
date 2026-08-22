# Vasuli — Architecture

## System diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         Frontend (Next.js)                       │
│  Dashboard · Live Agent Feed · Event Drill-down · Exceptions ·  │
│  vs. Baseline (incremental recovery + audit-integrity badge)    │
│  hosted on Vercel                                                 │
└───────────────┬───────────────────────────────▲──────────────────┘
                │ REST (batch trigger, queries)  │ Supabase Realtime
                ▼                                │ (live decision stream)
┌─────────────────────────────────────────────────────────────────┐
│                    Backend (Python, FastAPI)                     │
│                                                                    │
│  ┌───────────────┐  ┌──────────────────────┐  ┌────────────────┐ │
│  │ Data Generator │→ │ Diagnosis Agent       │→ │ Guardrail       │ │
│  │ (synthetic     │  │ Groq → Gemini →       │  │ Engine          │ │
│  │  events)       │  │ heuristic (§2.5)      │  │ (12 rules,      │ │
│  └───────────────┘  └──────────────────────┘  │  §2.2/§2.3)     │ │
│                                                 └────────┬────────┘ │
│                                                          ▼          │
│  ┌──────────────────────┐   ┌───────────────────────────────────┐ │
│  │ Recovery Executors     │←→│ Razorpay Test Mode API (real,     │ │
│  │ (retry, payment link,  │   │ zero-cost payment links)         │ │
│  │ nudge, B2B chase,      │   └───────────────────────────────────┘ │
│  │ mandate re-auth sims)  │                                         │
│  └───────────┬────────────┘                                         │
│              ▼                                                      │
│  ┌────────────────────────┐                                         │
│  │ Audit Trail (hash-       │──────────► Supabase Postgres            │
│  │ chained, §2.4) + Metrics │           (events, decisions, views)    │
│  └────────────────────────┘                                         │
│                                                                       │
│  ┌────────────────────────────────────────────────────────────┐    │
│  │ Evaluation harness (app/eval/, §2.1) — do_nothing /          │    │
│  │ fixed_dunning / vasuli / max_pressure, common random numbers  │    │
│  └────────────────────────────────────────────────────────────┘    │
│  hosted on Render (Web Service, free tier)                          │
└───────────────────────────────────────────────────────────────────┘
```

**The one rule the whole system is built around: the LLM never touches
money directly.** The diagnosis layer produces a proposed root cause and
action; `guardrails/rules.py` — plain deterministic Python, no LLM call —
is the only thing that decides whether that action is allowed to run, and
`recovery/executors.py` is the only thing allowed to actually run it. The
LLM cannot argue its way past either layer.

## Request flow (one event, end to end)

1. **Generate** — `data/generator.py` produces a `RevenueEvent` (one of
   `payment_failed`, `subscription_charge_failed`, `checkout_abandoned`,
   `invoice_overdue`), each carrying a shared envelope plus type-specific
   fields (`data/schema.py`), including a `dispute_opened` flag (a small
   fixed rate — see the dispute-freeze rule below).
2. **Diagnose** — `agents/diagnosis_agent.py` sends the event's full
   context, customer history, and the fixed allow-listed action menu to
   Groq (primary) via tool-calling, returning a strict JSON diagnosis:
   `root_cause`, `confidence`, `reasoning`, `recommended_action`,
   `action_params`, `customer_message`. On a Groq error or rate limit, the
   client retries against Gemini (`agents/llm_client.py`) and logs the
   fallback event. **If both LLM providers fail**, the pipeline degrades to
   `agents/heuristic_agent.py` — a small, explicit, zero-API-key rule-based
   diagnosis function over the same signals, choosing from the same
   allowed action set. This is a real fallback, not a theoretical one: it
   has fired in development when Groq emitted malformed tool-call JSON and
   Gemini's free-tier daily quota was simultaneously exhausted.
3. **Guardrail-check** — `guardrails/rules.py` runs all 12 rules against
   the proposed action, regardless of what the diagnosis layer recommended.
   Every rule's pass/fail result is recorded, not just the ones that
   blocked something.
4. **Execute (if cleared)** — `recovery/executors.py` runs the actual
   action. `smart_retry` and `generate_payment_link` call
   `recovery/razorpay_client.py`, which creates a real Razorpay Test Mode
   payment link (live and verified — not a placeholder); comms actions
   (`send_nudge`, `escalate_b2b_chase`, `initiate_mandate_reauth`) format
   their outgoing message from a small fixed DLT-registered template set,
   not the LLM's freeform draft; every action produces a probabilistic
   outcome from `recovery/outcome_model.py` (never a hard-coded win).
5. **Write the audit record** — `audit/logger.py` writes one row to the
   `decisions` table per event, then chains it: `audit/hash_chain.py`
   computes `record_hash = sha256(previous_hash + canonical_json(row))`
   from the row exactly as Postgres hands it back (see "Hash-chained audit
   trail" below for why this two-phase write matters), and writes the hash
   back. Supabase Realtime pushes the insert to any subscribed client —
   this is what drives the live agent feed with zero polling.
6. **Aggregate** — `audit/metrics.py` reads three Postgres views
   (`metrics_overview`, `metrics_by_root_cause`, `metrics_exceptions`),
   computed on read from `decisions`, never stored redundantly.

## Guardrail rules — 12 total, named regulations where they apply

| Rule | Regulatory / policy basis | Logic |
|---|---|---|
| Max retry attempts | Card network rules cap retry attempts on a declined instrument | Block retry if `attempt_number >= 3` for payments, `>= 4` for subscriptions |
| Cool-down window | RBI fair-practice codes | No repeat contact within 4 hours of the last attempt |
| Daily contact cap | RBI fair-practice codes | Max 2 recovery touches per customer per 24h across all channels |
| Opt-out enforcement | TRAI DND registry + customer's own opt-out flag | No comms action if the customer opted out |
| Spend/amount cap | Internal policy | Invoices over ₹1,00,000 flagged for human review only |
| Retry rate limit | Card network rules (timing dimension) | No more than 1 retry per payment per 30 minutes — prevents retry storms |
| Reliability floor (B2B) | Internal policy | `payment_reliability_score < 0.3` → firmer tier, `>= 0.7` → soft reminder |
| Contact window | RBI recovery-agent guidelines: contact roughly 08:00–19:00 IST | No customer-facing action outside this window |
| E-mandate pre-debit notice | RBI's e-mandate/recurring-payment framework | A retry/re-auth against an active mandate requires a confirmed notice period (`action_params.pre_debit_notice_hours >= 24`), never fires silently |
| DLT template compliance | TRAI mandates pre-registered SMS/WhatsApp content | Comms actions draw from a fixed template set (`guardrails/rules.py::DLT_APPROVED_TEMPLATES`), enforced at the executor layer |
| Dispute freeze | Standard chargeback-handling practice | `event.dispute_opened == true` hard-stops all action on that case |
| Economic stopping rule | Cost figures stated in `recovery/cost_model.py` | Forces `no_action_recommended` when expected recovery < 3x the action's (cost + nuisance-cost) |

We deliberately do not cite a specific rupee threshold or notice-period
figure for the e-mandate rule — that figure has changed in 2026 rule
updates and hasn't been independently re-verified here; the code states the
*existence* of the requirement and uses its own conservative operating
minimum (24h), not a claimed regulatory number.

Covered by `backend/tests/test_guardrails.py` (every rule, pass + block
case) and `backend/tests/test_guardrails_adversarial.py` — a stub agent
recommending the single worst legal action for every case across 3 seeds
(240 cases total); 100% blocked, zero disallowed actions reach the executor.

## Allowed action set

The diagnosis layer (LLM or heuristic) chooses exactly one of these per
event — never a freeform action: `smart_retry`, `generate_payment_link`,
`send_nudge`, `escalate_b2b_chase`, `initiate_mandate_reauth`,
`flag_for_human_review`, `no_action_recommended`.

## Hash-chained audit trail

Each `decisions` row carries `record_hash` and `chain_seq`
(`supabase/migrations/0002_hash_chain.sql`). `record_hash` is
`sha256(previous_row_hash + canonical_json(this_row))`, where
`canonical_json` (`audit/hash_chain.py`) excludes the chain bookkeeping
fields themselves and sorts keys for deterministic serialization.
`GENESIS_HASH` is a fixed constant for the first row in the chain.

**Why the write is two-phase** (insert, then hash-and-update, rather than
computing the hash before inserting): Postgres reformats values on the way
in — numeric precision, timestamptz string format, JSONB key ordering. If
the hash were computed from the pre-insert Python dict, a later
verification pass recomputing it from the *post-insert* representation
would never match, even with nothing tampered. Hashing the row exactly as
the database hands it back — both at write time and at verify time —
means the two are always working from the same representation.

`python -m app.audit.verify` walks the chain in `chain_seq` order and
recomputes each hash, printing `✅ N records verified, chain intact` or
failing loudly with the first broken position. Covered by
`test_hash_chain.py` (pure-function tests) and `test_pipeline_integration.py`
(a batch run's chain verifies clean; mutating a row afterward is correctly
caught at that exact position). The dashboard's **vs. Baseline** tab
surfaces this via `GET /api/audit/verify`.

Known scope limitation, stated plainly: this assumes a single sequential
writer, true today (the batch pipeline writes one decision at a time). A
concurrent writer would need a DB-side trigger or transaction to keep the
chain atomic — out of scope for this build.

## Evaluation harness — incremental recovery, not raw

`backend/app/eval/` (`policies.py`, `run_comparison.py`) runs the same
batch of synthetic cases through four policies:

- **`do_nothing`** — never intervenes. Still has a chance to recover: some
  fraction of at-risk value resolves organically (`outcome_model.
  natural_recovery_probability`), and every other arm's raw recovery number
  already includes this for free.
- **`fixed_dunning`** — the same fixed action for every event of a given
  type (always `smart_retry` for payment/subscription events, etc.),
  regardless of cause, attempt history, or guardrails.
- **`vasuli`** — the heuristic diagnosis agent + the real guardrail engine
  + the real outcome model. Uses the heuristic, not the live LLM, so the
  comparison is fast, deterministic, and reproducible, and so the LLM's own
  action-choice stochasticity doesn't confound the comparison.
- **`max_pressure`** — the most aggressive action available, guardrails
  ignored entirely.

**Common random numbers**: each case gets one seed
(`policies.py::_case_seed`, derived from a master seed + the case's
`event_id`) used identically across all four arms immediately before that
arm's one outcome draw, so a case that "gets lucky" gets lucky in every
arm — differences between arms are attributable to policy, not noise.

**Deferred-to-organic correctness**: whenever an arm takes no real action
(blocked by a guardrail, or the diagnosis itself is
`flag_for_human_review`/`no_action_recommended`), that case defers to the
*same* organic-recovery draw `do_nothing` uses for that case, rather than a
hard zero. This was a real bug caught while building the harness: scoring
"no action taken" as a hard zero made Vasuli's own restraint look like a
loss relative to `do_nothing`, producing a nonsensical negative incremental
number. Fixed and covered by a regression test
(`test_eval_harness.py::test_incremental_recovery_never_negative_for_any_arm`).

**Headline metric**: incremental recovery
(`recovered_under_policy - recovered_under_do_nothing`), not raw recovery —
see the README for the actual 500-case output and its interpretation.
Reported alongside it: cost per ₹ recovered and contacts per case
(`recovery/cost_model.py`'s stated, illustrative cost figures).

Simplifying assumption, stated explicitly: each case is evaluated
independently, no cross-case history. Guardrail rules that depend on
history (cool-down, daily cap, retry-rate-limit) therefore see an empty
history for every case — this is why `fixed_dunning` and `max_pressure`
land on identical figures in this harness (see the README for the full
reasoning); a real sequential simulation would very likely diverge them.

`now` is fixed to a single daytime instant for every case in every arm, so
the contact-window rule doesn't introduce arbitrary noise unrelated to the
policy being compared.

Reachable via `GET /api/eval/comparison?cases=500&seed=42` or
`python -m app.eval.run_comparison --cases 500 --seed 42`.

## Data model

- **`events`** — one row per synthetic loss event. Shared envelope columns
  (`event_id`, `event_type`, `timestamp`, `merchant_id`, `amount`,
  `currency`, `customer_id`) plus `customer` and `payload` JSONB columns
  holding the full type-specific context, so the schema doesn't need a
  migration every time the generator's field set changes.
- **`decisions`** — one row per (event, batch-run) decision: diagnosis,
  `guardrail_checks` (JSONB array, every rule's pass/fail), action taken,
  outcome, `razorpay_payment_link` / `is_live_integration`, and
  `record_hash` / `chain_seq` (hash-chain bookkeeping, §2.4).
- **`metrics_overview` / `metrics_by_root_cause` / `metrics_exceptions`** —
  read-only SQL views over `decisions`, joined to `events` where needed.
  Nothing is denormalized or cached — every dashboard number is a live
  aggregate.

Full schema: [`supabase/migrations/0001_init.sql`](../supabase/migrations/0001_init.sql)
and [`0002_hash_chain.sql`](../supabase/migrations/0002_hash_chain.sql).

## API surface (FastAPI, `backend/app/api/main.py`)

| Route | Purpose |
|---|---|
| `GET /health` | Liveness check (also useful to pre-warm Render's free-tier cold start before a demo) |
| `POST /api/run-batch` | Generates `n` events and runs the full pipeline synchronously, writing each decision as it completes — the live feed sees these arrive one at a time via Realtime while the request is still in flight |
| `GET /api/events` | Raw event rows, most recent first |
| `GET /api/decisions` | Decision/audit rows, most recent first |
| `GET /api/decisions/{event_id}` | Full decision record for one event — backs the drill-down panel |
| `GET /api/metrics` | Overview + by-root-cause + exceptions, in one response |
| `GET /api/audit/verify` | Walks the hash chain, returns `{ok, records_checked, error}` |
| `GET /api/eval/comparison` | Runs the evaluation harness on demand (`cases`, `seed` query params), returns the full comparison report |

## The failure stories

### The retry storm

**What broke:** an early version of the retry executor had no rate limit —
a customer whose `insufficient_funds` payment failed would get retried on
every batch run, including runs seconds apart during testing. Real payment
networks treat rapid repeat retries as suspicious and soft-decline them,
meaning the retry itself was making recovery *worse*, not better.

**How it was found:** the audit trail's `guardrail_checks` log showed
`passed: true` on every attempt with no rule in place to catch the
pattern, and the outcome log showed a recovering payment flipping to a new
decline reason (`risk_declined`) after multiple rapid retries against the
same customer — the system's own audit trail surfaced the bug.

**The fix:** added the 30-minute per-payment retry rate limit and the
4-hour cross-channel cool-down (both in the guardrail table above), and
gave the audit trail an explicit `rate_limited` block reason so this class
of failure is visible, not silent.

### The non-reproducible evaluation harness

**What broke:** the evaluation harness's common-random-numbers design keys
each case's seed off its `event_id`. `data/generator.py` generated IDs with
`uuid.uuid4()`, which reads from the OS's CSPRNG and completely ignores
`random.seed()`. Running `python -m app.eval.run_comparison --seed 42`
twice silently produced two different reports, defeating the entire point
of a seeded, reproducible comparison.

**How it was found:** re-running the same `--seed 42` invocation twice
during development and noticing the headline numbers didn't match.

**The fix:** IDs are now drawn from the seeded `random` module
(`generator.py::_random_hex`) instead of `uuid.uuid4()`. Verified: two
separate CLI invocations with the same seed now produce byte-identical
reports.

Both failure stories share a pattern worth naming: both were caught by the
system's own tooling (the audit trail; a repeated harness run) rather than
by inspection, and both fixes are in deterministic code, not a prompt or a
one-off patch.

## Known limitations

- Render's free tier cold-starts after ~15 minutes idle — ping `/health`
  a few minutes before any demo/judging window.
- `POST /api/run-batch` runs synchronously with a small delay between LLM
  calls (to stay inside Groq's free-tier rate limit), so a large `n` takes
  proportionally longer to return; the live feed still updates in
  real time throughout via Supabase Realtime regardless of when the HTTP
  response completes.
- All comms channels (WhatsApp/SMS/email) are simulated in-UI, clearly
  labeled as such — no paid delivery provider is wired up.
- Single-merchant demo: no auth/login system, no multi-tenancy.
- The hash chain and the evaluation harness's `vasuli` arm both assume a
  single sequential writer/evaluator — a deliberate scope cut for this
  build, not an oversight (see their respective sections above).
- The evaluation harness's `vasuli` arm uses the heuristic diagnosis agent,
  not the live LLM — a deliberate choice for speed, determinism, and
  reproducibility (see "Evaluation harness" above), not a claim that the
  heuristic and the LLM always agree.
