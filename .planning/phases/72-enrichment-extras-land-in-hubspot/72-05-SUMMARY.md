---
phase: 72-enrichment-extras-land-in-hubspot
plan: 05
subsystem: enrichment-merge-engine
tags: [n8n, hubspot, merge-policy, provenance, overflow-slots, hubspot-schema]

requires:
  - phase: 72-enrichment-extras-land-in-hubspot
    provides: "plan 04's opts.now / opts.historyByField recency gate and system-correctable promotion, reused unchanged by the overflow-routing gate calls"
provides:
  - "lv_phone_2 (contacts), lv_mobilephone_2 (contacts) and lv_phone_2 (companies) — created LIVE in the portal (D-72-23), not merely declared"
  - "opts.rankedByField overflow routing in mergeContacts.js/mergeCompanies.js and route_overflow()/rank_candidates() in src/merge_policy.py"
  - "72-PORTAL-PROBE.json — the settled verdict on hs_additional_emails/hs_additional_domains/hs_country_region_code for plans 06 and 08"
affects: ["72-06 (reads the probe verdict for hs_additional_domains/hs_country_region_code)", "72-08 (property-creation step becomes a verify-exists step; disarmed workflow deploy still pending)"]

actuals:
  tokens: 587141
  tasks: 3
  commits: 6
  # measured as chars/4 over `git diff 7674971e..HEAD` (7674971e = last commit before
  # this plan's Task 1). The raw character count (2,348,563) is inflated by n8n's own
  # JSON shape: each Code node's jsCode is ONE JSON string with escaped \n, so a
  # single-character change inside a large embedded script (e.g. Merge Company,
  # ENRICH_MERGE) makes git diff print the WHOLE multi-KB line as removed+added even
  # though the line-count diff (713 insertions / 57 deletions, `git diff --stat`) was
  # modest. Reported as instructed (measured, not narrated, not rounded toward the
  # 125,000 estimate) — the estimate's own "low confidence" flag anticipated this.

tech-stack:
  added: []
  patterns:
    - "Closed overflow-slot map (_overflowSlot()/_overflow_slot()): a primary field maps to at most one named HubSpot property; absence means no overflow route exists in the code at all, not just in configuration."
    - "opts.rankedByField: caller passes a PRE-SORTED, PRE-SCORED candidate list (scoreCandidates().ranked); the merge engine only dedupes on normalizedValue and splits winner/overflow/tail — no second ranking mechanism anywhere."
    - "Live schema creation ahead of its originally planned step, gated by the same two-key sync-tool gate, with the undo manifest committed in its own dedicated commit so the schema-coverage guard can verify it independently of the code that references the new properties."

key-files:
  created:
    - .planning/phases/72-enrichment-extras-land-in-hubspot/72-PORTAL-PROBE.json
    - config/hubspot_migration/undo-manifest-481a5c99-ec62-4f59-940a-7387f5e2a7ad.json
    - tests/n8n/overflowSlots.test.mjs
  modified:
    - config/hubspot_properties.yaml
    - config/field_policy.yaml
    - operator-claude-plugin/config/field_policy.yaml
    - n8n/code/mergeContacts.js
    - n8n/code/mergeCompanies.js
    - src/merge_policy.py
    - scripts/build_cloud_workflows.py
    - n8n/wf_contact_ingest_cloud.json
    - n8n/wf_contact_ingest_local.json
    - n8n/wf_enrichment_cloud.json
    - n8n/wf_enrichment_local.json
    - n8n/wf_enrichment_local_live.json
    - n8n/wf_review_decision_cloud.json
    - n8n/wf_scheduled_maintenance_cloud.json
    - tests/test_merge_policy.py
    - tests/n8n/widenedKeyParity.test.mjs
    - tests/fixtures/companies_jscode_frozen.json
    - operator-claude-plugin/tests/test_preingest_merge.py

key-decisions:
  - "D-72-23 (operator ruling, execution-time): create the three overflow-slot properties LIVE in this plan, not plan 08, via scripts/sync_hubspot_properties.py's existing two-key gate — the schema-coverage guard (BUG-14) correctly refuses a cloud-workflow reference to a property no manifest or snapshot records as created, and this plan's declare-now/create-later split was novel enough that the guard was never written to admit it."
  - "D-72-10 outcome: hs_additional_emails is writable but typed `enumeration` (not `string`) — a v3 PATCH of an arbitrary email address to an enumeration is rejected regardless of readOnlyValue. The second-email write is NOT built; the second email lands in provenance only, via the same rankedByField/tailStart=1 path a slot-less field already takes."
  - "The Python oracle's route_overflow() is intentionally narrower than the JS wrapper: it only touches fields with a configured _overflow_slot (phone/mobilephone). The JS production wrapper explicitly opts email into opts.rankedByField for its own provenance-tail fallback; there is no Python caller with an equivalent need, so no Python parity gap exists — this is a scoped, not missing, mirror."
  - "TDD order corrected on resume: RED (tests/n8n/overflowSlots.test.mjs + tests/test_merge_policy.py fixtures) committed before GREEN (the parked engine/wrapper implementation), per the operator's explicit instruction that the prior session's GREEN-before-RED order be reversed."

