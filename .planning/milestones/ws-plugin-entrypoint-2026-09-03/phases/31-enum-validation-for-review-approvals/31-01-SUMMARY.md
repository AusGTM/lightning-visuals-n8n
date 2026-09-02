---
phase: 31-enum-validation-for-review-approvals
plan: 01
subsystem: n8n-backend
tags: [enum-validation, hubspot-schema, review-loop, mergeCompanies, generated-module, defense-in-depth]

requires:
  - phase: 30
    plan: 07
    provides: "the RB-9 armed canary that recorded the live BUG 28/29 evidence (company 9604614548, industry = 'arts, entertainment, and recreation')"
  - phase: 25
    plan: null
    provides: "mergeCompanies.js / DEFAULT_COMPANY_POLICY — the staging engine this plan adds a guard inside"
provides:
  - "n8n/code/hubspotEnums.js — normalizeEnumValue/enumRefusalMessage/isEnumBound, the ONE validator both mergeCompanies.js and reviewApply.js consult"
  - "n8n/code/hubspotEnums.generated.js + scripts/gen_hubspot_enums_js.py — the generated values+labels module and its generator, following the taxonomy.generated.js pattern"
  - "reviewApply's `invalid` return key — an all-or-nothing refusal, exactly like `stale`"
  - "reviewDecision's `refused` outcome on an invalid enum candidate — empty properties on BOTH dry_run states"
  - "mergeCompanies' `rejected` validation_status on an unmappable enum candidate, forced to stage_only"
  - "review_skip on the 15-minute backstop's Apply Review node, replacing a bare `stale` test on Review IF Stale"
affects:
  - "31-02 (not_allowlisted outcome + writeAllowed input) — builds on the outcome vocabulary this plan left `refused` occupying for enum refusal"
  - "31-03 (disarmed redeploy) — ships the workflow JSON this plan regenerated"

tech-stack:
  added: []
  patterns:
    - "generated-module pattern (taxonomy.generated.js) reused verbatim for a second vocabulary: a Python generator renders a DO-NOT-EDIT JS data file from a pinned JSON snapshot, a hand-written sibling module holds the logic that reads it, and a pytest currency test byte-compares render() to the checked-in file"
    - "validate-and-refuse, no mapping layer (31-CONTEXT.md, locked 2026-08-03): the ONLY normalization is an exact case-insensitive label->value match; everything else is refused, not guessed at"
    - "all-or-nothing refusal beside the existing stale compare-and-set (reviewApply): one invalid field withholds the whole candidate, mirroring D-10/REVIEW-05's stale handling exactly"
    - "empty properties -> hasWrite:false -> dry_run resolves true regardless of the caller's request (REVIEW_BUILD_DECISION wrapper) — this is what makes preview and apply return an identical refusal for free, no new branching needed"
    - "defense in depth: mergeCompanies now validates enum candidates itself rather than trusting an upstream research/provider guard — proven live by two pre-existing tests that had documented the OLD (buggy) assumption and needed updating"

key-files:
  created:
    - scripts/gen_hubspot_enums_js.py
    - n8n/code/hubspotEnums.generated.js
    - n8n/code/hubspotEnums.js
    - tests/n8n/hubspotEnumValidation.test.mjs
    - tests/test_hubspot_enums_generated_currency.py
  modified:
    - n8n/code/reviewApply.js
    - n8n/code/reviewDecision.js
    - n8n/code/mergeCompanies.js
    - scripts/build_cloud_workflows.py
    - n8n/wf_enrichment_cloud.json
    - n8n/wf_enrichment_local_live.json
    - n8n/wf_review_decision_cloud.json
    - n8n/wf_scheduled_maintenance_cloud.json
    - tests/fixtures/companies_jscode_frozen.json
    - tests/n8n/countryRegionResearchMergePromotion.test.mjs
    - tests/n8n/parity.test.mjs
    - .planning/workstreams/plugin-entrypoint/ROADMAP.md

