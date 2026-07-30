---
phase: 15-hubspot-property-migration
verified: 2026-07-22T00:00:00Z
status: passed
score: 6/6 ROADMAP criteria verified; 13/13 checklist checks verified
behavior_unverified: 0
overrides_applied: 0
---

# Phase 15: HubSpot Property Migration Verification Report

**Phase Goal:** The metadata properties the pipeline needs exist, created safely — this
phase's primary deliverable is SAFETY AND REVERSIBILITY (tooling + provenance model +
ICP write-path retirement), not a live schema migration. Live property creation is an
explicit, disclosed operator runbook step, not something this phase's autonomous
execution performs.
**Verified:** 2026-07-22
**Status:** PASSED
**Re-verification:** No — initial verification.

---

## PORTAL UNTOUCHED — the safety-critical finding

**Verdict: CONFIRMED. No live mutation is reachable by any offline/test/build path in
this repository state. The live HubSpot portal (22617666) was not touched by this
phase's execution.**

Evidence, in order of strength:

1. **All four live scripts exit 0 with zero network calls when run with no credentials**
   (ran myself, this session, with `HUBSPOT_PRIVATE_APP_TOKEN`/`HUBSPOT_PORTAL_ID`
   explicitly unset):
   ```
   scripts/snapshot_hubspot_schema.py   -> "skipped (no credentials)" / exit 0
   scripts/sync_hubspot_properties.py   -> "skipped (no credentials)" / exit 0
   scripts/rollback_property_migration.py -> "skipped (no credentials)" / exit 0
   scripts/rollback_canary_proof.py     -> "skipped (no credentials)" / exit 0
   ```

2. **Every script has a portal-ID guard BEFORE any call** — `_portal_ok()` checked
   immediately after the credentials check, refusing with no API call on a mismatch
   (`EXPECTED_PORTAL_ID = "22617666"`, read from `HUBSPOT_EXPECTED_PORTAL_ID` env or
   defaulted, never a token).

3. **Read all four scripts line-by-line; every mutating call is gated:**
   - `snapshot_hubspot_schema.py`: only `requests.get` in the default path (read-only,
     writes files to disk verbatim). The one `requests.patch` (in `_run_probe`) is
     reachable only via `--probe` AND `DRY_RUN=false` AND a non-empty
     `TEST_COMPANY_IDS` — three conditions, none satisfied by default.
   - `sync_hubspot_properties.py`: `_writes_allowed()` requires BOTH `DRY_RUN=false`
     AND `ALLOW_HUBSPOT_PROPERTY_WRITES=true` before any `requests.post` (property/group
     create) fires; the diff/report path is GET-only.
   - `rollback_property_migration.py`: refuses without BOTH an undo manifest AND a
     baseline snapshot present on disk; `--live` requires a typed `"yes"` confirmation
     (or `--confirm yes`); every `requests.delete` is inside the `--live` branch only,
     and each archive call is preceded by a live `hubspotDefined` re-check that refuses
     even under `--live`.
   - `rollback_canary_proof.py`: `_writes_allowed()` — same two-key gate as the sync
     script — required before its one `POST`/`DELETE` pair (a throwaway
     `lv_rollback_canary_<UTC>` property).

4. **Grepped every `requests.post/patch/delete` call site** across the four scripts —
   every one sits behind the gates described above; none is reachable from the default
   invocation.

5. **No test imports these scripts in a way that could execute a live call.** Every
   offline test file (`test_snapshot_hubspot_schema.py`, `test_sync_hubspot_properties.py`,
   `test_rollback_property_migration.py`) installs a `hermetic` fixture that monkeypatches
   `requests.get/post/patch/delete` to a `raise_http()` sentinel raising
   `AssertionError("a live HubSpot request leaked past a guard...")`. All these tests pass
   (verified this session: `pytest -q` → 199 passed, 0 failed), meaning the sentinel never
   fired — no live call leaked through any guard during the whole offline suite.

