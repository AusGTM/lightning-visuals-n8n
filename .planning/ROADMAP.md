# Roadmap: HubSpot Enrichment + ICP Scoring

## Milestones

- ✅ **v0.3** — archived (`milestones/v0.3-ROADMAP.md`)
- ✅ **v0.4 Reachability & Verification Debt** — shipped 2026-07-29
- ✅ **v0.5** — shipped (no MILESTONES.md entry; see the v0.5 ledger note in `MILESTONES.md`)
- ✅ **v0.6 Claude Plugin Entrypoint** — Phases 23–32, workstream `plugin-entrypoint` — shipped 2026-08-04
- ✅ **v0.7 HubSpot Scoring Engine Remediation** — Phases 39–43 — shipped 2026-08-08
- ✅ **v0.8 Execution Budget Safety** — Phases 44–45 — shipped 2026-08-11
- ✅ **v0.9 ICP Rubric Calibration & Veto Remediation** — Phases 46–50 (`milestones/v0.9-ROADMAP.md`, `milestones/v0.9-REQUIREMENTS.md`) — shipped 2026-08-19
- ⏸️ **v1.0 Direct Backfill & Scoring Coverage** — Phases 51–52. Phase 51 complete; **Phase 52 deferred INDEFINITELY** (2026-08-25, reaffirmed 2026-08-30 after its gates were satisfied). Not abandoned — deferred by decision.
- ✅ **v1.1 Unattended Session Runs** — Phases 53–63 (`milestones/v1.1-ROADMAP.md`, `milestones/v1.1-REQUIREMENTS.md`, `milestones/v1.1-phases/`) — shipped 2026-09-04
- 📋 **v1.2 Yield and Friction** — Phases 64–69 (`milestones/v1.2-ROADMAP.md`, `milestones/v1.2-REQUIREMENTS.md`) — **ACTIVE, not started**

## Standing facts

These outlive any single milestone. Read them before planning anything that writes.

- **The first live unattended, credit-spending batch has NOT run, and nothing is armed.** Phase 57 landed the ceilings, refusal-before-start and post-run proof; Phase 61's backend is deployed and disarmed-proven only. At 57-05's Task 4 gate the operator chose a small, *supervised* first live batch — explicitly not the unattended one. D-61-08's unattended gate stays shut until a phase asks and the operator answers (v1.2 `AUTO-04`).
- **The committed `n8n/*.json` is AHEAD of the running n8n Cloud instance** — regenerated and committed without deploying since 2026-09-02 (CLAUDE.md §13.0.2). An in-repo node is not evidence of what n8n is executing.
- **Never hand-edit `n8n/wf_*.json`** — change `n8n/code/*.js` or the builder and re-run `scripts/build_cloud_workflows.py`.

## Phases

<details>
<summary>✅ v1.1 Unattended Session Runs (Phases 53–63) — SHIPPED 2026-09-04 · 10 phases, 62 plans, 162 tasks</summary>

- [x] Phase 51: Backfill pipeline, credit sizing & dry run (3/3) — v1.0 carry-in, archived here
- [x] Phase 53: Operator-openable write grant (4/4) — verified by live operator walk, run 3
- [x] Phase 54: Single-pass armed dispatch (7/7)
- [ ] Phase 55: Async run — submit, poll, resume — **ABSORBED into 61** (D-61-08)
- [ ] Phase 56: The unattended pair pipeline — **ABSORBED into 61** (D-61-08)
- [x] Phase 57: Ceilings, refusal-before-start, and post-run proof (5/5) — completed 2026-09-01
- [x] Phase 58: Take what the operator actually has (6/6)
- [x] Phase 59: Frictionless write path (9/9)
- [x] Phase 60: Review-lane authority (5/5)
- [x] Phase 61: Autonomous batch runs (6/6) — absorbs 55 + 56
- [x] Phase 62: Suggest the contacts nobody named (12/12)
- [x] Phase 63: The unattended lane actually runs unattended (5/5) — 28/28 must-haves

**Closeout type:** override close. Phases 52, 55 and 56 carry no verification and none is
open work — 52 is deferred indefinitely by operator decision, 55 and 56 were absorbed into 61
so that they would *not* be planned separately. 11 open artifacts were acknowledged rather
than resolved at close; they are listed in STATE.md § Deferred Items and 5 of the 8 todos
among them are already scheduled as v1.2 phases.

</details>

### 📋 v1.2 Yield and Friction (Phases 64–69) — ACTIVE

Full detail in `milestones/v1.2-ROADMAP.md`; requirements in `milestones/v1.2-REQUIREMENTS.md`.

Every phase moves the system one direction — **yield more, stop less, without moving any
safety gate.** Seven of the eight source items came from the first two live
`suggest-contacts` rounds (Brisbane Roar FC, The Roma Turf Club), each with a filed todo
carrying its live evidence.

- [x] Phase 64: The ladder stops at the best page, not the first (completed 2026-09-04)
- [x] Phase 65: Round-empty re-entry, keyed on the cause (completed 2026-09-07)
- [x] Phase 66: Rich enrichment, not minimum enrichment (completed 2026-09-04)
- [ ] Phase 67: An autonomy flag with sensible defaults
- [x] Phase 68: State the price and keep moving (completed 2026-09-07)
- [ ] Phase 69: Held rows survive the round

