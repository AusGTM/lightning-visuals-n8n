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
- 📋 **v1.2 Yield and Friction** — Phases 64–70 (`milestones/v1.2-ROADMAP.md`, `milestones/v1.2-REQUIREMENTS.md`) — **all six phases complete 2026-09-08; milestone not yet closed (`/gsd-complete-milestone`)**

## Standing facts

These outlive any single milestone. Read them before planning anything that writes.

- **The first live unattended, credit-spending batch has NOT run, and nothing is armed.** Phase 57 landed the ceilings, refusal-before-start and post-run proof; Phase 61's backend is deployed and disarmed-proven only. At 57-05's Task 4 gate the operator chose a small, *supervised* first live batch — explicitly not the unattended one. **Updated 2026-09-07 (Phase 67, AUTO-04): the gate has been ASKED and ANSWERED — the operator reversed the 57-05 decision, and autonomy now defaults ON for all three levels (`read_only`/`spend_no_write`/`write`), recorded verbatim in `operator-claude-plugin/skills/backend-control/SKILL.md`.** This is a decision, not an execution: Phase 67 ran nothing and armed nothing, so the first live unattended credit-spending batch still has NOT run and nothing is armed — only the standing REFUSAL that no phase may open this gate as a side effect is what changed, by explicit answer rather than default.
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
- [x] Phase 67: An autonomy flag with sensible defaults (completed 2026-09-07)
- [x] Phase 68: State the price and keep moving (completed 2026-09-07)
- [x] Phase 69: Held rows survive the round (completed 2026-09-08)
- [x] Phase 70: One merge, one result channel — n8n runtime truth (added 2026-09-09 from the first live batch UAT) (completed 2026-09-11)
- [x] Phase 71: A held new person lands in HubSpot with one reply (added 2026-09-12 after quick batch 260911-w6n) (completed 2026-09-12)

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

**Plans:** 4/4 plans complete

Plans:
**Wave 1**

- [x] 67-01-PLAN.md — the AUTO-04 reversal put to the operator first, then three named autonomy
  levels as default-setter settings keys, pinned unreachable from the headless arm path (wave 1)

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 67-02-PLAN.md — each batch skill reads its own level at the one ask-or-proceed site Phase 68
  left, and the three unknown bounds are disclosed and passed rather than refused (wave 2)

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 67-03-PLAN.md — the end-of-run report becomes mandatory at `contact-upload` and
  `suggest-contacts`, and the two paragraphs that forbade one of them are corrected (wave 3)

**Wave 4** *(blocked on Wave 3 completion)*

- [x] 67-04-PLAN.md — the reversal recorded where the arming posture is read, and release 0.41.0
  stating the changed write posture plainly (wave 4)

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

**Requirements:** HELD-01, HELD-02, HELD-03

**Brief:** `.planning/todos/pending/2026-09-04-skill-step8-routes-holds-into-a-queue-that-refuses-them.md`.

**Plans:** 3/3 plans complete

Plans:

- [x] 69-01-PLAN.md — the decline store and its own reason-code vocabulary (wave 1)
- [x] 69-02-PLAN.md — step 8 routes declines into it; step 9 reports this round and the backlog (wave 2)
- [x] 69-03-PLAN.md — the standalone drain skill: send / defer / delete / export (wave 3)

- `SKILL.md` step 8 routes partition holds through `held_queue.build_entry`; `held_queue.save`
  raises `HeldQueueError` on `no_email` / `email_domain_mismatch`. Hit live on the Roma round.
- **The code is right and the skill is wrong.** `ALL_HOLD_CODES` is the match-gate vocabulary
  ("could not identify"); the partition codes mean "identified fine, declined to send".
  Widening the frozenset would let a suggestion-round decline enter the review queue wearing a
  match verdict's clothes. **Do not fix it that way.**
- The real question is durability: after Roma, the only record of two correctly-held committee
  members is a chat message. Either give suggestion-round declines their own store, or state
  plainly in the skill that they are report-only.

### Phase 70: One merge, one result channel — n8n runtime truth

