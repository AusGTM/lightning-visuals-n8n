# Phase 61 — Premises answered from n8n's published documentation

**Recorded:** 2026-08-30
**Source of the correction:** operator, with citations. Verified independently against the cited
pages before being recorded here.
**Status:** documented fact, NOT observed behaviour on this account. See "The standing caveat".

## Why this document exists separately

`61-SPIKE-VERDICT.md` is owned by the parked 61-01 executor and its premises block is pinned by
`operator-claude-plugin/tests/test_spike_verdict_61.py`. These findings are recorded here instead
and should be folded into the verdict by 61-01's continuation agent when its checkpoint resolves.

**The mistake this corrects.** The spike verdict assigned P-05, P-08 and P-09 an owner of
"n8n admin / ask n8n Cloud support", and that ownership was propagated without anyone checking
whether n8n's own public documentation already answered them. It does, for all three. Marking a
question unanswerable when the vendor has published the answer is the same class of error as
CLAUDE.md §4.0's documented-vs-as-built trap, running in the opposite direction: there, source was
mistaken for deployed truth; here, published truth was mistaken for unavailable.

---

## P-05 — Is the executions API metered under a separate quota?

**Answer: no separate billable API-call quota is documented.** Confidence: medium-high.

n8n defines billable usage as production *workflow executions*, not management-API requests. A
client calling `GET /api/v1/executions` is not running a workflow. If a production workflow calls
that endpoint via an HTTP Request node, the enclosing run counts once; the individual request is
not separately metered.

**What this does NOT establish:** that the management API has no protective throttling or
undocumented fair-use rate limit. Billing metering and operational rate limiting are different
questions, and only the first is answered. The absence of a `/api/limits` endpoint means plan
allowance cannot be read programmatically — it does not prove no other quota exists.

**Relevance:** conditional. P-05 only bites if the executions-API run-state store is selected.

---

## P-08 — Does a parked execution survive an n8n restart?

**Answer: yes, for database-backed parked executions.** Confidence: high, with a hard boundary.

Wait-node executions are offloaded to the database and reloaded when the resume condition occurs.
The architecture is deliberately such that a parked execution does not depend on the original
process staying alive.

**The boundary, which is load-bearing for design:**

| Wait duration | Storage | Restart-safe? |
| --- | --- | --- |
| >= 65 seconds | offloaded to database | yes |
| < 65 seconds | stays in-process | **no** |
| webhook/form wait | persisted, pending external resume | yes |

A design that parks work MUST NOT use a sub-65-second timed wait and call it durable. This is a
silent trap: the short-wait version works perfectly until the one restart that matters.

**Also note:** persisting a Wait execution does not imply recovery from an arbitrary process crash
at any arbitrary node. It is a guarantee about parked executions, not about executions generally.

---

## P-09 — Is there a concurrent-execution cap?

**Answer: yes, per-plan, and this account is on Starter.** Confidence: high.

| Plan | Concurrent executions |
| --- | --- |
| **Starter — this account** | **5** |
| Pro | 20 |
| Enterprise | 200+ |

Starter also carries 2.5K workflow executions/month, which matches the 2,500 figure the repo
already tracks in `write_grant.py`'s `EXECUTIONS_BASIS`.

Executions beyond the cap **queue FIFO** and are processed as capacity frees. Exceeding
concurrency is therefore a throughput bound, **not an error condition** — a fan-out of 50 does not
fail, it drains 5 at a time.

**The empirical burst test is now unnecessary.** It was never able to establish a cap's absence or
value — only an observed floor — and the published figure supersedes it. Do not spend executions
on it.

---

## The finding that changes the architecture: sub-workflows are doubly exempt

Verified verbatim from two separate n8n documentation pages.

**Not metered** — from `docs.n8n.io/build/understand-workflows/understand-executions/`, listing
what does NOT count toward the quota:

> "Sub-workflow executions: When a workflow calls another workflow with the Execute Sub-workflow
> node, only the parent (top-level) execution counts."

(also excluded: manual executions, error-workflow executions, polls returning no data, and
malformed or rejected webhook requests)

**Not concurrency-capped** — from `docs.n8n.io/deploy/use-n8n-cloud/understand-concurrency/`:

> "Concurrency control applies only to production executions: those started from a webhook or
> trigger node. It doesn't apply to any other kinds, such as manual executions, sub-workflow
> executions, or error executions."

### What follows from it

The spike's `chunk_count + record_count` cost formula assumes every unit of work costs an
execution. If work is dispatched to **sub-workflows**, that assumption is wrong in the cheap
direction: a parent fanning out to N children costs **one** billable execution, not N+1, and the
children do not consume any of the 5 concurrent slots.

This makes **substrate 3 (sub-workflow dispatch, `Execute Workflow` with wait-for-completion off)**
by far the most attractive dispatch mechanism available on a Starter plan — it is the only one that
escapes both ceilings at once.

