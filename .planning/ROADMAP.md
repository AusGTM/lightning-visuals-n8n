# Roadmap: HubSpot Enrichment + ICP Scoring

## Milestones

- ✅ **v0.3** — archived (`milestones/v0.3-ROADMAP.md`)
- ✅ **v0.4 Reachability & Verification Debt** (shipped 2026-07-29)
- ✅ **v0.5** — shipped (no MILESTONES.md entry; see Ledger gaps below)
- ✅ **v0.6 Claude Plugin Entrypoint** — Phases 23–32, workstream `plugin-entrypoint` (shipped 2026-08-04)
- ✅ **v0.7 HubSpot Scoring Engine Remediation** — Phases 39–43 (shipped 2026-08-08)
- ✅ **v0.8 Execution Budget Safety** — Phases 44–45 (shipped 2026-08-11)
- ✅ **v0.9 ICP Rubric Calibration & Veto Remediation** — Phases 46–50, archived (`milestones/v0.9-ROADMAP.md`, `milestones/v0.9-REQUIREMENTS.md`) (shipped 2026-08-19)
- ⏸️ **v1.0 Direct Backfill & Scoring Coverage** — Phases 51–52 (Phase 51 complete; **Phase 52 deferred INDEFINITELY** — 2026-08-25 in favour of v1.1, reaffirmed 2026-08-30 after its gates were satisfied)
- 🚧 **v1.1 Unattended Session Runs** — Phases 53–62 (`milestones/v1.1-ROADMAP.md`, `milestones/v1.1-REQUIREMENTS.md`).
  Complete: 53, 54, 58, 59, 61. Open: **57 (next)**, 60, 62. Absorbed into 61: 55, 56 (D-61-08).
  ~~Phases 53–60~~ — corrected 2026-08-30, Phase 61 was inserted ahead of everything.
  **The first live unattended, credit-spending batch has NOT run** — it is gated on Phase 57.

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

- [ ] **Phase 52: Staged Canary Execution & Safety Verification** — ⏸️ **DEFERRED INDEFINITELY**
      (operator, in favour of v1.1 Phase 53 — the client is blocked on the write path). Write the
      credit-capped population in gated stages (1 → 5 → 25 → chunked remainder), polling every
      result against its committed prediction, and close by proving the 66 already-scored
      companies are untouched. **On resume:** re-derive Phase 51's population and credit sizing
      before planning — the dry-run artifacts were finalized 2026-08-19 and drift with every
      enrichment run — and resolve the deferred FILL-04 third-disposition question.
      **Gated on Phases 59 and 55** (operator ruling 2026-08-27): the ~646-company run goes
      through the cheap, low-ceremony write path, not the current one. Do not resume 52 first.
      **RESOLVED 2026-08-30 (operator): DEFERRED INDEFINITELY.** Both named gates are now built —
      Phase 59 completed 2026-08-29, and Phase 55's async work landed inside Phase 61 — so the
      2026-08-27 gating ruling is discharged. The operator has nonetheless deferred 52 with no
      scheduled resume: the backfill is not a current priority. **Do not treat the satisfied gate
      as permission to resume.** If it is ever revived, Phase 51's population and credit sizing
      must be re-derived first (the dry-run artifacts were finalized 2026-08-19 and drift with
      every enrichment run), and the run would still be subject to Phase 57's ceilings.

### 🚧 v1.1 Unattended Session Runs (Phases 53–61)

One operator grant at session start carries a batch through ingest → enrichment → HubSpot write,
unattended. Driven by a client UAT on 2026-08-25 that found three arming surfaces for one write,
a write path unreachable from the operator's own surface (`ALLOW_N8N_ARM` is a shell environment
variable), and a design that runs the provider waterfall twice per written record. Full detail:
`milestones/v1.1-ROADMAP.md`; evidence: `quick/260825-contact-company-association/UAT.md`.

