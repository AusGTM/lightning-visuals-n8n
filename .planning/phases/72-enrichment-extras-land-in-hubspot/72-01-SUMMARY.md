---
phase: 72-enrichment-extras-land-in-hubspot
plan: 01
subsystem: n8n-ingest
tags: [n8n, ingest, mergeContacts, columnMap, mobilephone, non-clobber-merge, tdd]

requires:
  - phase: 71-a-held-new-person-lands-in-hubspot-with-one-reply
    provides: F71-5's evidence (Busteed 352422766048 dropped mobilephone + lv_linkedin_url) that this plan's tracer proves fixed
provides:
  - "mobilephone as its own canonical ingest column, split off the phone alias group"
  - "ADAPT_SEARCH_RESULTS stamping a matched contact's real existingRecord onto the ingest row"
  - "MERGE_CONTACTS gating every candidate field against real existing values on a matched row (was always {})"
  - "per-field confidence override (D-72-22) so a provider-sourced candidate carries its provider's own confidence grade instead of the flat csv 80"
affects: [72-02, 72-03, 72-04, 72-08]

actuals:
  tokens: 34413
  tasks: 3
  commits: 3
plan_head_before: 3adaa13773f0ce2d7575a48c34e1f24d2469ed98

tech-stack:
  added: []
  patterns:
    - "existingRecord stamped by the search-results adapter, read by the merge wrapper — mirrors the enrichment lane's ENRICH_ADAPT_SEARCH/ENRICH_MERGE pair, now also true on the ingest lane"
    - "confidenceByField derived per-row from source_by_field at the merge call site, never a policy-level change — a request-level provenance map turned into a per-field confidence override"

key-files:
  created:
    - tests/n8n/ingestWidenedFieldsFlow.test.mjs
  modified:
    - config/column_mapping.yaml
    - operator-claude-plugin/config/column_mapping.yaml
    - n8n/code/columnMap.js
    - scripts/build_cloud_workflows.py
    - n8n/wf_contact_ingest_cloud.json
    - n8n/wf_contact_ingest_local.json
    - operator-claude-plugin/skills/contact-upload/extraction.md
    - operator-claude-plugin/scripts/suggestion_declines.py
    - operator-claude-plugin/tests/test_extraction_handoff.py
    - operator-claude-plugin/tests/test_preingest_merge.py
    - operator-claude-plugin/tests/test_preview_rendering.py
    - tests/n8n/parity.test.mjs

key-decisions:
  - "D-72-22 (operator ruling, raised mid-task as a blocking-human checkpoint): MERGE_CONTACTS derives confidenceByField[f]=85 for any field whose source_by_field[f] names a real provider (anything but csv/absent); csv-typed or unlisted fields keep the flat 80. No min_confidence moved (SAFE-01 intact)."
  - "existingRecord is taken ONLY from the value-matched candidate (BUG-22b match, never by index); zero hits or a batch-wide lookup_failed yields {} exactly as before — mirrors ENRICH_ADAPT_SEARCH's shape rather than inventing a second one."
  - "Task 3 produced no new workflow diff: mergeContacts.js's ENRICH_MERGE call site already passed row.existingRecord || {} before this plan, so only the two ingest-lane JSONs (wf_contact_ingest_cloud.json, wf_contact_ingest_local.json) changed — D-72-21's deploy set for plan 08 is exactly those two, not the full eight."

requirements-completed: [D-72-01, D-72-03]

