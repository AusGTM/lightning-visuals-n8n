---
phase: 75-config-driven-region-whitelist-and-scoring-version-staleness
plan: 04
subsystem: hubspot-migration-tooling
tags: [icp-scoring, hubspot-flow, codegen, write-safety, arming, tdd]

# Dependency graph
requires:
  - phase: 75-01
    provides: config/icp_scoring.yaml regions.home, src/icp_scoring.py::regions_home(),
      scripts/gen_icp_scoring_js.py generator precedent
  - phase: 75-02
    provides: config/hubspot_properties.yaml's widened lv_country_region_normalized
      (8 new options, UK hidden) and the new lv_icp_scoring_version property declaration
      -- both declared, not yet live
  - phase: 75-03
    provides: ALLOW_HUBSPOT_RECOMPUTE_WRITES in WRITE_SAFETY_DEFAULTS (ships "false"),
      the version-stale recompute lane
provides:
  - scripts/gen_geography_flow.py -- the HubSpot geography-score flow's branch values are
    generated from regions.home, never hand-edited; a live divergence is ordinary drift
  - scripts/sync_hubspot_properties.py's new update bucket + _update_property_options_live
    -- the tool can now add enum options and hide an existing one live, refusing by
    construction to ever drop one
  - scripts/bounce_n8n_workflows.py verifies ALLOW_HUBSPOT_RECOMPUTE_WRITES against the
    COMMITTED workflow body (not a hardcoded literal) and surfaces its value per row
  - tests/test_recompute_flag_isolation.py -- pins that the fourth flag is structurally
    unreachable from every arming/overlay/disarm surface
affects: [75-05, 75-06]

# Actuals (#2632)
actuals:
  tokens: 13100
  tasks: 3
  commits: 6
plan_head_before: ed2c67f9d5a4dab8af0fb502e888f454cd15f2a0

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "One recursive filter-location walker (_find_geography_filters) shared between the
      offline generator and the live drift comparator -- same pattern this repo already
      uses for region aliases/veto reasons (one loader, no second parser)"
    - "compute_property_diff's third bucket (update, alongside create/drift) -- an
      existing property's option set may only ever WIDEN or change hidden, never shrink;
      the refusal is structural (classification), not a runtime guard"
    - "A read-back script comparing LIVE state against the COMMITTED workflow body it
      already has on disk, rather than a hardcoded literal, so a deliberately-true-able
      flag can be verified in both directions without the read-back needing to know which
      value is 'correct' at any given moment"

key-files:
  created:
    - scripts/gen_geography_flow.py
    - tests/test_geography_flow_conformance.py
    - tests/test_recompute_flag_isolation.py
  modified:
    - config/hubspot_flows/4626722240-geography-score.after.json
    - scripts/check_schema_drift.py
    - scripts/sync_hubspot_properties.py
    - scripts/bounce_n8n_workflows.py
    - scripts/deploy_n8n_workflows.py
    - tests/test_check_schema_drift.py
    - tests/test_sync_hubspot_properties.py

key-decisions:
  - "HubSpot's PATCH /crm/v3/properties/{objectType}/{propertyName} contract was verified
    live (curl, no token) against developers.hubspot.com this session -- method+path+the
    endpoint's own documented description ('Perform a partial update ... Provided fields
    will be overwritten') confirms Assumption A1's full-array-replace shape. The
    per-option hidden field's settability was NOT independently re-confirmed via this
    specific fetch (the page's field-level schema renders client-side); recorded as
    [documented], not [observed live], per CLAUDE.md's tagging discipline rather than
    overclaimed."
  - "Added a --dry-run no-op flag to sync_hubspot_properties.py's argparse (Rule 3,
    blocking): the plan's own <verify> command invokes `--dry-run`, and the pre-existing
    parser had zero registered arguments -- any flag raised 'unrecognized arguments' and
    exited 2 before the credential check ever ran."
  - "Fixed a Rule-1 bug in sync_object_type's post-write confirmation loop while wiring
    the new update path: the pre-existing bare if/else (kind=='property' vs implicit
    'else -> group') would have silently checked a new 'property_update' entry against
    fresh_groups instead of fresh_props the first time a live update actually ran.
    Rewritten as an explicit three-way branch; the property_update branch additionally
    re-GETs and asserts the live options now equal the PATCHed desired set."
  - "Split each task's tests and implementation into separate RED and GREEN commits
    (mirroring Plans 01-03), even though the plan's own tdd=\"true\" text did not spell
    out the two-commit shape for every task -- for Task 3 this meant recognizing that 5
    of the 8 new isolation assertions already passed against unmodified code (n8n_arming.py
    and deploy_n8n_workflows.py needed no functional change), so only the 3 _row_ok
    assertions constitute the task's real RED; verified by temporarily restoring each
    task's pre-change file, confirming the target failures, then restoring the
    implementation -- gsd_run check tdd-red-evidence remains TAP-only (Plans 01/02/03's
    repeated finding) and was not relied on."

