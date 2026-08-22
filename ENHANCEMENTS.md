# Vasuli — Competitive Enhancement Addendum

This is a delta on top of `PRD_1.md`, `docs/architecture.md`, and `README.md`
— written after reviewing four public repos from other Track 03 entrants.
Read this alongside the PRD, not instead of it. Where this doc conflicts
with the PRD, this doc wins.

---

## 1. Competitive scan (what's actually better elsewhere)

| Repo | What they do better | Verdict |
|---|---|---|
| `Ovais-Maker/razorpay-buildathon-recoup` | Baseline-compared, incremental-recovery evaluation across 4 arms with shared random draws; real regulations named; hash-chained audit trail with a `verify` command; honest heuristic-vs-LLM comparison reported even though the heuristic won | The one to worry about. Adopt items 2–6 below primarily because of this repo. |
| `kirangunaga992/recoup` | Real scikit-learn classifier, held-out test set with confusion matrix, 8% deliberately mislabeled training rows, zero-API-key operation | Strong reliability story. We don't need to copy the ML classifier, but we should copy "runs with zero API key." |
| `sreechandhana54/recovr-ai-revenue-recovery` | Close to our current spec, not materially ahead | Low threat, no action needed beyond our existing plan. |
| `manimimohit-glitch/voice-recovery-agent` | Real Hinglish TTS/STT audio artifact (Piper + Whisper) | Interesting but caused them real friction (had to gitignore a large model file). Our Web Speech API plan gets 80% of the "wow" for near-zero setup risk — keep our approach, don't chase theirs. |

---

## 2. Priority-ordered changes (do these, in this order, inside your 3 days)

### 2.1 Baseline-comparison evaluation harness (highest priority)

Add a new module, `backend/app/eval/`, that runs the *same* batch of cases
through multiple policies and reports **incremental** recovery, not raw
recovery. This is the single most important change on this list.

- **Arms to implement:** `do_nothing` (no intervention, ever), `fixed_dunning`
  (a naive fixed retry+reminder ladder, same for every case regardless of
  cause), `vasuli` (your actual guardrailed agent). A `max_pressure` arm
  (contact/retry as often as technically possible, ignoring guardrails) is
  optional but a strong addition if time allows — it's what makes "zero
  compliance violations vs. thousands" a headline number.
- **Common random numbers:** each case gets one pre-drawn random seed used
  identically across all arms, so a case that "gets lucky" gets lucky in
  every arm. Without this, differences between arms are partly just noise.
- **Incremental recovery formula:** `incremental = recovered_under_policy -
  recovered_under_do_nothing`, computed per case, then summed. Report this
  number as the headline, with raw recovery as a secondary figure. This
  directly answers Ovais-Maker's own framing: "roughly 20% of at-risk value
  comes back on its own, and counting it is the easiest way for a recovery
  product to flatter itself."
