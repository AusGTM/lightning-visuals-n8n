# Roadmap: HubSpot Enrichment + ICP Scoring

## Milestones

- ✅ **v0.3** — archived (`milestones/v0.3-ROADMAP.md`)
- ✅ **v0.4 Reachability & Verification Debt** (shipped 2026-07-29)
- ✅ **v0.5** — shipped (no MILESTONES.md entry; see Ledger gaps below)
- ✅ **v0.6 Claude Plugin Entrypoint** — Phases 23–32, workstream `plugin-entrypoint` (shipped 2026-08-04)
- ✅ **v0.7 HubSpot Scoring Engine Remediation** — Phases 39–43 (shipped 2026-08-08)
- ✅ **v0.8 Execution Budget Safety** — Phases 44–45 (shipped 2026-08-11)
- ✅ **v0.9 ICP Rubric Calibration & Veto Remediation** — Phases 46–50, archived (`milestones/v0.9-ROADMAP.md`, `milestones/v0.9-REQUIREMENTS.md`) (shipped 2026-08-19)
- ⏸️ **v1.0 Direct Backfill & Scoring Coverage** — Phases 51–52 (Phase 51 complete; **Phase 52 deferred by the operator 2026-08-25** in favour of v1.1)
- 🚧 **v1.1 Unattended Session Runs** — Phases 53–60 (`milestones/v1.1-ROADMAP.md`, `milestones/v1.1-REQUIREMENTS.md`)

## Phases

### 🚧 v1.0 Direct Backfill & Scoring Coverage (Phases 51–52)

Backfill the ~646 never-scored HubSpot companies with ZoomInfo firmographics plus targeted
research, in-session, writing the scoring inputs and the six numeric properties HubSpot's
calculation engine reads. Zero n8n executions — the operator has no credits for it, and none are
needed: HubSpot already derives `lv_icp_fit_score` and `lv_icp_tier_derived` from those six
numbers on its own. Decisions in `.planning/MILESTONE-CONTEXT.md`; requirements in
`.planning/REQUIREMENTS.md`.

- [x] **Phase 51: Backfill Pipeline, Credit Sizing & Dry Run** - Size the population and the
      ZoomInfo credit cap live, pin the thousands-to-dollars revenue conversion, and dry-run a
      sample's exact PATCH payloads and pre-registered tier predictions — zero writes

- [ ] **Phase 52: Staged Canary Execution & Safety Verification** — ⏸️ **DEFERRED 2026-08-25**
      (operator, in favour of v1.1 Phase 53 — the client is blocked on the write path). Write the
      credit-capped population in gated stages (1 → 5 → 25 → chunked remainder), polling every
      result against its committed prediction, and close by proving the 66 already-scored
      companies are untouched. **On resume:** re-derive Phase 51's population and credit sizing
      before planning — the dry-run artifacts were finalized 2026-08-19 and drift with every
      enrichment run — and resolve the deferred FILL-04 third-disposition question.
      **Gated on Phases 59 and 55** (operator ruling 2026-08-27): the ~646-company run goes
      through the cheap, low-ceremony write path, not the current one. Do not resume 52 first.

### 🚧 v1.1 Unattended Session Runs (Phases 53–60)

One operator grant at session start carries a batch through ingest → enrichment → HubSpot write,
unattended. Driven by a client UAT on 2026-08-25 that found three arming surfaces for one write,
a write path unreachable from the operator's own surface (`ALLOW_N8N_ARM` is a shell environment
variable), and a design that runs the provider waterfall twice per written record. Full detail:
`milestones/v1.1-ROADMAP.md`; evidence: `quick/260825-contact-company-association/UAT.md`.