requirements-completed: []

coverage:
  - id: D1
    description: "config/hubspot_flows/4626722240-geography-score.after.json's geography
      branch values are generated from regions.home by scripts/gen_geography_flow.py
      (D-75-09), never hand-edited; a live divergence is reported as ordinary drift
      (exit 1) by scripts/check_schema_drift.py without reclassifying the flow's
      presence/enabled state out of the existing exit-2 do-not-archive set (D-75-11)"
    verification:
      - kind: unit
        ref: "tests/test_geography_flow_conformance.py (4 tests: byte-equality, render()
          idempotence, raises on 0/2 matching filters)"
        status: pass
      - kind: unit
        ref: "tests/test_check_schema_drift.py (6 new geography_flow_drift_entry /
          exit_code_for cases, offline against a synthetic body)"
        status: pass
      - kind: other
        ref: "git diff before/after the generator run: only the values array changed
          (3180 -> 3450 bytes), top-level key list identical, .before.json byte-unchanged;
          re-running the generator produces zero further diff"
        status: pass
    human_judgment: false
  - id: D2
    description: "scripts/sync_hubspot_properties.py can add enum options and hide an
      existing one live (the UK hide + 8 new region codes on
      lv_country_region_normalized), gated behind the same ALLOW_HUBSPOT_PROPERTY_WRITES
      two-key gate and the same undo-manifest mechanism as create, and refuses by
      construction to ever drop a live option (T-75-16)"
    verification:
      - kind: unit
        ref: "tests/test_sync_hubspot_properties.py (17 tests total, 8 new: update vs
          drift classification including the real Plan-02 manifest against a synthetic
          pre-Phase-75 live schema, the option-delete refusal, gate isolation, undo-manifest
          pre_update_options shape)"
        status: pass
      - kind: other
        ref: "grep -c 'requests.patch\\|\\.patch(' scripts/sync_hubspot_properties.py == 1;
          grep -n 'delete' shows only the two option-delete-refusal prose comments, no
          call path"
        status: pass
    human_judgment: true
    rationale: "HubSpot's exact PATCH contract for this endpoint was confirmed via a live
      curl to HubSpot's own public documentation this session (method, path, replace
      semantics) but the per-option hidden field's settability on update, and the PATCH
      call itself, were never exercised against the real HubSpot API -- that live proof
      is Plan 05's job. The verifier should read this deliverable as offline-proven
      classification + gate logic + a documented (not observed) API contract."
  - id: D3
    description: "scripts/bounce_n8n_workflows.py reads ALLOW_HUBSPOT_RECOMPUTE_WRITES and
      compares its LIVE value against the COMMITTED workflow body's own value (not a
      hardcoded false), in both directions, and surfaces the flag's current value in its
      per-row output (T-75-15); operator-claude-plugin/scripts/n8n_arming.py,
      scripts/deploy_n8n_workflows.py's overlay spec, and config/execution_budget.yaml
      remain structurally unable to ever touch or widen this standing authority (D-75-18)"
    verification:
      - kind: unit
        ref: "tests/test_recompute_flag_isolation.py (8 assertions: WRITE_SAFETY_DEFAULTS
          ships false, absent from n8n_arming's 3 sets and deploy's overlay spec,
          set_write_safety/disarmed_targets both refuse to target it, _row_ok accepts
          live=committed=true / rejects live-true-committed-false / rejects
          live-false-committed-true)"
        status: pass
      - kind: other
        ref: "git status --porcelain -- config/execution_budget.yaml operator-claude-plugin/
          empty throughout (only the pre-existing untracked .DS_Store, unrelated to this
          plan)"
        status: pass
    human_judgment: false

duration: 42min
completed: 2026-09-20
status: complete
---

# Phase 75 Plan 04: HubSpot Tooling Learns the Two New Facts Summary