**Goal:** a batch with two identity lanes and two actions returns every row once, from the
write that happened, on one client result channel — and the offline harness would have
caught every finding the 2026-09-09 UAT found.

**Requirements:** TBD

(No milestone requirement IDs — the phase was added after v1.2-REQUIREMENTS.md was cut. The
locked decisions are D-70-01..19 in
`.planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-CONTEXT.md`.)

**Brief:** `.planning/todos/pending/2026-09-09-n8n-lanes-reconverge-by-name-reads-one-result-channel.md`
(seven instances of one idiom, F1/F5/F5b/F10/F11/F12 plus the July research-lane row loss).

- Not a debug continuation: the F1/F5/F10–F12 fixes patch sites; this phase retires the idiom.
- ~~Depends on the F10–F12 fixes landing and the UAT record closing.~~ Both done 2026-09-09
  (`e4415b9`; live proof on executions 12194/12196).
- Binding on all six (SAFE-01..05) applies unchanged; nothing armed during the phase.

**Plans:** 18/18 plans complete

+ 3 round-2 gap-closure plans (planned 2026-09-10, waves 1–2),

sequential on the builder file except 70-05 ∥ 70-06.

Plans:
**Wave 1**

- [x] 70-01-PLAN.md — Wave 0: the graph walker over the committed JSON, its own RED-detection unit tests, and the by-name-read detector proven against today's violations
- [x] 70-02-PLAN.md — Wave 1: TRACER — one ingest row end to end (Merge at the convergence, carry Merge across the HTTP hops, ack-only webhook, runData at the client); leads with the one-way contract checkpoint and closes on a disarmed live Merge-semantics probe before any expansion plan runs

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 70-03-PLAN.md — Wave 2: a Merge at every enrichment and review convergence point; the enrichment webhook answers with an ack; refusals become rows; the opt-in flag retired

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 70-04-PLAN.md — Wave 3: carry Merges at every provider/HubSpot hop, the last parameter-expression reads retired, `nodeRunRecovery.js` deleted, and the by-name-read assertion wired into generation

**Wave 4** *(blocked on Wave 3 completion)*

- [x] 70-05-PLAN.md — Wave 4: one canonical `write_request`, an IF-shaped gate emitting refusals, a real gate on the enrichment lane, one verdict for an update and its association
- [x] 70-06-PLAN.md — Wave 4: the client result channel — runData always, refusal before start on a missing API key, a write-only ledger, one per-row verdict, repo scripts migrated

**Wave 5** *(blocked on Wave 4 completion)*

- [x] 70-07-PLAN.md — Wave 5: the two mixed-batch acceptance tests, the operator-facing docs and version bump, and the disarmed live run whose rows must match the walker

**Gap closure** *(planned 2026-09-10 from `70-UAT.md` — G-70-2/G-70-3 blockers, G-70-4 minor; D-70-20/21/22)*

- [x] 70-08-PLAN.md — Wave 0: D-70-21 live rollback prepared — the pre-Phase-70 bundle pinned and tested, an operator runbook, a zero-write dry-run diff, and Gate 4 recorded
- [x] 70-09-PLAN.md — Wave 1: the walker corrected toward the engine, RED first — executions 12203 and 12206 reproduced against frozen copies of the graph that ran them, the literal D-70-20 mechanism priced, and the RED inventory taken
- [x] 70-10-PLAN.md — Wave 2: D-70-23 decided, then the sentinel mechanism gated in the generator, the starved carry Merge bypassed, the ingest lane green, and the Merge-input contract test landed
- [x] 70-11-PLAN.md — Wave 3: the enrichment, review and local lanes converted, the fifteen-input response Merge split, the contract made a generation-time refusal, and the whole harness green
- [x] 70-12-PLAN.md — Wave 4: G-70-4's like-with-like comparator, the observed-live platform facts recorded with their execution ids, and Gates 5 and 6 written up

**Gap closure, round 2** *(planned 2026-09-10 from `70-UAT.md` — G-70-5 blocker; D-70-24/25/26/27)*

