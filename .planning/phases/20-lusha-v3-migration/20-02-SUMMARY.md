---
phase: 20-lusha-v3-migration
plan: 02
subsystem: infra
tags: [lusha, provider-api, enrichment, v3-migration, n8n-code-node]

# Dependency graph
requires:
  - phase: 20-lusha-v3-migration (plan 01)
    provides: "docs/LUSHA-V3-CONTRACT.md — the confirmed v3 wire contract both lanes
      build against, plus the re-scoped REQ-lusha-selective-reveal (reveal[] as PII
      hygiene, not a cost lever)"
provides:
  - "n8n/code/lushaRequest.js — the single v3 request-body builder for both Lusha
    lanes: LUSHA_REVEAL_BY_FIELD, lushaReveal(), lushaContactBody(), lushaCompanyBody()"
  - "All five contacts+companies emission sites (CLOUD, LOCAL-LIVE builders + HTTP
    nodes, dry-run harness) POSTing v3 search-and-enrich instead of the retired v2
    GET endpoints"
  - "Anti-drift parity test locking the hand-written CLOUD n8n-expression body to the
    shared lushaRequest.js module"
affects: [20-03, 20-04, 20-05]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "One dependency-free JS module (n8n/code/lushaRequest.js), inline()'d into
      Code-node builders and require()'d by the harness, with the ONE consumer that
      cannot import it (a raw n8n expression) pinned to it by a deep-equality parity
      test instead — the seam Task 2 could not close by construction, closed by Task 3"
    - "Fixed literal allow-list (LUSHA_REVEAL_BY_FIELD) + hasOwnProperty lookup as the
      standard shape for turning an upstream gate's dynamic field-name array into a
      billed/PII-sensitive provider request parameter, prototype-pollution-safe by
      construction"

key-files:
  created:
    - n8n/code/lushaRequest.js
    - tests/n8n/lushaRequest.test.mjs
  modified:
    - scripts/build_cloud_workflows.py
    - scripts/dryrun_batch.mjs
    - tests/n8n/lushaRequestContract.test.mjs
    - tests/test_cloud_companies_branch.py
    - tests/test_provider_gate_topology.py
    - n8n/wf_enrichment_cloud.json
    - n8n/wf_enrichment_local_live.json

key-decisions:
  - "reveal is attached to the v3 contacts body even though docs/LUSHA-V3-CONTRACT.md's
    §3 winning-body example for /contacts/search-and-enrich shows NO reveal key at all
    (the live A/B in §6 that measured reveal-count vs. billed-cost was run against the
    two-step /contacts/enrich endpoint, not the combined endpoint this plan ships on).
    Proceeded per the plan's explicit Task 1 action text — attach lushaReveal(missing)
    to lushaContactBody() — on the reasonable assumption that the combined endpoint's
    'enrich' half accepts the same reveal option the standalone enrich endpoint does,
    and that the general 'reveal must contain at least 1 elements' validation message
    is endpoint-agnostic. NOT independently live-probed for /search-and-enrich
    specifically — flagged here for Plan 03/05 to confirm against a live 200/400 if a
    tighter guarantee is ever needed."
  - "lushaContactBody() always emits a non-empty reveal (defaults to [\"emails\"] when
    lushaReveal(missingFields) returns []), even though lushaReveal() itself (the pure
    mapping function) returns [] for empty/no-mapped input per the plan's own Task 1
    behavior spec. Reconciles the plan's literal lushaReveal() test cases with the
    amended_premise's 'empty reveal is invalid' constraint: the pure mapper stays a
    pure map, and the request-body composer is where the invalid-empty-reveal
    correction lives."
  - "Companies lane gets zero reveal-derivation code, per the Plan 01 re-scope and this
    plan's own coverage matrix — lushaCompanyBody() never emits a reveal key at all."
  - "CLOUD's narrow identity set (email + linkedinUrl only) is carried forward
    unchanged rather than unified with LOCAL-LIVE/the harness's broader
    firstName+lastName+companyName+companyDomain set — per the plan's explicit
    instruction not to silently unify a pre-existing, unverified split inside a
    migration."

patterns-established:
  - "Anti-drift parity test: for any n8n expression that cannot require() a shared
    module, assert its evaluated output deep-equals the module's output across a
    matrix of inputs, rather than trusting a hand-copied mirror to stay in sync."