coverage:
  - id: D1
    description: "D-72-03: 'mobile'/'cell'/'mobile phone'/'mobile number' now map to canonical mobilephone, not phone; phone remains the landline/office slot in both config/column_mapping.yaml and n8n/code/columnMap.js"
    requirement: D-72-03
    verification:
      - kind: unit
        ref: "tests/n8n/columnMapAliasParity.test.mjs"
        status: pass
      - kind: integration
        ref: "tests/n8n/ingestWidenedFieldsFlow.test.mjs#a CSV column headed 'mobile' maps to canonical key mobilephone; 'phone' still maps to phone"
        status: pass
    human_judgment: false
  - id: D2
    description: "D-72-01 tracer: a mobilephone value on a net_new ingest row reaches the HubSpot Create request body, proven by walking the committed wf_contact_ingest_cloud.json — the exact field F71-5 recorded as paid-for and dropped for Busteed 352422766048"
    requirement: D-72-01
    verification:
      - kind: integration
        ref: "tests/n8n/ingestWidenedFieldsFlow.test.mjs#D-72-01 tracer: mobilephone reaches HubSpot Create for a net_new row, is withheld from an update that already holds a different value, and fills a blank one"
        status: pass
    human_judgment: false
  - id: D3
    description: "existingRecord wiring (ADAPT_SEARCH_RESULTS stamps it, MERGE_CONTACTS reads row.existingRecord || {}): a matched row's non-blank fill_blank_only field is NOT overwritten by a differing candidate value"
    verification:
      - kind: integration
        ref: "tests/n8n/ingestWidenedFieldsFlow.test.mjs#D-72-01 tracer: mobilephone reaches HubSpot Create for a net_new row, is withheld from an update that already holds a different value, and fills a blank one"
        status: pass
      - kind: integration
        ref: "tests/n8n/ingestWidenedFieldsFlow.test.mjs#existingProps gate: phone/firstname/lastname/jobtitle/email all stay off an update body once HubSpot holds different non-blank values"
        status: pass
    human_judgment: false
  - id: D4
    description: "D-72-22: a provider-sourced candidate (source_by_field names a real provider) carries that provider's own confidence grade (85) instead of the flat csv 80, so it can clear mobilephone/lv_linkedin_url's fill_blank_only@85 threshold; a csv-typed or unlisted field is unaffected"
    verification:
      - kind: integration
        ref: "tests/n8n/ingestWidenedFieldsFlow.test.mjs#D-72-22 negative: without source_by_field naming mobilephone, a CSV mobile stays at the flat csv confidence and never reaches HubSpot Create"
        status: pass
    human_judgment: false
  - id: D5
    description: "Every regenerated n8n/wf_*.json is still v1, disarmed, and idempotent; D-72-21's changed-body set for plan 08 is exactly the two ingest-lane files"
    verification:
      - kind: unit
        ref: "python -c executionOrder v1 check over glob n8n/wf_*.json"
        status: pass
      - kind: e2e
        ref: "node --test tests/n8n/*.test.mjs (1105/1105)"
        status: pass
    human_judgment: false
  - id: D6
    description: "Two operator-visible policy consequences of the existingProps wiring (firstname/lastname/company no longer overwrite a non-blank existing value; a differing jobtitle now routes to review pre-TTL) — genuine judgment calls, not proven by a test"
    human_judgment: true
    rationale: "These are deliberate, correct consequences of D-72-02 (field_policy.yaml is the single source) surfacing for the first time on a lane that never consulted it before. Whether the operator wants a different default for firstname/lastname/company, or wants jobtitle's TTL (plan 04) prioritized, is a product decision, not something a test can adjudicate."

duration: 55min
completed: 2026-09-12
status: complete
---

# Phase 72 Plan 01: Enrichment Extras Land in HubSpot — Tracer Summary

**A CSV-carried mobile number now reaches a newly-created HubSpot contact and is withheld from an update whose contact already holds a different one — the exact field/record class (Busteed 352422766048) F71-5 recorded as paid-for and dropped.**

## Performance

- **Duration:** 55 min
- **Started:** 2026-09-12T08:05:00Z (approx, continuation after checkpoint resolution)
- **Completed:** 2026-09-12T09:00:00Z (approx)
- **Tasks:** 3
- **Files modified:** 12 (2 created — 1 test file; the JSON regen touched 2 files)

## Accomplishments