- [x] 70-13-PLAN.md — Wave 1: TRACER — the self-referencing fan-out deleted from the enrichment graph, `scale_up: true` refused as a row, a self-dispatching node made a generation-time refusal, and the client's ability to ask for one retired
- [x] 70-14-PLAN.md — Wave 2: D-70-25 marker filtering at both response builders, RED-first on Gate 5's recorded recovered shape, plus execution 12316 frozen as a documented walker divergence
- [x] 70-15-PLAN.md — Wave 2: the retirement and the runaway's platform facts recorded with their execution ids, the two-minute burst watch made a standing deploy step, and Gates 7/8/9 written up

**Gap closure, round 3** *(planned 2026-09-10 from `70-UAT.md` — G-70-6 blocker; D-70-28/29/30/31)*

- [x] 70-16-PLAN.md — Wave 1: TRACER — every generated workflow flipped onto n8n's v1 execution order from one generator constant, a non-v1 body made a generation-time refusal, and the walker stopped claiming to model the legacy engine it was never observed to model correctly
- [x] 70-17-PLAN.md — Wave 2: the v1 setting pinned against every path that can revert it — both PUT paths, the bind pipeline, the bounce read-back and the proof driver's verdict
- [x] 70-18-PLAN.md — Wave 3: the source-cited engine rule and Gate 8's observations recorded with their tags and execution ids, the stale live-state note corrected, and Gates 10/11/12 written up with Gate 9 superseded

### Phase 71: A held new person lands in HubSpot with one reply

**Goal:** a rich `no_match` reveal of a new person (the Jimmy Busteed shape — usable email at a
company already in HubSpot) reads `new_person` and lands in HubSpot with ONE count-restating
reply, on both surfaces (`enrich-before-ingest` step 6's ready answer and `review-triage`'s one
table), with the operator never asked a question. Target function and UX carried from the F2
ruling (operator, 2026-09-11): most frictionless operator experience with relative safety,
review over approve, both routes offered with equal weight, absent company stays a server-side
downgrade (CLAUDE.md §13.0.1).

**Why a phase, not a fourth quick batch:** quick batch `260911-w6n` shipped every item to its own
plan and still left the headline false end to end — both callers seed `known_company_domains =
set()`, so `classify_facet` never returns `new_person` (design todo
`2026-09-11-known-company-domains-never-seeded-...`), and settlement is keyed on a positional
`row_id` that collides across runs (design todo `2026-09-11-held-queue-row-id-is-positional-...`).
Seams between parallel-planned items; no batch step owned the cross-item contract.

**Rulings needed before planning (discuss-phase):** (1) which legitimate source seeds
`known_company_domains` — step-2 match-confirmed domains of the same run, a HubSpot companies
domain lookup at facet time, operator statement only; (2) the stable held-entry identity that
replaces positional `row_id`, and who migrates the entries already on disk.

**Gate:** end-of-phase live UAT on the second-round `contact-upload` CSVs
(`docs/OPERATOR-AUTONOMOUS-BATCH-UAT.md` §1d) — the first run that can observe a `new_person`
row live. Nothing armed during the phase; SAFE-01..05 unchanged.

**Requirements**: TBD — no requirement IDs are mapped. The headline claim IS the acceptance
criterion: Jimmy Busteed reads `new_person` on both surfaces and lands with one `create all 1`
reply. Decisions D-71-01..06 (`71-CONTEXT.md`) are what the plans are verified against.
**Depends on:** Phase 70; quick batch 260911-w6n (plugin 0.47.0)
**Plans:** 3/3 plans complete

Plans:
**Wave 1**

- [x] 71-01-PLAN.md — the one cross-item seam: persist-time company-known stamp, stable held-entry identity, forbidden-marker key narrowing, legacy-document refusal (wave 1, tracer-led)

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 71-02-PLAN.md — both surfaces read the stamp, `rows_to_resume` keys on the stable identity, skill-sequence registry updated (wave 2)

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 71-03-PLAN.md — todo triage, plugin 0.48.0 release, and the single end-of-phase D-71-06 live gate (wave 3)