requirements-completed: [REQ-lusha-v3-request-builders, REQ-lusha-selective-reveal]

coverage:
  - id: D1
    description: "n8n/code/lushaRequest.js: LUSHA_REVEAL_BY_FIELD (frozen, 2 entries),
      lushaReveal() (prototype-safe, sorted, tolerant of undefined/null/non-array),
      lushaContactBody() (v3 contacts body, no contactId, non-empty reveal default),
      lushaCompanyBody() (v3 companies body, domain-only, no reveal key)"
    requirement: "REQ-lusha-v3-request-builders"
    verification:
      - kind: unit
        ref: "node --test tests/n8n/lushaRequest.test.mjs (18 tests, all passing)"
        status: pass
    human_judgment: false
  - id: D2
    description: "All 3 contacts-lane emission sites (CLOUD HTTP node expression,
      LOCAL-LIVE builder + HTTP node) plus scripts/dryrun_batch.mjs issue
      POST /v3/contacts/search-and-enrich with a reveal list derived from the gate's
      missingFields; zero v2/person references remain in either built workflow"
    requirement: "REQ-lusha-v3-request-builders"
    verification:
      - kind: unit
        ref: "tests/test_cloud_contacts_branch.py, tests/test_builder_flag_parity.py, tests/test_enabled_build_invariants.py -q (28 passed)"
        status: pass
      - kind: unit
        ref: "grep -o 'https://api.lusha.com/v3/contacts/search-and-enrich' n8n/wf_enrichment_cloud.json|n8n/wf_enrichment_local_live.json (>=1 each); grep -o 'api.lusha.com/v2/person' (0 each)"
        status: pass
    human_judgment: false
  - id: D3
    description: "Both companies-lane HTTP nodes (CLOUD, LOCAL-LIVE) POST
      /v3/companies/search-and-enrich with a domain-only body via the shared
      lushaCompanyBody(); zero v2/company references remain in either built workflow"
    requirement: "REQ-lusha-v3-request-builders"
    verification:
      - kind: unit
        ref: "tests/test_cloud_companies_branch.py -q (12 passed)"
        status: pass
      - kind: unit
        ref: "grep -o 'https://api.lusha.com/v3/companies/search-and-enrich' n8n/wf_enrichment_cloud.json|n8n/wf_enrichment_local_live.json (>=1 each); grep -o 'api.lusha.com/v2/company' (0 each)"
        status: pass
    human_judgment: false
  - id: D4
    description: "Anti-drift parity: the CLOUD Lusha Enrich node's hand-written
      jsonBody expression deep-equals n8n/code/lushaRequest.js's lushaContactBody()
      output across 5 identity/missing-field combinations; verified live by
      temporarily perturbing a reveal value and observing the parity test fail, then
      reverting"
    requirement: "REQ-lusha-selective-reveal"
    verification:
      - kind: unit
        ref: "tests/n8n/lushaRequestContract.test.mjs — 'CLOUD expression output deep-equals lushaContactBody() for a matrix of inputs (anti-drift)'"
        status: pass
    human_judgment: false
  - id: D5
    description: "Full regression: no built-workflow or contract-test regression
      elsewhere in the repo from the migration; the one intentionally-retired Track B
      guard is the only test-count delta"
    requirement: "REQ-lusha-v3-request-builders"
    verification:
      - kind: unit
        ref: ".venv/bin/python -m pytest -q (602 passed, was 603 before this plan minus the 1 retired Track B test)"
        status: pass
      - kind: unit
        ref: "node --test tests/n8n/*.test.mjs (331 passed)"
        status: pass
    human_judgment: false

duration: 17min
completed: 2026-07-30
status: complete
---

# Phase 20 Plan 02: Lusha v2 -> v3 Request Builders Summary

**Both Lusha lanes (contacts + companies) now POST v3 `search-and-enrich` in all three
built targets plus the dry-run harness, from a single shared `n8n/code/lushaRequest.js`
module with a prototype-safe reveal allow-list and a deep-equality parity test locking
the one hand-written n8n expression to it.**

## Performance

- **Duration:** ~17 min
- **Started:** 2026-07-30T03:31:37Z (approx., first Read of plan/contract docs)
- **Completed:** 2026-07-30T03:47:20Z (Task 3 commit)
- **Tasks:** 3
- **Files modified:** 9 (2 created, 7 modified — see key-files)

