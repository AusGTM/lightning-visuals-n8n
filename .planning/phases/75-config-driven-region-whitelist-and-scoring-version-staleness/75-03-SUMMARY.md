---
phase: 75-config-driven-region-whitelist-and-scoring-version-staleness
plan: 03
subsystem: scoring-engine
tags: [icp-scoring, version-staleness, recompute-lane, write-safety, n8n, hubspot, tdd]

# Dependency graph
requires:
  - phase: 75-01
    provides: config/icp_scoring.yaml's version field, scripts/gen_icp_scoring_js.py,
      n8n/code/icpScoring.generated.js (VERSION export), the lv_icp_scoring_version
      write-side stamp in ENRICH_DECIDE_CO_CLOUD
  - phase: 75-02
    provides: the "icpScoring.generated.js" inline() ordering convention (declaration
      before consumer) three ENRICH_NORMALIZE_SCORE* call sites already established
provides:
  - lv_icp_scoring_version fetched everywhere it is read (cloud + local-live company
    search/fetch lists, SJ-2's search)
  - ALLOW_HUBSPOT_RECOMPUTE_WRITES -- the fourth ALLOW_HUBSPOT_* authority, standing
    (not session-scoped), off by default, unreachable from the other three
  - the version-stale skip -> recompute reroute riding the EXISTING IF Company Recompute
    lane (zero new nodes) on the cloud enrichment workflow, guarded off on local-live
  - SJ-2's monthly version-stale backstop (search filter widening + gate fix), armed-only
    by design, classified "enrich" not "recompute"
affects: [75-04, 75-05, 75-06]

# Actuals (#2632)
actuals:
  tokens: 181947
  tasks: 3
  commits: 4

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Per-lane parameterized Code-node body (_enrich_co_gate(version_stale_reroute))
      replacing a shared module-level string constant -- the mechanism for baking a
      build-time-only boolean into two otherwise-identical jsCode bodies without a
      runtime flag or a hand-duplicated body"
    - "A fourth ALLOW_HUBSPOT_* write-safety authority deliberately unreachable from the
      other three and excluded from the arming/disarming tooling (D-75-16/D-75-18a) --
      the second precedent after ALLOW_SJ3_DRAIN_WRITES for a flag that is NOT part of
      the session-scoped grant model"
    - "write_request.action as a SEPARATE classification from the row's own action --
      'what this row is' vs 'which authority may write it' now diverge for the first
      time (recompute vs enrich)"

key-files:
  created:
    - tests/n8n/companyVersionStaleRecompute.test.mjs
    - tests/n8n/sj2VersionStaleGate.test.mjs
    - .planning/todos/pending/2026-09-20-sj2-version-stale-backstop-classifies-enrich-not-recompute.md
  modified:
    - scripts/build_cloud_workflows.py
    - n8n/wf_enrichment_cloud.json
    - n8n/wf_enrichment_local_live.json
    - n8n/wf_scheduled_maintenance_cloud.json
    - n8n/wf_review_decision_cloud.json
    - n8n/wf_contact_ingest_cloud.json
    - tests/test_hubspot_properties_config.py
    - tests/n8n/companyRecomputeLaneFlow.test.mjs
    - tests/n8n/materialConflictNoVetoFlip.test.mjs
    - tests/n8n/sjPredicates.test.mjs
    - tests/test_cloud_write_path.py
    - tests/test_bug10_company_search_transport.py

key-decisions:
  - "The write-gate wiring (_write_gate_js) needed a genuine code change beyond what the
    plan's <action> text spelled out: without teaching the gate to read
    write_request.action==='recompute' and override its own static, per-node-type
    classification, ALLOW_HUBSPOT_RECOMPUTE_WRITES would be UNREACHABLE end to end --
    'HubSpot Company Update Write Gate' would keep calling _writeSafetyAllows('enrich',
    ...) regardless of what Decide Company Action emitted. The plan's own read_first line
    ('the four-arg shape whose first argument becomes the gate's action') states this as
    fact; it wasn't yet true of the code. Fixed via a one-line override, scoped so every
    non-recompute row's classification is byte-unchanged (verified: only
    ENRICH_DECIDE_CO_CLOUD ever emits a 'recompute' write_request, only on the
    companies-update path)."
  - "VERSION_RECOMPUTE (and SJ2_CO_GATE's mirror predicate) both gate on
    !row.lookup_failed, which the plan's <action> text did not name. Found by the
    full-suite run: a lookup-failed row's existingRecord is {} (we don't know whether
    the record exists), and treating {}.lv_icp_scoring_version === undefined as 'known
    and stale' rerouted a fail-closed 'skip' into 'enrich' -- the opposite of the plan's
    stated intent ('so a transport error still wins'), which the ORDERING instruction
    alone does not achieve without this explicit exclusion."
  - "The reroute rides the EXISTING IF Company Recompute node via a marker on the row
    (row.recompute/row.recompute_reason), not a literal IF-splice onto IF Company Skip's
    true branch. Verified SAFE by direct inspection, not merely by following the plan's
    instruction: Decide Company Action Merge is append-mode with requiredInputs=1 (v1
    semantics), so a marker delivered by the pre-existing 'Recompute Not Requested
    Sentinel' arriving on the SAME Merge input as a real version-stale row's data (both
    keyed off the same IF Company Recompute true-branch producer) is harmless -- Decide
    Company Action's own '.filter((it) => Object.keys(it.json || {}).length > 0)' drops
    the marker. No sentinel re-pointing was needed."
  - "ENRICH_CO_GATE became the function _enrich_co_gate(version_stale_reroute: bool),
    called once per lane (ENRICH_CO_GATE_CLOUD=True, ENRICH_CO_GATE_LOCAL_LIVE=False)
    rather than a single shared string -- the only way to bake a build-time-only literal
    into two otherwise-identical jsCode bodies without a runtime flag or duplicating the
    whole body by hand."

