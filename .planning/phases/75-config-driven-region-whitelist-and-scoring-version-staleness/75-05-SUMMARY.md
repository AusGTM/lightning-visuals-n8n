---
phase: 75-config-driven-region-whitelist-and-scoring-version-staleness
plan: 05
subsystem: hubspot-live-schema
tags: [hubspot, schema-migration, enum-options, flow-put, operator-window]

# Dependency graph
requires:
  - phase: 75-02
    provides: config/hubspot_properties.yaml declaring the 8 new region options, UK hidden,
      and lv_icp_scoring_version
  - phase: 75-04
    provides: sync_hubspot_properties.py's update bucket (add/hide, never drop),
      gen_geography_flow.py, check_schema_drift.py's geography comparator
provides:
  - live company property lv_icp_scoring_version (string/text, group lv_enrichment)
  - live lv_country_region_normalized carrying 16 options (UK hidden, 8 added)
  - pinned snapshot portal-schema-companies-phase75.json + regenerated hubspotEnums.generated.js
    -- plan 02's inert window for the eight new codes is CLOSED
  - live flow 4626722240 Geography Score branching on the 12 regions.home codes (revision 14)
  - check_schema_drift.py geography comparator that actually reads the flow body (bug fix)
affects: [75-06]

# Actuals (#2632)
actuals:
  tokens: 0
  tasks: 4
  commits: 6
plan_head_before: 4a46f0fb83a7bd9e537ea74838322cdcb9b667c2

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Operator-run live window: every token-bearing command was run by the operator from the
      interactive shell with .env sourced inline; the orchestrator verified each result from the
      artefact it wrote (manifest, snapshot, fetched flow body, drift report), never from the
      script's own exit line"
    - "Independent read-back for a schema write is a fresh full snapshot, parsed offline"

key-files:
  created:
    - .planning/phases/75-config-driven-region-whitelist-and-scoring-version-staleness/75-SCHEMA-RECORD.md
    - .planning/phases/75-config-driven-region-whitelist-and-scoring-version-staleness/75-schema-drift.json
    - config/hubspot_migration/undo-manifest-7ee513f4-644d-4788-8b1f-fcda558fb767.json
    - config/hubspot_migration/baseline/portal-schema-companies-phase75.json
    - config/hubspot_migration/baseline/portal-schema-contacts-phase75.json
    - config/hubspot_flows/4626722240-geography-score.pre75.json
    - config/hubspot_flows/4626722240-geography-score.post75.json
  modified:
    - scripts/gen_hubspot_enums_js.py
    - n8n/code/hubspotEnums.generated.js
    - n8n/wf_enrichment_cloud.json
    - n8n/wf_enrichment_local_live.json
    - n8n/wf_review_decision_cloud.json
    - n8n/wf_scheduled_maintenance_cloud.json
    - scripts/check_schema_drift.py
    - tests/test_check_schema_drift.py

key-decisions:
  - "Task 0 checkpoint:decision (gate=blocking-human) was answered PROCEED by the operator,
    who then ran every live command via the `!` shell because the subagents cannot read .env
    (the D-75-10 fallback, exercised in full)."
  - "Rollback body for the flow is config/hubspot_flows/4626722240-geography-score.pre75.json
    (fetched live immediately before the PUT), NOT the plan-named .before.json -- that file is
    Phase 40's archive of the pre-fix flow filtering native `country` by name. .before.json
    left byte-unchanged."
  - "check_schema_drift.py's geography comparator walked the GET /automation/v4/flows LIST
    response (no `actions`) and so could only ever report ambiguous_branch/found 0. Fixed
    root-cause (RED 4a73ae7a, GREEN 0221804a): main() GETs the single flow body. This is the
    Rule-1 defect that plan 04's offline-only tests could not see."

requirements-completed: []

coverage:
  - id: D-75-10
    description: "Live schema writes and the flow PUT ran in-plan with the operator running
      the identical command when the subagent could not"
    verification:
      - kind: live
        ref: "75-SCHEMA-RECORD.md -- POST 201, PATCH 200, manifest 7ee513f4, snapshot phase75,
          post-write dry-run zero pending, flow revision 13->14, drift in_sync exit 0"
        status: pass
  - id: D-75-07
    description: "lv_country_region_normalized carries 16 options live, UK hidden not deleted"
    verification:
      - kind: live
        ref: "portal-schema-companies-phase75.json parsed: 16 options, UK hidden:true, EU unchanged"
        status: pass
  - id: D-75-09
    description: "Flow 4626722240 branches on the 12 regions.home codes, regenerated not hand-edited"
    verification:
      - kind: live
        ref: "4626722240-geography-score.post75.json == committed after.json except revisionId"
        status: pass
  - id: D-75-11
    description: "Both enforcement points agree: offline conformance test and live drift comparator"
    verification:
      - kind: unit
        ref: "tests/test_geography_flow_conformance.py, tests/test_check_schema_drift.py (36 tests)"
        status: pass
      - kind: live
        ref: "75-schema-drift.json geography_flow_drift.status == in_sync"
        status: pass