- Split `mobile`/`cell`/`mobile phone`/`mobile number` off the `phone` alias group onto a new `mobilephone` canonical target, in `config/column_mapping.yaml` (+ the byte-identical shipped copy) and `n8n/code/columnMap.js`'s embedded `ALIASES`.
- Wired the ingest lane's `ADAPT_SEARCH_RESULTS` to stamp `existingRecord` (the matched contact's real current HubSpot properties, taken only from the value-matched candidate) onto every row — the unstated prerequisite the plan called out: without this, `MERGE_CONTACTS` always merged against `{}` and every update would have become an unconditional clobber once the candidate set widened.
- Rewired `MERGE_CONTACTS` to call `mergeContacts(row.existingRecord || {}, candidate, ...)` instead of a literal `{}`, and added `mobilephone` to its candidate loop.
- Resolved a blocking-human checkpoint (D-72-22, operator ruling) discovered by this task's own tracer: the flat `{ source: "csv", confidence: 80 }` call meant a CSV-carried `mobilephone`/`lv_linkedin_url` (both `fill_blank_only` @ 85) could never promote, even into a blank field. `MERGE_CONTACTS` now derives `confidenceByField[f] = 85` for any field whose `row.source_by_field[f]` names a real provider; a field resolving to `csv` or absent from the map keeps the flat 80.
- New `tests/n8n/ingestWidenedFieldsFlow.test.mjs` walks the committed `n8n/wf_contact_ingest_cloud.json` for all three tracer directions (create, protect, fill), the D-72-22 negative case, header aliasing, and the existingProps gate for the seven pre-existing candidate keys — 4 test blocks, all green.
- Regenerated every `n8n/wf_*.json`; confirmed idempotent, `settings.executionOrder: "v1"` on all eight, nothing armed. Only `wf_contact_ingest_cloud.json` (69→69 nodes) and `wf_contact_ingest_local.json` (13→13 nodes) actually changed bytes versus the plan's starting commit — `mergeContacts.js`'s `ENRICH_MERGE` call site already passed `row.existingRecord || {}` before this plan, so the enrichment/review/scheduled-maintenance/backend-status workflows have nothing to regenerate here.

## Task Commits

TDD plan (Task 1 followed RED-GREEN discipline; Tasks 2-3 are `type="auto"`):

1. **Task 1 RED: failing tracer for mobilephone create/protect/fill** — `d3e34c1f` (test)
2. **Task 1 GREEN: mobilephone lands without clobbering an existing value** — `202adb3f` (feat)
3. **Task 2: pin the existingProps gate for the seven pre-existing candidate keys** — `e9d489e5` (test)

Task 3 produced no commit: a clean-tree regeneration of every `n8n/wf_*.json` produced zero further diff (the two ingest-lane files were already regenerated and committed in Tasks 1-2; the other six are untouched by this plan — see Decisions and the D-72-21 table below).

**Plan metadata:** this commit (SUMMARY + STATE + ROADMAP).

### RED evidence (Task 1)

`node --test --test-reporter=tap tests/n8n/ingestWidenedFieldsFlow.test.mjs` exited 1 against the pre-fix lane. Target test `"D-72-01 tracer: mobilephone reaches HubSpot Create for a net_new row, is withheld from an update that already holds a different value, and fills a blank one"` failed on a real assertion (`TypeError: Cannot read properties of undefined (reading 'decision')` — `Merge Contacts` never gated a matched row against real existing values, and the D-72-22 confidence override did not exist yet). Verdict: `RED_EVIDENCE_OK` (via `gsd_run check tdd-red-evidence`).

## Files Created/Modified