requirements-completed: []

coverage:
  - id: D1
    description: "lv_icp_scoring_version is fetched everywhere existingRecord.lv_icp_scoring_version
      is read (ENRICH_COMPANY_SEARCH_PROPERTIES_CSV, HS_CO_SEARCH_BODY_EXPR, SJ-2 Search's
      properties_csv), so the version comparison can never silently route the whole
      population one way via an undefined read"
    verification:
      - kind: unit
        ref: "tests/test_hubspot_properties_config.py#test_lv_icp_scoring_version_appears_in_the_company_fetch_property_list"
        status: pass
      - kind: unit
        ref: "tests/n8n/sj2VersionStaleGate.test.mjs#SJ-2 Search (stale refresh) fetches lv_icp_scoring_version"
        status: pass
      - kind: integration
        ref: "grep -c lv_icp_scoring_version n8n/wf_enrichment_cloud.json (4)"
        status: pass
    human_judgment: false
  - id: D2
    description: "ALLOW_HUBSPOT_RECOMPUTE_WRITES exists, ships false, grants a
      recompute-classified write on that flag ALONE (no TEST_RECORD_IDS/TEST_RECORD_DOMAINS
      allowlist), is unreachable from the other three ALLOW_HUBSPOT_* flags, and is
      reachable end to end from Decide Company Action through the spliced write gate"
    verification:
      - kind: unit
        ref: "tests/n8n/companyVersionStaleRecompute.test.mjs#HubSpot Company Update Write Gate: disarmed build denies a recompute-classified row even with an empty allowlist requirement bypassed"
        status: pass
      - kind: unit
        ref: "tests/n8n/companyVersionStaleRecompute.test.mjs#HubSpot Company Update Write Gate: armed build allows a recompute-classified row with NO allowlist entry at all"
        status: pass
      - kind: unit
        ref: "tests/n8n/companyVersionStaleRecompute.test.mjs#HubSpot Company Update Write Gate: arming ALLOW_HUBSPOT_RECOMPUTE_WRITES grants NOTHING to an ordinary enrich-classified sibling row"
        status: pass
    human_judgment: false
  - id: D3
    description: "A version-stale company whose gate verdict is skip is rerouted into
      Decide Company Action through the existing IF Company Recompute lane -- zero new
      nodes, zero provider/research/judge/merge cost -- while a version-fresh skip and
      every create/enrich verdict are untouched; the webhook recompute:true lane is
      unaffected; the local-live preview lane is guarded off by a per-lane build-time
      literal"
    verification:
      - kind: unit
        ref: "tests/n8n/companyVersionStaleRecompute.test.mjs (17 tests, full behaviour matrix)"
        status: pass
      - kind: unit
        ref: "tests/n8n/companyRecomputeLaneFlow.test.mjs (8 tests, request-level lane regression guard)"
        status: pass
      - kind: integration
        ref: "python one-liner: node count 289 (unchanged), no new IF/Merge node, IF Company Skip edges unchanged"
        status: pass
    human_judgment: false
  - id: D4
    description: "SJ-2's monthly stale-refresh search selects a version-stale-but-input-fresh
      company (widened filterGroups, within HubSpot's documented 5-group/6-filter/18-total
      cap) and SJ2_CO_GATE stops treating a version mismatch as skip, so the row reaches
      SJ-2 Set Requested -- while staying allowlist-gated (write_request classified
      'enrich', not 'recompute') by deliberate choice, recorded as a named assumption"
    verification:
      - kind: unit
        ref: "tests/n8n/sj2VersionStaleGate.test.mjs (8 tests)"
        status: pass
      - kind: other
        ref: "HubSpot CRM search docs fetched live (developers.hubspot.com/docs/api/crm/search) and grepped for the filterGroups cap statement during this task"
        status: pass
    human_judgment: true
    rationale: "SJ-2 is a monthly scheduled job; nothing in this plan runs it live (no
      deploy, no bounce, no arm). The verifier should read this deliverable as
      offline-proven structure + gate logic, not a live-observed dispatch -- SJ-2 has
      never selected a real version-stale record on the running instance."

