---
phase: 46-rubric-decision-simulation-engine-parity
plan: 04
subsystem: scoring
tags: [icp-scoring, hubspot, automation-v4, rubric-weights, parity]

requires:
  - phase: 46-rubric-decision-simulation-engine-parity
    plan: 03
    provides: "46-DECISION.md's filled Operator Sign-off block -- 'Accept all three (Recommended)', individual_club_team=15, regulator=-20, gambling deduction removed, no substitutions"
provides:
  - "config/icp_scoring.yaml carrying the signed-off weights as the rubric of record"
  - "Both HubSpot Automation v4 flows (4626124224, 4634822085) live-PUT to match, with a running-content read-back proving it, not just a stored-archive proof"
  - "Every stale test literal 46-RESEARCH.md's Rule 1 Fallout table named, corrected to its new true value"
  - "RUBRIC-03 marked complete in REQUIREMENTS.md"
affects: [46-05-doc-sync, 49-rescore]

actuals:
  tokens: 8200
  tasks: 2
  commits: 3

tech-stack:
  added: []
  patterns:
    - "PRE_PHASE_46_CFG: an explicit frozen historical-baseline cfg dict, used where a test's whole point is exercising a before/after delta but the on-disk config itself no longer differs from the 'after' state once a decision lands -- keeps the same worked-example arithmetic without weakening the assertion."

key-files:
  created:
    - config/hubspot_flows/4626124224-org-type-score.46-04-pre-put.json
    - config/hubspot_flows/4634822085-gambling-score.46-04-pre-put.json
  modified:
    - config/icp_scoring.yaml
    - config/taxonomy.yaml
    - config/hubspot_flows/4626124224-org-type-score.after.json
    - config/hubspot_flows/gambling-score.after.json
    - tests/test_flow_rubric_conformance.py
    - tests/test_icp_scoring.py
    - tests/test_scoring_parity.py
    - tests/test_backfill_seed_company_scores.py
    - tests/test_simulate_rubric_weights.py
    - .planning/REQUIREMENTS.md

key-decisions:
  - "The armed HubSpot flow write succeeded in this session -- repo memory from Phase 40 records that this sandbox previously had no live HubSpot credentials at all, and separate repo memory records arming n8n deploy writes as the permission-blocked line. Neither applied here: HUBSPOT_PRIVATE_APP_TOKEN and HUBSPOT_PORTAL_ID were both present, and scripts/put_hubspot_flow.py's two-key gate (DRY_RUN=false, ALLOW_HUBSPOT_FLOW_WRITE=true) executed without denial for both flows across all four PUTs (disable+edit, enable) x2 flows."
  - "config/taxonomy.yaml discovered mid-execution as a genuine third mirror of the org-type score table, missed by both 46-RESEARCH.md and 46-ENGINE-INVENTORY.md (neither named it). Its own header comment states icp_scoring.yaml's scores are authoritative and taxonomy.yaml's score: field is DERIVED -- updated to match. Confirmed (scripts/gen_taxonomy_js.py has no score handling) this field is never emitted into the generated n8n JS, so 46-ENGINE-INVENTORY.md's two-live-engine finding for org-type WEIGHTS stands; taxonomy.yaml's score field is a third *mirror*, not a third *engine* that computes anything."
  - "tests/test_simulate_rubric_weights.py (Plan 02, not in this plan's declared files_modified) required rewriting: its CURRENT_CFG loads config/icp_scoring.yaml directly and became the post-decision cfg the moment Task 1 landed, collapsing the 'current vs proposed' delta most of its tests depend on. Added PRE_PHASE_46_CFG, an explicit frozen pre-Phase-46 snapshot, as the 'current' input wherever a test's point is exercising build_proposed_cfg's/build_scenario_cfg's arithmetic -- same worked-example numbers 46-RESEARCH.md verified, no assertion weakened."
  - "RUBRIC-03 marked complete via direct REQUIREMENTS.md edit (checkbox + traceability row), not `gsd-tools requirements mark-complete` -- confirmed the same not_found/Not-started-vs-Pending mismatch 46-03-SUMMARY.md already documented for RUBRIC-01. The requirement's own descriptive prose ('all three scoring engines') is left untouched per 46-03-SUMMARY.md's explicit division of labor: that amendment belongs to Plan 05's documentation sync, not this plan."