**The geography-score flow's whitelist is now generated from `regions.home` with live
drift detection on both sides, `sync_hubspot_properties.py` gained an option-update path
that can add codes and hide `UK` but structurally refuses to ever drop a live option, and
`bounce_n8n_workflows.py` verifies the new standing `ALLOW_HUBSPOT_RECOMPUTE_WRITES`
authority against the committed workflow body — all three offline; nothing was deployed,
bounced, armed, or written live.**

## Performance

- **Duration:** 42 min
- **Started:** 2026-09-20T06:37:00Z (approx, immediately following Plan 03's closing commit)
- **Completed:** 2026-09-20T07:19:00Z
- **Tasks:** 3
- **Files modified:** 10 (3 created, 7 modified)

## Accomplishments

- `scripts/gen_geography_flow.py` (new): walks the committed
  `4626722240-geography-score.after.json`, asserts exactly one filter on
  `lv_country_region_normalized`/`IS_EQUAL_TO` exists, and replaces its `operation.values`
  with `list(regions_home())`. Ran once — the committed body's branch grew from
  `["AU","NZ","ANZ"]` to the 12 `regions.home` codes (3180 → 3450 bytes; top-level key
  list, `.before.json`, and every other byte unchanged; re-running is now a no-op diff).
- `scripts/check_schema_drift.py` gained `geography_flow_drift_entry()`, reusing the
  generator's own filter-location walker: a live branch mismatch is ordinary drift
  (exit 1), reported alongside — never instead of — the flow's existing exit-2
  presence/enabled do-not-archive check.
- `scripts/sync_hubspot_properties.py::compute_property_diff` gained a third `update`
  bucket: an existing property whose live option values are a subset of desired's (new
  codes, and/or only `hidden` differs) is `update`; a live value absent from desired stays
  `drift`, report-only, never auto-fixed — the option-delete refusal (T-75-16). New
  `_update_property_options_live` issues one `PATCH /crm/v3/properties/{objectType}/{propertyName}`
  carrying the full desired options array, gated behind the same
  `ALLOW_HUBSPOT_PROPERTY_WRITES` two-key gate as create, and records an undo-manifest
  entry carrying `pre_update_options`.
- `scripts/bounce_n8n_workflows.py` compares `ALLOW_HUBSPOT_RECOMPUTE_WRITES`'s live
  literal against the flag's literal in the COMMITTED workflow body (bidirectional check),
  and prints it in a new "recompute flag" column on every row.
- `tests/test_recompute_flag_isolation.py` (new, root `tests/`) pins that the fourth flag
  is absent from every arming/overlay/disarm surface, and that `set_write_safety`/
  `disarmed_targets` both refuse it outright.

## Task Commits

Each task followed a RED (test-only) then GREEN (implementation) split:

1. **Task 1 RED:** `9d5ee0c3` (test) — `tests/test_geography_flow_conformance.py`; the
   byte-equality case failed genuinely (3 codes vs 12) before the generator existed.
2. **Task 1 GREEN:** `7ced9e57` (feat) — `scripts/gen_geography_flow.py`, the regenerated
   `after.json`, `check_schema_drift.py`'s new comparator, and its offline tests.
3. **Task 2 RED:** `acfb5d70` (test) — `tests/test_sync_hubspot_properties.py`'s 8 new
   cases; confirmed failing (`KeyError: 'update'`, `AttributeError`, missing report text)
   against the unmodified Phase-15 implementation.
4. **Task 2 GREEN:** `19f806d3` (feat) — the `update` bucket, `_update_property_options_live`,
   the post-write-confirmation fix, and the `--dry-run` flag.