duration: 33min (commit span; full session including context loading longer)
completed: 2026-09-20
status: complete
---

# Phase 75 Plan 03: Config-Driven Region Whitelist and Scoring-Version Staleness Summary

**Every company Decide Company Action touches now has its scoring rubric version fetched
and compared; a version-stale skip reroutes into the existing zero-cost recompute lane
with no new node; recompute writes get a fourth, standing write authority
(`ALLOW_HUBSPOT_RECOMPUTE_WRITES`) wired end to end through the spliced write gate; and
SJ-2's monthly job now selects and gates (though does not yet write to) a
version-stale-but-input-fresh company as the documented backstop.**

## Performance

- **Duration:** 33 min (commit span: 2026-09-20T06:19:43Z start of session context load,
  first RED commit shortly after, closing commit 2026-09-20T06:52:19Z)
- **Started:** 2026-09-20T06:20:00Z (approx)
- **Completed:** 2026-09-20T06:52:19Z
- **Tasks:** 3
- **Files modified:** 18 (3 created, 15 modified)

## Accomplishments

- `ENRICH_COMPANY_SEARCH_PROPERTIES_CSV` and its local-live sibling `HS_CO_SEARCH_BODY_EXPR`
  both now fetch `lv_icp_scoring_version`; `WRITE_SAFETY_DEFAULTS` gains
  `ALLOW_HUBSPOT_RECOMPUTE_WRITES = "false"` with a comment enumerating the exact
  four-property recompute PATCH set; `_writeSafetyAllows` gains a first branch (grew 18 ->
  25 lines) that grants a `"recompute"`-classified write on that flag ALONE, bypassing the
  shared allowlist entirely.
- `_write_gate_js` (the shared write-gate splice function) now reads
  `write_request.action === "recompute"` and overrides its own static, per-node-type
  classification when it sees it — the missing half of the wiring the plan's own
  `<read_first>` assumed already existed. Without this, the new flag would have been
  dead code.