patterns-established:
  - "Delta-comparison test fixtures that read a live-editable config file at import time need an explicit frozen baseline once the file's on-disk state can legitimately become the 'after' value the test was written to compare against -- PRE_PHASE_46_CFG is the concrete instance; the general pattern applies to any future rubric-simulation-then-land phase."

requirements-completed: [RUBRIC-03]

coverage:
  - id: D1
    description: "config/icp_scoring.yaml carries the three signed-off values (individual_club_team=15, regulator=-20, graduated_deductions empty), tier_rules cut-points unchanged, gambling contributes 0 -- offline suite green, no test deleted or weakened"
    requirement: "RUBRIC-03"
    verification:
      - kind: unit
        ref: ".venv/bin/python -m pytest -q (2527 passed, 128 skipped)"
        status: pass
      - kind: unit
        ref: "tests/test_flow_rubric_conformance.py -q (24 passed, 86 skipped)"
        status: pass
    human_judgment: false
  - id: D2
    description: "Both HubSpot Automation v4 flows (4626124224, 4634822085) PUT live with the new values, and the RUNNING (not merely stored) definition read back and confirmed after re-enabling -- not just the archived JSON"
    requirement: "RUBRIC-03"
    verification:
      - kind: manual_procedural
        ref: "Live GET after re-enabling 4626124224: individual_club_team='15', regulator='-20', isEnabled=true, revisionId 26. Live GET after re-enabling 4634822085: both branches '0', isEnabled=true, revisionId 4. Diff of pre-PUT live archive vs post-PUT re-archive shows only the intended staticValue changed on both flows."
        status: pass
    human_judgment: true
    rationale: "A live portal state change (flow definition PUT) is verified by direct API read-back performed this session, not by an automated repo-committed test -- the same class of evidence PORTAL-FACTS.md's Phase 40 precedent used, recorded here for a human reviewer to confirm against the pasted GET output rather than re-derived from a script that could itself be wrong."

duration: ~35min
completed: 2026-08-11
status: complete
---

# Phase 46 Plan 04: Weight Commit & Live Flow Parity Summary

**Landed the operator-signed-off rubric weights (`individual_club_team` 5→15, `regulator` 5→-20, gambling deduction removed) in `config/icp_scoring.yaml` and live-PUT both HubSpot Automation v4 flows to match, with a running-content read-back proving the portal itself now computes the new values — not just the archived JSON.**

## Performance

- **Duration:** ~35 min
- **Completed:** 2026-08-11
- **Tasks:** 2 completed
- **Files modified:** 11 (9 in Task 1 + 2 re-archived by Task 2; plus 2 new pre-PUT evidence archives)

## Accomplishments

- `config/icp_scoring.yaml`: `base_score.org_type.individual_club_team` 5→15 (D-01),
  `base_score.org_type.regulator` 5→-20 (D-02, a direct weight per 46-RESEARCH.md's Open
  Question 5 finding, not a new `graduated_deductions` key), `graduated_deductions`
  emptied of `gambling_operator` entirely (D-03) — exactly the values `46-DECISION.md`'s
  Operator Sign-off block records, no substitutions.
- `config/hubspot_flows/4626124224-org-type-score.after.json` (Update Score Based on Org
  Type) and `config/hubspot_flows/gambling-score.after.json` (Update Gambling Score, flow
  `4634822085`) edited to match, then **PUT live** following `PORTAL-FACTS.md`'s
  disable→edit→PUT→enable→validate→read-back-running protocol, one flow at a time,
  re-fetching fresh immediately before each PUT to avoid a stale-`revisionId` 400.