5. **Task 3 RED:** `e6e2bbcd` (test) — `tests/test_recompute_flag_isolation.py`; 3 of 8
   assertions genuinely failed (`_row_ok`'s missing `committed_body` parameter) against
   the unmodified bounce script, the other 5 already passed (n8n_arming.py/deploy
   overlay spec needed no code change).
6. **Task 3 GREEN:** `5264fa11` (feat) — `bounce_n8n_workflows.py`'s `committed_body`
   comparison and per-row recompute-flag column, plus a comment-only addition to
   `deploy_n8n_workflows.py`.

**Plan metadata:** this SUMMARY's own commit (below).

## Files Created/Modified

- `scripts/gen_geography_flow.py` — new generator, mirrors `gen_escalation_js.py`'s
  header/render()/main() shape
- `config/hubspot_flows/4626722240-geography-score.after.json` — regenerated (branch
  values only)
- `scripts/check_schema_drift.py` — `geography_flow_drift_entry()`, `GEOGRAPHY_FLOW_ID`,
  `exit_code_for()` extended (backward compatible)
- `tests/test_geography_flow_conformance.py` — new, 4 tests
- `tests/test_check_schema_drift.py` — 6 new tests
- `scripts/sync_hubspot_properties.py` — `update` bucket, `_options_hidden_map`,
  `_update_property_options_live`, `sync_object_type`'s update loop + post-write-confirmation
  fix, `_print_report`, `--dry-run` flag
- `tests/test_sync_hubspot_properties.py` — 8 new tests, `hermetic` fixture extended with
  `requests.patch`
- `scripts/bounce_n8n_workflows.py` — `COMMITTED_TRUTH_FLAGS`, `_flag_values(flags=...)`,
  `_row_ok(committed_body=...)`, `main()`'s new table column
- `scripts/deploy_n8n_workflows.py` — comment only, no functional change
- `tests/test_recompute_flag_isolation.py` — new, 8 tests

## Decisions Made

See `key-decisions` in the frontmatter above.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] `sync_hubspot_properties.py --dry-run` had no registered flag**
- **Found during:** Task 2, running the plan's own `<verify>` command literally
- **Issue:** `main()`'s argparse registered zero arguments; passing `--dry-run` (exactly
  as the plan's `<verify>` command does) raised `unrecognized arguments: --dry-run` and
  exited 2 before the credential check ever ran — the plan's own verification step could
  not pass as written.
- **Fix:** Added a `--dry-run` `store_true` flag, documented as a no-op (dry-run was
  already the unconditional default absent both `DRY_RUN=false` and
  `ALLOW_HUBSPOT_PROPERTY_WRITES=true`).
- **Files modified:** `scripts/sync_hubspot_properties.py`
- **Verification:** `sync_hubspot_properties.py --dry-run` now exits 0 and prints
  "skipped (no credentials)" as intended
- **Committed in:** `19f806d3` (Task 2 GREEN)

**2. [Rule 1 - Bug] Post-write confirmation loop would have mis-checked a `property_update`
entry against `fresh_groups`**
- **Found during:** Task 2, wiring `sync_object_type`'s new update loop
- **Issue:** The pre-existing confirmation loop was a bare `if kind == "property": ...
  else: assert ... in fresh_groups`. With a third `kind` value (`property_update`) now
  possible, the implicit `else` branch would have incorrectly checked a genuine property
  name against the GROUP name set the first time a live update actually ran — a latent
  crash this plan's own new code path introduced.
- **Fix:** Rewrote as an explicit three-way `if/elif/elif` (group / property /
  property_update); the `property_update` branch additionally re-GETs and asserts the
  live options now equal the PATCHed desired value set (stronger than a bare existence
  check).
- **Files modified:** `scripts/sync_hubspot_properties.py`
- **Verification:** `tests/test_sync_hubspot_properties.py::test_manifest_records_pre_update_options_for_a_confirmed_update`
- **Committed in:** `19f806d3` (Task 2 GREEN)

---

**Total deviations:** 2 auto-fixed (1 Rule 3 blocking-issue fix, 1 Rule 1 bug fix), both
confined to Task 2's own new code, both necessary for the plan's stated goal to be true
rather than merely declared. No frozen fixture or stress-test file was touched.

## HubSpot PATCH contract finding (Task 2, per the plan's own instruction)

Confirmed live this session via `curl` (no HubSpot token — HubSpot's own public developer
docs, not the HubSpot API): `https://developers.hubspot.com/docs/api/crm/properties`
carries a route-metadata entry for the CRM properties API naming, verbatim:

```
openapi: "specs/legacy/v3/crm-properties-v3.json PATCH /crm/v3/properties/{objectType}/{propertyName}"
description: "Perform a partial update of a property identified by '{propertyName}'.
  Provided fields will be overwritten."
```

This confirms Assumption A1 (RESEARCH.md): the endpoint is `PATCH
/crm/v3/properties/{objectType}/{propertyName}`, and "provided fields will be
overwritten" means whichever field is sent (here, `options`) replaces the live value
wholesale — a full-array replace, not a delta/merge — so `_update_property_options_live`
must always send the complete desired `options` array, which it does.

**[documented]**, per CLAUDE.md's tagging discipline — not `[observed live]`. The
per-option `hidden` field's settability on this specific endpoint was not independently
re-confirmed via this fetch: the page's field-level request/response schema renders
client-side in the live docs site and was not present in the static HTML this session's
`curl` retrieved (confirmed by trying both a default and a Googlebot user-agent — same
static payload either way). This repo's own `config/hubspot_properties.yaml` and
`check_schema_drift.py` already treat `hidden` as a live-round-trippable
`Property.options[]` field (Plan 02), and the create-property endpoint (already exercised
live by this repo in prior phases) shares the same `Property` object schema — but the
PATCH endpoint's own live acceptance of `hidden` is genuinely unproven until Plan 05
actually issues one.

