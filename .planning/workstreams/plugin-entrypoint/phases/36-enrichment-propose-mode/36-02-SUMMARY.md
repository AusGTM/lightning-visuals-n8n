---
phase: 36-enrichment-propose-mode
plan: 02
subsystem: infra
tags: [n8n, hubspot, code-node, workflow-builder, match-lane]

# Dependency graph
requires:
  - phase: 36-enrichment-propose-mode
    plan: "01"
    provides: "n8n/code/matchProposal.js (laneOf/mediumCandidates/summarizeMatch), the lane stamp on every enrichment row, both existing adapters filtered to their own lane"
provides:
  - "the MEDIUM match lane: IF Has Email -> IF Name Searchable -> HubSpot Name Search -> Adapt Name Search, hanging off IF Bare Event's false edge"
  - "a match verdict (tier/auto/reason/candidates) stamped on every contacts row, from all three adapters"
  - "Enrichment Gate's skip rule for a row with no email, no linkedin_url, and no lastName+companyName pair"
provides_downstream: [36-03-propose-mode-dispatch, 36-04-response-shape, 37-client-chunking]

# Actuals (#2632)
actuals:
  tokens: 5529
  tasks: 3
  commits: 3

tech-stack:
  added: []
  patterns:
    - "Match-lane cascade off an existing false edge: IF Bare Event's true lane (fetch-by-id) is untouched; only the false lane re-points, so the email lane's own downstream chain (HubSpot Search -> Adapt Search -> Enrichment Gate) is reused byte-for-byte via IF Has Email's true branch"
    - "existingRecord stays the empty-object literal on every path of a proposal adapter — a MEDIUM candidate is judged by the caller, never promoted to an auto-matched update target"

key-files:
  created: []
  modified:
    - scripts/build_cloud_workflows.py
    - scripts/deploy_n8n_workflows.py
    - n8n/wf_enrichment_cloud.json
    - n8n/wf_enrichment_local.json
    - n8n/wf_enrichment_local_live.json
    - tests/test_fetch_by_id_topology.py
    - tests/test_enrichment_contacts_search_transport.py
    - tests/test_enrichment_lane_dedup.py

key-decisions:
  - "HubSpot Name Search filters lastname EQ + company CONTAINS_TOKEN in ONE AND-group, via the credential-bound _hs_http_search_node transport (never a native HubSpot node), registered in NODE_CREDENTIAL_MAP in the same commit as the node's creation"
  - "IF Has Email / IF Name Searchable route on the lane field Build Identity already stamps (36-01's laneOf) rather than re-deriving the email/name predicates — one source of truth for both routing and adapter filtering"
  - "Adapt Name Search always emits existingRecord: {} on both the failure and success paths — a MEDIUM candidate is a proposal (auto:false), never written into the field the gate treats as a confirmed match"
  - "Enrichment Gate's new skip rule lives in the wrapper beside the existing lookup_failed override, never in the frozen enrichmentGate.js module — mirrors that override's exact idiom"
  - "Company Gate (ENRICH_CO_GATE) deliberately gets no equivalent skip rule — the match lane and its cost-control guard are contacts-only per 36-CONTEXT.md sec7 step 8"
  - "The one pinned false-lane assertion in test_fetch_by_id_topology.py is amended (not silenced): a new false_lane_target key per branch, with the reason inline, plus a new reachability companion assertion so the amendment cannot hide a severed edge"

patterns-established:
  - "Reserve a node's build position/x,y in one task, land the actual node in a later task in the same plan when the plan splits topology-wiring from node-content work — the connections dict can reference a node name before nodes.append() adds it, since n8n's connections are keyed by name and this builder never asserts a target's existence"

requirements-completed: [STRUCT-02, STRUCT-04, DISPATCH-02]