- `ENRICH_CO_GATE` is now `_enrich_co_gate(version_stale_reroute: bool)`, called once for
  the cloud build (`ENRICH_CO_GATE_CLOUD`, `true`) and once for local-live
  (`ENRICH_CO_GATE_LOCAL_LIVE`, `false`). A version-stale `skip` row is marked
  `recompute: true, recompute_reason: "version_stale"` — the SAME marker the existing
  `IF Company Recompute` node already routes on — so the reroute rides the existing lane
  with ZERO new IF/Merge nodes (node count unchanged: 289). Gated on `action === "skip"`
  (a `create` verdict is never rerouted), `!row.lookup_failed` (a transport-failure row
  has no real existing record to be "stale" about — found via the full-suite run), and
  `!RECOMPUTE_REQUESTED` (mutual exclusivity with an operator-requested recompute).
- `ENRICH_DECIDE_CO_CLOUD`'s `write_request` first argument is
  `row.recompute === true && action === "enrich" ? "recompute" : action` — the row's own
  top-level `action` is untouched; only the write authority classification moves.
- SJ-2 backstop: `SJ-2 Search (stale refresh)`'s `properties_csv` and `filterGroups`
  widened (2 new OR'd groups, verified against HubSpot's own live-fetched documentation
  to stay within the 5-group/18-filter cap); `SJ2_CO_GATE` treats a version mismatch as
  not-skip while its `RECOMPUTE_REQUESTED = false` constant and plain `"enrich"`
  `write_request` classification stay byte-unchanged — deliberately kept allowlist-gated,
  recorded as a `kind: question` todo naming the operator as owner.
- Two new test files (25 tests total) plus fixture fixes in 5 more pre-existing test
  files that would otherwise have been broken by the new "complete records must also
  carry a real `lv_icp_scoring_version`" axis.

## Task Commits

1. **Task 1 RED:** `59955fd7` (test) — `tests/test_hubspot_properties_config.py`
   assertion demonstrating `lv_icp_scoring_version` missing from the company fetch list;
   confirmed failing against unmodified production code.
2. **Task 1 GREEN:** `57ddb603` (feat) — fetch-list additions, `ALLOW_HUBSPOT_RECOMPUTE_WRITES`,
   `_writeSafetyAllows`'s new branch, regenerated workflow JSON.
3. **Task 2:** `b960d9ad` (feat) — the `_enrich_co_gate` per-lane function, the reroute
   marker, the `_write_gate_js` wiring fix, `ENRICH_DECIDE_CO_CLOUD`'s write_request
   classification, `companyVersionStaleRecompute.test.mjs` (new), and fixture fixes in
   `companyRecomputeLaneFlow.test.mjs`, `materialConflictNoVetoFlip.test.mjs`,
   `test_cloud_write_path.py`.
4. **Task 3:** `e7c4e2e2` (feat) — SJ-2 Search filter/fetch widening, `SJ2_CO_GATE`'s
   version check, `CURRENT_ICP_SCORING_VERSION` build-time constant,
   `sj2VersionStaleGate.test.mjs` (new), fixture fixes in `sjPredicates.test.mjs` and
   `test_bug10_company_search_transport.py`, the `kind: question` todo.

**Plan metadata:** this SUMMARY's own commit (below).

## Files Created/Modified

- `scripts/build_cloud_workflows.py` — fetch-list additions, `ALLOW_HUBSPOT_RECOMPUTE_WRITES`,
  `_writeSafetyAllows`'s recompute branch, `_write_gate_js`'s override, `_enrich_co_gate()`,
  `ENRICH_DECIDE_CO_CLOUD`'s write_request classification, SJ-2 search/gate changes,
  `CURRENT_ICP_SCORING_VERSION`
- `n8n/wf_enrichment_cloud.json`, `n8n/wf_enrichment_local_live.json`,
  `n8n/wf_scheduled_maintenance_cloud.json`, `n8n/wf_review_decision_cloud.json`,
  `n8n/wf_contact_ingest_cloud.json` — regenerated (no hand-edit)
