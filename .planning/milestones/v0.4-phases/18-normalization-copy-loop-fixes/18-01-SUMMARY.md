---
phase: 18-normalization-copy-loop-fixes
plan: 01
subsystem: enrichment-normalization
tags: [n8n, code-node, normalization, waterfall-scoring, zoominfo, lusha, apollo, naics]

# Dependency graph
requires:
  - phase: 16.3-01
    provides: mergeCompanies.js stale-timestamp fix precedent (frozen-module discipline, rebuild-and-verify-determinism cycle)
provides:
  - "_industryText helper in n8n/code/normalizeProviders.js — a bare NAICS code can no longer be emitted as an industry candidate value"
  - "tests/n8n/industryNormalization.test.mjs — the NORM-01 offline proof, built on the real recorded execution-19 shape"
  - "Regenerated n8n/wf_enrichment_cloud.json / wf_enrichment_local.json / wf_enrichment_local_live.json"
affects: [18-02, future-icp-scoring-phases]

# Tech tracking
tech-stack:
  added: []
  patterns: ["prefer-name-over-code fallback helper (NAICS entry .name -> provider industry text fallback -> null, never a bare code)"]

key-files:
  created:
    - tests/n8n/industryNormalization.test.mjs
  modified:
    - n8n/code/normalizeProviders.js
    - tests/n8n/enrichment.test.mjs
    - n8n/wf_enrichment_cloud.json
    - n8n/wf_enrichment_local.json
    - n8n/wf_enrichment_local_live.json

key-decisions:
  - "D-NORM-empty: a bare NAICS code with no text fallback emits NO industry candidate at all, rather than converting it into a fabricated text value (no NAICS lookup table introduced, per RESEARCH's Don't Hand-Roll guidance)."
  - "D-NORM-precedence: when both a NAICS .name and a text fallback exist, the NAICS .name wins."
  - "D-NORM-lusha: the identical-shape hazard in lushaCandidates() was fixed defensively in the same pass via the same _industryText helper, even though no live fixture proves Lusha ever returns object-shaped naicsCodes."
  - "Equality/agreement semantics (scoreEnrichment.js's _eq / _norm) were left untouched — this is a normalization fix upstream of the scorer, not a scoring-logic change."

requirements-completed: [NORM-01]

coverage:
  - id: D1
    description: "A numeric provider industry code (ZoomInfo's bare NAICS code) can no longer be emitted as an `industry` candidate value by any company mapper — it is replaced by human-readable text or omitted entirely."
    requirement: "NORM-01"
    verification:
      - kind: unit
        ref: "tests/n8n/industryNormalization.test.mjs#CRITERION 1: ZoomInfo live industry candidate is human-readable text, never a bare NAICS code"
        status: pass
      - kind: unit
        ref: "tests/n8n/industryNormalization.test.mjs#EDGE D-NORM-empty: ZoomInfo bare NAICS code with no primaryIndustry emits ZERO industry candidates"
        status: pass
      - kind: unit
        ref: "tests/n8n/industryNormalization.test.mjs#EDGE D-NORM-empty (Lusha): bare NAICS code with no mainIndustry emits ZERO industry candidates"
        status: pass
    human_judgment: false
  - id: D2
    description: "A numeric code can never win the cross-provider industry waterfall on the ZoomInfo source-trust constant alone — the winning value's shape is always text."
    requirement: "NORM-01"
    verification:
      - kind: unit
        ref: "tests/n8n/industryNormalization.test.mjs#CRITERION 2: industry waterfall winner is text even though ZoomInfo's source trust beats Apollo's"
        status: pass
      - kind: unit
        ref: "tests/n8n/enrichment.test.mjs#score industry: Apollo+ZoomInfo agree on text; ZoomInfo wins on fresher recency"
        status: pass
    human_judgment: false

duration: 40min
completed: 2026-07-29
status: complete
---

# Phase 18 Plan 01: Industry normalization (NORM-01) Summary

**Added `_industryText` to `normalizeProviders.js` so ZoomInfo's and Lusha's company mappers emit the NAICS entry's human-readable name (or nothing) instead of a bare numeric code, closing the gap where a code could win the industry waterfall purely on source trust.**

## Performance

- **Duration:** ~40 min
- **Completed:** 2026-07-29T08:06:45Z
- **Tasks:** 2
- **Files modified:** 5 (1 created, 4 modified)

