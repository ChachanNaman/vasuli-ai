# Vasuli — 5-minute demo / pitch script

Target: a judge should be able to complete this whole path themselves,
without narration, in under 5 minutes. This script is the version *with*
narration, for the recorded pitch video.

Before recording: hit `GET /health` on the Render backend a few minutes
ahead of time so the free-tier instance isn't cold when you start.

---

## 0. Cold open (10s)

> "Vasuli watches a merchant's failed payments, abandoned checkouts,
> failed subscription mandates, and overdue invoices — figures out *why*
> each one is losing money, picks a bounded action, and executes it under
> hard guardrails it can't argue its way past. It's built for Razorpay's
> AI Buildathon, Track 03: AI Revenue Recovery."

Cut to the landing page.

## 1. Landing page (20s)

- Show the hero: one-sentence pitch, "Run live batch" CTA.
- Scroll through "How it works" (the four-layer architecture cards) just
  long enough to land the one line that matters:

> "The LLM never touches money directly. It proposes — a deterministic
> guardrail engine and the recovery executors are the only things allowed
> to act."

- Scroll past the recovery action gallery (the fixed action menu) —
  mention it's a fixed, allow-listed set, never a freeform action.

## 2. The live batch run — the "prove it's real" moment (90s)

This is the single most important beat in the whole video. Don't cut away
from it.

1. Click into the dashboard, click **Run recovery batch**.
2. Switch to the **Live agent feed** tab immediately.
3. Let decisions stream in one at a time — for each one, call out:
   - the event and its root cause,
   - the action the agent picked,
   - whether a guardrail blocked it (point at one blocked decision if the
     batch produces one — it should visibly slow down / flash amber-red,
     reading as a deliberate safety feature, not a bug),
   - the outcome.
4. Specifically wait for a `smart_retry` or `generate_payment_link`
   decision and open its Razorpay link — this proves the agent is
   touching real (sandboxed) payment infrastructure, not narrating.

> "That link is real — a live Razorpay Test Mode payment link the agent
> generated through the API, not a screenshot. Zero real money moves in
> test mode, but the object is real."

## 3. Drill-down — the reasoning trace (45s)

1. Click into any single decision from the feed or the overview table.
2. Walk through, in order: the raw event data → the LLM's diagnosis and
   confidence → every guardrail check with pass/fail → the action taken →
   the outcome.

> "Nothing here is a black box. Every decision carries its full reasoning
> and every guardrail check it passed or failed, whether or not anything
> got blocked."

## 4. Dashboard metrics (20s)

- KPI row: total ₹ at risk, ₹ recovered, recovery rate, guardrail blocks.
- Recovery-by-cause bar chart, recovery-over-time area chart.

> "These aren't hand-picked wins — they're computed live from an 80+
> record synthetic batch with a probabilistic outcome model, documented
> in `recovery/outcome_model.py`."

## 5. Exceptions tab — the honest list (25s)

- Show the exceptions tab: everything flagged for human review or
  explicitly not actioned, with reasons.

> "When the agent isn't confident, it says so instead of guessing —
> `flag_for_human_review` and `no_action_recommended` are both first-class
> outcomes here, not hidden failures. A system that admits what it can't
> safely automate is more trustworthy than one that always confidently
> acts."

## 5a. vs. Baseline tab — incremental recovery, not raw (30s)

- Switch to the **vs. Baseline** tab. Point at the audit-integrity badge
  first.

> "That's a live hash-chain verification — every decision on record is
> provably unaltered, not just logged."

- Then the comparison table.

> "This runs the same batch through four policies with common random
> numbers — do nothing, a naive fixed retry ladder, Vasuli, and a
> max-pressure policy that ignores guardrails entirely. The headline
> number is incremental recovery, not raw — about 15 to 20 percent of
> at-risk value comes back with zero intervention, so raw recovery alone
> flatters any recovery product. Vasuli trades some raw recovery for
> roughly a quarter of the guardrail violations a naive policy racks up,
> at lower cost per case. That trade-off is the real story, not a single
> recovery-rate number."

## 6. The failure story (30s)

> "An early version of the retry executor had no rate limit — a customer
> whose payment failed with `insufficient_funds` got retried on every
> batch run, seconds apart during testing. Real payment networks treat
> that as suspicious and soft-decline it, so the retry itself was making
> recovery worse. The system's own audit trail caught it — a recovering
> payment flipping to a new decline reason after rapid repeat retries. The
> fix was a guardrail, not a prompt tweak: a 30-minute per-payment retry
> rate limit and a 4-hour cross-channel cool-down, both visible in the
> guardrail table today."

## 7. Close (15s)

> "Vasuli — the AI agent that gets your money back. Repo, architecture
> doc, and full test suite are linked below."

---

## B-roll / cutaway shots to grab while recording

- The architecture diagram (`docs/architecture.md`, rendered) as a
  full-screen cutaway during section 0 or 6.
- The guardrail rule table, full-screen, during section 6.
- The Razorpay Test Mode dashboard showing the generated payment link
  object, as proof alongside the in-app link during section 2.
- A blocked-by-guardrail decision in the live feed, paused/zoomed, during
  section 2.

## Known-risk fallback

If live Groq/Gemini calls fail during judging (free-tier rate limits),
fall back to a pre-run "known good" batch captured earlier — the
dashboard reads from Supabase regardless of when the batch was run, so a
pre-populated decision set demos identically to a live one. Mention this
contingency in the README rather than hoping no one notices a stall.