coverage:
  - id: D6
    description: "IF Bare Event's false lane routes through the new match-lane cascade (IF Has Email -> IF Name Searchable -> HubSpot Name Search -> Adapt Name Search) before reaching Enrichment Gate; the true lane and the companies branch are untouched"
    requirement: STRUCT-02
    verification:
      - kind: structural
        ref: "tests/test_fetch_by_id_topology.py::test_gate_exists_and_true_false_lanes_target_fetch_and_search_respectively (amended) + test_search_node_is_still_reachable_from_the_gate_if (new)"
        status: pass
    human_judgment: false
  - id: D7
    description: "HubSpot Name Search uses lastname EQ + company CONTAINS_TOKEN (never bare CONTAINS), the credential-bound httpRequest transport with shape parity to HubSpot Search, and is registered in NODE_CREDENTIAL_MAP"
    requirement: STRUCT-04
    verification:
      - kind: structural
        ref: "tests/test_enrichment_contacts_search_transport.py::test_hubspot_name_search_uses_contains_token_never_the_bare_operator, test_hubspot_name_search_has_shape_parity_with_hubspot_search, test_node_name_stays_mapped_to_lv_hubspot_in_node_credential_map"
        status: pass
    human_judgment: false
  - id: D8
    description: "Adapt Name Search re-verifies HubSpot Name Search hits via mediumCandidates and stamps a match verdict via summarizeMatch, with existingRecord staying the empty-object literal on every path"
    requirement: STRUCT-04
    verification:
      - kind: structural
        ref: "tests/test_enrichment_lane_dedup.py::test_adapt_name_search_exists_and_calls_mediumcandidates_and_summarizematch, test_adapt_name_search_never_assigns_a_non_empty_existingrecord_on_the_success_path"
        status: pass
    human_judgment: false
  - id: D9
    description: "All three contact adapters (Adapt Search, Adapt Fetch By Id, Adapt Name Search) stamp a match verdict, so a tier reaches the response for every lane including the unsearchable one"
    requirement: STRUCT-04
    verification:
      - kind: structural
        ref: "tests/test_enrichment_lane_dedup.py::test_all_three_contact_adapters_stamp_a_match_verdict"
        status: pass
    human_judgment: false
  - id: D10
    description: "Enrichment Gate skips a row with no email, no linkedin_url, and no lastName+companyName pair before it can reach IF Provider Processing Needed; Company Gate deliberately carries no equivalent rule"
    requirement: DISPATCH-02
    verification:
      - kind: structural
        ref: "tests/test_enrichment_lane_dedup.py::test_enrichment_gate_skips_a_row_with_no_email_no_linkedin_and_no_name_plus_company, test_company_gate_does_not_carry_the_same_guard"
        status: pass
    human_judgment: false

duration: ~35min
completed: 2026-08-05
status: complete
---

# Phase 36 Plan 02: Match-Lane Topology, Proposal Adapter, Unmatchable-Row Skip Summary

**The MEDIUM match lane lands end-to-end: a contact row with a surname and a company but no email now reaches a real HubSpot search, gets re-verified by value, and returns as a judgeable proposal — never an auto-match, and never a burned provider call when nothing is searchable at all.**

## Performance

- **Duration:** ~35 min
- **Tasks:** 3/3 completed
- **Files modified:** 8 (0 new; 5 `n8n/*.json` regenerated via the builder, never hand-edited)

## Accomplishments

- **Task 1 — match-lane topology:** four new nodes (`IF Has Email`, `IF Name Searchable`,
  `HubSpot Name Search`, `Adapt Name Search` reserved) hang off `IF Bare Event`'s false
  edge. `HubSpot Name Search` filters `lastname EQ` + `company CONTAINS_TOKEN` in one
  AND-group via `_hs_http_search_node`, using `ENRICH_CONTACT_FETCH_BY_ID_PROPERTIES_CSV`
  so a MEDIUM candidate carries `company` for re-verification. Registered in
  `NODE_CREDENTIAL_MAP` in the same commit as the node build. The companies branch
  (`IF Company Bare Event`) is untouched.
