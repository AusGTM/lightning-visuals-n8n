# Phase 57: Ceilings, refusal-before-start, and post-run proof - Context

**Gathered:** 2026-08-31
**Status:** Ready for planning

<domain>
## Phase Boundary

**A run cannot spend what it does not have, and proves afterwards that it wrote only what it was
granted.**

This phase turns the existing *disclosure* into an actual *constraint*, and makes the end-of-run
report say what really happened to every row.

**Closes:** RUN-05, AFTER-01, AFTER-03, G-4. Supplies the `ceiling_breach` producer that
`write_grant.py` already consumes but that nothing currently emits.

**It also releases a gate.** D-61-08 holds the first live unattended, credit-spending batch until
this phase lands. Phase 61's backend is deployed and disarmed-proven; nothing has been armed. This
phase is what makes that first real run survivable.

### The thing being overturned

`write_grant.py:116-153` is explicit that today's ceiling does nothing:

> *"These figures are this grant's ceiling, and they describe what this batch can cost — they do
> not prevent it. The ceiling is computed FROM the batch you named, so it cannot block anything
> that batch already implies."*

That is D-53-02, and it was correct when a human watched every send. It is not correct for an
unattended batch of hundreds. **Phase 57's core job is to make a ceiling refuse.**

### Out of scope

- Re-running Phase 52's backfill (deferred indefinitely, 2026-08-30).
- The scheduled/cron poller's own double pass (OP-54-02, `WINDOWS.md` 27) — headless paths are
  out of this milestone per D-1.1-01.
- Changing the non-clobber merge policy, the write-safety gates, or per-send armed-window
  narrowing. Ceilings sit *beside* those guards, never in place of them.

</domain>

<decisions>
## Implementation Decisions

### Ceiling authority — what a breach does

- **D-57-01:** A mid-run ceiling breach **holds the remaining rows and lets the batch finish.**
  Spending stops; unspent rows go to the held queue with a ceiling reason; the run completes and
  the operator gets one review pass. The grant is then closed by emitting `ceiling_breach`
  (`write_grant.CLOSED_CEILING_BREACH`, already accepted at `write_grant.py:667,909,932` and
  pinned by `test_write_grant.py:1507`).
  — **Reversibility:** costly — the hold path is shared with D-61-07's confidence holds and with
  61-06's no-company holds; changing the breach shape later means re-deciding what a held row
  means in all three producers and re-cutting the review queue's reason vocabulary.

  **Why not abort:** an abort leaves a partial batch the operator must reconcile by hand, and rows
  already dispatched may still land — the opposite of the "one run, one review" shape D-61-07
  established. Holding is the same mechanism the system already uses for "we should not proceed on
  this row", applied to a new reason.

  **Why mid-run enforcement is needed at all, not just RUN-05's pre-flight refusal:** P-10 measured
  the `chunk_count + record_count` projection as *over*-stating (real 2-record chunk projected 3,
  listed 1). A projection that is not exact cannot be the only guard. Note the direction — nothing
  found suggests it ever *under*-projects, so pre-flight refusal is conservative rather than
  permissive; mid-run enforcement covers the case where reality diverges anyway.

### Unknowable budgets — what a ceiling does when blind

- **D-57-02:** An **unreadable balance does not block the run.** It is disclosed at grant time and
  named in the end-of-run report as an explicit blind spot.
  — **Reversibility:** reversible — a per-provider policy switch; no stored shape depends on it.

  **Why not refuse:** G-4 records that **two of three provider balances currently read `unknown`**
  (Apollo `unrecognized_response_shape`, expected; ZoomInfo `provider_error`). Refusing on unknown
  would block essentially every run today, which makes "refuse" indistinguishable from "the feature
  is off" — a guard that always fires teaches the operator to bypass it.

  **The honesty requirement this creates.** Because the ceiling cannot fully guard provider spend
  while a balance is unreadable, the report must not imply it did. It says which balances were
  readable, which were not, and therefore which part of the spend was actually bounded.

  **This interacts with D-57-01 and the planner must not miss it.** With provider balances partly
  blind, the *mid-run breach* is doing more protective work than it would otherwise — it becomes
  the main thing standing between an unattended batch and an overspend. How confidently a breach
  is **detected** therefore matters more under this combination. Detection quality is a first-class
  concern of this phase, not an implementation detail.

  **G-4 is in scope as a fix, not just a disclosure.** Improving the Apollo and ZoomInfo balance
  reads narrows the blind spot directly, and is the cheapest available increase in how much of the
  spend is genuinely guarded.

### Report vocabulary — written vs would-have-been