- **Report alongside it:** contacts-per-case, cost-per-₹-recovered
  (assume small fixed costs per action type — a retry costs paise, a
  WhatsApp message costs more, a human-escalation costs the most — pick
  illustrative numbers and say so explicitly in the README, exactly as
  Ovais-Maker did with "the generator states every distribution explicitly
  in code, so any number can be argued with").
- **Where it lives:** `backend/app/eval/run_comparison.py`, callable as
  `python -m app.eval.run_comparison --cases 500`, output a markdown/JSON
  report plus (reuse the dataviz-appropriate approach) 2-3 charts: recovery
  by arm, recovery-by-cause, contacts-vs-recovery.

### 2.2 Guardrail table — cite real regulations by name

Replace the generic descriptions in PRD Section 7 with named regulations
(verified via search — cite these correctly, they're real as of 2026):

| Rule | Regulatory basis | Logic |
|---|---|---|
| Contact window | RBI recovery-agent guidelines restrict borrower contact to roughly 8:00am–7:00pm | No customer-facing action (call, SMS, WhatsApp) outside this window; queue until window opens |
| E-mandate pre-debit notice | RBI's e-mandate/recurring-payment framework requires prior notification before an auto-debit, on a set notice period | `initiate_mandate_reauth` and any retry against an active mandate must respect a pre-debit notice step, not fire a silent retry |
| DLT-registered templates only | TRAI mandates all commercial SMS/WhatsApp content be pre-registered on the DLT platform | `send_nudge` message templates must come from a small fixed, "pre-registered" template set — never freeform LLM-generated text sent directly, even though the LLM *drafts* the content (see 2.5) |
| DND / opt-out enforcement | TRAI DND registry + your own opt-out flag | Same as existing rule, now explicitly tied to the regulatory reason, not just "good practice" |
| Max retry / card-network cap | Card network rules cap retry attempts on a declined instrument | Same as existing max-retry rule, cite the card-network basis explicitly |
| Contact frequency cap | Reasonable-conduct expectation under RBI fair-practice codes | Same as existing daily/weekly cap |
| Dispute freeze | Once a payment is disputed/charged back, further collection action on it should stop pending resolution | New rule: any event flagged `dispute_opened` (add this field to the schema) hard-stops all agent action on that case |

Keep the exact numeric thresholds you already picked (30-min retry
cool-down, 4h contact cool-down, etc.) — the goal here is citing *why* the
rule exists, not re-deriving the numbers. Do not state specific rupee
thresholds for e-mandate AFA requirements in your materials since that
figure has changed in 2026 rule updates — reference the *existence* of the
requirement, not a number you haven't independently verified for the
current framework revision.

### 2.3 Economic stopping rule + cost metrics

Add to the guardrail engine: a `no_action_recommended` outcome is forced
whenever `expected_recovery < 3 * (action_cost + nuisance_cost)`, where
`action_cost` is a small fixed cost per action type (retry ≈ ₹0.05,
SMS/WhatsApp ≈ ₹0.30–0.50, human escalation ≈ ₹50+) and `nuisance_cost` is
an illustrative constant representing goodwill erosion from over-contacting
— state these numbers explicitly in a comments block, same transparency
move as the competitor's "the generator states every distribution
explicitly in code."

Add two new headline metrics next to recovery rate: **cost per ₹ recovered**
and **contacts per case**. These are what let you make the claim "we
recovered comparably well while contacting people less" — a much stronger
story than recovery rate alone, and it's the exact shape of Ovais-Maker's
strongest table.

### 2.4 Hash-chained audit trail

Minimal version: each `decisions` row gets a `record_hash` column computed
as `sha256(previous_record_hash + canonical_json(this_record))`. Store the
genesis hash as a constant. Ship `backend/app/audit/verify.py` as a CLI
(`python -m app.audit.verify`) that walks the chain and confirms no record
has been altered or removed — prints "✅ N records verified, chain intact"
or fails loudly with the first broken link. This is a small addition to
`audit/logger.py` (compute+store the hash at write time) plus one new
small file, for a genuinely impressive proof-of-integrity demo moment.

### 2.5 Zero-API-key deterministic baseline + honest LLM comparison

Add `backend/app/agents/heuristic_agent.py`: a small, explicit rule-based
diagnosis function (if/elif over `failure_reason_code`, `attempt_number`,
`mandate_status`, etc., mirroring the same allowed action set from PRD
8.2). This gives you three things at once:

1. **A true fallback of last resort** — if Groq *and* Gemini both fail
   during judging, the pipeline degrades to this instead of failing the
   whole batch (stronger than the current plan, which only had
   `flag_for_human_review` as the fallback).
2. **A working zero-API-key demo mode** — the whole app can run and produce
   real, structured metrics with no external dependency at all, matching
   `kirangunaga992`'s biggest reliability advantage.
3. **The strongest possible "AI judgment" evidence**: run both the
   heuristic and the LLM agent over the same batch (same seeds), and report
   the comparison honestly in the README — win or lose. If the LLM wins,
   great, you have a number. If the heuristic wins on raw recovery but the
   LLM handles a few genuinely ambiguous/unanticipated cases better, *say
   that* — a specific, honest, evidenced answer beats a vague claim either
   way, and judges have now seen at least one other team make exactly this
   move well.

Keep this scoped small — this is the one item on this list that's genuine
net-new work rather than reframing something you already planned, so if Day
3 is tight, this is the one to cut first, not items 2.1–2.4.

### 2.6 Adversarial guardrail test

Add one test file, `backend/tests/test_guardrails_adversarial.py`: a stub
"agent" that, for every case in a batch, recommends the worst possible
action (retry a hard-declined instrument, contact an opted-out customer at
3am, exceed every cap). Assert the guardrail engine blocks 100% of it and
that zero disallowed actions reach the executor layer. A few hours of work,
and it converts "the guardrail can't be argued past" from an assertion in
your README into a test that actually tries to break it and fails to.

---

## 3. What NOT to chase (deliberately, to protect your 3 days)

- Do not build a real voice-call pipeline (Piper/Whisper or similar). The
  Web Speech API read-aloud moment already planned gets most of the visual
  impact for near-zero setup risk; the competitor who did build real voice
  had to gitignore a large model file, a sign of exactly the kind of setup
  friction you don't have time for.
- Do not build a trained ML classifier (RandomForest or similar) to replace
  the LLM. A well-scoped heuristic (2.5) gets you the reliability and
  comparison value without a training/evaluation pipeline you don't have
  three days for.
- Do not try to match every regulation citation with an exact numeric
  threshold pulled from memory — cite the existence and direction of the
  rule (contact window, pre-debit notice, DLT registration) and let the
  code's own constants be the source of truth for the actual numbers, exactly
  as the strongest competitor did.

---

## 4. Implementation order (single session, no day-boxing)

You already have working guardrails, a real Razorpay Test Mode integration,
and a passing test suite — this is a delta applied on top of that code, not
a rebuild. Do it in this order, since later items assume earlier ones exist:

1. Add the regulation-named guardrail rules and the dispute-freeze rule
   (2.2) to the existing guardrail engine, plus the economic stopping rule
   and cost metrics (2.3). Extend existing guardrail tests to cover the new
   rules; add the adversarial guardrail test (2.6).
2. Add the hash-chained audit trail (2.4) to the existing audit logger, plus
   the `verify` CLI.
3. Add the heuristic/rule-based fallback agent (2.5) alongside the existing
   Groq/Gemini agent, wire the three-way degradation (Groq → Gemini →
   heuristic), and only if time allows, run the honest LLM-vs-heuristic
   comparison and write up whichever way it goes.
4. Build the baseline-comparison evaluation harness (2.1) — do-nothing,
   fixed-dunning, and Vasuli arms, common random numbers, incremental
   recovery as the headline number, cost-per-₹-recovered and
   contacts-per-case alongside it. Run this before touching the frontend so
   you have a real number to react to.
5. Wire the "vs. baseline" panel and an "audit integrity: verified ✅"
   indicator into the existing dashboard, sourced from steps 2 and 4.
6. Update the README/architecture docs to reflect all of the above —
   named regulations, the incremental-recovery number, the hash-chain
   verify result, and the heuristic-vs-LLM finding if you built it.

If you run out of time, cut in this order: the `max_pressure` eval arm →
publishing the LLM-vs-heuristic comparison (keep the heuristic as a silent
fallback only) → the adversarial guardrail test. Never cut the
incremental-recovery harness or the named-regulation guardrail table —
those two are the highest-leverage items on this entire list.