- **Task 2 — Adapt Name Search:** new `ENRICH_ADAPT_NAME_SEARCH` constant filters to the
  `name` lane, re-verifies every HubSpot hit through `mediumCandidates` (case-insensitive
  lastname equality + company token overlap), and stamps `match` via `summarizeMatch`.
  `existingRecord` is the empty-object literal on every path — a MEDIUM candidate is a
  proposal (`auto:false`), never an auto-matched update target. Both existing adapters
  (`Adapt Search`, `Adapt Fetch By Id`) also gained a `match` stamp, so every lane now
  produces a verdict.
- **Task 3 — Enrichment Gate skip rule:** a second override beside the existing
  `lookup_failed` one — no email, no `linkedin_url`, and not both `lastName` and
  `companyName` sets `action = "skip"` before `IF Provider Processing Needed`, so an
  unmatchable row never burns three provider calls. `Company Gate` deliberately gets no
  equivalent rule.
- Every new/amended assertion red-checked individually (revert the specific builder
  edit, confirm the specific assertion fails, restore) — including both directions of
  Task 3's companies-must-not-carry-the-guard check.
- One deviation from the plan's literal acceptance-criteria text, documented below
  (Deviations).

## Task Commits

Each task was committed atomically:

1. **Task 1: match-lane topology** — `33f2edf` (feat: IF Has Email, IF Name Searchable,
   HubSpot Name Search, credential map entry, amended pinned test)
2. **Task 2: Adapt Name Search** — `fe917a2` (feat: ENRICH_ADAPT_NAME_SEARCH, match stamp
   on all three contact adapters)
3. **Task 3: Enrichment Gate skip rule** — `d0c85c3` (feat: unmatchable-row skip guard)

## Files Created/Modified

- `scripts/build_cloud_workflows.py` — `IF Has Email`/`IF Name Searchable`/
  `HubSpot Name Search` node builds + connections; `ENRICH_ADAPT_NAME_SEARCH` constant +
  node registration; `match` stamp added to `ENRICH_ADAPT_SEARCH` and
  `ENRICH_ADAPT_FETCH_BY_ID_CONTACT`; `ENRICH_GATE`'s new skip override
- `scripts/deploy_n8n_workflows.py` — `NODE_CREDENTIAL_MAP["HubSpot Name Search"]`
- `n8n/wf_enrichment_cloud.json`, `n8n/wf_enrichment_local.json`,
  `n8n/wf_enrichment_local_live.json` — regenerated via the builder (never hand-edited);
  `wf_enrichment_local.json` picks up the `match`/skip changes because `ENRICH_GATE` and
  `ENRICH_ADAPT_SEARCH`/`ENRICH_ADAPT_FETCH_BY_ID_CONTACT` are shared constants
- `tests/test_fetch_by_id_topology.py` — `false_lane_target` per branch, amended pinned
  assertion with reason inline, new reachability companion assertion
- `tests/test_enrichment_contacts_search_transport.py` — `CONTAINS_TOKEN`-present /
  bare-`CONTAINS`-absent assertion, shape-parity assertion vs `HubSpot Search`
- `tests/test_enrichment_lane_dedup.py` — 5 new tests: `Adapt Name Search` existence/
  shape, the `existingRecord`-stays-empty structural guard, match-verdict parity across
  all three adapters, the gate's skip guard present on `Enrichment Gate` and absent from
  `Company Gate`

## Decisions Made

- `HubSpot Name Search`'s `properties_csv` is `ENRICH_CONTACT_FETCH_BY_ID_PROPERTIES_CSV`
  (not the plain search CSV) because `mediumCandidates` re-verifies a hit against
  `company`, which the plain search CSV omits.
- `IF Name Searchable`'s false lane goes straight to `Enrichment Gate` — this is that
  node's fourth inbound branch, carrying no `existingRecord` by design; Task 3's gate
  rule (built in the same plan) turns it into a skip before any provider call, so the
  first-arrival exposure this documented pattern already carries (per `Build Response`)
  never actually matters for this branch.