---

# Plan 75-05 Summary — Live HubSpot schema + flow window

- **Completed:** 2026-09-20
- **Tasks:** 4 (Task 0 decision + 3)
- **Files:** 7 created, 8 modified

## Accomplishments

- **Task 0:** operator selected `proceed` at the `blocking-human` checkpoint.
- **Task 1:** `lv_icp_scoring_version` created (201); `lv_country_region_normalized` widened
  8 → 16 options with `UK` hidden (200); undo manifest `7ee513f4`; independent read-back via a
  fresh schema snapshot; post-write dry-run shows zero pending. Commit `805468fc`.
- **Task 2:** `SNAPSHOT` repointed to `portal-schema-companies-phase75.json`; enum module and
  four workflow bodies regenerated in ONE commit (`e220bf61`); re-regeneration is a no-op.
  **Plan 02's declared inert window for `GB, IE, CA, ZA, HK, SG, AE, IN` is now closed** —
  `n8n/code/hubspotEnums.js` accepts them. `tests/test_hubspot_schema_coverage.py` (red since
  plan 01) is green.
- **Task 3:** flow `4626722240` PUT (revision 13 → 14, `updatedAt 2026-09-20T08:50:43.543Z`),
  read back as `post75.json`, drift comparator `in_sync`, exit 0. Commit `3df08750`.

## Task Commits

| Task | Commit | Message |
| --- | --- | --- |
| 1 | `805468fc` | docs(75-05): record the live schema window |
| 2 | `e220bf61` | feat(75-05): pin the phase75 schema snapshot and regenerate the enum module |
| 3 | `4a73ae7a` | test(75-05): RED - geography drift comparator must read the single-flow body |
| 3 | `0221804a` | fix(75-05): geography drift comparator reads the single-flow body |
| 3 | `3df08750` | docs(75-05): record the geography flow PUT, read-back and drift verdict |
| 2 | `afdebf4e` | test(75-05): re-baseline frozen companies jsCode fixture after the enum snapshot repoint |

## Deviations from Plan

### Auto-fixed Issues

1. **[Rule 1 — bug] `check_schema_drift.py` walked the flows LIST response.** First live run
   reported `ambiguous_branch: found 0` on a flow carrying exactly one branch. Root-caused to
   `build_report` receiving `GET /automation/v4/flows` summaries (no `actions`). Fixed by fetching
   the single flow body in `main()` and passing it as `live_geography_flow`; two tests pin both the
   fix and the reason. Second live run: `in_sync`, exit 0.
2. **[Rule 3 — blocking] Plan-named rollback body is wrong.** `.before.json` is the Phase 40
   pre-fix archive on native `country`; the true rollback is the live body fetched pre-PUT
   (`pre75.json`), now committed and named in the record.
3. **[Rule 3 — blocking] `check_schema_drift.py` requires `--out`.** The plan's verify command
   omitted it; run with an explicit phase-dir report path.
4. **[explicit re-baseline] `tests/fixtures/companies_jscode_frozen.json`.** The post-wave gate
   failed `tests/test_companies_factory_frozen.py` (2 tests): Task 2's regeneration changed the
   `Merge Company` node's inlined `hubspotEnums.generated.js` — snapshot header + the eight added
   region values, cloud and local-live, nothing else (verified by per-node unified diff before
   re-baselining). This is the deliberate change Task 2 exists to make, so the fixture was
   re-baselined as the explicit, reviewed act the test's own header requires (precedent
   `6e1442e8`, Phase 72). Commit noted below.
5. **Operator ran every live command.** The D-75-10 fallback was the ONLY path: the subagents
   cannot read `.env`. The orchestrator drove the plan inline rather than spawning an executor
   that would have blocked at each token-bearing step.

## HubSpot flow `shouldReEnroll` note (per D-75-09/D-75-11)

The PUT re-scores nothing by itself: HubSpot re-evaluates flow `4626722240` only when
`lv_country_region_normalized` CHANGES on a record (`shouldReEnroll: true`, event-based on that
property). Existing records gain their new `geography_score` only when their region is next
written, so `geography_score` is deliberately NOT part of plan 06's recompute proof.

## Issues Encountered

- First `!` attempt without `.env` sourced printed `skipped (no credentials)`; no call made.

## User Setup Required

None beyond what the operator already ran. Nothing on n8n deployed, bounced or armed.

## Next Phase Readiness

Plan 06 (exit UAT) can run: the live portal now holds `lv_icp_scoring_version`, so the disarmed
deploy + bounce and the two zero-cost recompute proofs have a real property to stamp.

## Self-Check: PASSED

- `75-SCHEMA-RECORD.md` carries dry-run output, commands, status codes, manifest id, both
  read-backs, flow `updatedAt` before/after, drift exit codes.
- `node -e` sixteen-values check, `test_hubspot_enums_generated_currency.py`,
  `/usr/bin/grep -c portal-schema-companies-phase75` = 1, `BODY_CURRENT`, drift exit 0.
