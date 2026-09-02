---
phase: 36-enrichment-propose-mode
plan: 04
subsystem: infra
tags: [n8n, hubspot, code-node, workflow-builder, propose-mode, write-safety, lusha]

# Dependency graph
requires:
  - phase: 36-enrichment-propose-mode
    plan: "03"
    provides: "mode threaded onto every enrichment row (Parse HubSpot Event -> ... -> Decide Action/Decide Company Action)"
provides:
  - "isReturnOnly(mode) — the shared two-state propose-mode write-guard predicate"
  - "action:\"proposed\" (contacts + companies) and action:\"needs_match_review\" (contacts) — both set before _writeSafetyAllows, reading no ALLOW_* constant"
  - "row_id/mode/match echoed on Decide Action and Decide Company Action output"
  - "cloud Lusha Enrich sending the full six-key identity set lushaContactBody() supports"
provides_downstream: [37-client-chunking]

# Actuals (#2632)
actuals:
  tokens: 67933
  tasks: 3
  commits: 3

tech-stack:
  added: []
  patterns:
    - "Write-guard predicate computed ONCE per row into a local const (`isReturnOnly(row.mode)`), then consulted by both the action-assignment and the BUG-19 seed guard — one source of truth per row, not two separately-derived checks that could drift apart"
    - "Ordering-as-safety-property: the propose/needs-match-review assignment sits textually before the `_writeSafetyAllows` call in source order, and the structural test asserts that ordering by character index — proving the no-write guarantee cannot be re-armed by flipping a flag, only by reordering the source itself (which the test catches)"
    - "Inline-expression parity via structural mirroring, not enumerated cases: the widened Lusha jsonBody expression's identity-present check (`Object.keys(c).length > 0`) mirrors `lushaContactBody()`'s own emptiness check (`Object.keys(contact).length === 0`) exactly, giving total parity across every identity combination rather than only the ones a test matrix happens to enumerate"

key-files:
  created: []
  modified:
    - n8n/code/matchProposal.js
    - scripts/build_cloud_workflows.py
    - n8n/wf_enrichment_cloud.json
    - n8n/wf_enrichment_local.json
    - n8n/wf_enrichment_local_live.json
    - tests/n8n/matchProposal.test.mjs
    - tests/n8n/lushaRequestContract.test.mjs
    - tests/test_cloud_write_path.py
    - tests/test_write_gate_coverage.py

key-decisions:
  - "The medium-tier demotion (create -> needs_match_review) and the propose demotion (any action -> proposed) are combined into one if/else-if rather than two independent if-statements, since the plan's own predicate makes them mutually exclusive (the medium guard only applies when NOT return-only) — simpler control flow, same source-order guarantee, same acceptance criteria"
  - "The cloud Lusha identity-present check is widened to `Object.keys(c).length > 0` (mirrors the module's own emptiness check for ALL six fields) rather than literally the plan's narrower prose (`email-or-linkedin OR (firstName AND lastName AND companyName)`) — the narrower predicate would leave domain-only and first-name-only identities producing `{contacts:[]}` from the expression while `lushaContactBody()` itself returns a non-empty request for those same inputs (verified live: the module has no field-pairing requirement, any single non-blank field survives its assignment loop), which would break the anti-drift deep-equality guarantee the plan's own PARITY_MATRIX explicitly requires for every new matrix entry. The `Object.keys` mirror is the only implementation that is byte-parity-correct for the entire input space, not just the five enumerated new cases — the true form of the anti-drift strengthening T-36-20 calls for."
  - "One pre-existing pinned test (`tests/n8n/lushaRequestContract.test.mjs`'s \"neither email nor linkedin_url present\" case) had its premise flipped by the widening — amended in place with the reversal reasoning inline (phase_hard_rules #8), never deleted or silently reworded to pass"