requirements-completed: [D-72-10, D-72-11, D-72-12, D-72-13]

coverage:
  - id: D1
    description: "The three uncertain portal facts (hs_additional_emails, hs_additional_domains, hs_country_region_code) are settled by a live read-only probe and recorded in a committed artifact."
    requirement: "D-72-10"
    verification:
      - kind: unit
        ref: "tests/n8n/overflowSlots.test.mjs (escalation-config regression check) — indirect; the probe artifact itself is validated by the plan's own automated <verify> command"
        status: pass
      - kind: other
        ref: ".planning/phases/72-enrichment-extras-land-in-hubspot/72-PORTAL-PROBE.json exists, is git-tracked, holds all three (object_type,name) pairs plus probed_at/status"
        status: pass
    human_judgment: false
  - id: D2
    description: "The three overflow-slot properties (lv_phone_2 x2 contacts+companies, lv_mobilephone_2 contacts) are declared and CREATED LIVE in the portal, under the sync tool's two-key gate, with an undo manifest."
    requirement: "D-72-11"
    verification:
      - kind: other
        ref: "DRY_RUN=true sync_hubspot_properties.py reports zero pending creations post-creation; schema-coverage guard (tests/test_hubspot_schema_coverage.py) passes"
        status: pass
    human_judgment: false
  - id: D3
    description: "Winner takes the primary slot, runner-up (by the same trust-rank sort) takes the single _2 slot, a third+ candidate is provenance-only, an agreement never manufactures a phantom overflow, and the _2 slot obeys its own fill_blank_only policy."
    requirement: "D-72-12"
    verification:
      - kind: unit
        ref: "tests/n8n/overflowSlots.test.mjs (7 tests, all passing)"
        status: pass
      - kind: unit
        ref: "tests/test_merge_policy.py (6 route_overflow fixtures, all passing)"
        status: pass
    human_judgment: false
  - id: D4
    description: "Every landed slot (primary and _2) is stamped in the correct per-object provenance property (lv_contact_enrichment_provenance for contacts, lv_enrichment_provenance for companies) — no new per-field _source/_verified_at property is declared."
    requirement: "D-72-13"
    verification:
      - kind: unit
        ref: "tests/n8n/overflowSlots.test.mjs::mergeContacts overflow tests assert provenance[field].source per slot"
        status: pass
      - kind: other
        ref: "grep -c lv_contact_enrichment_provenance n8n/code/mergeContacts.js scripts/build_cloud_workflows.py (both non-zero)"
        status: pass
    human_judgment: false
  - id: D5
    description: "No judge call or material-conflict suppression fires for a phone/mobilephone/email disagreement (RO-2 unmodified)."
    verification:
      - kind: unit
        ref: "tests/n8n/overflowSlots.test.mjs::escalation config test; tests/test_merge_policy.py::test_route_overflow_no_material_conflict_groups_touched_ro2"
        status: pass
      - kind: unit
        ref: "tests/test_judge_spec.py::test_ro2_judge_gate_cannot_see_size_conflicts (unmodified, still green)"
        status: pass
    human_judgment: false

duration: 55min
completed: 2026-09-12
status: complete
---

# Phase 72 Plan 05: Overflow Slots for a Second Phone/Mobile Summary

**A second mobile or work phone the waterfall paid for now lands in `lv_mobilephone_2`/`lv_phone_2` (created live in the portal) instead of being silently discarded — routed by the same trust-rank sort that already picks the primary winner, with every landed slot stamped in the object's own provenance blob and zero new judge calls.**

## Performance