**Binding on all six** (`SAFE-01`..`SAFE-05`): no `min_confidence` lowered, no
`fill_blank_only` weakened, no drop path softened; a refusal stays terminal; fetch and search
caps never reset; ceilings stay refusals in code, not prose; D-61-08's unattended gate stays
shut unless `AUTO-04` is explicitly answered.

**Items 1–2 of the operator's priority list are already done as quick tasks, not phases here:**
`260905-rf1` (one-word club titles now classify) and `260905-ad2` (a company may carry more
than one domain).

#### Phase detail (v1.2)

### Phase 64: The ladder stops at the best page, not the first

**Goal:** a company whose real staff list sits deeper than its first people-bearing page is
walked to that list.

**Brief:** `.planning/todos/pending/2026-09-05-fallback-is-keyed-on-ladder-empty-not-round-empty.md`
(first half).

- `SKILL.md:101`/`:299` currently stop the walk *"at the first one that yields people."* A
  contact page naming one receptionist ends the walk before `/board/` is read.
- Decide what "better" means and make it testable — more people, more office-bearer titles, a
  higher-ranked candidate path — rather than leaving it to the model's judgement in prose.
- `MAX_FOLLOWUP_FETCHES` is unchanged and still bounds the whole walk. Continuing further is
  spending the SAME budget better, never a larger one.

**Requirements:** LADDER-01, LADDER-02 (inherits SAFE-02, SAFE-03)

**Plans:** 1/1 plans complete

Plans:

- [x] 64-01-PLAN.md — the walk stops at a cumulative role-hit bar, accumulates a deduped
  union across walked pages, and reports how it ended

### Phase 65: Round-empty re-entry, keyed on the cause

**Goal:** a round that ends with nothing usable does not stop because an intermediate stage
reported success.

**Brief:** same todo (second half).

- The search fallback fires on **ladder**-empty (`eligible_after_ladder`), but the operator's
  intent is **round**-empty. On AU sporting clubs, which reliably publish a committee page,
  ladder-empty is rare and round-empty is common — which is why the fallback has never run
  outside its offline tests across two live attempts.
- **Do not build a blanket retry.** Neither live round would have been rescued by one:
  Brisbane's zero was a matcher failure (search re-finds the same titles) and Roma's was an
  email failure (search cannot produce a club-domain email — the waterfall supplies emails).
  Re-entry names its cause and routes accordingly; a single `round_empty` boolean would spend
  on exactly the two cases where spending cannot help.
- Three hard constraints: a refusal stays terminal even by a second route; `MAX_FOLLOWUP_FETCHES`
  and `MAX_FALLBACK_SEARCHES` do not reset, and `cap_exhausted` must not become a retry
  trigger; and it cannot literally be a loop — no plugin script may contain `while`
  (`test_report_sufficiency.py::_has_while_loop`).

**Depends on:** 64, and on the two quick tasks — until false zeros stop, this phase would be
designed against noise.

**Requirements:** LADDER-03, LADDER-04, LADDER-05, RICH-04 (RICH-04 re-routed from Phase 66 by operator ruling 2026-09-04 — `merge_enriched` lives in `preingest.py` (shared; the ruling said `suggest_contacts.py`, corrected by 65-RESEARCH.md), which 66's domain excludes; LADDER-03/04/05 were always mapped to Phase 65 in REQUIREMENTS.md's LADDER section but were missing from this line until 2026-09-07)

**Plans:** 2/2 plans complete

Plans:
**Wave 1**

- [x] 65-01-PLAN.md — the pure `round_outcome` cause classifier, its at-most-one cause-selected re-entry through `eligible_after_ladder`, and the per-company cause + breakdown the report reads (wave 1)

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 65-02-PLAN.md — RICH-04: `merge_enriched`'s allowlist widened to the field policy's promotable contact keys, with the dispatch-boundary strip and both callers traced (wave 2)

### Phase 66: Rich enrichment, not minimum enrichment

**Goal:** the waterfall fills every field it can confidently reach, instead of the minimum that
makes a contact usable.

**Brief:** `.planning/todos/pending/2026-09-04-phone-is-never-chased-only-accepted.md`.

- Measured: the contacts merge policy can promote **12** fields; the gate's `REQUIRED` list
  chases **3** (`email`, `jobtitle`, `mobilephone`). The other 9 are filled only if a provider
  volunteers them. Because that list also drives Lusha's selective reveal, a minimum became a
  ceiling.
- `phone` specifically is never asked for — the operator's stated target is phone AND email,
  with email-only as the fallback.
- `lv_linkedin_url` is in the policy at 85 and **has no producer at all**:
  `normalizeProviders.js` contains no `linkedin` reference, while Apollo and ZoomInfo both
  return one. It is arriving and being discarded.
- Live evidence: on a CREATE row with every field blank, the round discovered
  `Head of Marketing and Content` and `seniority: Director` and kept neither.