patterns-established:
  - "Structural test collision avoidance: `_writeSafetyAllows(` as a bare substring also matches the function DECLARATION (which is always inlined ahead of the map body, so it always precedes any call textually) — the ordering assertions search for `!_writeSafetyAllows(` (unique to the guarded call site, since the declaration is never negated) rather than the bare function name, to actually test source order rather than always trivially passing/failing on the declaration's fixed early position"

requirements-completed: [DISPATCH-02, STRUCT-04, STRUCT-02]

coverage:
  - id: D15
    description: "isReturnOnly(mode) is the two-state write-guard predicate: mode absent/null or \"write\" (case/whitespace-insensitive) is false; every other value, including a typo, is true. Never throws."
    requirement: STRUCT-04
    verification:
      - kind: unit
        ref: "tests/n8n/matchProposal.test.mjs (11 new cases: absent, null, write/WRITE/\" Write \", propose, typo, empty string, 0, {}, never-throws)"
        status: pass
    human_judgment: false
  - id: D16
    description: "Decide Action sets action:\"proposed\" immediately after `let action = row.action;`, unconditionally on isReturnOnly(row.mode) alone and strictly before the _writeSafetyAllows call; a medium-tier match on the write path is demoted to needs_match_review before the same call; the BUG 19 email seed is gated on !returnOnly; the returned object names row_id/mode/match"
    requirement: DISPATCH-02
    verification:
      - kind: structural
        ref: "tests/test_cloud_write_path.py (5 new tests: ordering-by-index, returned-fields, email-seed-guard, medium-tier-demotion) + tests/test_write_gate_coverage.py (1 new test: IF Create/IF Enrich cannot match either return-only action string)"
        status: pass
      - kind: regression
        ref: ".venv/bin/python -m pytest -q (1956/6 after Task 1, no regression vs 1951/6 baseline)"
        status: pass
    human_judgment: false
  - id: D17
    description: "Decide Company Action carries the identical guard: action:\"proposed\" set before _writeSafetyAllows on isReturnOnly(row.mode) alone; the BUG 19 domain/name seed gated on !returnOnly; row_id/mode/match returned; NO medium-tier guard (companies has no match lane, so no companies row can ever carry a medium tier — commented explicitly so the omission reads as deliberate, not missed)"
    requirement: DISPATCH-02
    verification:
      - kind: structural
        ref: "tests/test_cloud_write_path.py (4 new tests: ordering-by-index, returned-fields, no-medium-guard, create-seed-guard)"
        status: pass
      - kind: regression
        ref: ".venv/bin/python -m pytest -q (1960/6 after Task 2, no regression)"
        status: pass
    human_judgment: false
  - id: D18
    description: "Cloud Lusha Enrich's inline jsonBody expression sends the full six-key identity set (email, linkedinUrl, firstName, lastName, companyName, companyDomain) lushaContactBody() supports; the identity-present check is Object.keys(c).length > 0, mirroring the module's own emptiness check for total parity; the \"deliberately narrow\" history comment is rewritten in place with the date and reversal reason, not deleted"
    requirement: STRUCT-02
    verification:
      - kind: unit
        ref: "tests/n8n/lushaRequestContract.test.mjs (PARITY_MATRIX widened with 5 new cases: name+company-only, domain-only, name+company+domain, first-name-only, explicit empty; 1 pre-existing pinned test amended in place with the reversal reason)"
        status: pass
      - kind: structural
        ref: "grep -c 'deliberately keeps sending the NARROW' scripts/build_cloud_workflows.py -> 0; jsonBody parameters contain firstName/lastName/companyName/domain"
        status: pass
      - kind: regression
        ref: ".venv/bin/python -m pytest -q (1960/6, unchanged) + operator-claude-plugin/tests (1052/5, unchanged) + node --test tests/n8n/*.test.mjs (609, unchanged vs post-Task-1 baseline)"
        status: pass
    human_judgment: false

duration: ~50min
completed: 2026-08-05
status: complete
---

# Phase 36 Plan 04: Propose Mode Write-Guard + Lusha Identity Widening Summary