- [ ] **Phase 53: Operator-openable write grant** - Replace the interactive path's
      `ALLOW_N8N_ARM` dependency with an admin-enabled capability plus an operator-opened session
      grant that is bounded, expiring and revocable — no terminal, no loss of record scoping
      — **4 plans** (`53-01` .. `53-04`), planned 2026-08-25.
      **⚠ OPERATOR WALK RUN 2026-08-28 — GRANT-01 STILL NOT TICKED** (record: `53-WALK-RECORD.md`).
      The walk found the grant machinery sound but the flow it serves broken: `enrich-before-ingest`
      step 5's documented `merge_enriched(rows, outcome.responses)` loses ALL enrichment silently
      (`dispatch_plan` returns per-chunk lists; every row lands in `unanswered`). Measured live:
      as documented `unanswered: 1` / email `None`; flattened, the email is there. Halted before
      any HubSpot write. Zero writes. Original note follows.
      **(surfaced 2026-08-28).** All four plans executed and the
      ledger read `Complete (verified)`, but `53-04-SUMMARY.md` records Task 3 as a blocking
      checkpoint that was never performed: *"the phase's own success criterion for GRANT-01 is
      the operator walk… Ticking it on the strength of tests would be exactly the claim G-2
      disproved — every component correct, the composition broken."* **Nobody has ever opened a
      grant and run a batch under it.** The 2026-08-27 phase-54 session is the argument for
      doing so: every component passed its tests and the composition broke twice on
      authorization locks nobody had walked. Step 1 (admin sets `allow_write_grants`) is
      already satisfied — verified `true` on 2026-08-28; steps 2–7 run from the operator's
      chair. Script: `53-04-PLAN.md` Task 3, restated in `59-CONTEXT.md` § specifics.
      **Phase 59 is blocked on this walk by operator decision 2026-08-28.**

- [x] **Phase 54: Single-pass armed dispatch** *(complete 2026-08-27, verified 9/9 truths,
      5/5 gap findings closed)* - A record is enriched once: no
      derive-then-rearm-then-derive-again, and the measured saving proven live before it is claimed
      — **7 plans** (`54-01`..`54-05`, plus gap closure `54-06`/`54-07`). Live proof: one real
      HubSpot write on contact `347569451461`, clear-and-stamp branch only; the promote branch
      remains test-proven, never live-proven, for want of a contacts candidate producer. Total
      live cost: 10 n8n executions, 1 write, 0 provider credits, 0 Anthropic calls.

- [ ] **Phase 55: Async run — submit, poll, resume** - A batch stops being bounded by n8n Cloud's
      ~100s response window; run state survives a restart or fails loudly — **pulled ahead of
      Phase 52** (operator ruling 2026-08-27) so the backfill is not run at `max_records_per_chunk:
      2`. Owns the response-window ceiling and the chunk cap; Phase 59 deliberately does not touch
      them. **Sequenced after 59**, which settles what a grant authorizes before async runs start
      outliving one. Still spike-first: n8n Cloud's execution model, not our code, decides what is
      possible here — if the spike fails, Phase 52 runs at chunk=2 and that is an accepted outcome.

- [ ] **Phase 56: The unattended pair pipeline** - One grant carries ingest → enrich → create →
      associate, creates included, held rows queued rather than guessed

- [ ] **Phase 57: Ceilings, refusal-before-start, and post-run proof** - A run cannot spend what
      it does not have, and proves afterwards it wrote only what it was granted

- [x] **Phase 58: Take what the operator actually has** *(complete 2026-08-26, verified 31/31)* - Every input an operator holds
      (screenshot, paste, URL, bare name) resolves to a company the backend can act on; missing
      domains researched then confirmed before write; refusal is the last resort — promoted
      ahead of 54–57 by operator decision 2026-08-25