- Cost inverts the usual argument: Lusha bills flat per contact regardless of reveal-field
  count, and ZoomInfo's fields return in a request already paid for. The cost is mapping work.
- Deliverable includes a producer/consumer matrix per field, and the same audit for companies.

**Requirements:** RICH-01, RICH-02, RICH-03, RICH-05, RICH-06
**Plans:** 3/3 plans complete

Plans:
**Wave 1**

- [x] 66-01-PLAN.md — contacts lane: chase the landline end-to-end, give `lv_linkedin_url` a producer, widen `REQUIRED` to the full promotable set (wave 1)

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 66-02-PLAN.md — the producer/consumer matrix for both lanes, then the companies gate derived from it (wave 2)

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 66-03-PLAN.md — phone-and-email completeness visible in the operator's report, flagged never held (wave 3)

**Planning note:** RICH-04 (`merge_enriched`'s keep/replace rule for a CREATE row) is mapped to
this phase in REQUIREMENTS.md but is EXCLUDED by 66-CONTEXT.md's `<domain>`, which scopes Phase 66
to the n8n lane and explicitly excludes `suggest_contacts.py`. It currently has no phase. See the
66 planning return for the options.

### Phase 67: An autonomy flag with sensible defaults

**Goal:** the operator can let functions run without per-step intervention, deliberately and
per tier.

**Brief:** `.planning/todos/pending/2026-09-04-autonomy-flag-with-sensible-defaults.md`.

**Requirements:** AUTO-01, AUTO-02, AUTO-03, AUTO-04, AUTO-05, AUTO-06 (always mapped to Phase 67 in REQUIREMENTS.md's AUTO section; line added 2026-09-07 so the planner coverage gates see them)

- The safety scaffolding already exists (Phase 57: per-run ceilings, refusal-before-start,
  post-run proof; Phase 61: run scope, resume, held rows). **This is the missing switch, not
  missing safety.**
- **It reverses a recorded decision.** At 57-05's Task 4 gate the operator chose option-a — a
  small, supervised first live batch, explicitly not the first unattended credit-spending one.
  The phase must present that reversal as such, not smuggle it in as a config default.
- ~~Fails closed on `CEILING_UNKNOWN`, on an unread provider balance, and on a missing allowance
  key.~~ **Reversed 2026-09-07 (D-67-09): discloses the unknown state and proceeds; `CEILING_OVER`
  and `CapRefused` remain the bounds.** Does not replace `ALLOW_N8N_ARM` for the headless path.
- "All functions" is three tiers — read-only, spend-no-write, write — not one boolean.

### Phase 68: State the price and keep moving

**Goal:** the round stops halting on statements the operator cannot act on differently.

**Brief:** `.planning/todos/pending/2026-09-04-state-the-price-and-keep-moving.md`.

**Requirements:** FLOW-01, FLOW-02, FLOW-03, FLOW-04, FLOW-05 (always mapped to Phase 68 in REQUIREMENTS.md's FLOW section; line added 2026-09-07 so the planner coverage gates see them)

- Step 4 already branches: with a grant open it SHOWS the price and does not stop. The halting
  case is the no-grant branch, whose affirmative **is** what arms the run — that is consent,
  not a price confirmation. The two must not be conflated.
- The real friction found live: a round invoked with `grant approved for session` in its
  argument string correctly got no machine grant, and so hit the per-round ask a grant exists
  to avoid. Easier grant opening delivers the outcome with one consent point per batch.
- Includes an audit of every disclosure in these skills that halts but should not — price lines
  on a granted round, disarmed-status statements, provenance summaries, post-run reports —
  distinguished from genuine decision points, which stay.

**Plans:** 3/3 plans complete

Plans:

- [x] 68-01-PLAN.md — the pre-spend pause (`watch.pre_spend_pause`, 5-10s, once per round) and the
  test pinning `scheduled_arm.py` grant-free, so the new posture cannot reach the headless lane
- [x] 68-02-PLAN.md — the default path prices a grant over the batch, states it, pauses, opens it and
  proceeds, at all four batch skills; the ungranted ask survives as the interrupted path
- [x] 68-03-PLAN.md — D-59-06 re-stated honestly for implicit consent at all four sites, and the
  per-skill disclosure audit shipped as a ratchet with its verdict table

### Phase 69: Held rows survive the round

**Goal:** a correctly-held person is not lost when the session ends.

**Brief:** `.planning/todos/pending/2026-09-04-skill-step8-routes-holds-into-a-queue-that-refuses-them.md`.

- `SKILL.md` step 8 routes partition holds through `held_queue.build_entry`; `held_queue.save`
  raises `HeldQueueError` on `no_email` / `email_domain_mismatch`. Hit live on the Roma round.
- **The code is right and the skill is wrong.** `ALL_HOLD_CODES` is the match-gate vocabulary
  ("could not identify"); the partition codes mean "identified fine, declined to send".
  Widening the frozenset would let a suggestion-round decline enter the review queue wearing a
  match verdict's clothes. **Do not fix it that way.**
- The real question is durability: after Roma, the only record of two correctly-held committee
  members is a chat message. Either give suggestion-round declines their own store, or state
  plainly in the skill that they are report-only.