## Accomplishments

- Built `n8n/code/lushaRequest.js`: `lushaReveal()` (frozen literal allow-list,
  `hasOwnProperty`-guarded against prototype-chain pollution, sorted for determinism),
  `lushaContactBody()` (v3 contacts request, no synthetic index key, non-empty reveal
  default), and `lushaCompanyBody()` (v3 companies request, domain-only, no reveal key
  — companies lane has none per Plan 01's probe).
- Rewired all 3 contacts-lane emission sites (CLOUD hand-written expression, LOCAL-LIVE
  builder + HTTP node) and `scripts/dryrun_batch.mjs` onto
  `POST /v3/contacts/search-and-enrich`, with the reveal list derived from the
  enrichment gate's `missingFields` as PII-minimization hygiene (per Plan 01's
  re-scope, not a cost lever).
- Rewired both companies-lane HTTP nodes (CLOUD, LOCAL-LIVE) onto
  `POST /v3/companies/search-and-enrich` via the shared `lushaCompanyBody()`; the
  `companyName`-in-identity exclusion from BUG 17 carries forward unchanged.
- Re-pinned `tests/n8n/lushaRequestContract.test.mjs` to the v3 contacts shape and
  added the anti-drift parity test asserting the CLOUD expression's output
  deep-equals `lushaContactBody()`'s across 5 identity/missing-field combinations —
  verified live by perturbing a reveal value, observing the test fail, then
  reverting.
- Re-pinned both `tests/test_cloud_companies_branch.py` tests to the v3 POST contract
  and retired the stale `tests/test_provider_gate_topology.py` Track B guard (its
  method/contract mismatch was resolved by BUG 17 and is now fully superseded by this
  migration), replacing it with a one-line pointer to `docs/LUSHA-V3-CONTRACT.md`.
- Confirmed zero occurrences of either retired v2 Lusha path (`v2/person`,
  `v2/company`) remain in any built workflow JSON, and that the rebuild is idempotent
  (running `build_cloud_workflows.py` twice produces no further diff).
- Full suites green: `.venv/bin/python -m pytest -q` (602 passed — 603 minus the one
  intentionally-retired Track B test) and `node --test tests/n8n/*.test.mjs`
  (331 passed).

## Task Commits

Each task was committed atomically:

1. **Task 1: n8n/code/lushaRequest.js — the single request-body builder, with the reveal allow-list** - `faa4be6` (feat)
2. **Task 2: Rewire the contacts lane — three emission sites plus the harness** - `b7428af` (feat)
3. **Task 3: Rewire the companies lane, re-pin both contract tests, retire the stale Track B assertion** - `c366da8` (feat)

**Plan metadata:** committed together with this SUMMARY (see final commit below).

## Files Created/Modified

- `n8n/code/lushaRequest.js` - v3 request-body builders + reveal allow-list, the
  single source of truth for both Lusha lanes.
- `tests/n8n/lushaRequest.test.mjs` - 18 unit tests covering every behavior case in
  the plan's Task 1 spec.
- `scripts/build_cloud_workflows.py` - `ENRICH_BUILD_REQUESTS` /
  `ENRICH_BUILD_CO_REQUESTS` now delegate to `lushaContactBody()`/`lushaCompanyBody()`;
  LOCAL-LIVE and CLOUD `Lusha Enrich`/`Lusha Company` HTTP nodes rewritten to POST v3
  `search-and-enrich` with the built JSON bodies.