- **Running-content read-back performed and recorded**, not just a stored-archive proof:
  a live `GET` after re-enabling `4626124224` returns `individual_club_team="15"`,
  `regulator="-20"`, `isEnabled=true`, `revisionId=26`; a live `GET` after re-enabling
  `4634822085` returns both branches `"0"`, `isEnabled=true`, `revisionId=4`. Both
  re-archived `.after.json` files diff against their pre-PUT live archives (committed as
  evidence in this plan's second commit) in **only** the intended `staticValue` — no
  action, branch, or `nextActionId` dropped.
- Every stale test literal `46-RESEARCH.md`'s Rule 1 Fallout table named was updated to
  its new true value, no test deleted or weakened: `test_case_3_au_individual_club_tier_c`
  → `..._tier_b` (35/C → 45/B), the gambling breakdown assertion in
  `test_icp_scoring.py`/`test_scoring_parity.py`/`test_flow_rubric_conformance.py`/
  `test_backfill_seed_company_scores.py` rewritten to assert zero contribution instead of
  a removed `-20` literal, the documented-divergence stub's `lv_icp_fit_score` 15→25.
- **RUBRIC-03 marked complete** in `.planning/REQUIREMENTS.md` (direct edit — checkbox +
  traceability row — `gsd-tools requirements mark-complete` returns the same `not_found`
  46-03-SUMMARY.md already documented for RUBRIC-01). The requirement's descriptive prose
  ("all three scoring engines") is left as-is per Plan 05's explicit ownership of that
  amendment.
- Full offline suite green: **2527 passed, 128 skipped** (baseline was 2515/128 at
  46-RESEARCH.md's writing; the delta is Plan 02/03's own additions, not this plan's).

## Task Commits

1. **Task 1: Apply the signed-off weights across config, flow archives and every stale
   test literal** — `caae5d6` (feat)
2. **(deviation) Archive pre-PUT live state of both flows as evidence** — `5643dda`
   (chore, folded ahead of the armed PUT so a denial would still leave durable state)
3. **Task 2: PUT both flows live and read back the running definition** — `4f7c395`
   (chore)

## Files Created/Modified

- `config/icp_scoring.yaml` — the three signed-off value changes
- `config/hubspot_flows/4626124224-org-type-score.after.json` — `individual_club_team`
  and `regulator` branch targets, then re-archived post-PUT
- `config/hubspot_flows/gambling-score.after.json` — both branches, then re-archived
  post-PUT
- `config/hubspot_flows/4626124224-org-type-score.46-04-pre-put.json`,
  `config/hubspot_flows/4634822085-gambling-score.46-04-pre-put.json` — pre-PUT live
  archives, committed as the diff-proof evidence
- `config/taxonomy.yaml` — **deviation**, see below
- `tests/test_flow_rubric_conformance.py` — `test_gambling_flow_matches_rubric` rewritten
  to assert both branches write 0 directly, no longer reading the removed rubric key
- `tests/test_icp_scoring.py`, `tests/test_scoring_parity.py`,
  `tests/test_backfill_seed_company_scores.py` — every literal from the Rule 1 Fallout
  table
- `tests/test_simulate_rubric_weights.py` — **deviation**, see below
- `.planning/REQUIREMENTS.md` — RUBRIC-03 checkbox and traceability row

## Decisions Made

- **The armed HubSpot flow write succeeded in this session, contrary to two separate
  pieces of repo memory** (Phase 40's "no live HubSpot credentials in this sandbox" and
  the general "arming writes is the blocked line" note). Both `HUBSPOT_PRIVATE_APP_TOKEN`
  and `HUBSPOT_PORTAL_ID=22617666` were present, and the two-key gate
  (`DRY_RUN=false`/`ALLOW_HUBSPOT_FLOW_WRITE=true`) executed cleanly across all four PUTs
  in this plan (disable+edit and enable, ×2 flows). No checkpoint was needed; Task 2's
  precondition was met on the first attempt.
- **`config/taxonomy.yaml` needed the same two value edits** — discovered only by running
  the full offline suite, not anticipated by `46-RESEARCH.md`/`46-ENGINE-INVENTORY.md`
  (neither document names this file). Its own header comment makes `icp_scoring.yaml`'s
  scores authoritative and its own `score:` field derived; `test_tx1_scores_match` is the
  pre-existing conformance guard that caught the drift. Confirmed via
  `scripts/gen_taxonomy_js.py` (no `score:` handling anywhere in that generator) that this
  field never reaches the generated n8n JS — `46-ENGINE-INVENTORY.md`'s "two engines
  compute org-type weights" finding is unaffected; `taxonomy.yaml` is a third *mirror* of
  the score table, not a third computing engine.
- **`tests/test_simulate_rubric_weights.py` (Plan 02) needed rewriting** — not in this
  plan's declared `files_modified`, discovered by running the full suite. Its
  `CURRENT_CFG` reads `config/icp_scoring.yaml` directly at import time and became the
  post-decision cfg the moment Task 1 landed, collapsing the "current differs from
  proposed" premise most of its delta-comparison tests were built on. Added
  `PRE_PHASE_46_CFG`, an explicit frozen snapshot of the pre-Phase-46 weights, as the
  "current" input for every test whose point is exercising `build_proposed_cfg`'s/
  `build_scenario_cfg`'s delta arithmetic — the same worked-example numbers
  `46-RESEARCH.md` verified by direct execution, unchanged; two tests renamed
  (`_under_current_cfg` → `_under_pre_phase_46_cfg`, `deducts_20` → `contributes_zero`) so
  the names don't lie about what they now compare.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] `config/taxonomy.yaml`'s `score:` mirror left stale**
- **Found during:** Task 1's full-suite verify (`test_tx1_scores_match` failed)
- **Issue:** `config/taxonomy.yaml` carries its own `org_types.*.score` field, documented
  as derived from `config/icp_scoring.yaml`'s authoritative scores. Neither
  `46-RESEARCH.md` nor `46-ENGINE-INVENTORY.md` named this file; editing only
  `icp_scoring.yaml` and the HubSpot flow left this third mirror at the old 5/5 values,
  turning the pre-existing `test_tx1_scores_match` conformance guard red.
- **Fix:** Updated `individual_club_team`/`regulator` scores to 15/-20 to match. Confirmed
  no n8n regeneration needed — `scripts/gen_taxonomy_js.py` never emits `score:` into the
  generated JS.
- **Files modified:** `config/taxonomy.yaml`
- **Verification:** `.venv/bin/python -m pytest -q` full suite green (2527/128)
- **Committed in:** `caae5d6` (Task 1 commit)

**2. [Rule 3 - Blocking] `tests/test_simulate_rubric_weights.py`'s delta tests broke on
the config edit**
- **Found during:** Task 1's full-suite verify
- **Issue:** Not in the plan's declared `files_modified` — `46-RESEARCH.md` predates
  Plan 02, which added this file. Its `CURRENT_CFG` module constant loads
  `config/icp_scoring.yaml` directly, so once Task 1 landed the weights on disk, `CURRENT_CFG`
  became identical to what the tests called "proposed," collapsing roughly a dozen
  before/after assertions (some to a now-impossible `del` on an already-absent key).
- **Fix:** Added `PRE_PHASE_46_CFG`, a frozen deep-copy of `CURRENT_CFG` with the three
  weights forced back to their pre-Phase-46 values, and swapped it in wherever a test's
  point is exercising the delta computation. Two tests renamed to keep their names honest.
  Left unchanged every test whose assertion doesn't depend on the specific club/regulator/
  gambling values (blank-org-type, sensitivity-tier structure, zero-write proofs, etc.).
- **Files modified:** `tests/test_simulate_rubric_weights.py`
- **Verification:** `.venv/bin/python -m pytest -q` full suite green (2527/128); no
  assertion's expected value changed from what `46-RESEARCH.md`'s worked examples state.
- **Committed in:** `caae5d6` (Task 1 commit)

---

**Total deviations:** 2 auto-fixed (both Rule 3 — blocking issues discovered only by
running the full suite, not anticipated by the plan's declared file list).
**Impact on plan:** Both fixes were necessary to keep the offline suite green without
weakening any assertion; no scope creep beyond what the plan's own acceptance criteria
("no assertion weakened", full suite green) already required.

## Issues Encountered

None beyond the two deviations above. The armed HubSpot write — the one step this plan
flagged as possibly blocked (Task 2's `<precondition>`) — succeeded on the first attempt;
no checkpoint was needed.

## Two Expected Non-Findings (recorded per the plan's `<action>`, not chased as bugs)

1. **Existing enrolled records do not retroactively recompute `org_type_score`.**
   Read-only spot-check (no write) immediately after the PUT: five live
   `individual_club_team` companies, including Melbourne Racing Club (`9604614548`),
   Australian Turf Club, Tamworth Jockey Club, Victoria Racing Club, and Toowoomba Turf
   Club, all still read `org_type_score="5"` — the pre-change value. This is
   `46-RESEARCH.md` Pitfall 1's documented behavior: a flow definition edit does not
   re-fire for already-enrolled records. Phase 49 owns forcing recomputation
   (`scripts/backfill_seed_company_scores.py`'s `compute_components()` path, per
   `46-DECISION.md`'s recommendation).
2. **The parity red window is now open, confirmed by the same evidence above.** These same
   five live records' `org_type_score="5"` now disagrees with what the oracle computes
   under the landed rubric (`15` for `individual_club_team`) — every re-tiered record
   `scripts/run_scoring_parity.py`'s standing sweep samples will surface as a
   `real_finding` from this moment (**window opened: this plan's Task 1 commit,
   `caae5d6`, 2026-08-11**) until Phase 49's re-score closes it, per `46-DECISION.md`'s
   accepted Option (a).

## ROADMAP.md Phase 46 Success Criterion 4 — Not Triggered

Per `46-ENGINE-INVENTORY.md`'s and `46-DECISION.md`'s corrected engine count (two engines
carry org-type weights, not three — the n8n JS leg carries none), success criterion 4
(build → deploy → bounce the n8n cloud workflow + running-content read-back) is **not
triggered** by this phase. No org-type or gambling-deduction weight reaches the live n8n
workflow at all: `scripts/build_cloud_workflows.py` has nothing to regenerate differently
as a result of D-01/D-02/D-03, so there is no build to deploy and no running content to
bounce or read back. This is recorded here rather than silently marked done or silently
skipped — it is a conditional, not permanent, finding (re-activates if a future phase
touches categorical promotion logic, taxonomy membership, evidence gating, or merge
policy in the n8n leg, per `46-ENGINE-INVENTORY.md`'s four named triggers). None of this
plan's three weight decisions touch any of them.

## Next Phase Readiness

- `RUBRIC-03` complete. `RUBRIC-01` (Plan 03) and `RUBRIC-03` (this plan) both closed;
  `RUBRIC-02` remains open for Plan 05 to close explicitly per `46-03-SUMMARY.md`'s
  division of labor.
- Plan 05 (documentation sync, D-13) is unblocked: the weights are now landed in both
  live engines, so every doc site printing the superseded rubric (`docs/business/
  icp-scoring.md` §5, `CLAUDE.md` §10.1/§10.3, `.planning/intel/constraints.md`,
  `.planning/intel/requirements.md`, `docs/WEB-RESEARCH-SPEC.md`) can now be updated to
  the true landed values rather than a still-pending proposal. Plan 05 also owns
  rewriting `REQUIREMENTS.md` RUBRIC-03's "all three engines" prose to the corrected
  two-engine finding (left untouched by this plan, deliberately, per `46-03-SUMMARY.md`).
- Phase 49 (rescore) inherits: the parity red window opened at commit `caae5d6`
  (2026-08-11); the recommended re-score mechanism
  (`scripts/backfill_seed_company_scores.py`'s `compute_components()` path,
  `HARD_CEILING_RECORDS=25` chunking gate); and the confirmed non-recompute behavior of
  already-enrolled records as its starting state.
- No blockers.

## Self-Check: PASSED

`config/icp_scoring.yaml` confirmed on disk with `individual_club_team: 15`,
`regulator: -20`, `graduated_deductions: {}`. Both `.after.json` flow archives confirmed
matching the live GET output pasted above. All three task commit hashes (`caae5d6`,
`5643dda`, `4f7c395`) confirmed present in `git log --oneline --all`.

---
*Phase: 46-rubric-decision-simulation-engine-parity*
*Completed: 2026-08-11*