- `tests/n8n/companyVersionStaleRecompute.test.mjs` — new, 17 tests
- `tests/n8n/sj2VersionStaleGate.test.mjs` — new, 8 tests
- `tests/test_hubspot_properties_config.py` — new fetch-list assertion
- `tests/n8n/companyRecomputeLaneFlow.test.mjs` — `completeRecord()` stamps a fresh
  version by default; one new named regression-guard test
- `tests/n8n/materialConflictNoVetoFlip.test.mjs` — `fullyRequiredCompanyRecord()`
  stamps a fresh version
- `tests/n8n/sjPredicates.test.mjs` — its 2-group assertion re-scoped to the first two
  (TTL) groups
- `tests/test_cloud_write_path.py` — `ENRICH_CO_GATE` import updated to
  `ENRICH_CO_GATE_CLOUD`
- `tests/test_bug10_company_search_transport.py` — SJ-2's expected `properties_csv`
  fixture updated
- `.planning/todos/pending/2026-09-20-sj2-version-stale-backstop-classifies-enrich-not-recompute.md` — new

## Decisions Made

See `key-decisions` in the frontmatter above.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] `_write_gate_js` needed to read `write_request.action`,
or the new flag would be unreachable**
- **Found during:** Task 2, while implementing `ENRICH_DECIDE_CO_CLOUD`'s write_request
  classification change and reasoning through the must_haves key_link ("Decide Company
  Action's `_buildWriteRequest` classification -> HubSpot Company Update Write Gate ->
  `_writeSafetyAllows('recompute', ...)`")
- **Issue:** `_write_gate_js(action)` bakes the Python-side `action` string statically at
  generation time (`_writeSafetyAllows({action!r}, ...)`), never reading
  `write_request.action` at runtime. Task 1's own `<read_first>` states as fact that "the
  four-arg shape whose first argument becomes the gate's `action`" — true of the intent,
  not yet true of the code. Without a fix, "HubSpot Company Update Write Gate" would keep
  calling `_writeSafetyAllows('enrich', ...)` forever, and `ALLOW_HUBSPOT_RECOMPUTE_WRITES`
  would be dead code from the moment it shipped.
- **Fix:** `_write_gate_js` now computes `var _action = (wr && wr.action === 'recompute')
  ? 'recompute' : {action!r};` and passes `_action` to `_writeSafetyAllows`. Scoped to a
  single override: every other classification stays the node's own static baked value.
  Confirmed only `ENRICH_DECIDE_CO_CLOUD` ever emits a `"recompute"` `write_request`, and
  only on the companies-update path, so no other write gate is affected.
- **Files modified:** `scripts/build_cloud_workflows.py`
- **Verification:** `tests/n8n/companyVersionStaleRecompute.test.mjs`'s 3 write-gate tests
  (disarmed denies, armed allows the recompute row with no allowlist entry, armed still
  refuses an ordinary enrich-classified sibling row)
- **Committed in:** `b960d9ad`

**2. [Rule 1 - Bug] `VERSION_RECOMPUTE` (and its SJ-2 mirror) needed a `!row.lookup_failed`
guard, or a transport failure would be rerouted into recompute**
- **Found during:** the full-suite run after Task 2's implementation
- **Issue:** `tests/n8n/bareEventChainFlow.test.mjs` and
  `tests/n8n/companyNameOnlyOutcome.test.mjs` both exercise a lookup-failed row
  (`existingRecord: {}`, `lookup_failed: true`), whose action is force-set `skip` by the
  pre-existing fail-closed override. Without a `!row.lookup_failed` conjunct,
  `{}.lv_icp_scoring_version !== VERSION` reads `true` (stale), and `VERSION_RECOMPUTE`
  fired, flipping the intentional fail-closed `"skip"` back to `"enrich"` — the OPPOSITE
  of the plan's own stated intent ("computed AFTER the lookup_failed override... so a
  transport error still wins"). The ORDERING instruction alone (compute AFTER the
  override) does not achieve "wins" without this explicit exclusion — a genuinely novel
  gap the plan's prose named the goal for but not the mechanism.