## HubSpot flow `shouldReEnroll` re-evaluation note (Task 1, per D-75-09/D-75-11)

Recorded per the plan's own instruction: after Plan 05's PUT of the regenerated flow
body, HubSpot re-evaluates flow `4626722240` only when `lv_country_region_normalized`
CHANGES on a record (`shouldReEnroll: true`, event-based on that property — see the
committed body's own `enrollmentCriteria`). The PUT alone re-scores nothing; an existing
record only gains its new `geography_score` when its region is next (re)written. This is
why `geography_score` is deliberately excluded from this phase's own recompute proof
(the two-execution, whitelisted/non-whitelisted proof named in the ROADMAP exit
criteria) — a recompute of the veto/tier fields does not, by itself, cause this flow to
re-fire.

## Issues Encountered

None beyond the deviations documented above — all were resolved within this plan's scope.

## User Setup Required

None — no external service configuration required. No live HubSpot or n8n call was made
by any task in this plan.

## Next Phase Readiness

- `scripts/gen_geography_flow.py`, `sync_hubspot_properties.py`'s update path, and
  `bounce_n8n_workflows.py`'s committed-truth comparison are all built and offline-proven,
  ready for Plan 05 to run them against the real portal/live n8n instance: the schema
  writes (enum options + `UK` hide + `lv_icp_scoring_version` create), the flow PUT, and
  the disarmed deploy + bounce + one recompute proof each (whitelisted / non-whitelisted
  company) the phase's exit criteria name.
- `tests/test_hubspot_schema_coverage.py`'s two known-red tests (unchanged deviation class
  from Plans 01/03 — `lv_icp_scoring_version` referenced by two cloud workflows but not
  yet live) remain the tracked blocker for **deploy** (not for continuing to plan/execute
  offline). Resolves when Plan 05 runs `sync_hubspot_properties.py` live and produces the
  undo-manifest entry this guard reads. Already tracked in `.planning/WINDOWS.md` from
  Plan 01 — no new entry needed.
- `ALLOW_HUBSPOT_RECOMPUTE_WRITES` ships `"false"` everywhere in every committed workflow
  JSON. `bounce_n8n_workflows.py` is now ready to verify the operator's post-supervised-
  sweep flip (D-75-17) in both directions once it happens — that flip itself remains an
  explicit, later, operator-run deploy step, out of this plan's and this phase's exit
  gate.
- The HubSpot PATCH contract for updating an enumeration property's options is
  `[documented]`, confirmed live-fetched this session; its actual live behavior (in
  particular, per-option `hidden` on update) is unproven until Plan 05's real PATCH call
  — flagged above, not silently assumed.

---
*Phase: 75-config-driven-region-whitelist-and-scoring-version-staleness*
*Plan: 04*
*Completed: 2026-09-20*

## Self-Check: PASSED

- `scripts/gen_geography_flow.py` — FOUND
- `tests/test_geography_flow_conformance.py` — FOUND
- `tests/test_recompute_flag_isolation.py` — FOUND
- Commit `9d5ee0c3` (test, Task 1 RED) — FOUND in `git log`
- Commit `7ced9e57` (feat, Task 1 GREEN) — FOUND in `git log`
- Commit `acfb5d70` (test, Task 2 RED) — FOUND in `git log`
- Commit `19f806d3` (feat, Task 2 GREEN) — FOUND in `git log`
- Commit `e6e2bbcd` (test, Task 3 RED) — FOUND in `git log`
- Commit `5264fa11` (feat, Task 3 GREEN) — FOUND in `git log`
- Full `pytest` suite: 5206 passed / 160 skipped / 2 known-red (pre-existing,
  `test_hubspot_schema_coverage.py`, documented above and in Plans 01/03)
- `node --test tests/n8n/*.test.mjs`: 1350 passed / 0 failed
- `git status --porcelain -- config/hubspot_flows/` after re-running the generator: empty
- `git status --porcelain -- config/execution_budget.yaml operator-claude-plugin/`: empty
  (only the pre-existing, unrelated untracked `.DS_Store`)
- No `n8n/wf_*.json`, no HubSpot property/flow, and no n8n workflow was deployed, bounced,
  or armed by this plan