- The `CONTAINS_TOKEN` operator choice stays `[ASSUMED]` per 36-RESEARCH.md's own
  provenance tag — the offline proof here is structural (asserted present, bare form
  asserted absent); the semantic proof is deferred to the first live propose run.

## Deviations from Plan

**1. [Rule 1 — verification methodology] Task 1's literal `json.dumps(d).count('"CONTAINS_TOKEN"')`
one-liner double-encodes and always returns 0 for this node.**
- **Found during:** Task 1 acceptance-criteria verification.
- **Issue:** `HubSpot Name Search`'s `operator: "CONTAINS_TOKEN"` lives inside a Python
  string value (the node's `jsonBody` n8n-expression field). `json.dumps(d)` on the
  already-parsed document re-serializes that string, escaping its embedded quotes to
  `\"CONTAINS_TOKEN\"` — so a literal `'"CONTAINS_TOKEN"'` substring check against the
  double-encoded output never matches, regardless of whether the builder is correct. This
  reproduces identically with the plan's exact literal command (verified before touching
  any code).
- **Fix:** Verified the actual intent (operator present, bare form absent) directly
  against the node's own `jsonBody` string (single-encoded, as every other structural
  test in this file already does), and added a persisted pytest assertion
  (`test_hubspot_name_search_uses_contains_token_never_the_bare_operator` in
  `tests/test_enrichment_contacts_search_transport.py`) doing exactly that, red-checked
  by temporarily reverting the operator to a bare form and confirming the specific
  failure.
- **Files modified:** `tests/test_enrichment_contacts_search_transport.py`.
- **Commit:** `33f2edf`.

No other deviations — the remaining two tasks executed exactly as written.

## Issues Encountered

None blocking. One process note: a `git stash`/`git stash pop` was used once during
Task 3's red-check prep and immediately reverted before any other action — per this
repo's own worktree-stash prohibition guidance, subsequent red-checks in this plan used
file copies (`cp`/`diff`) instead, which is also the safer pattern in a shared-checkout
context.

## User Setup Required

None — no external service configuration required. This plan makes zero live/deploy
changes; `scripts/deploy_n8n_workflows.py` was not run (denied to agents per this phase's
constraints).

## Next Phase Readiness

- Every contacts row now carries a `match` verdict (`tier`/`auto`/`reason`/`candidates`)
  regardless of which lane it took — 36-03 (propose-mode dispatch) can echo `match`
  straight from the row without any further derivation.
- The MEDIUM match lane is live in the topology; an unmatchable row is skipped before any
  provider call.
- Verification suites green against baselines: `.venv/bin/python -m pytest -q` -> 1947
  passed / 6 skipped (baseline 1938/6 after 36-01, +9 new this plan). `node --test
  tests/n8n/*.test.mjs` -> 585 passing (unchanged from 36-01 — no new `.mjs` tests this
  plan; all new tests are pytest structural guards over the built JSON).
  `.venv/bin/python -m pytest operator-claude-plugin/tests/ -q` -> 1052 passed / 5
  skipped (unchanged — this phase touches no plugin file).
  `grep -c 'ALLOW_HUBSPOT_[A-Z_]* = "true"' n8n/*.json` -> 0 for every file.
  Builder idempotent — a second `scripts/build_cloud_workflows.py` run leaves
  `git diff --stat n8n/` empty for every regenerated file. No blockers for 36-03.

## Self-Check: PASSED

- FOUND: `.planning/workstreams/plugin-entrypoint/phases/36-enrichment-propose-mode/36-02-SUMMARY.md`
- FOUND commit: `33f2edf`
- FOUND commit: `fe917a2`
- FOUND commit: `d0c85c3`

---
*Phase: 36-enrichment-propose-mode*
*Completed: 2026-08-05*