## Accomplishments

- Root-caused and closed NORM-01: `zoominfoCandidates`/`lushaCandidates` no longer push a bare NAICS code as the `industry` candidate value; they push the NAICS entry's own `.name`, fall back to the provider's industry text field, or emit no candidate at all.
- Proved both ROADMAP Phase 18 success criteria (1 and 2) with a new offline test built directly on the real recorded `zoominfo_live_company.json` (Racing NSW) fixture plus the actual `"media production"` Apollo industry text observed live during execution-19 (never previously fixture-ized; provenance recorded in `.planning/debug/bug-17-lusha-company-400.md`).
- Updated the two now-stale pinned assertions in `tests/n8n/enrichment.test.mjs` in the same commit as the source fix, converting a NAICS-code "agreement" into a genuine cross-provider TEXT agreement.
- Rebuilt only the three workflow artifacts that inline `normalizeProviders.js`; confirmed the rebuild is deterministic (byte-identical on a second run, md5-verified).
- Zero regressions: 596 pytest / 289 node (285 baseline + 4 new NORM-01 tests) all green; all five frozen shared JS modules and the frozen companies node-body fixture untouched.

## Task Commits

Each task was committed atomically:

1. **Task 1: Author the NORM-01 red test against the real execution-19 shape** - `ae46e63` (test)
2. **Task 2: Add _industryText, apply to both company mappers, update the two collateral pins, rebuild** - `d54ed27` (feat)

_Note: Task 2 is `tdd="true"` in the plan; the RED commit (Task 1) and GREEN commit (Task 2) satisfy the gate — no separate REFACTOR commit was needed._

## Files Created/Modified

- `tests/n8n/industryNormalization.test.mjs` - New NORM-01 red-before-green proof (4 tests: 2 criteria + 2 D-NORM-empty edges)
- `n8n/code/normalizeProviders.js` - New `_industryText(naicsEntry, textFallback)` helper; rewired into `zoominfoCandidates` and `lushaCandidates` company branches
- `tests/n8n/enrichment.test.mjs` - Two pinned assertions updated (live-fixture NAICS name, company-scoring text-agreement)
- `n8n/wf_enrichment_cloud.json`, `n8n/wf_enrichment_local.json`, `n8n/wf_enrichment_local_live.json` - Regenerated build artifacts (the three factory sites that inline `normalizeProviders.js`); `wf_contact_ingest_*.json` and `wf_scheduled_maintenance_cloud.json` were unaffected

## Verbatim Task 1 RED output (before the fix)

```
✖ CRITERION 1: ZoomInfo live industry candidate is human-readable text, never a bare NAICS code (0.929667ms)
✖ CRITERION 2: industry waterfall winner is text even though ZoomInfo's source trust beats Apollo's (0.431083ms)
✖ EDGE D-NORM-empty: ZoomInfo bare NAICS code with no primaryIndustry emits ZERO industry candidates (0.239166ms)
✖ EDGE D-NORM-empty (Lusha): bare NAICS code with no mainIndustry emits ZERO industry candidates (0.173083ms)
ℹ tests 4
ℹ suites 0
ℹ pass 0
ℹ fail 4

✖ failing tests:

test at tests/n8n/industryNormalization.test.mjs:51:1
✖ CRITERION 1: ZoomInfo live industry candidate is human-readable text, never a bare NAICS code
  AssertionError [ERR_ASSERTION]: normalizedValue must not be an all-ASCII-digit NAICS code
    actual: '71'
    expected: /^\d+$/
    operator: 'doesNotMatch'

test at tests/n8n/industryNormalization.test.mjs:66:1
✖ CRITERION 2: industry waterfall winner is text even though ZoomInfo's source trust beats Apollo's
  AssertionError [ERR_ASSERTION]: no all-digit value may win the industry waterfall on trust alone
    actual: '71'
    expected: /^\d+$/
    operator: 'doesNotMatch'

test at tests/n8n/industryNormalization.test.mjs:96:1
✖ EDGE D-NORM-empty: ZoomInfo bare NAICS code with no primaryIndustry emits ZERO industry candidates
  AssertionError [ERR_ASSERTION]: a bare code with no fallback text must never emit a numeric industry candidate
    actual: 1
    expected: 0

test at tests/n8n/industryNormalization.test.mjs:110:1
✖ EDGE D-NORM-empty (Lusha): bare NAICS code with no mainIndustry emits ZERO industry candidates
  AssertionError [ERR_ASSERTION]: a bare code with no fallback text must never emit a numeric industry candidate
    actual: 1
    expected: 0
```