key-decisions:
  - "The generator's ENUM_PROPERTIES list is hand-typed but PINNED by a two-sided test (Task 3) against both config/field_policy.yaml (via mergeCompanies.js's DEFAULT_COMPANY_POLICY, read as TEXT) and the snapshot's own `type` field — the milestone's five-times-burned rule applied to a third contract."
  - "The enum guard forces `decision = 'stage_only'` unconditionally on refusal, overriding whatever the deterministic gate returned (including `needs_review`) — an unmappable value must never reach the review queue, not just never promote."
  - "Two pre-existing tests (countryRegionResearchMergePromotion.test.mjs (e), parity.test.mjs's industry case) encoded the exact bug class this phase closes — one literally commented 'the guard lives upstream, not here.' Both were updated to assert the new, correct stage_only/rejected behavior rather than left broken or worked around."
  - "reviewApply's own enum guard is exercised in tests via a HAND-CRAFTED candidate JSON (the producer shape, not a live mergeCompanies() call) because post-Task-2 mergeCompanies can no longer manufacture a needs_review decision holding an invalid value — the guard is now defense-in-depth against a candidate written before this fix existed, or hand-edited in HubSpot (T-31-02)."

metrics:
  duration: ~2h10min
  completed: 2026-08-03
status: complete

actuals:
  tokens: 187540
  tasks: 3
  commits: 4
---

# Phase 31 Plan 01: Enum Validation for Review Approvals — the enum spine Summary

Builds the single validated path a value travels to reach a HubSpot enumeration property:
one generated values-and-labels module sourced from the pinned schema snapshot, one
hand-written validator that performs the ONLY mapping this repo does (exact
case-insensitive label match), and that validator wired into both places a candidate
value can reach HubSpot — enrichment staging (`mergeCompanies.js`) and review approve
(`reviewApply.js`, called by both the synchronous decision endpoint and the 15-minute
backstop).

## What was built

**Task 1 (tracer) — end-to-end refusal on the approve path** (`2f003d0`)

- `scripts/gen_hubspot_enums_js.py` renders `n8n/code/hubspotEnums.generated.js` from
  `config/hubspot_migration/baseline/portal-schema-companies-post-orgtype-enum.json`,
  covering exactly the six `DEFAULT_COMPANY_POLICY` keys whose snapshot `type` is
  `enumeration`: `industry`, `lv_org_type`, `lv_content_type`, `lv_revenue_band`,
  `lv_employee_band`, `lv_country_region_normalized`. Refuses non-zero if a listed
  property is absent or not `type: enumeration`. Running it twice is byte-identical
  (verified: same md5 both runs).
- `n8n/code/hubspotEnums.js` exports `isEnumBound`, `normalizeEnumValue`,
  `enumRefusalMessage`. Single-select: exact match wins, then a lowercased
  `labelToValue` lookup, then refusal (original value preserved for the caller).
  Multi-select (`lv_content_type`, the only `fieldType: checkbox` property): splits an
  array or `;`-string, normalizes every part, ok only if every part is ok, preserves the
  input container shape.
- `reviewApply.js` gained an `invalid` return key: after the stale compare-and-set,
  every candidate is re-validated; one invalid field withholds the WHOLE candidate
  (empty `canonicalPatch`/`clearPatch`), exactly like `stale` — the all-or-nothing rule
  REVIEW-05 requires.
- `reviewDecision.js`'s approve branch returns `outcome: "refused"` (the existing word,
  no new vocabulary) with empty `properties` when `reviewApply` reports `invalid`.
  Because `properties` is empty, the `REVIEW_BUILD_DECISION` wrapper's `hasWrite` is
  false and `dry_run` resolves `true` regardless of the caller's request — this is what
  makes the preview and the real submit return an IDENTICAL refusal (BUG 29 closed for
  free, no new branching).
