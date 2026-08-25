# Vasuli, explained from zero

This is written for someone who has never seen this codebase and doesn't
know the track. No jargon without an explanation first. Read this top to
bottom once, then keep it as a reference while you look at the actual
dashboard/code.

---

## 1. The competition (so the "why" makes sense)

**Razorpay's AI Buildathon, Track 03: "AI Revenue Recovery."**

Razorpay is an Indian payments company (like Stripe for India). Every
payments company loses money in predictable ways:

- A customer's card payment **fails** (bank server down, wrong OTP, card
  expired, insufficient balance...).
- A customer's **subscription** charge fails (their auto-pay mandate
  expired or got revoked).
- A customer **starts** checking out, sees the price, and just... leaves
  without paying (cart abandonment).
- A business customer gets sent an **invoice** and doesn't pay it on time.

All four of these are money the merchant *should* have gotten, and didn't
— yet. Some of it comes back on its own (the customer retries themselves
later). Some of it is recoverable if someone nudges the right person at
the right time in the right way. The track's challenge: build an
**autonomous agent** that watches for these events, figures out *why*
each one happened, does something sensible about it, and proves — with
real numbers — that it actually got money back, not just that it looks
busy.

The track's judging bar (paraphrased): don't just detect the problem —
show **measured recovered money** across a batch of cases, with
**compliant** behavior (don't spam people, don't break Indian
regulations), **stopping rules** (know when *not* to act), and a
**paper trail** for every decision. Vasuli is built so each of those
is a literal feature you can click on, not a claim in a slide deck.

---

## 2. What Vasuli actually is, in one paragraph

Vasuli watches a stream of "we lost money" events. For each one, an AI
model looks at the details and **proposes** one action from a small
fixed menu (retry the payment, send a reminder, generate a fresh payment
link, etc.). Before that proposal is allowed to run, it passes through
**12 hard-coded safety rules** that have nothing to do with AI — plain
Python `if` statements checking things like "have we already contacted
this person twice today?" or "is it 2am in India right now?". Only if
every rule passes does the action actually execute. Every single step —
what was proposed, what was checked, what ran, what happened — gets
written down permanently and tamper-evidently. That's the whole system.

**The one sentence that matters most:** *the AI never touches money
directly.* It only ever gets to *suggest*. A separate, boring, 100%
predictable piece of code is the only thing that's allowed to say "yes,
go ahead" or "no, blocked." This is the system's single biggest
selling point to a judge, and it's true of every single decision it
ever makes.

---

## 3. The four kinds of "lost money" events

Everything starts as one of these four **event types** (all fake/synthetic
data generated for the demo, made to look like real Razorpay data):

| Event type | Plain English | Example field that matters |
|---|---|---|
| `payment_failed` | A one-time card/UPI/etc. payment declined | `failure_reason_code` — *why* it failed (`insufficient_funds`, `card_expired`, `bank_server_down`...) |
| `subscription_charge_failed` | A recurring auto-pay charge declined | `mandate_status` — is the auto-pay authorization still `active`, or `expired`/`revoked`? |
| `checkout_abandoned` | Customer left before paying | `minutes_since_abandon` — how long ago, and `checkout_stage_reached` — how far they got |
| `invoice_overdue` | A B2B invoice is late | `payment_reliability_score` — 0 to 1, how reliably this business customer has paid historically |

Each event also carries a `customer` object: name, whether they've opted
out of being contacted, their preferred contact channel (SMS/WhatsApp/
email/call), and whether they prefer Hindi-English mix ("hinglish") or
English.

---

## 4. The brain: how one event gets diagnosed

For one event, here's exactly what happens, in order:

### Step 1 — Diagnose

The event's full details get sent to an LLM (a large language model —
think ChatGPT, but here it's **Groq** first, hosting Llama models). The
LLM is told: "here's everything about this failure — pick exactly ONE
action from this fixed list of 7, and tell me why." It must answer in a
strict format (root cause, confidence 0–1, reasoning, one action,
optionally a draft customer message).

**Why "exactly one from a fixed list," never "whatever you think is
best"?** Because letting an LLM invent free-text actions is exactly the
kind of unpredictability a payments company can't tolerate. The 7 allowed
actions are:

1. `smart_retry` — try the payment again (good for temporary problems)
2. `generate_payment_link` — send a fresh link to pay a different way (good when retrying the same method won't work, e.g. expired card)
3. `send_nudge` — a reminder message (good for abandoned checkouts)
4. `escalate_b2b_chase` — a structured reminder sequence for overdue invoices
5. `initiate_mandate_reauth` — ask the customer to re-authorize a dead subscription mandate
6. `flag_for_human_review` — "I'm not confident enough to automate this, a human should look"
7. `no_action_recommended` — "doing anything here would likely make it worse or there's nothing left to try"

**What if Groq is down or errors?** The system tries **Gemini** next
(Google's LLM) automatically. **What if Gemini also fails?** — this is
the part most demos skip — it falls back to a small set of hand-written
`if`/`elif` rules (`heuristic_agent.py`) that make the exact same kind of
decision, using no AI at all, guaranteed to always work, zero API cost.
This is called **three-way degradation**: Groq → Gemini → deterministic
rules. The system is never fully "down."

### Step 2 — Guardrail check (the part that actually matters most)

Whatever action got proposed in Step 1 now has to survive **12
independent checks**, all plain code, zero AI:

| # | Rule (plain English) | Why (the real-world reason) |
|---|---|---|
| 1 | Don't retry a payment more than 2–3 times | Card networks (Visa/Mastercard rules) cap retry attempts |
| 2 | Don't contact the same person again within 4 hours | Basic fair-treatment norm (RBI = India's central bank guidance) |
| 3 | Don't contact the same person more than 2x per day | Same |
| 4 | Never contact someone who opted out | India's TRAI "Do Not Disturb" telecom rules + the customer's own preference |
| 5 | Never auto-escalate an invoice over ₹1,00,000 without a human | Internal policy — big money needs a human |
| 6 | Don't retry the same payment twice within 30 minutes | Prevents a "retry storm" (see the real bug story below) |
| 7 | For B2B invoices, be gentler with historically reliable customers | Internal policy |
| 8 | Only contact customers between 8am–7pm IST | RBI recovery-agent contact-hour guidelines |
| 9 | Never silently retry an active subscription mandate — must have a confirmed 24h+ notice | RBI's e-mandate rules require advance notice before an auto-debit |
| 10 | Any message sent must come from a small pre-approved template, never the AI's raw free text | TRAI's DLT rule: all commercial SMS/WhatsApp content must be pre-registered |
| 11 | If a payment is under dispute/chargeback, freeze everything | Standard practice — don't chase money that's actively being disputed |
| 12 | **Economic stopping rule** (the interesting one — see below) | Don't spend money trying to recover money if the math doesn't work |

**Every single one of these 12 checks runs for every single decision**,
whether it blocks anything or not — and every result (pass or fail) gets
permanently recorded. That's what "every rule check, not just the ones
that blocked something, is written to the audit trail" means in practice.

**Rule #12, the economic stopping rule, explained with real math:**
Every action has an estimated cost (a retry costs about ₹0.05 — it's
just an API call; a human review costs ₹50 — someone's actual time) plus
a "nuisance cost" of ₹2 for anything that contacts the customer (annoying
someone has a cost even if it's not a rupee amount). The rule says:
**expected money recovered must be at least 3× the action's cost**, or
it's blocked and downgraded to "no action." Expected recovery = `payment
amount × probability of success`. So if a ₹100 payment has only a 2%
chance of being recovered by a retry, expected recovery is ₹2, the
retry's cost floor (3× ₹0.05+₹2 ≈ ₹6.15) isn't cleared, and the system
correctly refuses to bother — trying doesn't come free just because a
retry is cheap.

If **any** of the 12 rules fails, the action is blocked
(`blocked_by_guardrail`) — except if opt-out is the *only* failing rule,
in which case it's labeled `skipped_opt_out` (a softer, expected outcome,
not really a "failure"). If all 12 pass, it's `executed`.

### Step 3 — Execute (only if it passed every check)

Only now does anything actually *do* something:

- `smart_retry` / `generate_payment_link` → creates a **real** Razorpay
  Test Mode payment link (fake money, but a real API call to Razorpay's
  sandbox — not a placeholder image).
- `send_nudge` / `escalate_b2b_chase` / `initiate_mandate_reauth` →
  "sends" a message, but only from the small pre-approved template list
  (rule #10 above) — never the LLM's own freely-generated wording, even
  though the LLM's draft is kept around for the audit log.

Every action then gets a **probabilistic outcome** — did it actually
recover the money or not? This is never a guaranteed win. Example
probabilities (all hand-picked and clearly labeled as illustrative, not
pulled from a real company's data):

- Retry after a `bank_server_down` failure: **70%** chance of success (it was a temporary glitch, probably fixed by now)
- Retry after `card_expired`: **5%** chance (retrying the same dead card obviously won't work — this is why the LLM is supposed to route this to `generate_payment_link` instead)
- WhatsApp nudge: **35%** base chance, decaying by half roughly every 24 hours the longer you wait to send it
- A subscription mandate re-auth: flat **30%** chance

The system literally rolls a weighted die for every action using these
numbers — it's not simulating a guaranteed happy outcome, it's simulating
reality (some things you try just don't work).

### Step 4 — Write the permanent record

One row goes into a `decisions` table containing *everything*: what was
diagnosed, all 12 guardrail results, what ran, what the outcome was, and
a cryptographic hash (explained in section 7). This table is what the
entire dashboard is built on top of.

---

## 5. A worked example, start to finish

Say the event is: *customer "Aditya Gupta" abandoned checkout 10 minutes
ago at the payment-method screen, cart value ₹1,200, prefers WhatsApp,
prefers Hinglish.*

1. **Diagnose:** LLM sees "abandoned recently, at a late stage" → picks
   `send_nudge`, confidence 0.85, draft message in Hinglish.
2. **Guardrails:** checks contact window (is it 8am–7pm IST? yes, pass),
   opt-out (not opted out, pass), daily cap (no prior contact today,
   pass), cool-down (no contact in last 4h, pass), DLT template
   compliance (a Hinglish template exists for `send_nudge`, pass),
   economic stopping rule (₹1,200 × 35% chance = ₹420 expected, action
   costs ~₹2.40, 420 ≫ 3×2.40, pass)... all 12 pass. Status: `executed`.
3. **Execute:** the actual message sent is the fixed template *"{name},
   aapka ₹{amount} ka payment complete nahi hua. Yahan complete karein:
   {link}"*, filled in — not the LLM's own wording, even though the LLM's
   draft is kept in the record for transparency.
4. **Outcome:** the system rolls the WhatsApp probability (~35%, decayed
   slightly for the 10-minute delay) → say it lands as **recovered**,
   ₹1,200 added to the "total recovered" number.
5. **Record:** one row written with all of the above, hash-chained to
   the previous row.

If instead this were the *second* nudge sent to Aditya today, rule #3
(daily contact cap) would fail, the action would be `blocked_by_
guardrail`, nothing would be sent, and the record would say exactly
that — "AI proposed send_nudge, guardrail blocked it, nothing was
substituted, here's why."

---

## 6. The dashboard — every number explained

### KPI cards (top of the page)

- **Total at risk** — sum of the `amount` field across every event in
  the current batch. "This much money was on the line."
- **Total recovered** — sum of `amount_recovered` across every decision
  where `recovered = true`. Money that actually, provably, came back.
- Underneath it (new): **"≈ N days of reduced receivables outstanding"**
  — takes the recovered ₹ and divides by an assumed average daily
  revenue figure (₹8,00,000/day — a stated, made-up-but-labeled
  assumption, not a real merchant's number) to translate a rupee figure
  into a business-relevant sentence a CFO would actually say out loud.
- **Recovery rate** — `recovered decisions ÷ total decisions × 100`.
- Underneath it (new): **"Prevented an estimated N% of at-risk
  subscription MRR from churning"** — same idea, but scoped just to
  `subscription_charge_failed` events (MRR = Monthly Recurring Revenue,
  the subscription-business metric that actually matters to a SaaS/
  subscription merchant).
- **Guardrail blocks** — how many proposed actions rule #1–12 actually
  stopped. A *high* number here isn't a bad sign — it's proof the safety
  layer is doing real work, not sitting there doing nothing.

### The three badges on every decision (new — "decision-source badges")

Every single decision anywhere in the UI now shows one of:

- 🤖 **AI-proposed** — the LLM (or a heuristic, if both LLMs were down)
  suggested this and the guardrail engine cleared it to actually run.
- ⚙️ **Guardrail-blocked** — something was proposed, a rule stopped it,
  nothing ran in its place (the record shows exactly which rule and why).
- 📐 **Heuristic-fallback** — both Groq and Gemini were unavailable, so
  the zero-AI backup rules made the call instead.

This exists because "the AI never touches money directly" is the
project's strongest safety claim — putting it on every single row means
a judge sees it by scrolling, not by being told.

### Live agent feed

A real-time list of decisions as they happen, streamed straight from
the database the instant each row is written (via something called
Supabase Realtime — no polling/refreshing needed). Click any row to open
the full detail.

### Exceptions tab

Every decision that was blocked, opted-out, or flagged for a human —
i.e., every case Vasuli **didn't** fully automate — shown honestly in
one place instead of being hidden. The pitch here: "we don't just show
you our wins."

### vs. Baseline tab (the evaluation harness — the most important math on the whole dashboard)

This answers the question a skeptical judge should ask: *"how do I know
this AI agent actually helps, versus doing nothing, or versus a much
dumber system?"*

It runs the **same set of test cases** through **four different
strategies** and compares them:

1. **do_nothing** — never intervenes at all. Turns out some money comes
   back anyway (customers retry on their own, businesses eventually pay
   late invoices) — roughly 10–20% depending on event type. This is the
   **organic baseline**.
2. **fixed_dunning** — a dumb system: always retries every payment
   failure, always nudges every abandoned cart, no matter the actual
   cause, no guardrails at all.
3. **vasuli** — the real thing: diagnosis + all 12 guardrails + the real
   outcome probabilities.
4. **max_pressure** — the most aggressive possible action every time,
   guardrails completely ignored. This exists to show what "no safety
   rules at all" looks like — spoiler, lots of guardrail violations.

**The headline number is "incremental recovery," not raw recovery.**
Raw recovery flatters everyone, because it counts money that would've
come back anyway. Incremental recovery = `(money recovered under this
policy) − (money recovered under do_nothing)` — i.e., *how much did this
policy actually add on top of what would've happened regardless?* That's
the only honest way to claim credit.

The comparison also uses a trick called **common random numbers**: every
policy gets tested against the exact same "luck" per case (the random
dice-roll for whether a retry succeeds is seeded identically across all
four arms for the same case). This means if `vasuli` recovers more than
`fixed_dunning`, it's because the *policy* is better — not because it
got a luckier dice roll.

Also shown: **guardrail violations per policy**. `vasuli` should show
near-zero (it enforces them). `max_pressure` should show a lot (it
ignores them on purpose, as a contrast).

### Fairness / consistency check (new)

A small honesty check: does Vasuli propose the *same kind* of action at
the *same rate* regardless of a customer's language preference,
preferred contact channel, or how long they've been a customer? It
compares the percentage of decisions routed to "flag for human review /
no action" across each group. If any group's rate differs by more than
15 percentage points from another, it's flagged as worth investigating;
otherwise it honestly reports "no evidence of differential treatment."
It does **not** claim to prove fairness — just that nothing suspicious
showed up in this batch. This is a genuinely rare feature — none of the
competing projects in this track check for this at all.

---

## 7. The audit trail — why it's "tamper-evident"

Every decision row, when written, gets a `record_hash` computed as:

```
record_hash = sha256(previous_row's_hash + this_row's_content)
```

This is a **hash chain** — the same core idea blockchains use. Each
record's hash depends on the row *before* it. If anyone ever went back
and edited an old decision (say, changing `amount_recovered` after the
fact to make the numbers look better), that row's hash would no longer
match what it should be, and — because every later row's hash was built
on top of the tampered one — **every row after it would also fail to
verify**. Running the verification (`GET /api/audit/verify`, or the
badge on the dashboard) walks the whole chain and tells you exactly
where — if anywhere — it breaks. This has an actual regression test that
tampers with a row on purpose and confirms verification catches it at
the exact right position.

---

## 8. The other new features, quickly

- **Live pause/resume kill switch** — while a batch is running, a
  "⏸ Pause agent" button stops the pipeline *between* events (never
  mid-decision — whatever's already in flight finishes cleanly). The UI
  shows "Paused — N of M processed." Nothing is silently dropped; the
  remaining events just wait. Resume picks up exactly where it left off.
  This exists to answer "what happens if this needs to stop right now?"
  live, in the demo, instead of as a claim in a doc.
- **Per-customer recovery journey** — click any customer ID anywhere and
  see their entire history as a timeline: `payment_failed → nudge sent →
  smart_retry attempted → recovered`, each step timestamped and badged.
  Same underlying data as the flat decision table, but told as a story —
  much stronger for a demo video than "here's a table of 80 rows."
- **Counterfactual sandbox** — on any decision's detail view, you can
  pick a *different* action than the one the AI actually chose, and run
  it through the **real, live** guardrail engine right there — same
  code, same customer contact history, same time-of-day. If it would be
  blocked, you see exactly which rule and why, in real time. If it would
  pass, you see the same probability math the system itself uses, but
  clearly labeled as a simulated projection — it never actually sends
  anything or calls Razorpay for real. This is the most convincing
  feature in the whole build, because instead of *telling* a judge the
  guardrails can't be argued past, it lets them try to break it live and
  watch it refuse.

---

## 9. Two real bugs that got caught and fixed (worth knowing for Q&A)

1. **The retry storm.** Early on, retries had no rate limit. A failed
   payment retried multiple times in quick succession started getting
   *worse* declines (`risk_declined` — payment networks treat rapid
   repeat attempts as suspicious and start blocking them harder). Fixed
   by adding the 30-minute retry rate limit (guardrail #6). Found by
   reading the system's own audit trail, not by guessing.
2. **A "seeded" comparison that wasn't actually reproducible.** The
   evaluation harness is supposed to give byte-identical results every
   time you run it with the same seed. It didn't, because event IDs were
   generated with `uuid.uuid4()`, which — unlike Python's `random`
   module — completely ignores any seed. Fixed by switching ID
   generation to the seeded random generator. Verified by literally
   running it twice and diffing the output.

Both of these are good stories for a judge Q&A: they show the system
catches its own mistakes rather than needing a human to notice by eye.

---

## 10. Glossary (plain definitions)

- **LLM** — Large Language Model, an AI that reads text and writes text
  back (here: Groq/Gemini, used only to *propose*, never to *execute*).
- **Guardrail** — a hard-coded safety rule that has veto power over
  whatever the AI suggests.
- **Root cause** — *why* something failed (e.g. `card_expired`), as
  opposed to just "it failed."
- **Action** — the one thing Vasuli decides to do about an event, from
  the fixed list of 7.
- **Guardrail-blocked** — the AI wanted to do something, a rule said no.
- **Incremental recovery** — money recovered *beyond* what would've come
  back with zero effort — the only fair way to measure an agent's value.
- **Common random numbers** — a technique to compare policies fairly by
  giving every policy the exact same "luck" per test case.
- **Hash chain** — a way of writing records so that editing an old one
  breaks a checkable mathematical fingerprint on every record after it.
- **DLT template** — a pre-approved, government-registered message
  template (India's TRAI rule) — no AI is allowed to write and send its
  own free-text SMS/WhatsApp content.
- **IST** — India Standard Time, used for the 8am–7pm contact-hours rule.
- **MRR** — Monthly Recurring Revenue, the standard subscription-business
  metric.

---

## 11. Where to look in the actual code, if you want to trace any of this yourself

- `backend/app/data/generator.py` — makes up the fake events
- `backend/app/agents/` — the LLM diagnosis + the zero-AI fallback
- `backend/app/guardrails/rules.py` — all 12 rules, one function each
- `backend/app/recovery/` — the executors + the probability math
- `backend/app/audit/` — the hash chain + the dashboard's numbers
- `backend/app/eval/` — the four-policy comparison harness + the fairness check
- `backend/app/api/main.py` — every API endpoint, one place
- `frontend/src/app/dashboard/` — the actual UI you click around in

Next step, whenever you're ready: the demo script (`docs/demo-script.md`)
— once this document makes sense to you, that one will be much easier to
memorize because you'll actually understand *why* each beat in the script
matters instead of just reciting it.