- **Duration:** 55 min (continuation session; excludes the prior session's Task 1/3 work)
- **Started:** 2026-09-12T11:25:00Z (approx, continuation resume)
- **Completed:** 2026-09-12T12:20:14Z
- **Tasks:** 3 (all complete: Task 1 read-only probe, Task 2 overflow routing, Task 3 slot declarations)
- **Files modified:** 18 modified + 3 created across the whole plan

## Accomplishments
- Settled the three uncertain live-portal facts (`hs_additional_emails` is a writable **enumeration**, not the assumed string — so D-72-10's second-email write is not built; `hs_additional_domains` is an enumeration; `hs_country_region_code` does not exist) in a committed, git-tracked probe artifact for plans 06 and 08 to read.
- Created `lv_phone_2` (contacts), `lv_mobilephone_2` (contacts) and `lv_phone_2` (companies) **live** in the HubSpot portal via the existing two-key-gated sync tool, per operator ruling D-72-23, with a committed undo manifest.
- Added a closed overflow-routing map (`_overflowSlot()`/`_overflow_slot()`) to all three merge engines (`mergeContacts.js`, `mergeCompanies.js`, `src/merge_policy.py`): the trust-rank runner-up for `mobilephone`/`phone` lands in its single `_2` slot through the same gate as any other field, a third+ candidate rides on the primary field's provenance entry only, and no `_3` slot can exist anywhere by construction.
- Regenerated all eight n8n workflow JSONs; confirmed idempotent regeneration (byte-identical on a second run) and byte-identical `config/field_policy.yaml` copies between the repo and the plugin.

## Task Commits

Task 1 and Task 3 were committed by the prior session before this continuation began:

1. **Task 1: Probe the three uncertain portal facts** - `ddf0af47` (feat)
2. **Task 3: Declare the three slot properties** - `a9c1a022` (feat)

This continuation session:

3. **D-72-23 operator ruling recorded** - `9fabfd55` (docs, prior session)
4. **Create the three overflow-slot properties live (D-72-23)** - `71102b0a` (feat)
5. **Task 2 RED: failing tests for overflow-slot routing** - `d5792daf` (test)
6. **Task 2 GREEN: winner/runner-up/tail routing implementation** - `fda76c95` (feat)

**Plan metadata:** (this commit)

## Files Created/Modified
- `.planning/phases/72-enrichment-extras-land-in-hubspot/72-PORTAL-PROBE.json` - the three-fact probe verdict
- `config/hubspot_migration/undo-manifest-481a5c99-ec62-4f59-940a-7387f5e2a7ad.json` - the D-72-23 live-creation undo manifest
- `config/hubspot_properties.yaml` - the three `_2` slot property declarations
- `config/field_policy.yaml` / `operator-claude-plugin/config/field_policy.yaml` - `lv_phone_2`/`lv_mobilephone_2` policy entries
- `n8n/code/mergeContacts.js` / `n8n/code/mergeCompanies.js` - `_overflowSlot()` + `opts.rankedByField` routing
- `src/merge_policy.py` - `rank_candidates()`/`route_overflow()`, wired into `build_merge_result`
- `scripts/build_cloud_workflows.py` - threads `scoreCandidates().ranked`, restricts `rankedByField` to phone/mobilephone/email, widens both search-property CSVs
- 6 `n8n/wf_*.json` files - regenerated, embedding the above
- `tests/n8n/overflowSlots.test.mjs` - new RED→GREEN test file (7 tests)
- `tests/test_merge_policy.py` - 6 new `route_overflow` fixtures
- `tests/n8n/widenedKeyParity.test.mjs` - exemption set grows by the two write-only overflow keys
- `tests/fixtures/companies_jscode_frozen.json` - re-baselined (explicit, reviewed act) for the Merge Company node's new jsCode
- `operator-claude-plugin/tests/test_preingest_merge.py` - SAFE-01 min_confidence pin extended

## Decisions Made
- **D-72-23 (operator ruling, blocking-human, resolved):** create the three overflow-slot properties live in this plan rather than deferring to plan 08, since the schema-coverage guard correctly refuses a workflow reference to an uncreated property and the declare-now/create-later split had no admitting mechanism. Executed via `scripts/sync_hubspot_properties.py`'s existing `DRY_RUN=false`+`ALLOW_HUBSPOT_PROPERTY_WRITES=true` gate, run from a scratchpad wrapper that loads `.env` with `python-dotenv` (the script itself does not load `.env`). Pre-check dry run confirmed exactly these three were pending (no other drift); all three POSTs returned 201; the script's own post-write re-GET confirmed existence; a follow-up dry run reports zero pending creations.
- **D-72-10 fallback taken:** `hs_additional_emails` is an enumeration, so the second-email write is not built. Recorded in provenance only.
- **Python oracle's `route_overflow()` scoped to slotted fields only** — the JS wrapper's email-provenance-tail behavior has no Python caller to mirror, so this is a deliberate scope boundary, not a missed parity requirement.
- **TDD order corrected on resume:** the prior session had written the implementation before any dedicated overflow test existed (GREEN-before-RED). This session wrote `tests/n8n/overflowSlots.test.mjs` and the `tests/test_merge_policy.py` fixtures first, confirmed RED (6 of 7 JS assertions failing; the Python module failing to collect on the not-yet-existing `route_overflow` import), committed RED, then applied/adjusted the parked implementation and confirmed GREEN before committing.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Re-baselined the frozen companies-jsCode fixture**
- **Found during:** Task 2 GREEN verification (`.venv/bin/python -m pytest tests/ operator-claude-plugin/tests/`)
- **Issue:** `tests/test_companies_factory_frozen.py`'s two byte-identity guards failed because the `Merge Company` node's jsCode legitimately changed (new `lv_phone_2` policy comment + overflow routing). The fixture's own docstring calls re-baselining "an explicit, reviewed act" for exactly this situation.
- **Fix:** Regenerated `tests/fixtures/companies_jscode_frozen.json` by calling `build_enrichment_cloud()`/`build_enrichment_local_live()` directly (same extraction logic the test itself uses) and writing the fresh jsCode back to the fixture.
- **Files modified:** `tests/fixtures/companies_jscode_frozen.json`
- **Verification:** `tests/test_companies_factory_frozen.py` (4/4 pass); diff against the prior fixture shows only the 3 expected jsCode line changes.
- **Committed in:** `fda76c95` (Task 2 GREEN commit)

**2. [Rule 1 - Bug] Extended the SAFE-01 min_confidence pin in `test_preingest_merge.py`**
- **Found during:** Task 2 GREEN verification
- **Issue:** `test_the_shipped_field_policy_copy_is_byte_identical_to_the_repo_source` asserts an exact `contacts:` key set with pinned `min_confidence` values; the new `lv_phone_2`/`lv_mobilephone_2` keys were correctly flagged as drift from that pin. The test's own comment invites exactly this: "update both this test and promotable_contact_props' expectations together."
- **Fix:** Added `lv_phone_2: 80` and `lv_mobilephone_2: 85` to the pinned dict, matching `config/field_policy.yaml`'s values exactly.
- **Files modified:** `operator-claude-plugin/tests/test_preingest_merge.py`
- **Verification:** `test_the_shipped_field_policy_copy_is_byte_identical_to_the_repo_source` and `test_promotable_contact_props_names_exactly_the_policys_promotable_contact_keys` both pass (the latter unaffected since `promote_to_canonical: false` on both new keys already excludes them from the promotable set).
- **Committed in:** `fda76c95` (Task 2 GREEN commit)

---

**Total deviations:** 2 auto-fixed (2 test-fixture updates, both explicitly invited by the affected tests' own comments)
**Impact on plan:** Both fixes are mechanical consequences of Task 2's legitimate, in-scope engine changes. No scope creep — no unrelated fixture or test was touched.

## Issues Encountered
- Task 3's acceptance criterion "the default dry run reports the three as pending creation" is now stale, superseded by D-72-23: after the live creation, the default dry run correctly reports **zero** pending creations (verified). This is the intended post-D-72-23 state, not a regression — CONTEXT.md's own D-72-23 entry anticipates it ("plan 08's create-properties step becomes a verify-exists step").
- `actuals.tokens` (587,141, measured as chars/4 over the full plan's `git diff`) is well above the plan's own 125,000-token estimate (flagged `confidence: low`). The gap is a measurement artifact, not scope creep: n8n stores each Code node's `jsCode` as one JSON string with escaped `\n`, so a single-character change inside a large embedded script makes `git diff` print the entire multi-KB line as removed+added. The line-level diff (`git diff --stat`: 713 insertions / 57 deletions across 23 files) reflects the actual size of the change.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Plan 06 can read `72-PORTAL-PROBE.json` for its `hs_additional_domains`/`hs_country_region_code` facts.
- Plan 08's property-creation step for these three slots is now a verify-exists step (undo manifest `config/hubspot_migration/undo-manifest-481a5c99-ec62-4f59-940a-7387f5e2a7ad.json` is the record); no n8n workflow deploy, bounce, or arm has occurred — that remains plan 08's job.
- No blockers.

## Self-Check: PASSED
- `.planning/phases/72-enrichment-extras-land-in-hubspot/72-PORTAL-PROBE.json` — FOUND
- `config/hubspot_migration/undo-manifest-481a5c99-ec62-4f59-940a-7387f5e2a7ad.json` — FOUND
- `tests/n8n/overflowSlots.test.mjs` — FOUND
- Commits `ddf0af47`, `a9c1a022`, `9fabfd55`, `71102b0a`, `d5792daf`, `fda76c95` — all present in `git log --oneline --all`
- `node --test tests/n8n/*.test.mjs` — 1146/1146 pass
- `.venv/bin/python -m pytest tests/ operator-claude-plugin/tests/` — 4947 passed, 154 skipped, 0 failed

---
*Phase: 72-enrichment-extras-land-in-hubspot*
*Completed: 2026-09-12*