- `tests/n8n/ingestWidenedFieldsFlow.test.mjs` — new. Four tests: header aliasing, the D-72-01 create/protect/fill tracer, the D-72-22 confidence-override negative case, and the existingProps gate for phone/firstname/lastname/jobtitle/email.
- `config/column_mapping.yaml`, `operator-claude-plugin/config/column_mapping.yaml` — `mobile: phone` removed; new `mobilephone` alias group added (byte-identical, confirmed by `diff -q`).
- `n8n/code/columnMap.js` — embedded `ALIASES` mirrors the YAML edit (pinned by `columnMapAliasParity.test.mjs`).
- `scripts/build_cloud_workflows.py` — `ADAPT_SEARCH_RESULTS` stamps `existingRecord`; `MERGE_CONTACTS` reads it, adds `mobilephone` to its candidate loop, and derives `confidenceByField` per D-72-22.
- `n8n/wf_contact_ingest_cloud.json`, `n8n/wf_contact_ingest_local.json` — regenerated (node counts unchanged: 69, 13).
- `operator-claude-plugin/skills/contact-upload/extraction.md` — canonical-vocabulary list (an executable-documentation block a test parses) now names `mobilephone`; `[Rule 3]` fix, see Deviations.
- `operator-claude-plugin/scripts/suggestion_declines.py` — `ROW_FIELD_ALLOWLIST` now includes `mobilephone`, restoring its own documented invariant (`== extraction.canonical_props()`); `[Rule 1]` fix.
- `operator-claude-plugin/tests/test_extraction_handoff.py` — `CANONICAL_PROPS` literal now includes `mobilephone` (Task 2's designated job).
- `operator-claude-plugin/tests/test_preingest_merge.py`, `operator-claude-plugin/tests/test_preview_rendering.py`, `tests/n8n/parity.test.mjs` — three pre-existing tests hardcoded the old `mobile`→`phone` mapping or the old three-key shared-props intersection; updated to the correct post-flip expectation. `[Rule 1]` fixes, see Deviations.

## Decisions Made

- **D-72-22 implementation** (operator ruling, recorded in `72-CONTEXT.md`): `confidenceByField[f] = 85` for any field whose `source_by_field[f]` names a real provider; csv-typed/absent fields keep the flat 80. No `min_confidence` moved.
- **existingRecord match rule**: taken only from the value-matched candidate (the existing BUG-22b email-equality match), never by index; a zero-hit or batch-wide `lookup_failed` row gets `{}` — mirrors `ENRICH_ADAPT_SEARCH`'s shape rather than inventing a second one, per the plan's `key_links`.
- **D-72-21's actual deploy set for plan 08 is narrower than the plan predicted**: only `wf_contact_ingest_cloud.json` changed among the cloud workflows in this plan (see table below) — `mergeContacts.js`'s `ENRICH_MERGE` call site already passed `row.existingRecord || {}` before Phase 72 began, so this plan's D-72-22 confidence override (which lives only in the ingest wrapper `MERGE_CONTACTS`) never touches the enrichment/review/scheduled-maintenance/backend-status bodies.

## D-72-21 changed-body table (Task 3)

Measured against this plan's own starting commit (`3adaa137`, the ledger base):

| File | Changed? | Nodes before | Nodes after |
|---|---|---|---|
| `n8n/wf_contact_ingest_cloud.json` | **YES** | 69 | 69 |
| `n8n/wf_contact_ingest_local.json` | **YES** | 13 | 13 |
| `n8n/wf_enrichment_cloud.json` | no | 287 | 287 |
| `n8n/wf_enrichment_local.json` | no | 10 | 10 |
| `n8n/wf_enrichment_local_live.json` | no | 82 | 82 |
| `n8n/wf_review_decision_cloud.json` | no | 55 | 55 |
| `n8n/wf_scheduled_maintenance_cloud.json` | no | 43 | 43 |
| `n8n/wf_backend_status_cloud.json` | no | 30 | 30 |

Every regenerated body still reads `settings.executionOrder: "v1"`; no body carries an armed write-safety literal (`ALLOW_HUBSPOT_RECORD_WRITES = "true"` / `ALLOW_HUBSPOT_CREATE = "true"` both grep to 0 across every `n8n/wf_*.json`). A second consecutive `.venv/bin/python scripts/build_cloud_workflows.py` produces no further diff.

**Note for plan 08 (D-72-21):** as later plans in this phase (02-07) land more `mergeContacts.js`/`mergeCompanies.js` changes, this table will grow — record each plan's own delta the same way rather than assuming the full eight-file set changes together.

## Operator Confirm Items (from Task 2, per the plan's explicit instruction — not resolved here)

**Operator confirm:** a CSV correcting a misspelled `firstname` (or `lastname`, or `company`) on an existing contact no longer applies on the ingest lane. Those three fields have no `config/field_policy.yaml` entry and now take the engines' `fill_blank_only`/80 default for the first time, because the lane finally gates a matched row against real existing values (it always merged against `{}` before this plan).

**Operator confirm:** a differing `jobtitle` on an ingest UPDATE row now routes to `needs_review` instead of applying, until plan 04's TTL branch lands and gives a genuinely stale title a promote path. F71-5's "provider jobtitle replaced the CSV jobtitle" was the *plugin's* `merge_enriched` rule (`refreshable_keys`), not this lane — the lane only applied it before because it merged every row against an empty existing-props object.

Neither policy default was changed to work around either consequence — both are the `stale_refreshable`/`fill_blank_only` policy behaving as written (D-72-02), now reachable for the first time.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 4 / operator ruling D-72-22] MERGE_CONTACTS needed provider-grade per-field confidence**
- **Found during:** Task 1 (the tracer itself — a disarmed dry run showed `mobilephone` always resolving `needs_review`, even into a blank net_new field)
- **Issue:** `MERGE_CONTACTS` called `mergeContacts({}, candidate, undefined, { source: "csv", confidence: 80, sourceByField })` — flat 80 — while `mobilephone` and `lv_linkedin_url` are `fill_blank_only` @ 85 in both `n8n/code/mergeContacts.js`'s `DEFAULT_CONTACT_POLICY` and `config/field_policy.yaml`. `_gate()` checks confidence before the blank-vs-non-blank branch, so a CSV `mobilephone` could never reach the `HubSpot Create` body regardless of policy class.
- **Fix:** raised as a `checkpoint:human-verify`/`blocking-human` decision to the orchestrator mid-task (this plan's own instructions record it as "raised as a blocking-human decision"). Operator ruled Option E ("provider-grade per-field confidence", D-72-22, recorded in `72-CONTEXT.md`): `MERGE_CONTACTS` derives `confidenceByField[f] = 85` for any field whose `row.source_by_field[f]` names a real provider; a field resolving to `csv` or absent from the map keeps the flat 80.
- **Files modified:** `scripts/build_cloud_workflows.py` (`MERGE_CONTACTS`), regenerated `n8n/wf_contact_ingest_cloud.json` / `n8n/wf_contact_ingest_local.json`.
- **Verification:** `tests/n8n/ingestWidenedFieldsFlow.test.mjs`'s main tracer (positive: promote at 85) and negative (needs_review at flat 80) tests both pass.
- **Committed in:** `202adb3f` (Task 1 GREEN commit).

### Rule 1/3 fallout from widening the alias table

**2. [Rule 3 - Blocking] `extraction.md`'s canonical-vocabulary block (executable documentation a test parses) did not name `mobilephone`**
- **Found during:** Task 1, running the full test suite after the alias flip.
- **Issue:** `test_every_canonical_prop_is_named_in_extraction_md` (an unplanned, pre-existing test) failed: the new canonical prop `mobilephone` was not named anywhere in `extraction.md`'s prose, and this test is a straight substring check over every value `extraction.canonical_props()` returns.
- **Fix:** added `mobilephone` to `extraction.md`'s "Canonical props — the entire vocabulary" list and its accompanying prose ("These nine are all there is").
- **Files modified:** `operator-claude-plugin/skills/contact-upload/extraction.md`.
- **Verification:** `operator-claude-plugin/tests/test_extraction_contract.py` full suite passes.
- **Committed in:** `202adb3f`.

**3. [Rule 1 - Bug] Three pre-existing tests and one hardcoded literal still expected the old `mobile`→`phone` mapping**
- **Found during:** Task 1, running the full JS + Python suites after the alias flip.
- **Issue:** `operator-claude-plugin/tests/test_preview_rendering.py::test_build_preview_reports_dropped_headers_and_unmapped_canonical_props` and `tests/n8n/parity.test.mjs`'s columnMap test both hardcoded `"Mobile" -> "phone"`; `operator-claude-plugin/tests/test_preingest_merge.py::test_the_allowlist_is_a_union_and_a_shared_key_behaves_as_before` hardcoded the shared-key set as exactly `{email, phone, jobtitle}`; `operator-claude-plugin/scripts/suggestion_declines.py`'s `ROW_FIELD_ALLOWLIST` is a hardcoded tuple whose own comment says it equals `extraction.canonical_props()` exactly, pinned by `test_row_field_allowlist_matches_canonical_props_and_excludes_row_id`.
- **Fix:** updated all four to the correct post-flip expectation — `"Mobile" -> "mobilephone"` in the two rendering/parity tests, the shared-key set now includes `mobilephone` as a fourth member (it is genuinely a shared key: both a `canonical_props()` member and a `field_policy.yaml` promotable-contact key), and `ROW_FIELD_ALLOWLIST` now includes `"mobilephone"`.
- **Files modified:** `operator-claude-plugin/tests/test_preview_rendering.py`, `tests/n8n/parity.test.mjs`, `operator-claude-plugin/tests/test_preingest_merge.py`, `operator-claude-plugin/scripts/suggestion_declines.py`.
- **Verification:** full `node --test tests/n8n/*.test.mjs` (1105/1105) and `.venv/bin/python -m pytest -q operator-claude-plugin/tests/ tests/` (4899 passed, 154 skipped) both green.
- **Committed in:** `202adb3f`.

---

**Total deviations:** 1 operator-ruling deviation (D-72-22, Rule 4) + 3 auto-fixed fallout groups (Rule 1/3), covering 7 files.
**Impact on plan:** the D-72-22 ruling was load-bearing for the plan's own must-have (a `mobilephone` reaching `HubSpot Create`) — without it the tracer's positive direction was unachievable by construction. The Rule 1/3 fallout is entirely test-fixture and documentation drift directly caused by widening the alias table; no production behavior beyond the alias flip itself was touched by those fixes.

## Issues Encountered

- **`git.base-branch --is-protected master` returns `true`** for this repo, and this plan's commits landed directly on `master`. This is placement, not drift: the orchestrator's `<sequential_execution>` block named `master` explicitly and instructed normal commits with hooks; `workflow.use_worktrees` is `false`; and the entire phase-72 planning trail (`3adaa137`, `1a328347`, `3666ae77`, …) already lives on `master` with no `agent-*`/phase branch anywhere in `git branch -a`. `git.allow_default_branch_commits` is absent from `.planning/config.json` — the operator may want to set it explicitly to silence this note in future sequential-mode runs. Not treated as a blocker; no self-recovery attempted.
- No pre-commit hook is installed in this repo (`.git/hooks/pre-commit`, `.pre-commit-config.yaml` both absent) — RED/GREEN commits ran with no hook interference.

## Known Stubs

None — every field this plan wires (mobilephone, existingRecord, confidenceByField) is exercised end-to-end by the new test file, and the regenerated workflow JSON is the same artifact the real n8n Cloud instance would run.

## User Setup Required

None — no external service configuration required. Nothing in this plan deploys, bounces, or arms anything (per the plan's own prohibitions; confirmed by the write-safety-literal grep in the D-72-21 table above).

## Next Phase Readiness

- Plan 02 can widen the ingest candidate set further (the `mergeContacts.js` engine already supports `confidenceByField`/`sourceByField`; plan 03 will populate `source_by_field` truthfully on the enrich-before-ingest path, making D-72-22's positive branch reachable in production, not just in this plan's test fixtures).
- The two "Operator confirm:" items above are unresolved product questions, not blockers — they should reach the operator before plan 08's live gate (D-72-17), which is the phase's first armed send and would otherwise surface them as a surprise on a real record.
- `docs/OPERATOR-AUTONOMOUS-BATCH-UAT.md`'s D-72-17 gate spec (not yet written — a later plan's job per the phase's `## Artifacts this phase produces` list) should read back `mobilephone` on the armed create, now that this plan proves the path.

## Self-Check: PASSED

- `[ -f tests/n8n/ingestWidenedFieldsFlow.test.mjs ]` → FOUND
- `git log --oneline --all | grep -q d3e34c1f` → FOUND
- `git log --oneline --all | grep -q 202adb3f` → FOUND
- `git log --oneline --all | grep -q e9d489e5` → FOUND
- All plan-level `<verification>` commands re-run and passing (see Accomplishments / D-72-21 table above).

---
*Phase: 72-enrichment-extras-land-in-hubspot*
*Completed: 2026-09-12*