### Phase 72: Enrichment extras land in HubSpot

**Goal:** every field the waterfall finds and the operator paid for reaches the HubSpot contact it
was found for — mobile, LinkedIn, seniority, persona, city/state/country — instead of being dropped
at the ingest dispatch boundary (`preingest.strip_enrichment_extras`, `extraction.canonical_props()`'s
8-header set). Four operator rulings (2026-09-12, at the D-71-06 gate, recorded in `71-UAT.md` and
`.planning/todos/pending/2026-09-12-ingest-lane-drops-paid-for-enrichment-extras-map-them-instead.md`):
(1) fix the `lv_linkedin_url` / `linkedin_url` naming defect (no `linkedin_url` contact property
exists; `hs_linkedin_url` does); (2) map extras onto HubSpot properties at the boundary, never drop;
(3) conflicts resolve with a RECENCY bias — newer observation wins — replacing blanket
fill-not-overwrite; (4) multiple email / phone / mobilephone values are acceptable
(`hs_additional_emails`, `work_email`, `mobilephone`, `hs_whatsapp_phone_number`). Live evidence:
Busteed `352422766048` landed with email+phone+title only while his held row carried a mobile and
a LinkedIn URL (F71-5).

**Touches:** `config/column_mapping.yaml` + `n8n/code/columnMap.js` (YAML/JS parity), the ingest
lane's contact property assembly in `scripts/build_cloud_workflows.py` (regenerate + deploy + bounce),
`preingest.merge_enriched`'s conflict rule, `config/field_policy.yaml`, HubSpot custom properties
(live-only validation). §13.0.1 (server-side association), SAFE-01..05 unchanged.

**Gate:** end-of-phase live UAT re-running one held new person and confirming the mapped fields
on the created contact; nothing armed before it.

**Requirements**: TBD — no requirement IDs are mapped. Coverage is by DECISION ID: the plans are
verified against D-72-01..D-72-21 (`72-CONTEXT.md`), every one of which is cited in at least one
plan's `must_haves`.
**Depends on:** Phase 71
**Plans:** 4/8 plans executed

Plans:
**Wave 1**

- [x] 72-01-PLAN.md — Tracer: `mobilephone` lands on create and is protected on update; the ingest lane starts merging against real existing HubSpot props instead of `{}` (D-72-01, D-72-03)

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 72-02-PLAN.md — The remaining seven widened keys reach the ingest candidate; `hs_linkedin_url` as a second write target; derived three-way parity test (D-72-01, D-72-02, D-72-04)

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 72-03-PLAN.md — `merge_enriched`: LinkedIn name reconciliation, CREATE-time provider-wins, held-row carry, a truthful round-level `source_by_field`; the strip goes inert (D-72-19, D-72-05, D-72-20)

**Wave 4** *(blocked on Wave 3 completion)*

- [x] 72-04-PLAN.md — Recency: a real TTL gate + generalized system-correctable clause in all three engines, plus the ingest lane's `propertiesWithHistory` hop (D-72-06..09)

**Wave 5** *(blocked on Wave 4 completion)*

- [ ] 72-05-PLAN.md — Portal probe, the three `_2` slot declarations, and winner/loser slot routing stamped in provenance (D-72-10..13)

**Wave 6** *(blocked on Wave 5 completion)*

- [ ] 72-06-PLAN.md — Company geo/phone producers where a provider really supplies them; contact geo can never reach the company region signal (D-72-14..16)

**Wave 7** *(blocked on Wave 6 completion)*

- [ ] 72-07-PLAN.md — Closing: charter todo retired, history gap filed, plugin 0.49.0, CLAUDE.md as-built delta, D-72-17 gate spec

**Wave 8** *(blocked on Wave 7 completion)*

- [ ] 72-08-PLAN.md — The one live gate: create the properties, deploy + bounce disarmed, one armed record, read it back, delete it (D-72-11, D-72-17, D-72-21)