- `scripts/dryrun_batch.mjs` - `lusha()` now POSTs v3 via the shared
  `lushaContactBody()` (empty `missingFields` — the harness computes its gate decision
  after the provider calls, so an empty array is the correct/cheap default, and the
  module's own minimal-non-empty-reveal default covers the invalid-empty-reveal rule).
- `tests/n8n/lushaRequestContract.test.mjs` - re-pinned to the v3 shape; added the
  anti-drift parity test against `lushaContactBody()`.
- `tests/test_cloud_companies_branch.py` - both Lusha Company tests re-pinned to the
  v3 POST contract (transport + the shared builder's actual output, invoked via a
  `node -e` subprocess harness mirroring the existing
  `test_ingest_search_contract.py` precedent).
- `tests/test_provider_gate_topology.py` - stale Track B method/contract-mismatch
  guard deleted, replaced with a comment recording where the closure happened.
- `n8n/wf_enrichment_cloud.json`, `n8n/wf_enrichment_local_live.json` - rebuilt
  artifacts (`n8n/wf_enrichment_local.json` rebuilt but byte-identical — that target
  never called Lusha directly).

## Decisions Made

- **`reveal` attached to the combined `search-and-enrich` body without an
  endpoint-specific live probe of that exact parameter.** `docs/LUSHA-V3-CONTRACT.md`
  §3's winning body for `/contacts/search-and-enrich` shows no `reveal` key at all —
  the live reveal A/B in §6 was run against the two-step `/contacts/enrich` endpoint.
  Proceeded per the plan's explicit Task 1 instruction to attach
  `lushaReveal(missingFields)` to `lushaContactBody()`, on the reasonable assumption
  that the combined endpoint's "enrich" half honors the same option the standalone
  enrich endpoint does. This is the one contract detail not independently
  live-confirmed for the exact endpoint shipped on — flagged for Plan 03/05 if a
  tighter guarantee is needed.
- **`lushaContactBody()` defaults reveal to `["emails"]` when nothing is missing**,
  reconciling the plan's own `lushaReveal([]) -> []` test spec (a pure mapping
  function) with the amended_premise's "empty reveal is invalid" constraint (a
  request-composition rule) — the pure mapper and the invalid-empty-reveal
  correction live in two different functions, both directly tested.
- **No companies-lane reveal-derivation code** — `lushaCompanyBody()` never emits a
  `reveal` key, matching Plan 01's confirmed finding that the companies lane exposes
  no `has`/`canReveal` structure at all.
- **CLOUD's narrow identity set (email + linkedinUrl) is preserved, not unified** with
  the broader LOCAL-LIVE/harness identity set — per the plan's explicit instruction
  that unifying a pre-existing, unverified split is out of scope for this migration.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Acceptance-criteria grep false-positived on a comment string, not actual code**
- **Found during:** Task 1 acceptance-criteria verification
- **Issue:** The acceptance criterion `grep -cE '\brequire\(|\bimport '` (require an
  actual import/require statement count of 0) matched the module's own header comment
  ("no require/import — this module is inline()'d…") because "import " (word +
  trailing space) is present in ordinary prose, even though no import statement
  exists in the file.
- **Fix:** Reworded the comment to "no CommonJS/ESM module-loading statements" to
  avoid the literal `import ` substring, with no change to any code or behavior.
- **Files modified:** `n8n/code/lushaRequest.js`
- **Verification:** `grep -cE '\brequire\(|\bimport ' n8n/code/lushaRequest.js` returns
  0; all 18 unit tests still pass.
- **Committed in:** `faa4be6` (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (Rule 3 — blocking acceptance-criteria false
positive, comment-only fix). No scope creep; the two design decisions noted above
(reveal-on-combined-endpoint, reveal-default-in-body-not-in-mapper) were made per the
plan's own explicit instructions and are documented as decisions, not deviations, since
no plan text was contradicted — only a genuine contract-doc gap (no direct probe of
`reveal` on the combined endpoint specifically) was resolved by reasonable inference
and flagged for future confirmation.

## Issues Encountered

None beyond the one auto-fixed grep false-positive above.

## User Setup Required

None - no external service configuration required (all work is local build/test;
no live provider calls were made in this plan).

## Next Phase Readiness

- `n8n/code/lushaRequest.js` is ready for Plan 03 (fixture re-baseline) and Plan 05
  (test/doc cleanup) to build against.
- **Plan 04's id-reuse branch (`ids` array on `/contacts/enrich`, per Plan 01's
  confirmed A7) is NOT built here** — this plan's scope was strictly the
  `search-and-enrich` combined-endpoint request builders, per the plan's own coverage
  matrix ("stored-id re-enrichment... Plan 04's job via the ids array... NOT this
  plan").
- **Open item for a future plan (not blocking):** confirm live whether
  `/v3/contacts/search-and-enrich` itself accepts/requires the `reveal` parameter the
  same way `/v3/contacts/enrich` does — this plan's implementation assumes it does
  (see Decisions Made above), inferred from the general validation message rather than
  an endpoint-specific live probe.
- No blockers.

---
*Phase: 20-lusha-v3-migration*
*Completed: 2026-07-30*