**It is also a confirmed candidate explanation for the P-10 anomaly** (`chunk_count = 1` projected
2 executions, measured 1): a child execution that was never counted would produce exactly that
discrepancy.

**Consequently P-13 is promoted from nice-to-have to the most decision-relevant open question in
the phase.** If a detached child's execution id cannot be correlated back to its parent, the most
attractive substrate becomes hard to observe and resume — which is precisely what 61-05's
"resume or fail loudly" must-have depends on. That probe is now the one that matters most.

### What is NOT established

- Whether "wait-for-completion **off**" is treated identically to a normal sub-workflow call for
  billing and concurrency purposes. The documentation does not distinguish them. Inferred, not
  observed.
- Whether the **executions list** and the **billed quota** agree. These are different systems; a
  child appearing in `GET /api/v1/executions` does not prove it was billed, nor the reverse.

---

---

## The three probed premises — RUN LIVE 2026-08-30, all answered

Operator granted the run. Machine-readable results: `61-PREMISE-PROBE-VERDICT.json`.
Total cost **5 n8n executions**; every `ZZ-PROBE-61-*` workflow was swept (instance verified
clean afterwards). Disarmed throughout — no HubSpot call, no provider call, no write window.

| Premise | Answer | Basis | Key observation |
| --- | --- | --- | --- |
| **P-07** | **true** | observed | Client round-trip 0.47s against a 5s wait; execution span 5.06s; the post-Respond `Set` node recorded `success`. An execution DOES keep running after its webhook response is sent. |
| **P-10** | **false** | measured | Real historical 2-record chunk (execution `11950`): formula projected **3**, executions list showed **1**. Delta **-2** — the formula OVER-states cost. |
| **P-13** | **true** | observed | A detached child's execution id IS recoverable from the parent's `Dispatch Child` runData, with `waitForSubWorkflow` **off** (`12036` -> `12037`) and **on** (`12038` -> `12039`) alike. Children also appear in the executions list. |

### P-13 is the decisive one, and it came back favourable

Sub-workflow dispatch is unmetered, uncapped **and observable**. The one thing that could have
disqualified the cheapest substrate did not. Detachment costs no correlation: the off case
behaved identically to the on case on both measures.

### A constraint discovered by failing

The first P-13 attempt failed with a 400 that is itself a finding, and is now recorded in the
probe's own source:

> `Cannot publish workflow: Node "Dispatch Child" references workflow <id> which is not
> published. Please publish all referenced sub-workflows first.`

**Any sub-workflow architecture must publish its children before the parent can be activated.**
That is a real deployment-ordering constraint on substrate 3, not probe scaffolding.

### P-14 — added 2026-08-30, operator-requested: can a workflow reference ITSELF?

**Answer: yes — activation succeeded.** Basis: observed. Cost: **0 executions.**

Asked because 61-05 chose substrate 1 and deferred substrate 3, and the operator wanted the
scale-up path de-risked while it was cheap. Substrate 3 has two possible routes: a
self-referencing `Execute Workflow` node, or a brand-new parent workflow with its own webhook
path (which would move the plugin's dispatch target). The self-reference is much the cheaper,
and P-13's publish-order constraint made it genuinely uncertain — at activation a
self-referencing workflow is its own unpublished dependency.

n8n resolved it without complaint (workflow `h2Sn4WGTNfmr4vLj`, activated, no error).

**Scope boundary, which matters:** activation only. **The webhook was never fired.** This says
nothing about whether a self-dispatch runs correctly, terminates, or how it is metered. The probe
workflow carries a depth guard, but that guard was never exercised — it exists so that an
accidental trigger cannot recurse without bound, not because recursion was tested. **Runtime
behaviour of a self-referencing dispatch remains UNPROBED**, deliberately: an unbounded
self-dispatch on a live 2,500/month instance is not a risk worth taking to learn something
activation already answered.

### What P-10 does and does not settle

Because P-13 established that sub-workflow executions ARE listed, the -2 shortfall is **not**
explained by children being invisible to the executions API — explanation (a), the formula
over-counting, is what the list supports.

Two residuals remain, and neither should be quietly closed:
- The scan filtered by the enrichment workflow's own id, so any child running under a
  *different* workflow id was out of that count's scope either way.
- **Listed is not billed.** The executions API and the billing quota are different systems.
  Nothing here observes what was actually charged.

The safe reading: the cost model is conservative — it over-projects. Nothing found suggests it
under-projects, which is the direction that would matter for a budget guard.

---

## The standing caveat

Everything above is **documentation**, not observation of this account. This repo's own history is
the argument for keeping that distinction sharp: CLAUDE.md §4.0's as-built deltas, the
`n8n-stored-vs-running-content` rule that a stored read-back proves nothing, and D-61-05's recorded
error of asserting deployed behaviour from source that no live lane reached.

Documented answers raise confidence enough to *design* against. They do not replace the disarmed
probes for P-07, P-10 and P-13, which observe what this instance actually does.
