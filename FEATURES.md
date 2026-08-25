# Vasuli — Differentiation Feature Spec

This is a delta on top of `PRD_1.md` and `ENHANCEMENTS.md`. Where
`ENHANCEMENTS.md` was about reaching parity with the strongest competitor,
this doc is about features none of the four competitor repos have — do
these after the parity items are done. Build in the order listed; 1–3 are
cheap and should always be done, 4–6 are worth it only if 1–3 are finished
with time to spare.

---

## 1. Decision-source badge (every row, not just the docs)

**What:** every decision, everywhere it's rendered (live feed, overview
table, drill-down panel), gets a small badge showing which layer actually
produced the outcome:

- 🤖 `AI-proposed` — the LLM (or heuristic) proposed this action and the
  guardrail engine cleared it to run
- ⚙️ `Guardrail-blocked` — the LLM proposed something, the guardrail engine
  vetoed it, and a different (safe) action ran instead — show *both* the
  original proposal and the substituted action, don't just show the final
  state
- 📐 `Heuristic-fallback` — Groq and Gemini were both unavailable and the
  deterministic fallback agent (from ENHANCEMENTS.md 2.5) made the call

**Where it lives:** this is a derived label, not new data — you already
have `diagnosis.recommended_action` vs `action_taken` vs
`action_status` in the decision record. Add a small pure function,
`badge_for_decision(decision) -> {icon, label, color}`, in the frontend
(or backend, whichever already owns decision formatting) and render it as
a `shadcn/ui` `Badge` component next to every decision, in every view.

**Why it matters:** your single strongest architectural claim — "the LLM
never touches money directly" — currently lives in a markdown file a judge
may never open. This makes it visible on literally every row of the UI,
so a judge sees the safety architecture just by scrolling, without you
having to explain it.

---

## 2. Live kill switch

**What:** a visible, always-present "⏸ Pause agent" control (top of the
dashboard, near "Run recovery batch") that halts an in-progress batch run
between events — not mid-decision, cleanly at an event boundary — leaving
every already-written decision intact and correctly recorded, and marking
any remaining ungenerated events in that batch as `skipped_paused` rather
than silently dropping them.

**Implementation shape:**
- The batch pipeline (`POST /api/run-batch`) already iterates events one
  at a time. Add a per-batch `pause_requested` flag (in-memory is fine for
  a single-merchant demo — a module-level dict keyed by `batch_id`, no new
  infra needed) that the loop checks before starting each new event.
- Add `POST /api/batches/{batch_id}/pause` and `.../resume` endpoints.
- On the frontend, the button calls pause, the live feed visibly stops
  advancing, and a clear "Paused — N of M events processed" state shows.
  A "▶ Resume" button un-pauses and the loop continues from where it left
  off in the same batch.

**Why it matters:** this answers the unspoken judge question — "what
happens if this needs to stop" — with a live moment in your demo instead
of a claim in your README. Genuinely cheap: your pipeline is already
sequential, this is a flag check plus two small endpoints.

---

## 3. Cash-flow framing on existing metrics (copy only, zero new code)

**What:** add a second line under your existing KPI numbers translating
them into business language a merchant CFO or ops lead would actually use,
computed from numbers you already have:

- Next to "₹ recovered": add "≈ N days of reduced receivables outstanding"
  — a simple derived stat: `recovered_amount / (merchant's average daily
  revenue)`, using a stated illustrative average-daily-revenue constant if
  you don't have a real one (say so explicitly, same transparency
  convention as everywhere else in this project).
- Next to "recovery rate" for the subscription-failure segment
  specifically: "prevented an estimated N% of at-risk MRR from churning"
  — `(subscription events recovered * amount) / (total subscription MRR
  represented in the batch)`.

**Where it lives:** this is UI copy plus one small derived-metrics
function in `audit/metrics.py` (or wherever `metrics_overview` is
assembled) — no schema changes, no new tables.

**Why it matters:** free reframing of numbers you already compute. The
difference between "a well-built agent" and "something a CFO would
actually want to buy" is often just which sentence describes the same
number.

---

## 4. Per-customer recovery-journey timeline