**`mode:"propose"` is now real on both contacts and companies — `action:"proposed"` is set on the
mode predicate alone, strictly before the write-safety gate, so the no-write guarantee cannot be
re-armed by flipping `ALLOW_HUBSPOT_*` — and the cloud Lusha request sends the same six-key
identity set its own module supports, so a name+company row with no email can now be enriched.**

## Performance

- **Duration:** ~50 min
- **Tasks:** 3/3 completed
- **Files modified:** 9 (0 new; 3 `n8n/*.json` regenerated via the builder, never hand-edited)

## Accomplishments

- **Task 1 — `isReturnOnly` + Decide Action's propose guard:** `isReturnOnly(mode)` is the
  shared two-state predicate — `undefined`/`null`/`"write"` (case/whitespace-insensitive) is
  `false`; every other value, including a typo, is `true`, never throwing. `Decide Action`
  computes it once per row (`const returnOnly = isReturnOnly(row.mode);`) and sets
  `action = "proposed"` immediately after `let action = row.action;`, unconditionally on that
  predicate and strictly before the `_writeSafetyAllows` call — the ordering the structural test
  proves by character index. A second, mutually-exclusive branch demotes `create -> needs_match_review`
  when `row.match.tier === "medium"` on the write path (a MEDIUM is a caller-unjudged proposal;
  auto-creating against it would duplicate the very candidate `mediumCandidates()` surfaced). The
  BUG 19 create-time email seed is now gated on `!returnOnly` so a propose response's `properties`
  never echoes the caller's own identity back as a discovered field. The returned object gained
  `row_id`/`mode`/`match` (falling back to `summarizeMatch({ lane: row.lane })` for a row that
  never reached an adapter).
- **Task 2 — Decide Company Action mirrors the guard:** `inline("matchProposal.js")` appended to
  the existing four-module inline list; the same propose assignment, BUG 19 seed guard, and
  returned-field additions, with NO medium-tier demotion (companies has no match lane — commented
  explicitly so the omission reads as a deliberate scope boundary, not a miss).
- **Task 3 — cloud Lusha widened to the module's full identity set:** the inline `jsonBody`
  expression now assigns all six fields `lushaContactBody()` supports; the identity-present check
  became `Object.keys(c).length > 0`, mirroring the module's own `Object.keys(contact).length === 0`
  check exactly rather than a hand-picked OR-combination — this gives byte-parity across the
  *entire* input space, not just the enumerated matrix entries (see Decisions). The "deliberately
  narrow" history comment was rewritten in place (not deleted) recording the date and the
  reversal reasoning.
- Every new/amended assertion red-checked individually by reverting the corresponding builder
  edit (or, for the ordering assertions, by hand-patching the built JSON) and confirming the
  SPECIFIC assertion failed before restoring: Task 1's ordering assertion, returned-fields
  assertion, and IF-router assertion; Task 2's companies-branch ordering and returned-fields
  assertions; Task 3's matrix parity assertion (dropping the `companyName` assignment failed
  exactly the name+company-only matrix case, as expected).