- [ ] **Phase 59: Frictionless write path** — **PLANNED 2026-08-28** (the blocking walk ran
      2026-08-28; see `59-CONTEXT.md` and `53-WALK-RECORD.md`). Still runs before Phase 55, and
      both before Phase 52.

      **Goal:** an operator who has granted once can see afterwards exactly which HubSpot
      records the run wrote — even when the run died partway or was revoked mid-flight — is
      told once at session start that a started run finishes, cannot have a routine test run
      spend money on their behalf, and is offered a resolvable proposal instead of a dead end
      wherever a gate used to simply refuse.

      **Plans:** 6 plans, 5 waves. Code only — the Phase 53 operator walk stays a Phase 53
      checkpoint (operator ruling 2026-08-28), so every plan is autonomous.

      Plans:

      - [x] 59-01-PLAN.md — TRACER: durable written-records artifact, flushed per chunk inside
            `dispatch_plan`, proven to survive a mid-loop interruption and a revoked run (D-59-07b)

      - [ ] 59-02-PLAN.md — root `tests/conftest.py` ambient-credential guard, gated on
            `RUN_LIVE_PARITY` rather than a marker that does not exist in this repo (D-59-04)

      - [ ] 59-03-PLAN.md — retire D-53-05's pre-emptive two-lane disclosure across four
            surfaces, replaced by a plain statement plus a pointer to the written list (D-59-07a)

      - [ ] 59-04-PLAN.md — the plugin's first `hooks/`: a `SessionStart` note that a started
            run continues to completion, instead of a grant-aware dispatch loop (D-59-06)

      - [ ] 59-05-PLAN.md — the gate inventory, and the extraction identity gate converted to
            resolve-then-propose with an unlaunderable closed provenance vocabulary (D-59-08)

      - [ ] 59-06-PLAN.md — the remaining CONVERT gates: enrichment-lane refusals and the
            walk's FINDING 1 grant dead end, with the authorization control untouched (D-59-08)

      Planning artifacts: `COVERAGE.md` (reasoned no-external-API declaration — this phase
      integrates nothing new), `59-VALIDATION.md`, and `59-GATE-INVENTORY.md` produced by 59-05.

      **The walk gave this phase real scope.** Its headline finding is a live silent-data-loss
      defect on the operator's own headline flow — `merge_enriched` filing complete provider
      answers under `unanswered`, the group meaning "nothing is known about this row". That has a
      strong claim on this phase or on a fix preceding it. D-59-08 (resolve-and-propose,
      cross-cutting) explicitly must NOT ship before it: a propose flow built on a merge that
      drops answers will propose from nothing and report "nothing known" about a fully-answered
      row.

      **Why deferred.** Discussing this phase on 2026-08-28 found two of the three items below
      mis-scoped, both from reading code review rather than the codebase:
      *(a)* the "session grant answers the per-send ask" item is **already built** — D-53-06
      shipped, `enrich-records/SKILL.md:182-222`; and
      *(b)* the "collapse the kill switches" item is **wrong as written** — the review lane is
      excluded from grants deliberately (`write_grant.py:66-69`, 30-01 D-02/D-08e), so deleting
      `ALLOW_REVIEW_SUBMIT` with nothing behind it leaves that lane authorized only by a deploy an
      operator cannot run, making it harder rather than easier. That went to its own phase
      (D-59-03).
      What survives untouched is the ambient-credential guard (D-59-04) and the grant-vs-run
      lifetime question. The rest is scoped after the walk says what is actually broken.

      **The bullets below are retained as history, not as scope.** Read `59-CONTEXT.md` first.

      - **Collapse the review-write kill switches.** Remove `ALLOW_REVIEW_SUBMIT`
        (`operator-claude-plugin/scripts/review_decision.py`) outright; `ALLOW_HUBSPOT_REVIEW_WRITES`
        plus the record allowlist survives as the single authority, because it is the one an
        operator cannot flip by editing a local file. Remove the now-dead `env.ALLOW_REVIEW_SUBMIT`
        from `.claude/settings.local.json` rather than leaving it behind. **Evidence:** on
        2026-08-27 a write the operator had already explicitly authorized was stopped twice — first
        by `ALLOW_REVIEW_SUBMIT` (`submit_not_enabled`), then by the backend allowlist — costing two
        human round trips and an arm-deploy for one six-property clear-and-stamp on one contact
        (`54-LIVE-PROOF.md`).

      - **Standing grant answers the per-send ask.** Phase 53 already shipped the bounded, expiring,
        revocable session grant; VOCAB-05's per-send consent still fires on top of it. An in-scope,
        unexpired grant answers the ask — asked once per grant, not once per send. Still asks when a
        send exceeds the grant's scope, cap or expiry.

      - **Define grant lifetime vs run lifetime — before Phase 55 needs it.** `revoke_grant` today
        refuses only the *next* send: `dispatch_plan` never consults a grant mid-loop, so a running
        dispatch finishes every remaining chunk under the arm it opened with (tested by
        `test_a_revocation_midway_does_not_stop_a_running_dispatch`). Bounded today; once 55 makes
        runs outlive their request, a grant can expire mid-run with no defined answer. Decide it
        here: either the run inherits the grant it started under, or `dispatch_plan` becomes
        grant-aware.

      - **Make the credential leak structurally impossible, not merely absent.** Folded in by
        operator decision 2026-08-27 (does not affect Phase 55, so it waits for 59). Add a root
        `tests/conftest.py` whose autouse fixture strips `ANTHROPIC_API_KEY` /
        `HUBSPOT_PRIVATE_APP_TOKEN` from `os.environ` unless a test is `@live`-marked, mirroring
        the reasoning `operator-claude-plugin/tests/conftest.py` already states for its own
        `no_network` fixture: *by construction rather than by discipline*.

        **Why, from evidence (2026-08-27, phase 54's regression gate).** A single module-level
        `load_dotenv()` in `tests/test_company_native_properties.py` pushed `.env` into
        `os.environ` at COLLECTION time, so `tests/test_merge_policy.py` — whose own header reads
        *"Fully OFFLINE and DETERMINISTIC — no Anthropic call, no network, no API key"* — made
        real billable Anthropic calls on every full-suite run. Fixed in commit `89c9871`; the
        full suite went 169s → 10.8s, and that 158-second drop was the live API traffic.

        **A sweep confirmed only that one instance existed** — `operator-claude-plugin/tests/`
        has zero `load_dotenv` calls, every other hit is inside a docstring wrapper idiom or
        explicitly deferred out of import (`main.py` / `src/service.py` both carry a "NOT called
        at module import" note), `scripts/apply_fit_score_formula.py`'s module-level call is
        imported by nothing, and no `pytest-dotenv`/`pytest-env` plugin or config `env` block
        exists. So this item is not cleanup; it is the guard that stops the NEXT one.
        **Two facts make it worth doing:** the root `tests/` suite has no `conftest.py` at all,
        and the plugin suite's `no_network` guard patches `requests` — while the Anthropic SDK
        uses `httpx`, so it would not have caught these calls either. Client construction sites
        to cover: `src/classifier_haiku.py:57`, `src/validator_sonnet.py:36`, and
        `src/web_research.py:126` (a bare `Anthropic()` reading the ambient key).

      **Deliberately untouched** (operator-confirmed load-bearing, 2026-08-27): the n8n
      write-safety gate nodes (HubSpot has no rollback; a bad merge hits ~700 live records), the
      material-conflict judge gate (caught a real false veto — execution `11983`, Series Futsal),
      and the non-clobber merge policy. Out of scope: the response-window ceiling and
      `max_records_per_chunk`, both owned by Phase 55.

- [ ] **Phase 60: Review-lane authority** - Split out of Phase 59 by operator decision
      2026-08-28 (`59-CONTEXT.md` D-59-03), to run **after** Phase 53's operator walk.
      Approving a flagged record is human triage, not unattended running — it is not on the
      ingest → enrich → write path and does not belong in a phase about that path.

      **The problem.** The review lane is the one lane grants deliberately do not reach
      (`write_grant.py:66-69` / 30-01 D-02/D-08e: *"arming a dispatch grants nothing on the
      review path, and `ALLOW_REVIEW_SUBMIT` is its own gate"*). So on 2026-08-27, approving a
      single flagged contact fell back to a plugin-side kill switch **plus** an admin-run
      arm-deploy — G-2's exact shape, still live on this one lane. Two human round trips for a
      six-property clear-and-stamp on one record (`54-LIVE-PROOF.md`).

      **Options, for that phase to choose between — not pre-decided:**
      (a) an admin-set settings key mirroring D-53-01's `allow_write_grants` — keeps 30-01's
      separation, removes the shell dependency; (b) make the review lane grantable — most
      friction removed, but deliberately reverses that separation and needs D-53-05's
      recorded-edit discipline; (c) accept the admin deploy as correct for occasional triage.
      **Not an option:** deleting `ALLOW_REVIEW_SUBMIT` with no replacement — that leaves the
      lane's only authority behind a deploy an operator cannot run.

## Phase Details

### Phase 54: Single-pass armed dispatch

**Goal**: A record is enriched once — no derive-then-rearm-then-derive-again. When a grant is
open the dispatch runs inside the armed window from the start, so there is no unarmed first
pass to throw away. The `write_blocked`-then-arm path stays reachable for the ungranted case
and is reported as what it is: a rehearsal that costs a second pass if it proceeds to a write.
The saving is **measured live on one record before it is claimed** (projection: 2 provider
passes → 1, ~$0.07 → ~$0.035 Anthropic, 2 executions → 1). Full detail:
`milestones/v1.1-ROADMAP.md` § Phase 54; defect: `milestones/v1.1-REQUIREMENTS.md` § G-3.

**Depends on**: Phase 53 (the grant this dispatch runs inside)

**Requirements**: G-3

**Also carries** (deferred here 2026-08-26): the contact review-flag lane — contacts get
flagged `lv_enrichment_needs_review` but no lane clears a contact flag.

**Plans**: 7/7 plans executed

- [x] 54-01-PLAN.md
- [x] 54-02-PLAN.md
- [x] 54-03-PLAN.md
- [x] 54-04-PLAN.md
- [x] 54-05-PLAN.md
- [x] 54-06-PLAN.md — gap closure WR-01/02/03: contacts review lane truth-up (widen the decision
      fetch to the whole contacts policy, correct three stale comments, scope the enum-guard claim),
      rebuild, deploy disarmed

- [x] 54-07-PLAN.md — gap closure WR-04: one bound, not two, in the Anthropic-spend sentence, and a
      test that checks the meaning

**Gap closure** (operator decision 2026-08-27, `54-VERIFICATION.md`): the phase goal stays 6/6
verified. All four findings are dormant — no live contacts candidate producer exists — and are
being closed by operator choice, not because anything is broken. Run
`/gsd-execute-phase 54 --gaps-only`.

### Phase 58: Take what the operator actually has

**Goal**: Every input an operator holds resolves to something the backend can act on, and a
refusal is the last resort rather than the first answer. Extend the contact lane's extraction
adapters (pasted text, foreign JSON, public URL, screenshots — Phase 35) to companies; when no
usable domain is present, research one and confirm it before writing (a wrong domain poisons
the dedupe anchor); never silently invent a domain — a profile URL is dropped, not passed
through. Closes INPUT-01..04. Research cost must be priced in the envelope and be declinable.
Full detail: `milestones/v1.1-ROADMAP.md` § Phase 58; decisions:
`phases/58-take-what-the-operator-actually-has/58-CONTEXT.md`.

**Requirements**: INPUT-01, INPUT-02, INPUT-03, INPUT-04

**Plans**: 6/6 plans executed

Plans:
**Wave 1**

- [x] 58-01-PLAN.md — company rows through the extraction machinery: identity config, record-type-aware validator, six source adapters (wave 1, tracer)
- [x] 58-02-PLAN.md — live spike: does a request-level propose mode reach the company decision node; operator decides the backend research node's scope (wave 1)

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 58-03-PLAN.md — propose/confirm/decline/correct: the domain decision lane, its envelope consumption, and the operator-facing confirm table (wave 2)

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 58-04-PLAN.md — the research line priced, named and declinable; backend website-seeking extension or a written INPUT-02 residual (wave 3)

**Wave 4** *(blocked on Wave 3 completion)*

- [x] 58-05-PLAN.md — gap closure: native country/city/employee-count written at landing, blank-fill only; native industry stays unwritten (Phase 31 refusal upheld 2026-08-26) (wave 4)

**Wave 5** *(blocked on Wave 4 completion)*

- [x] 58-06-PLAN.md — gap closure: judge escalation for material property conflicts; no anti-ICP veto flip without a judge verdict or human review (wave 5)

### Phase 51: Backfill Pipeline, Credit Sizing & Dry Run

**Goal**: Before any HubSpot write, the operator can see the live-derived population of
never-scored companies, a ZoomInfo-credit-sized cap on how many can be attempted, and — for a
representative sample of that capped population — the exact PATCH payload and predicted
`lv_icp_tier_derived` for every record, computed entirely by reusing `src/icp_scoring.py`
(never a reimplementation), with zero n8n executions and zero live writes.

**Depends on**: Nothing (first phase of milestone)

**Requirements**: FILL-01, FILL-03, FILL-04, SAFE-01

**Success Criteria** (what must be TRUE):

  1. The never-scored population is re-derived live (`NOT_HAS_PROPERTY(lv_icp_fit_score)`, ~646
     expected) and the count is recorded in a committed artifact — never a stale census carried
     over from `.planning/MILESTONE-CONTEXT.md`'s estimate, mirroring the D-01/Phase-48 lesson
     that a population must be re-derived, not trusted from a prior snapshot.

  2. Operator can see the live ZoomInfo credit balance, a population cap derived from it, and an
     Anthropic research-cost estimate for the gap-fill fields, all recorded in a committed
     artifact before any record is enriched. A run whose estimated cost would exceed the balance
     is capped up front — discovering exhaustion partway through a run is a failure of this
     criterion, not bad luck.

  3. A committed unit test pins that ZoomInfo GTM revenue (returned in THOUSANDS, per the landmine
     carried in from prior provider work) is converted to dollars before banding; the dry run's
     revenue-band outputs reflect that conversion, not a raw thousands pass-through that would put
     every company one band too low.

  4. Over a representative sample of the capped population, the dry run separates matched from
     unmatched records: every unmatched sample record appears in a skip log with a stated reason
     and carries no write payload of any kind — no company is scored on guessed data, and "not yet
     enriched" stays distinguishable from "enriched and genuinely low-fit."

  5. For every matched sample record, the dry run prints the exact PATCH payload — the `lv_*`
     scoring inputs (`lv_org_type`, `lv_produces_content`, `lv_country_region_normalized`,
     `lv_revenue_band`, `lv_is_gambling_operator`, `lv_is_hardware_vendor`) plus the six numeric
     properties (`org_type_score`, `geography_score`, `annual_revenue_score`,
     `produces_content_score`, `gambling_score`, `lv_anti_icp_flag_num`) — alongside its
     pre-registered predicted `lv_icp_tier_derived`, all committed to an artifact before any write.

  6. A before-snapshot of the 66 already-scored companies is committed, read-only, as the SAFE-04
     baseline Phase 52 will diff against at close.

  7. Operator has explicitly approved the dry-run artifacts before Phase 52 opens any write
     window. This approval is the phase's exit gate — structurally, not as a task inside a
     write-capable phase — per the locked sequence: plan → dry run → **operator approval** →
     canary execution.

**Plans**: 3/3 plans executed

- [x] 51-01-PLAN.md — Tracer: one never-scored company, credit-gated, end-to-end dry run (ZoomInfo
      client, revenue thousands→dollars, None-safe region, four-branch tier prediction)

- [x] 51-02-PLAN.md — Gap-fill research lane, skip-log partition, credit/cost sizing artifact, and
      the pre-registered prediction artifact over the capped sample

- [x] 51-03-PLAN.md — Read-only before-snapshot of the already-scored population, API coverage
      matrix, validation contract, and the operator approval exit gate

---

### Phase 52: Staged Canary Execution & Safety Verification

**Goal**: The credit-capped population of never-scored, ZoomInfo-matched companies is written in
operator-gated stages — 1 → 5 → 25 → chunked remainder — with each record's prediction committed
before it is written and its actual tier confirmed by polling against that prediction, and the
milestone closes with proof that the 66 already-scored companies and the D-07/Phase 49 parity
evidence are unchanged.

**Depends on**: Phase 51, gated on explicit operator approval of the dry-run artifacts — no write
in this phase precedes that approval.

**Carried forward from Phase 51 (operator ruling, 2026-08-19, explicitly deferred — not an
oversight):** the FILL-04 third-disposition question is unresolved by design. Today a company
ZoomInfo matches but for which no scoring input at all could be resolved lands in the predictions
side with a mostly-empty payload — there is no separate "matched but unscoreable" disposition
distinct from "predicted" and "skipped". The operator was asked to rule on this at the Phase 51
checkpoint and explicitly declined to decide it there, directing it to be decided during Phase 52
planning instead. This phase's planner must resolve it (either confirm the current two-way
partition is sufficient or add a third disposition) before Phase 52's write path is built — do not
silently inherit Phase 51's placeholder behavior without a decision.

**Requirements**: FILL-02, SAFE-02, SAFE-03, SAFE-04

**Success Criteria** (what must be TRUE):

  1. For every stage, each record's prediction (computed by `src/icp_scoring.py`, identical to
     Phase 51's method) is appended to the prediction artifact BEFORE that record is written — no
     record is ever written before its prediction is committed.

  2. Each matched company written in this phase shows non-blank `lv_org_type`,
     `lv_produces_content`, `lv_country_region_normalized`, `lv_revenue_band`,
     `lv_is_gambling_operator`, `lv_is_hardware_vendor`, and the six numeric properties, matching
     `src/icp_scoring.py`'s computed values for that record — the observable acquisition of
     scoring inputs FILL-02 requires.

  3. Execution proceeded in exactly four stages — 1, then 5, then 25, then the chunked remainder —
     with an explicit operator gate before each stage and a checkpoint between remainder chunks;
     no stage began without a recorded operator go-ahead, and the remainder was never written as
     one ~615-record batch.

  4. Every write happened inside a deliberately armed, record-scoped window — the Python-side
     two-key gate (`DRY_RUN=false` plus a dedicated allow-key), portal-id-guarded, under the same
     discipline as `scripts/rescore_population.py`'s W1 window. This is a zero-n8n write path, so
     there is no second, n8n-side allowlist to arm alongside it (do not carry over Phase 48's
     dual-surface arming rule here). Every window was disarmed afterward, with the disarmed state
     read back and confirmed.

  5. Every written record's `lv_icp_tier_derived` was confirmed by polling (never a single
     immediate read — calculated properties backfill ~70–130s) and compared against its committed
     prediction; any mismatch is surfaced as a defect — a bad provider value or a wrong
     normalization — never narrated after the fact as an expected outcome.

  6. After the run, the 66 already-scored companies read identically to the Phase 51 before-
     snapshot, and re-running `scripts/check_tier_derived_parity.py`'s D-07 gate still passes —
     the committed parity evidence and Phase 49's settled tiers are re-verified, not assumed.

**Plans**: TBD

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
| ----- | --------- | -------------- | ------ | --------- |
| 44. SJ-3 Dispatch Gate, Drain & Cap | v0.8 | 3/3 | Complete (verified) | 2026-08-10 |
| 45. Burn-Rate Alarm | v0.8 | 3/3 | Complete (verified) | 2026-08-10 |
| 46. Rubric Decision, Simulation & Engine Parity | v0.9 | 5/5 | Complete (verified) | 2026-08-11 |
| 47. Veto Remediation | v0.9 | 4/4 | Complete (verified) | 2026-08-12 |
| 47.5. Veto Recompute Path | v0.9 | 6/6 | Complete (verified) | 2026-08-12 |
| 48. Enrichment Coverage | v0.9 | 7/7 | Complete (verified) | 2026-08-13 |
| 49. Re-score Strategy & Reporting | v0.9 | 7/7 | Complete (verified) | 2026-08-13 |
| 50. Derived Tier Property | v0.9 | 6/6 | Complete (verified) | 2026-08-14 |
| 51. Backfill Pipeline, Credit Sizing & Dry Run | v1.0 | 3/3 | Complete (verified) | 2026-08-19 |
| 52. Staged Canary Execution & Safety Verification | v1.0 | 0/TBD | Deferred (operator, 2026-08-25) | - |
| 53. Operator-openable Write Grant | v1.1 | 4/4 | Complete — walk RUN 2026-08-28, **GRANT-01 not ticked** (composition defect found) | 2026-08-26 |
| 54. Single-pass Armed Dispatch | v1.1 | 7/7 | Complete (verified) | 2026-08-27 |
| 58. Take What the Operator Actually Has | v1.1 | 6/6 | Complete (verified) | 2026-08-26 |
| 59. Frictionless Write Path | v1.1 | 1/6 | In Progress|  |
| 60. Review-lane Authority | v1.1 | 0/TBD | Split from 59 (operator, 2026-08-28) | - |

## Ledger gaps (known)

- **v0.5 has no MILESTONES.md entry and no roadmap/phase archive.** Found during the v0.8 close
  on 2026-08-11: the ledger jumps v0.4 → v0.6 and `milestones/` holds no `v0.5-*` files, yet
  `v0.5.0` exists as a git release tag. v0.5 appears to have shipped without being run through
  `/gsd-complete-milestone`. Not reconstructed at v0.8 close (out of scope) — recorded so it is
  not mistaken for a numbering skip.

- **v0.6 has a MILESTONES.md entry but no roadmap/phase archive** under `milestones/`. Same
  likely cause, lesser impact: the narrative record survives, the phase artifacts were never
  archived under a `v0.6-*` label.