**What:** on the event drill-down (or a new "Customer" view reachable by
clicking a customer name anywhere), render that customer's full sequence
of decisions as a vertical timeline component — not a table row, an
actual timeline: `payment_failed → nudge sent (WhatsApp, Hinglish) →
smart_retry attempted → recovered`, each step timestamped, each step
showing its own decision-source badge from Feature 1.

**Implementation shape:** query `decisions` filtered by `customer_id`
(you already have this field), ordered by timestamp. Render with a simple
vertical stepper — `shadcn/ui` doesn't ship one natively, but a Tremor or
Magic UI timeline component, or a hand-rolled flex-column with connecting
lines, is a small component. Reuse the badge component from Feature 1 at
each step.

**Why it matters:** same underlying data as your flat decision table, but
a timeline reads as a *story* — this is the single highest-leverage
change for how memorable your 5-minute video is, because "watch one
customer's payment get rescued, step by step" is a much stronger demo
beat than "here's a table of 80 rows."

---

## 5. Counterfactual override sandbox

**What:** in the event drill-down panel, add a small "Try a different
action" control — a dropdown of the fixed allowed-action set (PRD 8.2)
plus a "run through guardrails" button. When clicked:

1. Run the *selected* (not the agent's original) action through the real
   guardrail engine for that event's actual state (attempt count, opt-out
   flag, time-of-day, etc.) and show pass/fail per rule, live.
2. If it passes, run it through the real outcome-probability model
   (`recovery/outcome_model.py`) and show the resulting probability of
   recovery, clearly labeled as a simulated projection, not a real
   re-execution — do not actually re-trigger a real Razorpay call for a
   counterfactual click.
3. If it's blocked, show exactly which rule blocked it and why, same
   format as a real guardrail-blocked decision.

**Implementation shape:** this is almost entirely reuse — one new
endpoint, `POST /api/events/{event_id}/counterfactual`, that calls the
*existing* guardrail-check function and the *existing* outcome-model
function with a caller-supplied action instead of the LLM's proposed one.
No new business logic, just a new entry point into logic you already have,
plus a small frontend form.

**Why it matters:** this is the most convincing thing on this whole list,
because it's not you telling a judge the guardrail can't be argued past —
it's the judge trying to make it do something unsafe, live, in your app,
and watching it refuse. Do this only after 1–3 are solid; it's real
incremental work even though it reuses existing logic.

---

## 6. Fairness / consistency check

**What:** a small, honestly-labeled statistical report, computed over a
completed batch, checking whether recovery *action assignment* (not
outcome — assignment, since outcomes are properly probabilistic) shows any
meaningful difference across customer segments that shouldn't matter:
language preference (`hinglish` vs `english`), preferred channel, and —
if you want a second dimension — tenure bucket (new vs long-standing
customer).

**Implementation shape:** for each event type, group decisions by segment
and compare the distribution of `recommended_action` (e.g. proportion
routed to `flag_for_human_review` vs proportion getting a direct
`smart_retry`/`send_nudge`). A simple chi-square or even just eyeballed
proportion deltas with a stated threshold ("no group's rate differs by
more than N percentage points") is enough — this doesn't need to be a
rigorous causal-fairness paper, it needs to be an honest, clearly-labeled
check. Report the result as-is: "no evidence of differential treatment by
language preference in this batch" if that's what you find, or the honest
opposite if you find a gap — do not tune the finding to be flattering.

**Where it lives:** one new function in `backend/app/eval/` (near the
comparison harness from ENHANCEMENTS.md 2.1, since it's the same kind of
"honest measurement" module), surfaced as one card in the dashboard, not
buried in a file only you will read.

**Why it matters:** none of the four competitor repos touch this at all.
It's a genuine, additional answer to "compliant escalation" beyond
contact caps and retry limits — showing the system doesn't just avoid
*illegal* treatment, it avoids *inconsistent* treatment. The honesty
framing ("no evidence of," not "proven fair") matters — an overclaimed
fairness statement would read worse than not having the feature at all.

---

## Explicitly not doing (stated once, so it isn't re-proposed later)

A shareable auto-generated results card/image, and a latency/throughput
observability dashboard. Both are reasonable ideas in general, but this
track is scored on recovery outcomes and judgment, not marketing assets or
ops maturity — lowest return on time of anything considered for this
project. Skip unless everything above, including item 6, is done with
real time still left over.