- No deviations from the plan's task structure — all three tasks executed as scoped. One
  implementation choice (Task 3's identity-present predicate) deliberately diverges from the
  plan's literal prose; see Decisions below for the reasoning and why the divergence is required
  to satisfy the plan's own stated parity requirement.

## Task Commits

Each task was committed atomically:

1. **Task 1: `isReturnOnly` + Decide Action** — `a40fa2b` (feat: action:"proposed" set before
   the write gate, 11 new node tests, 5 new + 1 companion structural test)
2. **Task 2: Decide Company Action** — `d4a3570` (feat: companies mirror of the propose guard,
   4 new structural tests)
3. **Task 3: Lusha widening** — `b2eb681` (feat: full six-key identity set, rewritten history
   comment, widened parity matrix, 1 pinned test amended in place)

## Files Created/Modified

- `n8n/code/matchProposal.js` — `isReturnOnly(mode)` added and exported
- `scripts/build_cloud_workflows.py` — `ENRICH_DECIDE_CLOUD`/`ENRICH_DECIDE_CO_CLOUD` gain the
  propose guard, medium-tier demotion (contacts only), gated BUG 19 seeds, and
  `row_id`/`mode`/`match` in the returned object; cloud `Lusha Enrich`'s `jsonBody` expression
  widened and its history comment rewritten in place
- `n8n/wf_enrichment_cloud.json`, `n8n/wf_enrichment_local.json`, `n8n/wf_enrichment_local_live.json`
  — regenerated via the builder (never hand-edited); the local/local-live diffs are incidental
  consequences of `matchProposal.js`'s inline growth (they also `inline("matchProposal.js")` via
  `ENRICH_BUILD_IDENTITY`/`ENRICH_ADAPT_SEARCH`)
- `tests/n8n/matchProposal.test.mjs` — 11 new `isReturnOnly` cases
- `tests/n8n/lushaRequestContract.test.mjs` — `PARITY_MATRIX` widened with 5 new cases; 1
  pre-existing pinned test amended in place with the reversal reason
- `tests/test_cloud_write_path.py` — 9 new structural tests across both Decide-node branches
- `tests/test_write_gate_coverage.py` — 1 new companion test (IF Create/IF Enrich cannot match
  either return-only action string)

## Decisions Made

- **Combined if/else-if for the propose vs. medium-tier guards** (Task 1): the plan describes
  them as two separate guards, but since the medium-tier demotion only applies when NOT
  return-only, they are mutually exclusive — an `if (returnOnly) {...} else if (...) {...}`
  captures the same source-order guarantee with less control flow.
- **Lusha identity-present check widened to `Object.keys(c).length > 0`, not the plan's literal
  `email-or-linkedin OR (firstName AND lastName AND companyName)` prose** (Task 3): live-testing
  `lushaContactBody()` directly confirms it has no field-pairing requirement — a lone `domain` or
  even a lone `firstName` survives its per-field assignment loop and produces a non-empty request
  (`Object.keys(contact).length === 0` is the ONLY gate). The plan's own `PARITY_MATRIX`
  instructions require every new matrix entry (including the domain-only and first-name-only
  cases) to deep-equal the module's output. A narrower predicate matching only the plan's prose
  would make the domain-only and first-name-only cases diverge from the module (expression
  returns `{contacts:[]}`, module returns a populated request) — breaking exactly the anti-drift
  guarantee T-36-20 exists to close. Mirroring the module's own emptiness check exactly is the
  only implementation that is correct for the *entire* input space, not just the five newly
  enumerated cases, and was verified live via `node -e` against `lushaContactBody()` before
  implementation.
- **One pinned test amended in place, not silently reworded**: `tests/n8n/lushaRequestContract.test.mjs`'s
  "neither email nor linkedin_url present" test asserted `{contacts:[]}` for a name+company+domain
  identity under the OLD narrow expression. Under the widened expression this identity now
  produces a real (non-empty) request — exactly the reversal Phase 36 exists to land. Renamed and
  rewritten with the reversal reasoning inline, per this repo's "amend a deliberately-changed
  pinned test WITH the reason inline" convention (phase_hard_rules #8) — never deleted.

## Deviations from Plan

**1. [Rule 1 - bug-prevention] Lusha identity-present check implemented as `Object.keys(c).length
> 0` instead of the plan's literal `email-or-linkedin OR (firstName AND lastName AND companyName)`
prose.**
- **Found during:** Task 3, while building the widened `PARITY_MATRIX` per the plan's own
  instructions to include a domain-only and a first-name-only case, each asserted to deep-equal
  `lushaContactBody()`'s output.