- `scripts/build_cloud_workflows.py`: `hubspotEnums.generated.js` + `hubspotEnums.js`
  added ahead of `mergeCompanies.js`/`reviewApply.js` in all 4 `inline()` call sites that
  named either (`ENRICH_MERGE_CO`, `ENRICH_DECIDE_CO_CLOUD`, `ENRICH_APPLY_REVIEW`,
  `REVIEW_BUILD_DECISION` — grepped, confirmed exhaustive, no fifth site exists).
  `ENRICH_APPLY_REVIEW`'s wrapper now emits `review_skip = result.stale === true ||
  Object.keys(properties).length === 0`, and `Review IF Stale` switches on `review_skip`
  instead of bare `stale` — an invalid-enum result is not stale, but its assembled patch
  is empty, so it must skip the write branch too (previously it fell through to PATCH an
  empty body).
- `tests/n8n/hubspotEnumValidation.test.mjs` — MODULE + FLOW sections (16 tests at this
  point; STAGING added in Task 2).

**Task 2 (tdd) — staging never offers an unmappable candidate** (`5c47d12` RED,
`d3663d6` GREEN)

`mergeCompanies.js` runs `normalizeEnumValue(field, value)` immediately after the blank
check, BEFORE the gate: on ok, the (possibly normalized) value is used everywhere from
that point on; on not-ok, the ORIGINAL value is kept for provenance/decisions, and the
decision is forced to `stage_only` — unconditionally, even overriding a gate result of
`needs_review` — with `validation_status: "rejected"` (the registered vocabulary value)
and the decisions-array `reason` set to the validator's own message. No new key added to
the provenance entry shape (byte-comparability with `src/merge_policy.py` preserved).

Followed the RED/GREEN gate literally: reverted the implementation
(`git checkout --`), ran the new STAGING assertions to confirm 5 genuine failures, committed
the failing tests, restored the implementation, confirmed all 31 tests green, then
committed.

**Task 3 — pin the generated module** (`8b74509`)

`tests/test_hubspot_enums_generated_currency.py`, three tests:
1. Currency — `gen_hubspot_enums_js.render()` byte-equals the checked-in file (verified
   the negative: hand-editing `"SPORTS"` to `"SPORTSBALL"` breaks it; restoring passes
   again — see Verification below).
2. Policy pin — `mergeCompanies.js` read as TEXT (never imported), `DEFAULT_COMPANY_POLICY`
   keys extracted by regex, intersected with the snapshot's own `type: enumeration` keys,
   asserted equal to `gen_hubspot_enums_js.ENUM_PROPERTIES`.
3. Fidelity — the snapshot's `industry` has exactly 148 options, `SPORTS` is one of
   them, and `"arts, entertainment, and recreation"` matches neither a value nor a label
   case-insensitively.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — bug, directly caused by Task 2] Two pre-existing tests encoded the exact
bug this phase closes**

- **Found during:** Task 2's full-suite regression pass (`node --test tests/n8n/*.test.mjs`
  showed 2 unexpected failures outside the plan's named "must not regress" file list).
- **`tests/n8n/countryRegionResearchMergePromotion.test.mjs` test (e):** asserted an
  unlisted research region value (`"Freedonia"`) "would still promote here" and its own
  comment stated *"Merge Company itself does not re-validate the enum — this is why the
  guard must live in Validate Research Output, not here."* Phase 31's entire purpose
  supersedes that assumption for `lv_country_region_normalized` (one of the six enum
  properties). Updated to assert `stage_only` / `validation_status: "rejected"` / never
  in `canonicalPatch`, with a comment pointing at T-31-02 (defense-in-depth).
- **`tests/n8n/parity.test.mjs`:** a candidate `industry: "Sports & Entertainment"`
  (present current value, previously asserted `needs_review`) now correctly stages —
  that string is not an exact case-insensitive match for any of the 148 HubSpot industry
  labels. Updated the assertion and the test name.
- **Files modified:** `tests/n8n/countryRegionResearchMergePromotion.test.mjs`,
  `tests/n8n/parity.test.mjs`.
- **Commit:** `d3663d6`.
- **Why Rule 1, not a plan deviation requiring a stop:** these failures were DIRECTLY
  caused by Task 2's change and the new (post-fix) behavior is unambiguously the correct
  one per the plan's own objective — an unmappable enum value must never be offered for
  review, full stop, regardless of which code path produced the candidate.

**2. [Rule 3 — blocking, fixture drift] `tests/fixtures/companies_jscode_frozen.json`
re-baselined twice**

- **Found during:** both Task 1 and Task 2, `pytest -q` failed on
  `test_companies_factory_frozen.py`'s byte-identity guard after `Merge Company`'s
  jsCode legitimately changed (Task 1: new `inline()` modules; Task 2: the enum-guard
  logic itself).
- **Fix:** rebuilt all cloud workflow JSON via `scripts/build_cloud_workflows.py`,
  regenerated the frozen fixture by calling `build_enrichment_cloud()` /
  `build_enrichment_local_live()` in-process and re-extracting the 7 frozen node
  bodies — the same mechanism the test itself uses, per the file's own "re-baselined
  ONLY by an explicit, reviewed act" rule. Diffed to confirm ONLY `Merge Company`
  changed in both `cloud` and `local_live` sections each time.
- **Commits:** `2f003d0` (Task 1's re-baseline), `d3663d6` (Task 2's).

No other deviations — the rest of the plan executed as written.

### Plan-path inaccuracy noted, not a deviation

The phase `<verification>` block names
`.venv/bin/python -m pytest tests/test_control_disarmed_artifacts.py -q`; the real path
is `operator-claude-plugin/tests/test_control_disarmed_artifacts.py` (confirmed the repo
root's `pytest.ini`-less config collects `operator-claude-plugin/tests/` into the same
root run, so the full-suite counts below already include it — ran it standalone too, 23
passed / 5 skipped, unaffected by this plan).

## The exact refusal message for the live case

```
"arts, entertainment, and recreation" is not a value HubSpot accepts for industry (148 options available). Closest accepted label(s): arts and crafts, entertainment, performing arts.
```

## inline() call sites changed (`scripts/build_cloud_workflows.py`)

| Constant | Node(s) | Change |
|---|---|---|
| `ENRICH_MERGE_CO` | `Merge Company` | + `hubspotEnums.generated.js`, `hubspotEnums.js` ahead of `mergeCompanies.js` |
| `ENRICH_DECIDE_CO_CLOUD` | `Decide Company Action` | same |
| `ENRICH_APPLY_REVIEW` | `Apply Review` | same, ahead of `mergeCompanies.js`/`reviewApply.js`; wrapper body also gained `review_skip` |
| `REVIEW_BUILD_DECISION` | `Build Review Decision` | same, ahead of `mergeCompanies.js`/`reviewApply.js`/`reviewDecision.js` |

`_if_bool_node("Review IF Stale", "stale", ...)` → `_if_bool_node("Review IF Stale",
"review_skip", ...)` (node name kept — plan explicitly scoped renaming the terminal
`Review Stale (NoOp)` label out of this phase).

## Verification

Test-count discipline (repo-root `pytest -q` already includes
`operator-claude-plugin/tests/`; node file-form per `tests/n8n/*.test.mjs`):

| Suite | Pre-phase baseline | Post-Task-1 | Post-Task-2 | Post-Task-3 (final) |
|---|---|---|---|---|
| `.venv/bin/python -m pytest -q` | 1686 passed, 6 skipped | 1686 passed, 6 skipped | 1686 passed, 6 skipped | **1689 passed, 6 skipped** |
| `node --test tests/n8n/*.test.mjs` | 509 pass, 0 fail | 525 pass, 0 fail | 540 pass, 0 fail | **540 pass, 0 fail** |

Net: **+3 pytest, +31 node** (16 MODULE/FLOW from Task 1, +15 STAGING from Task 2, +3
currency/pin from Task 3), zero regressions once the two pre-existing tests were
corrected to the new intended behavior.

`test_hubspot_enums_generated_currency.py`'s hand-edit-breaks-it proof (acceptance
criterion, demonstrated live): replaced `"SPORTS",` with `"SPORTSBALL",` in the checked-in
generated file → `test_hubspot_enums_generated_js_currency` failed with a clean diff
naming the substitution; restored the file from a pre-edit copy → passed again. The file
in the repo is the regenerated (correct) version, not the hand-edited one.

Disarmed gate, every commit:

```
grep -c 'ALLOW_HUBSPOT_[A-Z_]* = "true"' n8n/*.json   ->  0 (all 8 files, every commit)
```

`operator-claude-plugin/tests/test_control_disarmed_artifacts.py` (standalone): 23
passed, 5 skipped.

No network call of any kind at any point. No `git stash`/`clean`/`reset --hard`. No
package installs.

## Known Stubs

None. Every code path returns a real value or a named refusal reason; no placeholder.

## Threat Flags

None beyond what the plan's own threat register (T-31-01 through T-31-05) already
covers — no new network endpoint, auth path, or schema change was introduced. The two
new modules (`hubspotEnums.generated.js`, `hubspotEnums.js`) are pure data + pure
functions with no I/O, consistent with T-31-05's disposition.

## What 31-02 / 31-03 need to know

1. **`outcome: "refused"` is now ALSO produced by an invalid enum candidate**, not only
   by the malformed/no-record/unknown-decision cases `reviewDecision.js` already
   returned it for. 31-02's `not_allowlisted` outcome is a distinct, additional value —
   do not collapse it into `refused`.
2. **`invalid` is a new key on `reviewApply`'s return shape**, always present
   (`[]` on every non-refusal path). Anything destructuring `reviewApply()`'s result and
   asserting an exact key set will need `invalid` added.
3. **`review_skip` is the new routing field on the scheduled-maintenance `Apply Review`
   node's output**, not `stale`. Anything reading that node's `stale` field downstream
   (there is currently nothing) should read `review_skip` instead, since it is a superset.
4. **Two-sided pin pattern for a NEW enum property, if one is ever added:** add it to
   `gen_hubspot_enums_js.ENUM_PROPERTIES`, add it to `config/field_policy.yaml`'s
   `companies` block with the matching HubSpot property, and
   `test_hubspot_enums_generated_currency.py`'s policy-pin test fails until the snapshot,
   the policy, and the generator list all agree.
5. **`hubspotEnums.generated.js`/`hubspotEnums.js` must ride any FUTURE `inline()` call
   that adds `mergeCompanies.js` or `reviewApply.js`** — there is no automated check for
   this yet (a possible future test in the shape of `test_taxonomy_conformance.py`'s
   TX-4).

## Self-Check: PASSED

- `scripts/gen_hubspot_enums_js.py` — FOUND
- `n8n/code/hubspotEnums.generated.js` — FOUND
- `n8n/code/hubspotEnums.js` — FOUND
- `tests/n8n/hubspotEnumValidation.test.mjs` — FOUND
- `tests/test_hubspot_enums_generated_currency.py` — FOUND
- `n8n/code/reviewApply.js` (invalid key) — FOUND
- `n8n/code/reviewDecision.js` (enum-refusal branch) — FOUND
- `n8n/code/mergeCompanies.js` (enum guard) — FOUND
- `scripts/build_cloud_workflows.py` (review_skip + 4 inline() sites) — FOUND
- commits `2f003d0`, `5c47d12`, `d3663d6`, `8b74509` — all FOUND in `git log`
- no file deletions in any commit
- `git status --porcelain n8n/` shows all 4 regenerated workflow JSON files as staged/committed