- **D-57-03:** The report **preserves the backend's own distinctions.** `written_records.classify_item`
  currently collapses every non-write action into `not_written`; that mapping widens to:

  | Outcome | Backend `action` | What the operator does |
  | --- | --- | --- |
  | `written` | `create`/`update` **with** an `hs_object_id` | nothing |
  | `created_id_unknown` | `create` whose response carried no id | nothing; id unrecoverable, never fabricated |
  | `gated` | `write_blocked` | **open a grant and re-send — this row would have been written** |
  | `held` | `review`, `needs_match_review` | review the row and decide |
  | `failed` | `research_failed`, `recompute_refused` | retry, or fix the input |
  | `no_action` | `skip`, `proposed` | **nothing — these are successes** |

  — **Reversibility:** costly — `written_records` entries are a persisted on-disk artifact; a later
  change to the outcome words means either migrating existing per-run files or teaching every
  reader two vocabularies.

  **This is not invention.** Every distinction above already exists in the backend's output and is
  being discarded at the client boundary. Two consequences of today's collapse are concrete
  defects: a `write_blocked` row is indistinguishable from a failure (**AFTER-03's exact case**),
  and `skip`/`proposed` rows — which are successes — currently make a clean run read as though
  half of it did not land.

  **`created_id_unknown` stays as-is.** It is the honest record of a create whose response carried
  no id (`written_records.py:38-48`); the fix for it belongs to whoever restores a post-write
  confirmation, not here. Never fabricate an id to make the report tidier.

### What refusal offers instead

- **D-57-04:** A run that would exhaust the allowance **auto-splits across runs**: it breaks the
  batch into affordable runs and queues the remainder, so the whole batch completes over time
  without the operator re-deciding each round.
  — **Reversibility:** costly — the queued-remainder store is a new persisted artifact other
  surfaces will read; removing it later means re-deciding what happens to a partially-run batch.

- **D-57-05:** **Auto-split queues WORK, never AUTHORITY.** (DERIVED — not asked; it follows from
  an existing operator ruling, and the planner must honour it.) GRANT-06 is that a grant is never persisted
  and never rehydrated, and 61-06 restated it: *"A resumed run gets a FRESH grant."* So the
  remainder queue holds rows still to do; it does **not** carry permission to write them. Each
  subsequent run opens its own grant.
  — **Reversibility:** one-way — persisting authority across runs would breach GRANT-06, and
  unwinding it means revoking a capability an operator had already been given. Treat as a hard
  constraint, not a preference.

  **The tension to state plainly in the operator-facing text:** auto-split is the most autonomous
  option and it schedules *future spend* at the moment of one yes. D-57-05 is what keeps that
  honest — the schedule is a plan of work, and each run's spend is still separately authorised.
  If the planner finds it cannot preserve both auto-split and GRANT-06, **that is a checkpoint for
  the operator, not a judgement call.**

### Claude's Discretion

- Where the ceiling check lives (client pre-flight, backend node, or both). The arithmetic is
  client-side today (`write_grant.envelope`), the spend is backend-side — follow the evidence.
- The remainder queue's storage shape. **Strongly prefer reusing `held_queue.py`'s durable-write
  idiom** (`durable_paths._atomic_write_0600`) over a second persistence mechanism; a second store
  is the duplication this codebase keeps paying for. Whether a queued remainder belongs *in* the
  held queue or beside it is a real design question.
- How a breach is detected mid-run (post-chunk reconciliation vs a running tally) — but see
  D-57-02: detection confidence is load-bearing here.
- Report format and delivery surface, as long as AFTER-01's contents are all present.

### Reviewed Todos (not folded)

- **Enrichment throughput — 82% of every full run is two sequential Anthropic calls**
  (`.planning/todos/pending/2026-08-04-enrichment-throughput-ceiling.md`). **Considered and not
  folded**, but flagged for the planner: this phase sets a ceiling on Anthropic dollars, and this
  todo is the largest single component of that spend. It is an optimisation, not a guard, so it
  does not belong in a phase about refusing — but the ceiling arithmetic should be written so that
  fixing this later does not invalidate it.
- **Sweep crontab pins a versioned plugin path** — headless/cron path, out of scope per D-1.1-01.
- **UAT 2.2 header aliases** — ingestion mapping, unrelated to ceilings.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### The thing being overturned, and the grant model
- `operator-claude-plugin/scripts/write_grant.py` §116-153 — the verbatim "ceiling is disclosure,
  not constraint" text (D-53-02) this phase overturns; `EXECUTIONS_BASIS` at :139;
  `envelope()` at :183 (the existing arithmetic); `CLOSED_CEILING_BREACH` at :667 and the
  breach branch at :909/:932 — the consumer with no producer.
- `operator-claude-plugin/tests/test_write_grant.py:1507` — `test_a_ceiling_breach_closes_the_grant_rather_than_continuing`, already green against a breach nothing emits.
- `.planning/phases/61-autonomous-batch-runs/61-06-PLAN.md` §Task 3 — GRANT-06, "a resumed run gets
  a FRESH grant", and the in-memory-only created-record admission. Binds D-57-05.

### Requirements
- `.planning/milestones/v1.1-REQUIREMENTS.md` — RUN-05, AFTER-01, AFTER-03 (all unticked), G-4 at
  :56, and AFTER-02 (ticked by 61-04/61-06) for what the held queue already does.

### Report and outcome plumbing
- `operator-claude-plugin/scripts/written_records.py` — module docstring §38-48 (the three
  outcomes and why `created_id_unknown` exists), `classify_item` (the collapse D-57-03 widens),
  `written_records_path(run_id)` at :118-128 (per-run scoping; REVIEW-C16 requires this, never the
  path-less `load()` which aggregates historical runs).
- `operator-claude-plugin/scripts/held_queue.py` — the durable queue D-57-01 routes breach-held
  rows into, and the write idiom the remainder queue should reuse.
- `scripts/build_cloud_workflows.py` — the emitting side of every `action` value in D-57-03's
  table.

### Budget reality
- `CLAUDE.md` §13.0.3 — n8n platform facts, each tagged `[documented]` / `[observed live]` /
  `[measured]`. Load-bearing here: Starter is **5 concurrent / 2.5K per month with FIFO
  queueing**, the executions list **is not** the billing quota, and the cost formula **over**-states.
- `.planning/phases/61-autonomous-batch-runs/61-PREMISE-DOCS-FINDINGS.md` — P-05 (no separate API
  quota documented), P-10 (the measured over-projection), P-12 (no usage endpoint, so every budget
  comparison is against the CONFIGURED allowance, never what is left this month).
- `operator-claude-plugin/scripts/chunking.py` — `chunk_ceiling` at :157, `CEILING_KEY` at :56
  (`max_records_per_chunk`), and `failed_batch`'s already-re-sendable specification.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `write_grant.envelope()` — already computes projected executions, provider credits and the chunk
  ceiling, and already renders the arithmetic for an operator. RUN-05's "refuses with the
  arithmetic" is mostly a matter of making this refuse rather than narrate.
- `write_grant`'s `ceiling_breach` close path — the consumer exists and is tested. This phase
  writes the producer.
- `held_queue.py` — durable, 0600, forbidden-name-refusing, carries a reason and a per-hold-code
  resume fingerprint. D-57-01's breach-held rows and (probably) D-57-04's remainder both belong on
  this machinery rather than a new one.
- `chunking.failed_batch` — an existing well-formed re-sendable specification; auto-split should
  hand back this shape, not derive a second one.

### Established Patterns
- **Disclosure-not-constraint** is the pattern being deliberately broken here — and it is written
  down as an operator ruling (D-53-02), so the plan must say so explicitly rather than quietly
  contradicting it.
- **Hold, don't block, don't guess** (D-61-07) — the shape D-57-01 reuses for a new reason.
- **One implementation of a rule** — CLAUDE.md's as-built deltas repeatedly record the cost of a
  second copy. Applies hard to the remainder queue.
- **Documented vs observed** — CLAUDE.md §13.0.3's tagging. Any ceiling arithmetic that rests on
  a `[documented]` fact must say so; the sub-workflow metering exemption in particular is
  documented and **not** verified against billing.

### Integration Points
- Client pre-flight: `write_grant.envelope()` → refusal decision → auto-split.
- Mid-run: wherever per-chunk outcomes are reconciled (`chunking.merge_chunk_verdicts`,
  `run_state.read_progress`) is where a running tally could detect a breach.
- Post-run: `written_records` (outcome vocabulary) + `run_manifest`/`run_state` (per-row verdicts)
  are the two halves AFTER-01's single report must join.

</code_context>

<specifics>
## Specific Ideas

- The end-of-run report is what the operator reads **instead of watching the run**. Every distinct
  word in D-57-03's outcome table corresponds to a distinct operator action; that is the test for
  whether a distinction earns its place.
- A guard that always fires is indistinguishable from a feature that is off — the reasoning behind
  D-57-02, and worth applying to any other refusal this phase adds.
- "Written" must never be inferred. `created_id_unknown` exists precisely because an id that did
  not come back must not be invented, and that discipline extends to the whole report.

</specifics>

<deferred>
## Deferred Ideas

- **Per-provider spend ceilings** (as opposed to one aggregate ceiling) — raised implicitly by
  D-57-02's per-provider blind spots. Worth its own consideration once the balance reads are
  fixed; not in scope here.
- **Restoring the post-write confirmation** that would eliminate `created_id_unknown` — scoped out
  in 59-01 and still out.
- **Enrichment throughput optimisation** — see Reviewed Todos above.

</deferred>