- **Issue:** `lushaContactBody()` has no field-pairing requirement (verified live via `node -e`) —
  ANY single non-blank identity field (including a lone `domain` or a lone `firstName`) produces a
  non-empty request from the module. The plan's literal three-clause OR predicate would leave the
  cloud expression returning `{contacts:[]}` for those two inputs while the module returns a
  populated request — a genuine parity break the plan's own matrix instructions explicitly forbid
  ("Each case asserts the evaluated expression deep-equals `lushaContactBody()`'s output").
- **Fix:** Widened the identity-present check to `Object.keys(c).length > 0`, structurally
  mirroring `lushaContactBody()`'s own `Object.keys(contact).length === 0` emptiness check. This
  guarantees parity for the *entire* identity-field combination space, not only the plan's
  enumerated matrix entries.
- **Files modified:** `scripts/build_cloud_workflows.py` (the `Lusha Enrich` `jsonBody`
  expression), `n8n/wf_enrichment_cloud.json` (regenerated), `tests/n8n/lushaRequestContract.test.mjs`
  (matrix cases + the one amended pinned test).
- **Commit:** `b2eb681`

## Authentication Gates

None encountered.

## Known Stubs

None — this plan wires real behavior end to end; no placeholder values or unwired data sources
were introduced.

## User Setup Required

None. This plan makes zero live/deploy changes; `scripts/deploy_n8n_workflows.py` was not run
(denied to agents per this phase's constraints). The tenant remains disarmed and untouched by
this plan.

## Next Phase Readiness

- A `mode:"propose"` request now returns merged `properties`, a `match` verdict, and `row_id` on
  both object types, taking no write branch — proven regardless of `WRITE_SAFETY_DEFAULTS` (the
  guarantee holds by source ordering, not by a flag's runtime value).
- `mode` absent is byte-identical to today: the predicate returns `false` for `undefined`/`null`,
  and the propose/needs-match-review branches are `if`/`else if` gated on `returnOnly` alone, so
  the write path's existing behavior is untouched when `mode` is absent.
- A typo `mode` value (e.g. `"proprose"`) returns proposals, never writes — verified directly via
  `isReturnOnly`.
- A MEDIUM match never auto-creates on the write path (`needs_match_review` demotion, contacts
  only — companies has no match lane by design).
- Cloud Lusha now sends the full identity set `lushaContactBody()` supports; the first live
  propose run against a name+company row is still the open proof point named in 36-CONTEXT.md
  §12 Risk 4 (unchanged by this plan — it widens the request, it does not run one live).
- Verification suites green against baselines: `.venv/bin/python -m pytest -q` -> 1960 passed / 6
  skipped (baseline 1951/6, +9 new: 5+4 structural tests across Tasks 1/2; Task 3 added zero new
  pytest tests). `node --test tests/n8n/*.test.mjs` -> 609 passing (baseline 598, +11: Task 1's
  `isReturnOnly` cases; Task 3 widened an existing matrix without adding new `test()` blocks).
  `.venv/bin/python -m pytest operator-claude-plugin/tests/ -q` -> 1052 passed / 5 skipped
  (unchanged — this phase touches no plugin file). `grep -c 'ALLOW_HUBSPOT_[A-Z_]* = "true"'
  n8n/*.json` -> 0 for every file. Builder idempotent — a second
  `scripts/build_cloud_workflows.py` run leaves `git diff --stat n8n/` empty. No blockers for
  36-05.

## Self-Check: PASSED

- FOUND: `.planning/workstreams/plugin-entrypoint/phases/36-enrichment-propose-mode/36-04-SUMMARY.md`
- FOUND: `n8n/code/matchProposal.js` (isReturnOnly present)
- FOUND: `n8n/wf_enrichment_cloud.json` (Decide Action / Decide Company Action / Lusha Enrich carry the changes)
- FOUND commit: `a40fa2b`
- FOUND commit: `d4a3570`
- FOUND commit: `b2eb681`

---
*Phase: 36-enrichment-propose-mode*
*Completed: 2026-08-05*