6. **No baseline snapshot files and no undo-manifest files exist on disk**
   (`.planning/phases/15-hubspot-property-migration/baseline/` does not exist; no
   `undo-manifest-*.json` anywhere in the repo) — physical confirmation that the operator
   runbook's live steps have genuinely never run. `git status --short` shows nothing
   pending besides a stray `.DS_Store`.

7. **The operator runbook is documented in 15-01-SUMMARY.md** as the human's next action
   (steps 1–6, in the correct order — baseline BEFORE create), never executed by the
   agent. The SUMMARY explicitly states: "Nothing below ran during this execution — every
   live script's no-credentials skip path is what actually ran."

**One disclosed, out-of-scope, pre-existing gap (not a Phase-15 regression, flagged for
awareness):** `src/ingest.py`'s `_CONTACT_PROPS`/`_SEARCH_PROPS` (a Phase-8 CSV-ingest
CLI harness, `main.py --ingest`) still reference bare `linkedin_url`/`persona_group` —
these were not renamed to `lv_linkedin_url`/`lv_persona_group` (SUMMARY Deviation 7,
honestly disclosed, out of this plan's declared `files_modified`). This path is gated
by the pre-existing single `DRY_RUN` gate (not this phase's two-key gate) and requires
an explicit `--ingest <file>` CLI invocation with real credentials to reach the network
at all — it is inert today and was not touched by anything in this phase's default or
test execution. Recorded as a WARNING for a later phase, not a blocker to Phase 15's own
goal (which is schema-migration tooling safety, not this pre-existing ingest harness).

---

## Goal Achievement

### Observable Truths / Checklist (13 checks)

| # | Check | Status | Evidence |
|---|-------|--------|----------|
| 1 | Test suites green | ✓ VERIFIED | `pytest -q` → **199 passed**, 0 failed. `node --test tests/n8n/*.test.mjs` → **77 passed**, 0 failed. (Ran with the glob form, never bare `node --test tests/n8n/`.) |
| 2 | Portal untouched (safety-critical) | ✓ VERIFIED | See dedicated section above. All 4 scripts: no-creds skip + portal guard + dry-run default + two-key (or --live+typed-confirm) gate before any POST/PATCH/DELETE. No live mutation reachable offline. |
| 3 | Provenance blob byte-identical parity | ✓ VERIFIED | `node --test tests/n8n/parity.test.mjs` → 17/17 green, incl. non-ASCII fixture row ("Ngā Puna Wai..."). **Personally re-fired the ensure_ascii break**: removed `ensure_ascii=False` from `src/merge_policy.py:60`, re-ran the parity test — it went genuinely red naming the exact non-ASCII case (`Ngā` vs `Ngā` escape mismatch, both the byte-parity test and DELIBERATE-BREAK 1). Restored via file copy from a pre-edit backup; re-ran green (17/17 node, 10/10 `pytest tests/test_merge_policy.py`), confirmed `git diff --stat` on the file was empty after restore. Python: `json.dumps(entries, sort_keys=True, separators=(",", ":"), ensure_ascii=False)` (src/merge_policy.py:60). JS: recursive `stableStringify()` in both `mergeCompanies.js` and `mergeContacts.js`. |
| 4 | No flat metadata/staging properties emitted | ✓ VERIFIED | Grepped `mergeCompanies.js`, `mergeContacts.js`, `merge_policy.py`, and all built `n8n/*.json` for `_source"`/`_confidence"`/`_validation_status"` property emission and `lv_waterfall_`/`lv_claude_web_`/`zoominfo_` staging emission — zero matches (only unrelated `min_confidence` policy-config keys and explanatory comments remain). Replaced by `lv_enrichment_provenance`/`lv_contact_enrichment_provenance` + 4 cache keys, confirmed in the manifest. |
| 5 | enrichmentGate.js reads cache-key property, not blob | ✓ VERIFIED | `n8n/code/enrichmentGate.js:85`: `const verifiedAt = existingRecord[_cacheKeyName(field)];` — `_cacheKeyName()` composes `lv_<field>_verified_at`, never touches any provenance blob. |
| 6 | ICP write-path retirement | ✓ VERIFIED | `grep -n "lv_icp_fit_score\|lv_icp_tier"` in `src/merge_policy.py`, `main.py`, `n8n/code/mergeCompanies.js`, `config/field_policy.yaml` → only explanatory comments remain, no live write sites. `git diff 6c65f79~1..HEAD -- src/merge_policy.py` shows the `canonical_patch.update({"lv_icp_fit_score": ...})` block genuinely deleted. All 3 previously-inverted assertions now assert absence: `tests/test_merge_policy.py:206-207`, `tests/test_main.py:61-62,87` all read `not in`. |
| 7 | Manifest = 33 | ✓ VERIFIED | Parsed `config/hubspot_properties.yaml` myself: companies = 19 properties (7 inputs + 1 blob + 2 cache + 9 review) / 1 group; contacts = 14 properties (2 renames + 1 blob + 2 cache + 9 review) / 1 group. Total 33 properties + 2 groups. The 5 existing `lv_*` company properties (`lv_org_type`, `lv_produces_content`, `lv_anti_icp_flag`, `lv_icp_fit_score`, `lv_icp_tier`) do NOT appear in the manifest — correctly excluded. `tests/test_hubspot_properties_config.py` asserts these exact counts (19/14/1/1) and passes. Sync script's `compute_property_diff()` derives create-list as `desired − actual`, so it is create-if-missing by construction. |
| 8 | PN-1 contact rename | ✓ VERIFIED | `linkedin_url`→`lv_linkedin_url`, `persona_group`→`lv_persona_group` renamed everywhere they round-trip as a HubSpot property: `config/field_policy.yaml`, `config/provider_priority.yaml`, `n8n/code/mergeContacts.js` DEFAULT_CONTACT_POLICY, `scripts/build_cloud_workflows.py` merge-candidate keys (`candidate.lv_linkedin_url = row.linkedin_url`). The raw upload/read-side fields (`row.linkedin_url`, `winners.linkedin_url`, `id.linkedin_url` feeding the Lusha `linkedinUrl` request-shape field) correctly remain unrenamed — confirmed by direct read of `build_cloud_workflows.py` lines 674, 1151. **One disclosed exception**, flagged as a WARNING, not this phase's regression: `src/ingest.py` (a pre-existing Phase-8 CSV harness, out of this plan's file scope) still uses bare `linkedin_url`/`persona_group` internally — see PORTAL UNTOUCHED section. |
| 9 | Rollback + canary real | ✓ VERIFIED | `rollback_property_migration.py` refuses without both manifest+baseline (read the code — hard `return 1` on missing either); archives ONLY manifest entries (`reverse_archive_order()` only ever iterates `manifest`, never a live schema); reverse order confirmed (properties before groups, each list reversed). `rollback_canary_proof.py` creates→archives→asserts on a throwaway `lv_rollback_canary_<UTC>` name via `sync._create_property_live`/`rollback._archive_property_live`/`rollback._get_property_live`. Offline-testable except the one live canary round-trip (documented, not run here — no credentials). Deliberate-break (`hubspotDefined` fixture) test (`test_hubspot_defined_property_in_manifest_is_hard_refused_even_under_live`) passed in the full suite run. |
| 10 | Rebuild determinism | ✓ VERIFIED | Ran `python scripts/build_cloud_workflows.py` twice myself; `git diff --exit-code -- n8n/` was clean both times (byte-no-op, and the committed tree already matched a fresh build). `test_top_level_is_exactly_the_deployable_set` passed in the full `test_architecture_guard.py` run (32/32 green). Only enrichment/contact-ingest wf JSONs are touched by the build script (confirmed by the plan's declared `files_modified` list and the diff against pre-phase commit `6c65f79~1`). |
| 11 | AR guards + new PN architecture guard (14 cases) green | ✓ VERIFIED | `pytest tests/test_architecture_guard.py -v` → 32/32 green. Counted the PN-specific cases myself: `test_pn1_contact_policy_configs_use_lv_prefixed_keys` (1) + `test_pn1_merge_contacts_default_policy_has_no_bare_keys` (1) + `test_pn1_build_script_never_writes_a_bare_linkedin_or_persona_property_key` (1) + `test_pn4_build_script_never_requests_a_bare_contact_cache_key` (1) + `test_pn4_no_bare_contact_cache_key_survives_in_built_workflows` (5 parametrized) + `test_no_flat_per_field_metadata_template_survives_in_built_workflows` (5 parametrized) = exactly **14**. All green. |
| 12 | Operator runbook present + correct | ✓ VERIFIED | Read `15-01-SUMMARY.md`'s "OPERATOR RUNBOOK" section: 6 numbered live steps (baseline snapshot → probe → dry-run diff → live create → confirm → canary proof), explicitly marked "Nothing below ran during this execution... This is the exact sequence the operator runs next, with real credentials." Order is correct (snapshot strictly before create, step 1 vs step 4). The two-key gate (`DRY_RUN=false` AND `ALLOW_HUBSPOT_PROPERTY_WRITES=true`) is spelled out verbatim at step 4 and matches the code (`_writes_allowed()`). A rollback subsection is also present with the correct dry-run-first / `--live` sequence. |
| 13 | Anti-patterns: no TODO/FIXME/placeholder | ✓ VERIFIED | Grepped all 23 phase-touched source/test files for `TBD\|FIXME\|XXX\|TODO\|PLACEHOLDER\|placeholder\|coming soon\|not yet implemented` — the only 2 hits are false positives (`\uXXXX` referring to the JSON Unicode-escape notation in a docstring/comment, not a debt marker). Clean. |

### ROADMAP Success Criteria (6, cross-checked against §0.6/§4/§0.7 of the spec)

| # | Criterion | Status | Evidence |
|---|-----------|--------|----------|
| C1 | Missing properties created; sync dry-runs by default, emits undo manifest | ✓ VERIFIED (tooling) | `config/hubspot_properties.yaml` (33/2) + `sync_hubspot_properties.py` built, offline-proven (idempotency, undo-manifest-only-on-201, dry-run default). Live creation is the disclosed operator step — ROADMAP itself marks this `[x]` with the same caveat. |
| C2 | RT-5 caching unblocked (4 cache-key datetimes) | ✓ VERIFIED | `lv_org_type_verified_at`, `lv_produces_content_verified_at` (companies), `lv_jobtitle_verified_at`, `lv_mobilephone_verified_at` (contacts) all present in the manifest and read by `enrichmentGate.js`'s `_cacheKeyName()`. |
| C3 | `lv_org_type` text→enumeration NOT performed | ✓ VERIFIED | Grepped the whole diff set + manifest for any type-change of `lv_org_type` — none found; manifest explicitly excludes `lv_org_type` from the create-list (already exists, untouched). |
| C4 | ICP write paths retired | ✓ VERIFIED | See checklist item 6 above — `git diff` proof, absence-asserting tests green. |
| C5 | PN-1..PN-5 naming (provenance model) | ✓ VERIFIED | Checklist items 3, 4, 5, 8, 11 above jointly cover this. |
| C6 | 4 missing contact properties manifested + rename landed | ✓ VERIFIED | `lv_linkedin_url`, `lv_persona_group`, `lv_jobtitle_verified_at`, `lv_mobilephone_verified_at` all present in `config/hubspot_properties.yaml`'s contacts list; PN-1 rename confirmed by the 14-case architecture guard. Live creation is the disclosed operator step. |

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `scripts/snapshot_hubspot_schema.py` | read-only baseline+probe | ✓ VERIFIED | exists, substantive (181 lines), no-creds skip confirmed live |
| `scripts/sync_hubspot_properties.py` | two-key-gated forward sync | ✓ VERIFIED | exists, substantive (239 lines), two-key gate confirmed |
| `scripts/rollback_property_migration.py` | reverse-direction archive | ✓ VERIFIED | exists, substantive (246 lines), manifest+baseline hard-refusal confirmed |
| `scripts/rollback_canary_proof.py` | live archive-mechanics proof | ✓ VERIFIED | exists, substantive (125 lines), two-key gate confirmed |
| `config/hubspot_properties.yaml` | 33-property/2-group manifest | ✓ VERIFIED | parsed myself: 19+14=33, 1+1=2, counts match test assertions |
| `tests/test_snapshot_hubspot_schema.py`, `tests/test_sync_hubspot_properties.py`, `tests/test_rollback_property_migration.py`, `tests/test_hubspot_properties_config.py` | offline coverage | ✓ VERIFIED | all pass, hermetic sentinel-monkeypatch pattern confirmed present |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `mergeCompanies.js`/`mergeContacts.js` provenance | `merge_policy.py` `serialize_provenance()` | shared stable-sort serialization rule | ✓ WIRED | byte-parity test green + personally re-fired ensure_ascii break |
| `enrichmentGate.js` staleness read | cache-key properties | `_cacheKeyName(field)` | ✓ WIRED | code read directly, line 85 |
| `sync_hubspot_properties.py` | `config/hubspot_properties.yaml` | `load_desired_config()` | ✓ WIRED | `compute_property_diff`/`compute_group_diff` consume it |
| `rollback_property_migration.py` | undo manifest + baseline | hard `return 1` refusal | ✓ WIRED | read code directly, confirmed |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| All 4 scripts skip cleanly with no creds | ran each script directly, unset env first | all printed "skipped (no credentials)", exit 0 | ✓ PASS |
| ensure_ascii=False is load-bearing | removed it from real source, ran parity test, restored | genuinely went red naming the non-ASCII case, restored clean, re-ran green | ✓ PASS |
| Rebuild is a byte no-op | ran `build_cloud_workflows.py` twice | `git diff --exit-code -- n8n/` clean both times | ✓ PASS |
| No baseline/manifest files exist | `find`/`ls` on the phase directory | neither exists — confirms no live run ever happened | ✓ PASS |

### Requirements Coverage

| Requirement | Description | Status | Evidence |
|-------------|-------------|--------|----------|
| PN-1 | `lv_`-prefixed names for created properties | ✓ SATISFIED | manifest + architecture guard |
| PN-2 | Native properties never renamed | ✓ SATISFIED | `lv_org_type`/`lv_produces_content` excluded from manifest; raw ident fields untouched |
| PN-3 | Staging property composition | N/A this phase | staging folded into provenance blob per coordinator decision — no `lv_<provider>_<field>` properties created (explicit scope call, recorded in plan) |
| PN-4 | Metadata property composition / cache keys | ✓ SATISFIED | 4 cache-key datetimes, `enrichmentGate.js` reads them correctly |
| PN-5 | Control property prefixing (review surface) | ✓ SATISFIED | 9 review-surface properties, `lv_`-prefixed, mirrored on both objects |
| RT-5 | Domain-keyed caching, 180-day TTL | ✓ UNBLOCKED | cache-key datetimes exist; TTL logic itself is Phase 16 scope (SJ-2), correctly deferred |

### Anti-Patterns Found

None (see checklist item 13).

### Human Verification Required

None. All checks were verifiable programmatically — the phase's own primary deliverable
(safety tooling) is provable via code reading, hermetic tests, and direct script
execution, not requiring a human to observe UI/runtime behavior.

### Gaps Summary

No gaps against this phase's declared scope. One pre-existing, disclosed, out-of-scope
item is carried forward as a WARNING for future attention (not a blocker):

- `src/ingest.py`'s `_CONTACT_PROPS`/`_SEARCH_PROPS` still reference bare
  `linkedin_url`/`persona_group` (a Phase-8 CSV-ingest CLI harness, explicitly outside
  this plan's declared `files_modified`, gated by the pre-existing single-`DRY_RUN` gate,
  requiring an explicit `--ingest` CLI invocation with real credentials to reach the
  network). This does not affect the portal-untouched finding for Phase 15's own tooling
  and was honestly disclosed in the SUMMARY as Deviation 7 / a carried-forward gap.

---

_Verified: 2026-07-22_
_Verifier: Claude (gsd-verifier)_