- [x] **Phase 53: Operator-openable write grant** *(GRANT-01 ticked 2026-08-29, walk run 3)* -
      Replace the interactive path's
      `ALLOW_N8N_ARM` dependency with an admin-enabled capability plus an operator-opened session
      grant that is bounded, expiring and revocable — no terminal, no loss of record scoping.
      ("Expiring" = event-triggered close per GRANT-04, NOT a wall-clock timestamp; a real
      `expires_at` was proposed and declined by the operator 2026-08-25, D-53-03. See
      `.planning/milestones/v1.1-ROADMAP.md` § Phase 53.)
      — **4 plans** (`53-01` .. `53-04`), planned 2026-08-25.
      **✅ WALK RUN 3, 2026-08-29 — GRANT-01 ACHIEVED AND TICKED** (record:
      `53-WALK-RECORD-2.md` § run 3). After run 2's FINDING B was fixed the same day
      (`extraction.strip_row_id`, commit `96eea82`, plugin 0.28.1, shipped with the composition
      test that would have caught it), the same record walked the whole flow under **one grant,
      one yes**: extraction → unarmed match → grant → arm → enrich → merge → strip → CSV → arm →
      **HubSpot create**. Contact `348695309760` (`josh@seriesfutsal.com`) created and
      auto-associated to Series Futsal Victoria `283816805830` by domain. **Independently
      confirmed** — the same probe that returned `unmatched: 1` in run 2 now returns
      `auto_matched: 1`. Backend `VERDICT: disarmed PASS` after; grant closed `batch_complete`.
      Cost: 4 n8n executions, ~2 provider credits, ~$0.07, 1 write.
      **Ticked under the operator's explicit authorisation of 2026-08-29, with two limitations
      recorded not waived:** it ran from Claude Code **with a terminal** (so the composition is
      proven, the operator's own constraint set is not), and against the **repo** at 0.28.1 rather
      than the installed plugin (marketplace clone still behind). A Claude-Desktop walk on the
      installed plugin is the only thing that proves G-2 is truly gone.
      **⚠ NEW OPEN DEFECT — FINDING C.** The written-records artifact **does not record the
      write**: it reports `outcome: "not_written"`, `hs_object_id: null` for the run that created
      `348695309760`. `written_records.append_chunk` has one call site (`chunking.py:395`, inside
      `dispatch_plan`); the contacts write goes through `dispatch.dispatch`, which never touches
      it. D-59-07's own promise to the operator is therefore unkept, and the artifact is a false
      negative in the exact direction it exists to prevent. A **Phase 59** defect, not a grant
      defect — and the fifth to survive a green suite on the same unit-boundary blind spot.
      **⚠ EARLIER: WALK RUN 2 2026-08-29 — halted at step 7** (record:
      `53-WALK-RECORD-2.md`). Re-run after Phase 59 shipped, same record, at plugin 0.28.0.
      **FINDING 2 is genuinely fixed and proven live** — same input, one day apart:
      `unanswered` went 1 → 0 and the email went `None` → `josh@seriesfutsal.com`, with no
      hand-patch. D-59-08 proved out twice (bare-URL extraction now proposes a resolution path;
      GATE-06's empty-record-set refusal now names the domain lookup that unblocks it),
      D-59-07/D-59-09's rewritten disclosure and per-run artifact both landed, and D-59-10's
      field was present and clean. Grant machinery sound end to end.
      **But the composition is still broken, one step further along — FINDING B.** The documented
      `enrich-before-ingest` step 7 sequence cannot execute: `merge_enriched`'s rows always carry
      the `row_id` that `build_rows_spec` mints, and `write_dispatch_csv` refuses non-canonical
      keys. Both behaviours are correct and individually unit-tested; **no test chains
      `merge_enriched` → `hold_emailless` → `write_dispatch_csv`**, which is the fourth defect
      this week to survive three green suites because tests drive unit boundaries, not the
      documented path. No strip helper exists anywhere. Halted rather than hand-stripping.
      Zero HubSpot writes; backend verified `disarmed PASS`; grant closed `session_end`.
      **Also found (FINDING A):** the plugin test suite writes `written_records-*.json` into the
      operator's REAL durable directory — 413 files from one session's suite runs — so
      `written_records.load()`'s union returns mostly test debris. Per-`run_id` reads are fine.
      **⚠ EARLIER WALK 2026-08-28 — GRANT-01 NOT TICKED** (record: `53-WALK-RECORD.md`).
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

- [x] **Phase 55: Async run — submit, poll, resume** — **ABSORBED INTO PHASE 61, 2026-08-30**
      (operator decision D-61-08). Not open work; do NOT re-plan it. Delivered inside Phase 61
      (plans `61-01` spike + `61-05` async submit/progress/resume): RUN-01, RUN-03 and RUN-04 are
      ticked in `milestones/v1.1-REQUIREMENTS.md`. The requirements it carried are retained below
      for traceability. ~~A batch stops being bounded by n8n Cloud's
      ~100s response window; run state survives a restart or fails loudly — **pulled ahead of
      Phase 52** (operator ruling 2026-08-27) so the backfill is not run at `max_records_per_chunk:
      2`. Owns the response-window ceiling and the chunk cap; Phase 59 deliberately does not touch
      them. **Sequenced after 59**, which settles what a grant authorizes before async runs start
      outliving one. Still spike-first: n8n Cloud's execution model, not our code, decides what is
      possible here — if the spike fails, Phase 52 runs at chunk=2 and that is an accepted
      outcome.~~ The spike was run and did not fail: `61-SPIKE-VERDICT.md` selected substrate 1
      (async ack), with substrate 3 (self-referencing fan-out) integrated behind an off-by-default
      flag and proven at runtime (disarmed executions `12044`–`12047`).

- [x] **Phase 56: The unattended pair pipeline** — **ABSORBED INTO PHASE 61, 2026-08-30**
      (operator decision D-61-08). Not open work; do NOT re-plan it. Delivered inside Phase 61
      (plans `61-04` confidence table + durable held-rows queue, `61-06` pair pipeline under one
      grant): RUN-02 and AFTER-02 are ticked in `milestones/v1.1-REQUIREMENTS.md`. Original text,
      retained for traceability: ~~One grant carries ingest → enrich → create →
      associate, creates included, held rows queued rather than guessed~~ — **its gate survived
      the fold**: the first live unattended run is still gated on Phase 57.

- [ ] **Phase 57: Ceilings, refusal-before-start, and post-run proof** — **NEXT PHASE.** A run
      cannot spend what it does not have, and proves afterwards it wrote only what it was granted.
      **This phase gates the first live unattended, credit-spending batch** (D-61-08) — Phase 61's
      backend is deployed and disarmed-proven, but no such run has happened. Closes RUN-05,
      AFTER-01, AFTER-03, G-4, and is the producer GRANT-02/GRANT-04's `ceiling_breach` still
      lacks.

      **Goal:** an operator can start a batch knowing it will be refused before it starts if it
      cannot afford itself, will stop spending rather than overrun if reality diverges mid-run,
      and can read afterwards exactly what happened to every row — with a record that would have
      been written never reading as one that was.

      **Plans:** 5 plans — wave 1: 57-01, 57-04 · wave 2: 57-02, 57-03 · wave 3: 57-05
      *(revised 2026-08-31 after cross-AI plan review — `57-REVIEWS.md`. Four blocking operator
      checkpoints now exist: what RUN-05 means if the sampling predicate makes the preflight
      refusal unreachable on this account; whether `written` may be claimed without terminal write
      evidence; auto-split's work-not-authority confirmation; and a phase gate that separates
      landing this phase from authorising the first live credit-spending batch.)*

      Plans:

      - [x] 57-01-PLAN.md — TRACER: the ceiling refuses before start, stops PRE-SEND mid-run, and closes the grant on every exit; every dispatch path under the ceiling; D-53-02's supersession recorded (RUN-05)
      - [ ] 57-02-PLAN.md — one outcome vocabulary across both client surfaces via a pure mapping, plus the `row_id` join key as far as it reaches (AFTER-03)
      - [ ] 57-03-PLAN.md — a lossless `failed_batch`, auto-split and the remainder queue: work queued, authority never (RUN-05, D-57-05 checkpoint)
      - [x] 57-04-PLAN.md — provider-balance blind spots: a disarmed ZoomInfo re-probe with its gate proved by zero network calls, Apollo disclosed as structural `http_403` (G-4). Live verdict: `readable` (9381 credits) — G-4's ZoomInfo half closed by observation, no code fix needed; G-4's disclosure half still lands in 57-05.
      - [ ] 57-05-PLAN.md — the one end-of-run report joining all five durable stores, naming contradictions rather than resolving them (AFTER-01, AFTER-03, G-4)

- [x] **Phase 58: Take what the operator actually has** *(complete 2026-08-26, verified 31/31)* - Every input an operator holds
      (screenshot, paste, URL, bare name) resolves to a company the backend can act on; missing
      domains researched then confirmed before write; refusal is the last resort — promoted
      ahead of 54–57 by operator decision 2026-08-25

- [x] **Phase 59: Frictionless write path** *(complete 2026-08-29, verified 18/18 after gap
      closure)* — the blocking walk ran 2026-08-28; see `59-CONTEXT.md` and `53-WALK-RECORD.md`.
      ~~Still runs before Phase 55, and both before Phase 52.~~ (Superseded 2026-08-30: Phase 55
      was absorbed into Phase 61, which is complete; Phase 52 stays deferred.) Plugin released
      0.21.0 → 0.28.0.

      **The lesson worth keeping.** All four gaps that first-pass verification found (14/18) had
      shipped past three green suites — root 3285, plugin 1678, node 776 — because every test drove
      a unit boundary rather than the integration path. Code review and goal verification caught
      them; the test counts did not. Gap closure's defining constraint was that each fix carry a
      test driving the real caller path: `plan_chunks` → `dispatch_plan`, two interleaved runs
      against one directory, a full `run_scheduled_arm_cycle`. Final: root 3308, plugin 1701,
      node 776.

      **Two rulings taken mid-phase**, recorded in `59-CONTEXT.md`: **D-59-09** — one written-records
      artifact per `run_id`, reader globs and unions (chosen over `flock`, which would put
      contention and a stale-lock failure mode on a path that must never block a dispatch);
      **D-59-10** — a records-write failure never stops a dispatch, and the resulting incomplete
      list is surfaced loudly across four surfaces, never swallowed, because an artifact that is
      silently short reads as a complete account of what was written.

      **Not done here, by operator ruling:** the Phase 53 operator walk. This phase was code only,
      so **GRANT-01 remains unticked** and the walk stays a Phase 53 checkpoint — it now needs the
      installed plugin updated to ≥0.28.0 first. D-59-06's live-host delivery check is likewise
      recorded as unperformed rather than claimed.

      **Goal:** an operator who has granted once can see afterwards exactly which HubSpot
      records the run wrote — even when the run died partway or was revoked mid-flight — is
      told once at session start that a started run finishes, cannot have a routine test run
      spend money on their behalf, and is offered a resolvable proposal instead of a dead end
      wherever a gate used to simply refuse.

      **Plans:** 9 plans, 8 waves (6 executed, plus gap closure `59-07`..`59-09` planned
      2026-08-29 against `59-VERIFICATION.md`'s 4 gaps). Code only — the Phase 53 operator walk
      stays a Phase 53 checkpoint (operator ruling 2026-08-28), so every plan is autonomous.

      Plans:

      - [x] 59-01-PLAN.md — TRACER: durable written-records artifact, flushed per chunk inside
            `dispatch_plan`, proven to survive a mid-loop interruption and a revoked run (D-59-07b)

      - [x] 59-02-PLAN.md — root `tests/conftest.py` ambient-credential guard, gated on
            `RUN_LIVE_PARITY` rather than a marker that does not exist in this repo (D-59-04)

      - [x] 59-03-PLAN.md — retire D-53-05's pre-emptive two-lane disclosure across four
            surfaces, replaced by a plain statement plus a pointer to the written list (D-59-07a)

      - [x] 59-04-PLAN.md — the plugin's first `hooks/`: a `SessionStart` note that a started
            run continues to completion, instead of a grant-aware dispatch loop (D-59-06)

      - [x] 59-05-PLAN.md — the gate inventory, and the extraction identity gate converted to
            resolve-then-propose with an unlaunderable closed provenance vocabulary (D-59-08)

      - [x] 59-06-PLAN.md — the remaining CONVERT gates: enrichment-lane refusals and the
            walk's FINDING 1 grant dead end, with the authorization control untouched (D-59-08)

      Gap closure (planned 2026-08-29, `gap_closure: true`, sequential waves 1-3):

      - [x] 59-07-PLAN.md — GAP 1: GATE-02..GATE-05's resolve-and-propose payload survives
            `dispatch_plan` and reaches the operator through both skills; gate inventory
            corrected to match delivery (D-59-08)

      - [x] 59-08-PLAN.md — GAP 2 + GAP 4: one written-records artifact per `run_id` with a
            globbing reader, and every grant — not only a multi-lane one — discloses it
            (D-59-09, D-59-07)

      - [x] 59-09-PLAN.md — GAP 3: a written-records failure never stops a dispatch, and the
            resulting incomplete list is loud in the outcome, the unattended exit code and both
            skills; `scheduled_arm.py`'s stale comment corrected in the same commit (D-59-10)

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
      `max_records_per_chunk`, both owned by Phase 55 — **which was absorbed into Phase 61
      (D-61-08); Phase 61 shipped the async shape that lifts the response-window bound.**

- [x] **Phase 61: Autonomous batch runs** — **COMPLETE 2026-08-30**
      (operator, 2026-08-30). Inserted ahead of everything after walk run 4 failed.
      **Plans:** 6/6 complete (planned and executed 2026-08-30; absorbs Phases 55 and 56 per
      D-61-08). Verified 12/12 must-haves — `61-VERIFICATION.md`.

      **Landed:** `linkedin_url` as a third identity group across both lanes with a YAML/JS
      parity test; a real confidence decision table plus a durable held-rows queue with
      per-hold-code resume fingerprints (the absence that WAS FINDING F); async submit/progress
      off the synchronous window; one grant across ingest/enrich/create/associate; the
      enrichment lane's unassociated-create gap closed by refusal, keeping ONE implementation
      of the association rule; and the substrate-3 scale-up fan-out integrated behind an
      off-by-default flag and proven at runtime.

      **Backend deployed 2026-08-30** (all five cloud workflows; enrichment 114 → 118 nodes),
      bounced, and exercised by disarmed runs — `12040`, and `12044`-`12047` for the fan-out.
      **STILL GATED ON PHASE 57 (D-61-08):** the first live *unattended, credit-spending*
      batch. Nothing armed; no such run has happened.

      **Premises closed:** P-05/P-08/P-09 from n8n's own docs; P-07/P-10/P-13/P-14 by live
      disarmed probes (`61-PREMISE-DOCS-FINDINGS.md`, `61-PREMISE-PROBE-VERDICT.json`,
      `61-SCALE-UP-VERDICT.json`). Two findings worth carrying: sub-workflow executions are
      documented as neither billed nor concurrency-capped (Starter = 5 concurrent, 2.5K/month),
      and a Wait under 65s stays in-process and is NOT restart-safe.

      **Goal:** an operator hands over a batch and gets it back done — research, enrichment and
      ingestion run autonomously, consent is once per batch rather than once per row, rows the
      system is not confident about are held and collected into one review queue, and the run is
      not bounded by the synchronous response window. The bar is 300 contacts as one run plus one
      review pass, not 300 conversations. Identity resolution (the LinkedIn-URL-only row) is the
      TRACER, not the scope. Closes INPUT-05, RUN-01, RUN-02, RUN-03, RUN-04, AFTER-02.

      Plans:

      - [x] 61-01-PLAN.md — spike n8n Cloud's execution model; verdict doc with a basis word per
            claim, execution arithmetic against the 2,500/month budget, and an operator decision
            on where run state lives

      - [x] 61-02-PLAN.md — the tracer's backend half: a `linkedin` match lane that reaches a
            HubSpot search on `lv_linkedin_url`, surviving stored-value variance

      - [x] 61-03-PLAN.md — the tracer's front-end half: the third identity group in all five
            D-61-06 sites, with a YAML-to-JS parity test left behind

      - [x] 61-04-PLAN.md — the confidence signal and hold-and-collect: confident rows proceed,
            unconfident rows are held with a reason, the batch always finishes

      - [x] 61-05-PLAN.md — async submit, progress-while-running, and resume-or-fail-loudly on the
            substrate 61-01 selected

      - [x] 61-06-PLAN.md — the unattended pair pipeline under one grant, association enforced,
            index lag absorbed by the run; first live run gated on Phase 57

      **The evidence.** Walk run 4 (`53-WALK-RECORD-3.md`) — the first walk ever run from the
      operator's own chair against the installed plugin (0.28.6) — **halted before the grant was
      opened**. Given only a LinkedIn URL, the plugin demanded a company. Steps 3–7 were never
      exercised; the grant surface remains untested from the operator's chair.

      **Why it is a defect, not strictness.** The plugin demanded a field its own backend does
      not need. `n8n/code/resolveIdentity.js:76-78` treats `linkedin_url` as a **strong** HubSpot
      match key (same tier as email); `n8n/code/lushaRequest.js:79-91` accepts a Lusha v3 enrich
      body carrying `linkedinUrl` alone (`lushaContactBody` takes any subset — only a wholly
      empty set skips). Both operations it refused were keyed on what the operator had supplied.

      **No-invention is NOT loosened.** Operator supplies the key, a licensed provider returns
      sourced fields, the operator confirms. A searched-and-sourced value is not an invented one;
      the two have been collapsed and the fix is separating them. `extraction.md`'s verbatim
      no-invention sentence stays as-is — it remains on the do-not-simplify list.

      **Not a regression.** No best-effort ruling was ever recorded in `.planning/`, and the
      extraction escalation ladder has only ever been same-host URL fetching (`url_fallback.py`,
      host-bound in code). The capability was never built. The root cause is process: a verbal
      operator ruling that was never written down, so nothing implemented it and nothing guarded
      it — the third documented-vs-actual gap to cost something in two days.

      **Design note:** for a **person**, web search is the weaker instrument — `claude_web` is
      company-oriented (`object_type: companies` throughout `src/web_research.py`). Use the
      licensed waterfall on `linkedin_url`.

      **Scope fence:** strong keys only (LinkedIn URL, email). Name-only rows keep routing to the
      existing `name_company` weak-key → `needs_review` path — a wrongly matched person is worse
      than an unmatched one.

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

- [ ] **Phase 62: Suggest the contacts nobody named** — **NUMBERED 2026-08-30** (operator).
      An enriched company with nobody at it is not a lead. After a company batch, the operator is
      offered contacts worth enriching, chosen by role and priced once. Closes SUGGEST-01..05.
      **Full scope:** `milestones/v1.1-ROADMAP.md` § Phase 62.

      **Why it needed numbering.** It was written as "Phase 59" in the milestone roadmap, but 59
      was reassigned to the as-built *Frictionless write path* (complete 2026-08-29) and Phase 60
      was split out of that. The suggestion scope was left with no number and no schedule — real
      work that no index pointed at. It is now a numbered phase so it cannot be silently dropped
      or re-planned from scratch.

      **Sequenced after Phase 57**, because a suggestion round spends provider credit and 57 owns
      the per-run ceilings, refusal-before-start and post-run proof that bound that spend.
      **Depends on** the 2026-08-25 association contract (a suggested contact must resolve a
      company or be held) and Phase 61's held-row queue (`held_queue.py`) for anything held —
      Phase 56 was absorbed into 61, so its queue is 61's.

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

### Phase 57: Ceilings, refusal-before-start, and post-run proof

**Status: PLANNED — NEXT PHASE.** 5 plans, converged through cross-AI review
(`57-REVIEWS.md`). **This phase gates the first live unattended, credit-spending batch**
(D-61-08): Phase 61's backend is deployed and disarmed-proven, but no such run has happened.

**Goal**: An operator can start a batch knowing it will be refused before it starts if it cannot
afford itself, will stop spending rather than overrun if reality diverges mid-run, and can read
afterwards exactly what happened to every row — with a record that would have been written never
reading as one that was.

**Closes**: RUN-05 (refuse before starting, with the arithmetic, offering a smaller batch),
AFTER-01 (one end-of-run report — PARTIAL, see below), AFTER-03 (written vs would-have-been
written), G-4 (name which provider balances were readable). It is also the producer
GRANT-02/GRANT-04's `ceiling_breach` close reason still lacks. Requirements live in
`milestones/v1.1-REQUIREMENTS.md`, NOT the root `REQUIREMENTS.md`, which is v1.0's.

**AFTER-01 ships PARTIAL, deliberately**: the pair pipeline's final ingest leg strips `row_id`
(`extraction.strip_row_id`), so that leg's rows return unjoinable. They are kept, rendered as
UNJOINABLE and named in the report's `gaps` rather than dropped or presented as a completed join.

**Plans**: 2/5 plans executed
57-04 (the ZoomInfo balance probe) · wave 2: 57-02 (the outcome vocabulary and `row_id`),
57-03 (the remainder queue and the split offer) · wave 3: 57-05 (the end-of-run report and the
phase gate).

**Four blocking operator checkpoints**, all of which must be answered by a human: what RUN-05
means if the sampling predicate makes the preflight refusal unreachable on this account; whether
`written` may be claimed without terminal write evidence; auto-split's work-not-authority
confirmation; and a phase gate that separates LANDING this phase from AUTHORISING the first live
credit-spending batch. Landing the phase authorises nothing.

**The residual this phase discloses rather than closes**: when the executions list will not yield
a sample, the ceiling verdict is `unknown` and no code in this repo can guard the MONTHLY
allowance. A run is then bound only by its own approved quote. 57-05's phase gate makes the
unattended option unselectable in that state.

### Phase 61: Autonomous batch runs

**Status: COMPLETE 2026-08-30** — 6/6 plans, verification 12/12 (`61-VERIFICATION.md`). Backend
deployed and bounced (all five cloud workflows; enrichment 114 → 118 nodes) and exercised by
DISARMED runs only (`12040`; `12044`–`12047` for the fan-out). **Nothing was armed, and the first
live unattended, credit-spending batch has NOT run — it is gated on Phase 57 (D-61-08).**

**Goal**: An operator hands over a batch and gets it back done. Research, enrichment and
ingestion run **autonomously**; consent is once per batch, not once per row; rows the system is
not confident about are **held and collected into one review queue** rather than guessed or
asked about mid-run; and the run is not bounded by the synchronous response window. The bar is
not "does a record land" — it is **300 contacts as one run plus one review pass, not 300
conversations**.

**The tracer, not the scope**: a contact given only a LinkedIn URL (or only an email) proceeds —
match HubSpot on that key, and where unmatched, enrich through the licensed provider waterfall on
that same key, proposing the result with its provenance. This is the exact row that failed the
walk, and it exercises identity resolution, the waterfall, the proposal surface and the write
path in one pass. A refusal for missing identity is correct only when NO strong key is present.

**Why now**: walk run 4 (2026-08-30) — the first walk ever run from the operator's own chair
against the installed plugin — FAILED, halting before the grant was opened because the plugin
demanded a company for a LinkedIn-URL-only contact. Inserted ahead of everything by operator
decision; a re-walk is blocked on this phase or it halts in the same place.
Full detail: `milestones/v1.1-ROADMAP.md` § Phase 61; evidence:
`phases/53-operator-openable-write-grant/53-WALK-RECORD-3.md` FINDING D; decisions D-61-01..05:
`phases/61-autonomous-batch-runs/61-CONTEXT.md`.

**Front-end AND backend, together** (corrected 2026-08-30 by `61-RESEARCH.md`; an earlier
"front-end contract fix only" claim here was WRONG). Lusha enrich by `linkedinUrl` alone is real
and live (`lushaRequest.js:79-98`). But **HubSpot matching by `linkedin_url` is dead on the live
path** — `resolveIdentity.js:76-90`'s linkedin branch is unreachable, the ingest lane's
`ADAPT_SEARCH_RESULTS` builds `searchResultsByKey.email` only, the match lane's
`matchProposal.js::laneOf()` never reads the key, and the plugin's own
`enrichment.py:71` `MATCH_LOOKUP_KEYS` filters it out before sending. **Fixing only the front-end
gate reproduces the failure in a new shape**: the row passes extraction then dead-ends in the
"could not look" bucket — failing later and more quietly than today's honest refusal.

**No-invention is NOT loosened** (D-61-02): the operator supplies the key, a licensed provider
returns a sourced value, the operator confirms. `extraction.md`'s verbatim no-invention sentence
stays as-is and stays on the do-not-simplify list. Scope fence (D-61-03): strong keys only —
name-only rows keep routing to the existing `name_company` weak-key → `needs_review` path.

**RE-SCOPED 2026-08-30 — absorbs Phases 55 and 56.** After the walk concluded, the operator's
diagnosis (FINDING F) reframed this phase: there is no confidence self-assessment, therefore no
autonomy, therefore an operator must walk every row. The three backend services ALREADY do the
research, enrichment and ingestion — the plugin exists because they clobber each other. Keep the
non-clobbering and remove the autonomy and the result is WORSE than the raw services.

**What it is now**: an operator hands over a batch and gets it back done. Research, enrichment
and ingestion run autonomously; consent is once per batch, not per row; unconfident rows are HELD
and collected into one review queue (D-61-07) rather than guessed or asked about mid-run; the run
is not bounded by the synchronous response window. The linkedin_url identity fix becomes the
TRACER, not the scope.

**Closes**: INPUT-05, RUN-01, RUN-02, RUN-03, RUN-04, AFTER-02.

**NOT relaxed** (operator kept these explicitly): the non-clobber merge policy, the write-safety
gates, the post-run account of what was written. With no HubSpot rollback and ~700 live records
reachable, those three are what make autonomy survivable rather than reckless.

**Phase 57 stays separate AND stays gating**: Phase 56's original gate survives the fold — the
first live unattended run is gated on 57's ceiling work. D-53-02 is explicit that a grant's
computed ceiling is disclosure, not constraint.

**Biggest unknown, inherited from 55 — RESOLVED by plan `61-01`**: ~~n8n Cloud's execution model —
not our code — decides what submit/poll/resume can do. SPIKE IT BEFORE PLANNING TASKS AROUND
IT.~~ The spike ran first, as directed: `61-SPIKE-VERDICT.md` plus `61-PREMISE-DOCS-FINDINGS.md`,
`61-PREMISE-PROBE-VERDICT.json` and `61-SCALE-UP-VERDICT.json`. Substrate 1 (async ack) was
selected; substrate 3 (self-referencing fan-out) shipped behind an off-by-default flag and was
proven at runtime. Run-state location was an operator decision: a HubSpot object for the run
handle and progress, plus `run_manifest.py` for per-row verdicts. Two findings worth carrying:
sub-workflow executions are documented as neither billed nor concurrency-capped, and a Wait under
65s stays in-process and is NOT restart-safe.

**Requirements**: INPUT-05, RUN-01, RUN-02, RUN-03, RUN-04, AFTER-02

**Plans**: 6/6 plans executed

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
| 53. Operator-openable Write Grant | v1.1 | 4/4 | Complete (verified) — GRANT-01 TICKED, walk run 3 | 2026-08-29 |
| 54. Single-pass Armed Dispatch | v1.1 | 7/7 | Complete (verified) | 2026-08-27 |
| 55. Async Run — Submit, Poll, Resume | v1.1 | — | Absorbed into Phase 61 (D-61-08) | 2026-08-30 |
| 56. The Unattended Pair Pipeline | v1.1 | — | Absorbed into Phase 61 (D-61-08) | 2026-08-30 |
| 57. Ceilings, Refusal-before-start, Post-run Proof | v1.1 | 2/5 | In Progress|  |
| 58. Take What the Operator Actually Has | v1.1 | 6/6 | Complete (verified) | 2026-08-26 |
| 59. Frictionless Write Path | v1.1 | 9/9 | Complete (verified 18/18, after gap closure) | 2026-08-29 |
| 60. Review-lane Authority | v1.1 | 0/TBD | Split from 59 (operator, 2026-08-28) | - |
| 61. Autonomous Batch Runs (absorbs 55 + 56) | v1.1 | 6/6 | Complete (verified 12/12) | 2026-08-30 |

## Ledger gaps (known)

- **v0.5 has no MILESTONES.md entry and no roadmap/phase archive.** Found during the v0.8 close
  on 2026-08-11: the ledger jumps v0.4 → v0.6 and `milestones/` holds no `v0.5-*` files, yet
  `v0.5.0` exists as a git release tag. v0.5 appears to have shipped without being run through
  `/gsd-complete-milestone`. Not reconstructed at v0.8 close (out of scope) — recorded so it is
  not mistaken for a numbering skip.

- **v0.6 has a MILESTONES.md entry but no roadmap/phase archive** under `milestones/`. Same
  likely cause, lesser impact: the narrative record survives, the phase artifacts were never
  archived under a `v0.6-*` label.