All four tests failed as required; no `n8n/code/` file was modified when this was captured (`git status --porcelain n8n/code/` was empty).

## Post-fix suite counts

- `node --test tests/n8n/industryNormalization.test.mjs` — 4/4 pass (was 0/4 pass before the fix).
- `node --test tests/n8n/enrichment.test.mjs` — 31/31 pass.
- `node --test tests/n8n/*.test.mjs` — **289 pass, 0 fail** (baseline was 285; +4 new NORM-01 tests, 0 regressions).
- `.venv/bin/python -m pytest -q` — **596 passed** (baseline was 596; 0 regressions).
- `.venv/bin/python -m pytest tests/test_companies_factory_frozen.py -q` — 4/4 pass (no frozen companies node body changed; `normalizeProviders.js` is not inlined into any of the seven frozen node bodies).
- `git diff --quiet n8n/code/scoreEnrichment.js n8n/code/judge.js n8n/code/webResearch.js n8n/code/mergeCompanies.js n8n/code/mergeContacts.js` — exit 0 (no frozen/shared module touched).

## Built artifacts whose diff changed

- `n8n/wf_enrichment_cloud.json`
- `n8n/wf_enrichment_local.json`
- `n8n/wf_enrichment_local_live.json`

`n8n/wf_contact_ingest_local.json`, `n8n/wf_contact_ingest_cloud.json`, and `n8n/wf_scheduled_maintenance_cloud.json` were rewritten by the builder but produced byte-identical content (no diff) — confirming the fix is scoped exactly to the three factory sites that inline `normalizeProviders.js` (contacts normalize, LOCAL mock normalize, companies normalize).

**Determinism:** ran the builder a second time and md5-compared the three changed files before/after — identical.

## D-NORM-lusha consequence confirmation

Confirmed exactly as planned: with the flat `lusha_company.json` fixture (`naicsCodes: ["711211"]`, no `mainIndustry` key), Lusha now emits **zero** `industry` candidates — the bare-code "agreement" between Lusha and ZoomInfo that the old test pinned no longer exists. In its place, `tests/n8n/enrichment.test.mjs`'s `"score industry"` test now asserts a genuine cross-provider TEXT agreement: Apollo's `"Spectator Sports"` and ZoomInfo's fallback to its own `primaryIndustry` text (`"Spectator Sports"`, since the flat `zoominfo_company.json` fixture's `naicsCodes` entry is a bare string with no `.name`) both normalize to `"spectator sports"`, and ZoomInfo wins on its fresher `validDate` recency.

## Decisions Made

- **D-NORM-empty, D-NORM-precedence, D-NORM-lusha, D-NORM-encoding** — all four planner decisions from the PLAN were implemented exactly as specified; no deviation from the documented rationale was needed.
- Passed `industry && industry.raw` / `industry && industry.key` directly to `_push` at both call sites (rather than wrapping the `_push` call in an `if`), matching the plan's `must_haves.key_links` requirement that "`_push` already no-ops on a null/undefined/empty `value`, so `_industryText` returning null needs no extra branch at either call site."

## Deviations from Plan

None — plan executed exactly as written. Both tasks' acceptance criteria were met on the first implementation pass; no auto-fixes (Rules 1-3) were needed, and no architectural questions (Rule 4) arose.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required. This is an offline-only fix; no live HubSpot or n8n API call was made.

## Next Phase Readiness

- `n8n/code/normalizeProviders.js`, `tests/n8n/enrichment.test.mjs`, and the three regenerated workflow artifacts are committed and stable for Plan 18-02 (COPY-01/COPY-02), which depends on this plan (wave 2, `depends_on: [18-01]`).
- The full offline suite is at 596 pytest / 289 node with 0 regressions — a clean baseline for 18-02 to build on.
- No blockers.

---
*Phase: 18-normalization-copy-loop-fixes*
*Completed: 2026-07-29*

## Self-Check: PASSED

All created/modified files verified present on disk; all three task/summary commit hashes (`ae46e63`, `d54ed27`, `8d42d9a`) verified present in `git log`.