- **Fix:** added `!row.lookup_failed` to `VERSION_RECOMPUTE`'s conjuncts in
  `ENRICH_CO_GATE`, and the identical guard to `SJ2_CO_GATE`'s own version-stale check
  (Task 3, same bug class, found proactively before it could recur).
- **Files modified:** `scripts/build_cloud_workflows.py`
- **Verification:** `tests/n8n/bareEventChainFlow.test.mjs`,
  `tests/n8n/companyNameOnlyOutcome.test.mjs` back to green;
  `tests/n8n/sj2VersionStaleGate.test.mjs`'s dedicated lookup-failed test
- **Committed in:** `b960d9ad` (ENRICH_CO_GATE half), `e7c4e2e2` (SJ2_CO_GATE half)

**3. [Rule 1 - Bug] Five more pre-existing test fixtures needed a stamped
`lv_icp_scoring_version`, or their "complete record -> skip" assertions broke**
- **Found during:** the full-suite run after Task 2's and Task 3's implementations
- **Issue:** `tests/n8n/companyRecomputeLaneFlow.test.mjs`'s `completeRecord()`,
  `tests/n8n/materialConflictNoVetoFlip.test.mjs`'s `fullyRequiredCompanyRecord()`, and
  `tests/test_cloud_write_path.py`'s `ENRICH_CO_GATE` import (now a function, not a
  constant) all predate this plan and never anticipated a genuinely-complete-record
  fixture needing a matching version stamp; `tests/n8n/sjPredicates.test.mjs`'s
  hardcoded `filterGroups.length === 2` assertion and
  `tests/test_bug10_company_search_transport.py`'s expected `properties_csv` fixture for
  "SJ-2 Search (stale refresh)" both predated the deliberate widening these plans make.
  None is in the plan's own `files_modified` scope.
- **Fix:** stamped `lv_icp_scoring_version: VERSION` on the two fixture builders
  (default parameter, so a caller can still pass a stale value explicitly); updated the
  `test_cloud_write_path.py` import to `ENRICH_CO_GATE_CLOUD`; re-scoped
  `sjPredicates.test.mjs`'s assertion to the first two groups (its own test name promises
  only that); updated the `properties_csv` fixture in `test_bug10_company_search_transport.py`.
- **Files modified:** the five files named above
- **Verification:** full `pytest` suite (5180 passed / 160 skipped / 2 known-red); full
  `node --test tests/n8n/*.test.mjs` (1350 passed / 0 failed)
- **Committed in:** `b960d9ad` (2 files), `e7c4e2e2` (2 files); the 5th
  (`test_cloud_write_path.py`) in `b960d9ad`

---

**Total deviations:** 3 auto-fixed groups (1 Rule 2 missing-critical-functionality group
covering 1 file, 2 Rule 1 bug-fix groups covering 2 and 5 files respectively).
**Impact on plan:** the Rule 2 fix was necessary for the plan's own stated goal (a
reachable, end-to-end write authority) to be true rather than merely declared; the two
Rule 1 groups were necessary consequences of the version-staleness axis this plan
introduces, none representing scope creep beyond making the plan's stated goal actually
true end-to-end. No frozen fixture or stress-test file was touched.

### Named Deviation (per the plan's own explicit instruction, D-75-12/D-75-16(a))

