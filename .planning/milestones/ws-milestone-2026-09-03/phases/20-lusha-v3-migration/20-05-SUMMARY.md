---
phase: 20-lusha-v3-migration
plan: 05
subsystem: infra
tags: [lusha, provider-api, enrichment, v3-migration, deployment-verification, n8n-cloud]

# Dependency graph
requires:
  - phase: 20-lusha-v3-migration (plan 01)
    provides: "docs/LUSHA-V3-CONTRACT.md — the confirmed v3 wire contract this plan's
      URL assertions and live verifier pin against"
  - phase: 20-lusha-v3-migration (plan 02)
    provides: "n8n/code/lushaRequest.js and the rewired v3 emission sites (CLOUD,
      LOCAL-LIVE) this plan's offline guard now protects against regression"
  - phase: 20-lusha-v3-migration (plan 04)
    provides: "lusha_contact_id/lusha_company_id staging + the stored-id enrich-by-id
      URL branch, which this plan's regex-free literal-URL assertions had to account
      for as a legitimate additional v3 URL"
provides:
  - "An offline regression guard (tests/test_provider_gate_topology.py) that fails if
    any built workflow ever regains a retired Lusha v2 URL, or loses either v3
    search-and-enrich endpoint, or emits a Lusha provider node that isn't POST with a
    body — checked against both the committed JSON and an in-process build"
  - "scripts/verify_live_lusha_urls.py — a read-only, re-runnable live verifier that
    reads the deployed LV Enrichment workflow back and reports v2/v3 URL counts and
    per-node method/body-presence, importing auth helpers from
    scripts/deploy_n8n_workflows.py rather than reimplementing them"
  - "Live evidence that the v3 migration is actually deployed: the pre-redeploy
    read-back caught the live LV Enrichment deployment predating Plans 02-04 (same
    shape as Phase 19's BUG 26), and the post-redeploy read-back confirms 0 retired
    URLs / both v3 endpoints live / POST+body on both Lusha provider-data nodes"
  - "docs/LUSHA-V3-CONTRACT.md's new 'Live deployment read-back' section recording the
    deploy date, before/after verifier output, and confirmation nothing was armed"
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Read-back-as-a-distinct-step: a redeploy's exit code proves the request
      succeeded, never that the live artifact is current. scripts/verify_live_lusha_urls.py
      is the third instance of this repo's read-back-proof idiom (after
      scripts/rollback_canary_proof.py and the Phase 19 operator runbook), and it
      caught a live BUG-26-shaped drift on its first real run, not in a test."
    - "Literal-string URL assertions built from parts, not regex — the retired
      major-version prefix is assembled inline (\"api.lusha.com/\" + \"v\" + \"2/\") so
      the pattern being searched for is legible in the test itself rather than a
      copy-pasted literal that could silently drift from what it's supposed to catch."

key-files:
  created:
    - scripts/verify_live_lusha_urls.py
  modified:
    - tests/test_provider_gate_topology.py
    - docs/LUSHA-V3-CONTRACT.md

key-decisions:
  - "Task 2 produced no file change. tests/test_companies_factory_frozen.py passed
    unmodified, and per the plan's own instruction a passing fixture is never
    re-baselined. Confirmed (not assumed) the reason: ENRICH_MERGE_CO (the 'Merge
    Company' node) inlines only taxonomy.generated.js + mergeCompanies.js
    (scripts/build_cloud_workflows.py:2273) — none of the seven frozen node names
    touch normalizeProviders.js, lushaRequest.js, or the decide-node patch assembly
    this phase's Plans 02-04 changed. No commit exists for Task 2 as a result; the
    verification evidence lives entirely in this SUMMARY."
  - "The live verifier's 'every Lusha node' method/body report scopes the POST+body
    assertion to the two provider-DATA nodes only (Lusha Enrich, Lusha Company) —
    LUSHA_PROVIDER_NODE_NAMES — and reports Lusha Usage (and any IF-gate node whose
    name contains 'Lusha') separately, tagged 'other'. Lusha Usage is a GET
    credit-check node by contract (scripts/provider_registry.py) and was never going
    to satisfy a POST+body assertion; asserting that on it would have been asserting
    something the contract itself contradicts."
  - "verify_live_lusha_urls.py imports _get_live_workflows() from
    deploy_n8n_workflows.py in addition to the plan-named _base_url()/_n8n_headers()
    — reusing the existing list-then-fetch-by-id idiom rather than re-deriving a
    second raw GET-list call the deploy script already owns."

patterns-established:
  - "Read-back-as-a-distinct-step (see tech-stack.patterns above) — the third
    instance of this idiom in the repo, now generalized to a provider-URL contract
    rather than a write-safety flag."

requirements-completed: [REQ-lusha-v3-verification]

coverage:
  - id: D1
    description: "Offline guard: zero retired Lusha v2 URL occurrences across all four
      built workflow artifacts (committed JSON + in-process build), plus positive
      assertions that both v3 search-and-enrich endpoints and the v3 account-usage
      endpoint are present, plus POST+non-empty-body on all four Lusha provider-data
      nodes across the two build targets"
    requirement: "REQ-lusha-v3-verification"
    verification:
      - kind: unit
        ref: "tests/test_provider_gate_topology.py::test_no_retired_lusha_major_version_url_remains_in_any_built_workflow, ::test_v3_search_and_enrich_urls_present_in_cloud_and_local_live_enrichment, ::test_v3_account_usage_url_present_in_cloud_artifact, ::test_all_four_lusha_nodes_are_post_with_a_non_empty_json_body"
        status: pass
      - kind: manual_procedural
        ref: "Live-verified once: a retired v2 URL was hand-inserted into scripts/build_cloud_workflows.py's Lusha Company URL literal, rebuilt, and both the negative and positive new tests failed as expected; then reverted and both suites confirmed green again."
        status: pass
    human_judgment: false
  - id: D2
    description: "Frozen companies jsCode fixture accounted for: passes unmodified,
      with the specific reason named (Merge Company inlines taxonomy + company-merge
      modules only, none of which this phase's edits touch); two consecutive builder
      runs leave git status --porcelain n8n/ empty"
    requirement: "REQ-lusha-v3-verification"
    verification:
      - kind: unit
        ref: "tests/test_companies_factory_frozen.py -q (4 passed, unmodified)"
        status: pass
      - kind: manual_procedural
        ref: "scripts/build_cloud_workflows.py run twice in sequence; git status --porcelain n8n/ empty after each run"
        status: pass
    human_judgment: false
  - id: D3
    description: "Disarmed redeploy of the current committed build (no ENABLE_BAKED_FLAGS
      overlay) followed by an independent live read-back via
      scripts/verify_live_lusha_urls.py, proving v3 URLs serve live with zero retired
      v2 URLs, recorded in docs/LUSHA-V3-CONTRACT.md"
    requirement: "REQ-lusha-v3-verification"
    verification:
      - kind: manual_procedural
        ref: "Full before/after verifier output + deploy command captured verbatim in docs/LUSHA-V3-CONTRACT.md's 'Live deployment read-back' section and in this SUMMARY's Task 3 notes below"
        status: pass
    human_judgment: true
    rationale: "A live third-party deployment's actual served state is a live fact, not something an offline test can assert — the plan's own design makes this a manual_procedural read-back by nature, same as the Phase 19 runbook and rollback_canary_proof.py precedents."
  - id: D4
    description: "Both full suites remain green throughout all three tasks"
    requirement: "REQ-lusha-v3-verification"
    verification:
      - kind: unit
        ref: ".venv/bin/python -m pytest -q (611 passed, up from 607 baseline plus this plan's 4 new tests)"
        status: pass
      - kind: unit
        ref: "node --test tests/n8n/*.test.mjs (352 passed, unchanged — no .mjs test file was touched this plan)"
        status: pass
    human_judgment: false

duration: ~40min
completed: 2026-07-30
status: complete
---

# Phase 20 Plan 05: Migration Verification — Offline Guard, Frozen Fixture, Disarmed Redeploy Summary

**Added a regression-proof offline test (zero retired Lusha v2 URLs across all four built
workflows, positive v3-endpoint pins, POST+body checks), confirmed the frozen companies
fixture is untouched for a named reason, and — via a new read-only live verifier —
caught then fixed a live BUG-26-shaped deployment drift: the production LV Enrichment
workflow was still serving the retired v2 Lusha endpoints until this plan's disarmed
redeploy.**

## Performance

- **Duration:** ~40 min
- **Started:** 2026-07-30T04:14:00Z (approx., first Read of plan/context docs)
- **Completed:** 2026-07-30T04:56:30Z
- **Tasks:** 3 (Task 2 produced no commit — verification-only, documented below)
- **Files modified:** 3 (1 created, 2 modified)

## Accomplishments

- Added four tests to `tests/test_provider_gate_topology.py`: a negative guard (zero
  occurrences of the retired v2 Lusha major-version path, assembled from parts —
  `"api.lusha.com/" + "v" + "2/"` — rather than written as a literal) across all four
  built artifacts (`wf_enrichment_cloud.json`, `wf_enrichment_local_live.json`,
  `wf_enrichment_local.json`, `wf_scheduled_maintenance_cloud.json`) plus an in-process
  build of the CLOUD and LOCAL-LIVE targets so an unrebuilt shared-module edit fails
  too; a positive assertion that both v3 `search-and-enrich` URLs are present in the
  CLOUD/LOCAL-LIVE artifacts; a positive assertion that the v3 account-usage URL is
  present in the CLOUD artifact; and a POST-plus-non-empty-body check across all four
  Lusha provider-data nodes (`Lusha Enrich`, `Lusha Company` x CLOUD, LOCAL-LIVE).
  Live-verified the guard actually guards: hand-inserted a v2 URL into the builder,
  rebuilt, watched both the negative and positive tests fail, then reverted.
- Confirmed `tests/test_companies_factory_frozen.py` passes unmodified and named the
  reason: `ENRICH_MERGE_CO` (the frozen `Merge Company` node) inlines only
  `taxonomy.generated.js` + `mergeCompanies.js`
  (`scripts/build_cloud_workflows.py:2273`) — none of this phase's edits (provider
  request builders, provider response adapter, decide-node patch assembly) touch
  either inlined module. Ran the builder twice in sequence and confirmed
  `git status --porcelain n8n/` is empty after each run — the committed artifacts are
  reproducible.
- Wrote `scripts/verify_live_lusha_urls.py`, a read-only live verifier importing
  `_base_url()`/`_n8n_headers()`/`_get_live_workflows()` from
  `scripts/deploy_n8n_workflows.py` (no auth logic of its own). It fetches the live
  `LV Enrichment (Cloud template)` workflow by name, reports occurrence counts of the
  retired v2 URL and both v3 endpoints, and reports method/body-presence for every
  Lusha-named node — printing only counts, node names, methods and URLs, never a
  credential or a full node body. Confirmed it skips with a banner and zero HTTP calls
  when n8n credentials are absent.
- **Ran the pre-redeploy read-back first (unplanned but load-bearing):** it found the
  live `LV Enrichment` deployment predated Plans 02-04 — 4 retired v2 URL occurrences,
  0 v3 endpoints served, `Lusha Enrich` still POSTing `v2/person`, `Lusha Company`
  still a GET against the retired-endpoint URL builder. This is the exact
  deployment-drift shape Phase 19's BUG 26 found, now caught again by design rather
  than by luck.
- Executed the disarmed redeploy (`DRY_RUN=false ALLOW_N8N_DEPLOY=true`, no
  `ENABLE_BAKED_FLAGS` at all) — updated all three cloud workflows (200 on each). The
  post-redeploy read-back confirms 0 retired v2 URLs, both v3 `search-and-enrich`
  endpoints present, the v3 account-usage endpoint present, and both Lusha
  provider-data nodes (`Lusha Enrich`, `Lusha Company`) reporting `method=POST` with a
  present body. Recorded the full before/after output and the exact deploy command in
  `docs/LUSHA-V3-CONTRACT.md`'s new "Live deployment read-back" section.
- Both full suites green throughout: `.venv/bin/python -m pytest -q` (611 passed — 607
  baseline + this plan's 4 new tests) and `node --test tests/n8n/*.test.mjs` (352
  passed, unchanged).

## Task Commits

Each task was committed atomically:

1. **Task 1: Offline guard — no retired Lusha URL may return to any built workflow** - `3ade361` (test)
2. **Task 2: Frozen fixture accounted for, and the build proven reproducible** - no commit (verification-only; fixture already passed, nothing to re-baseline — see Decisions Made)
3. **Task 3: Disarmed redeploy and an independent live read-back proving v3 is serving** - `28d42f5` (feat)

**Plan metadata:** committed together with this SUMMARY (see final commit below).

## Files Created/Modified

- `tests/test_provider_gate_topology.py` - four new tests: the T-20-12 offline guard
  (negative v2 assertion + positive v3 assertions across four artifacts, in-process
  build included) and the POST+body check on all four Lusha provider-data nodes.
- `scripts/verify_live_lusha_urls.py` - new read-only live verifier for the deployed
  LV Enrichment workflow, reusing `deploy_n8n_workflows.py`'s auth/URL helpers.
- `docs/LUSHA-V3-CONTRACT.md` - new "Live deployment read-back" section: deploy date,
  the exact disarmed deploy command, the pre-redeploy drift finding, the
  post-redeploy PASS output, and confirmation nothing was armed.

## Decisions Made

See `key-decisions` in the frontmatter for the full list. In summary: Task 2 made no
file change because the frozen fixture already passes and the specific inlined-module
reason was confirmed rather than assumed; the live verifier's POST+body assertion is
scoped to the two Lusha provider-data nodes (not the GET-only `Lusha Usage` credit
node, which is reported separately and tagged accordingly); and the verifier reuses
`deploy_n8n_workflows.py`'s existing list-then-fetch-by-id helpers rather than
re-deriving a second raw GET call.

## Deviations from Plan

### Auto-fixed Issues

None — Rules 1-3 were not triggered.

**Unplanned but in-scope addition:** the plan's Task 3 action text describes writing
the verifier then redeploying then reading back once. This execution ran the verifier
against the live deployment BEFORE the redeploy too (not explicitly required by the
plan text, but a natural extension of "the read-back is a distinct step from the
redeploy" and directly useful evidence: it is what surfaced the live BUG-26-shaped
drift that the redeploy then fixed). This is documented as additional evidence, not a
scope deviation — no plan instruction was contradicted, and the redeploy + single
post-redeploy read-back the plan calls for both happened exactly as specified.

---

**Total deviations:** 0 auto-fixed. One unplanned-but-harmless additional verifier run
(pre-redeploy), which surfaced load-bearing evidence rather than causing any rework.

## Issues Encountered

The live `LV Enrichment (Cloud template)` deployment was found stale (predating Plans
02-04, still serving retired v2 Lusha URLs) on the pre-redeploy read-back. This was
exactly what Task 3's disarmed redeploy step exists to fix, not a blocker — resolved by
running the redeploy exactly as the plan specifies, then confirming via the
post-redeploy read-back.

## User Setup Required

None — no external service configuration required. Plan 04's pending operator action
(live creation of `lusha_contact_id`/`lusha_company_id` HubSpot properties) remains
open from that plan and is unaffected by this plan's scope (verification only, no
HubSpot writes of any kind occurred here).

## Next Phase Readiness

- Phase 20's roadmap success criterion 5 is met in full: the v3 request builders
  (Plan 02), the frozen fixture accounted for (this plan), both suites green, and a
  disarmed redeploy read-back showing v3 live with zero v2 remaining (this plan).
- `scripts/verify_live_lusha_urls.py` is re-runnable at any time before the
  2026-11-18 v2 sunset, and again during a future armed canary (Phase 22 per
  PROJECT.md's v0.5 milestone plan) — no changes needed for that reuse.
- The offline regression guard in `tests/test_provider_gate_topology.py` will fail the
  suite immediately if a future edit reintroduces a retired Lusha v2 URL, or silently
  drops a v3 endpoint while satisfying the negative assertion by deletion.
- Plan 04's pending operator action (live `lusha_contact_id`/`lusha_company_id`
  property creation) is the one open item carried forward from this phase — untouched
  by this plan, tracked in `20-04-SUMMARY.md`'s "Pending Operator Actions" section.
- No blockers for whatever closes Phase 20 or opens the next phase.

---
*Phase: 20-lusha-v3-migration*
*Completed: 2026-07-30*