Task 2's `<action>` text required this to be named explicitly, both in code and here.
D-75-12's wording sketches the mechanism as `"IF Company Skip" additionally tests`.
The literal IF-splice was REJECTED in favor of a marker read by the EXISTING
`IF Company Recompute` node — D-75-16(a)'s own text licenses this shape by naming
`row.recompute === true` / "the D-75-12 reroute marker carried to the gate" as an
acceptable signal. `IF Company Skip`'s true branch feeds a Merge
(`IF Company Skip -> Build Response Merge Pass-Through`); inserting a two-output IF there
would create two new branches that can each legitimately deliver zero items, exactly the
Phase 70 G-70-2/G-70-3 defect class (CLAUDE.md §13.0.3). The marker approach adds ZERO
nodes and ZERO new Merge inputs; the behavioural outcome is identical. Verified SAFE
beyond the plan's own instruction (see key-decisions above): `Decide Company Action
Merge` is append-mode with `requiredInputs: 1` (v1 semantics), so a pre-existing
whole-request sentinel's marker co-arriving on the same Merge input as a real
version-stale row's data is harmless — `Decide Company Action` already filters
empty-json marker items before treating anything as a real row.

### Plan-text discrepancy (documented, not silently resolved)

Task 3's `<action>` text repeats Task 2's "LOCAL-LIVE LANE GUARD" paragraph verbatim,
instructing a per-lane `VERSION_STALE_REROUTE`-style guard for `SJ2_CO_GATE` against a
local-live sibling. Verified during execution: `SJ2_CO_GATE` has exactly ONE call site
(`scripts/build_cloud_workflows.py:11241`, inside `build_scheduled_maintenance_cloud()`
only) — it is not shared with `build_enrichment_local_live()` at all, unlike
`ENRICH_CO_GATE`. This paragraph is inapplicable to Task 3 and was not implemented for
it; the reasoning appears to be a copy-paste carryover from Task 2's own text rather than
a genuine SJ-2-specific requirement. No guard was added to `SJ2_CO_GATE` for this reason,
and none is needed.

## Issues Encountered

None beyond the deviations documented above — all were resolved within this plan's
scope.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `ALLOW_HUBSPOT_RECOMPUTE_WRITES` ships `"false"` everywhere; the operator's flip to
  `"true"` (deploy + bounce, after the first supervised bump sweep is reviewed per
  D-75-17) is a later-plan / runbook step, explicitly out of this phase's exit gate.
- `.planning/todos/pending/2026-09-20-sj2-version-stale-backstop-classifies-enrich-not-recompute.md`
  is the recorded, operator-owned question about whether SJ-2's backstop should ever get
  its own standing authority — revisit at the trigger named there, not before.
- `tests/test_hubspot_schema_coverage.py`'s known-red test (unchanged deviation class from
  Plan 01, now spanning a second workflow file for the identical reason — Plan 01's
  original entry in `.planning/WINDOWS.md` covers this; no new WINDOWS entry needed)
  remains the tracked blocker for **deploy** (not for continuing to plan/execute
  offline) — resolves when a later plan runs `sync_hubspot_properties.py` live.
- Nothing in this plan touches `config/hubspot_flows/4626722240-geography-score.after.json`,
  the enum-option live PUT, or `scripts/sync_hubspot_properties.py`'s new
  `_update_property_options_live` function — those are D-75-09/D-75-10/D-75-11's scope,
  presumably a later plan in this phase (04/05).

---
*Phase: 75-config-driven-region-whitelist-and-scoring-version-staleness*
*Plan: 03*
*Completed: 2026-09-20*

## Self-Check: PASSED

- `tests/n8n/companyVersionStaleRecompute.test.mjs` — FOUND
- `tests/n8n/sj2VersionStaleGate.test.mjs` — FOUND
- `.planning/todos/pending/2026-09-20-sj2-version-stale-backstop-classifies-enrich-not-recompute.md` — FOUND
- Commit `59955fd7` (test, RED) — FOUND in `git log`
- Commit `57ddb603` (feat, Task 1 GREEN) — FOUND in `git log`
- Commit `b960d9ad` (feat, Task 2) — FOUND in `git log`
- Commit `e7c4e2e2` (feat, Task 3) — FOUND in `git log`
- Full `pytest` suite: 5180 passed / 160 skipped / 2 known-red (documented deviation,
  same root cause as Plan 01's, now spanning a second file)
- `node --test tests/n8n/*.test.mjs`: 1350 passed / 0 failed
- `.venv/bin/python scripts/build_cloud_workflows.py && git diff --quiet -- n8n/`: exits
  0 (n8n/ clean after regeneration)
- `n8n/wf_enrichment_cloud.json` node count: 289 (unchanged from pre-plan value)
- No committed `n8n/wf_*.json` contains `ALLOW_HUBSPOT_RECOMPUTE_WRITES` set to `"true"`
- Nothing deployed, bounced or armed
