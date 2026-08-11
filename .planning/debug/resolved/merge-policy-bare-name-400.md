---
status: resolved
trigger: "fix the merge_policy bare property names too"
created: 2026-08-11
updated: 2026-08-11
diagnose_only: false
---

# merge_policy's status_patch writes property names that do not exist in HubSpot

## Symptoms

- **Expected:** a live run of the Python lane (`main.py` with `DRY_RUN=false`, or
  `src/ingest.py`'s contact-matched PATCH) PATCHes only properties that exist in the portal.
- **Actual (REPRODUCED live, 2026-08-11):** `build_merge_result`'s `status_patch` carries 11
  keys, of which only 3 have a live counterpart. A live PATCH with these bare keys 400s with
  "Property \"…\" does not exist" for all 8 orphans (confirmed verbatim below).
- **Repro (executed):** `patch_record("companies", <test id>, status_patch, dry_run=False)`
  against `TEST_COMPANY_IDS` (9604614548) reproduced the 400 exactly as predicted.
- **Timeline:** the portal has only ever had `lv_`-prefixed enrichment properties; the bare
  names in `status_patch` appear never to have matched it.

## Evidence

- timestamp: 2026-08-11 — Live property listing (`GET /crm/v3/properties/companies`):
  26 `lv_*` properties on companies, 16 on contacts. **Zero bare `enrichment_*` properties.**
  Dump saved this session at scratchpad `live_props.json` (ephemeral — re-derive, or commit a
  fixture copy if a test depends on it).
- timestamp: 2026-08-11 — `src/merge_policy.py:369-385` `status_patch` keys and their live
  counterparts:
  - `enrichment_requested`   -> `lv_enrichment_requested`   EXISTS
  - `enrichment_status`      -> `lv_enrichment_status`      EXISTS
  - `enrichment_needs_review`-> `lv_enrichment_needs_review` EXISTS
  - `last_enrichment_run_id`, `last_enriched_at`, `enrichment_confidence`,
    `enrichment_last_sources`, `enrichment_primary_source`, `enrichment_source_count`,
    `enrichment_validation_path`, `enrichment_last_decision` -> **no live property at all**
    (8 orphans; spec'd in CLAUDE.md §4.1 but never created — see the §4.0 as-built delta,
    commit 54d7fe4).
- timestamp: 2026-08-11 — `status_patch["enrichment_requested"] = False` is a Python bool.
  Established portal behaviour: HubSpot booleans must be the strings `"true"`/`"false"`, so
  this key would fail live even under the correct name.
- timestamp: 2026-08-11 — Live-capable callers of `build_merge_result`: `main.py:44` and
  `src/ingest.py:85`. `main.py` reaches `patch_record(..., dry_run=DRY_RUN)`, so
  `DRY_RUN=false` is a genuine live-write boundary. **`src/ingest.py`'s live-write status is
  UNVERIFIED** — prior note says Milestone 3 moved contact ingestion into n8n Cloud with
  Python as oracle only. Confirm before treating it as a second boundary.
- timestamp: 2026-08-11 — **CORRECTION to the entry above (that entry described the
  CLAUDE.md §7.1/§6.1 SPEC, not the code as it now stands — stale).** Ran a dry
  `build_merge_result()` (mock providers + mock web research, no live API calls) and
  intersected `full_patch.keys()` against a live `GET /crm/v3/properties/companies`
  listing. Actual measured `full_patch` for this fixture: the 11 `status_patch` keys
  above, plus exactly ONE metadata key: `lv_enrichment_provenance`. `staging_patch` is
  **always `{}`** — commit `9451f4b` ("Phase 15... provenance stamper rewrite... wrapper
  fold, cache keys") already retired the flat `{provider}_{field}` staging properties AND
  the flat `{field}_source`/`{field}_confidence` metadata properties in favor of ONE JSON
  provenance blob (`lv_enrichment_provenance`) plus 2 top-level cache-key datetimes
  (`lv_org_type_verified_at`, `lv_produces_content_verified_at`) — all three already
  `lv_`-prefixed and confirmed live. **Zero missing keys** when checking the full set of
  possible `canonical_patch`/`metadata_patch` keys (all `config/field_policy.yaml` company
  + contact field names, both native-bare and `lv_`-prefixed) against the live listing.
  **The orphan problem is confined entirely to `status_patch`'s 11 keys** (3 renamable + 8
  orphans, per the entry above) — confirmed identical shape on companies AND contacts.
- timestamp: 2026-08-11 — Reproduced the 400 live. First attempt (status_patch verbatim,
  including the Python-list-valued `enrichment_primary_source`) 400'd on a DIFFERENT,
  earlier failure: `"Cannot deserialize value of type <...> from Array value"` — HubSpot's
  PATCH `properties` map is `Map<String,String>`; a raw JSON array value fails generic
  request deserialization before any per-property existence check runs. Removing that one
  key reproduced the PREDICTED failure exactly: `PROPERTY_DOESNT_EXIST` for all 8 orphans
  plus the 3 renamable bare names (`enrichment_requested`, `enrichment_status`,
  `enrichment_needs_review`). Not in scope to fix `enrichment_primary_source`'s
  list-vs-string mismatch: it is one of the 8 dropped orphans, so it never reaches HubSpot
  regardless.
- timestamp: 2026-08-11 — **`src/ingest.py:87` CONFIRMED as a second live-write boundary**
  (debug file's prior "UNVERIFIED" item resolved). `run_contact_ingest`'s matched-contact
  branch calls `patch_record("contacts", ident.contact_id, merge.full_patch, dry_run=dry_run)`
  directly with the untranslated bare-name patch, `dry_run` sourced from
  `run_ingest_cli`'s `DRY_RUN` env var — same live-write shape as `main.py:72`. Live
  `GET /crm/v3/properties/contacts` confirmed identical orphan/rename shape to companies
  (same 3 renamable, same 8 orphans; contacts' native fields `email/phone/mobilephone/
  jobtitle/seniority` all live; `linkedin_url`/`persona_group` correctly NOT native, per
  `config/field_policy.yaml`'s own PN-1 comments — `lv_linkedin_url`/`lv_persona_group`
  are the real live names and are what the field_policy/candidates already use).

## Eliminated

- hypothesis: the bare names are simply wrong and should be renamed — **ELIMINATED as the
  fix shape.** Bare names are the Python oracle's correct INTERNAL contract: they are pinned
  by `tests/fixtures/company_current.json`, `src/ingest.py:24`, and `tests/test_merge_policy.py`,
  and CLAUDE.md §4.0 now documents the two-lane convention deliberately (live/n8n lane =
  `lv_`-prefixed; local Python MVP lane = bare). A rename inside `build_merge_result` breaks
  the oracle and its JS-parity relationship.
- hypothesis: the missing properties mean the ICP rubric is only partially scorable —
  **ELIMINATED.** All four `base_score` inputs (`lv_org_type`, `lv_produces_content`,
  `lv_country_region_normalized`, `lv_revenue_band`) plus both veto/deduction inputs
  (`lv_is_hardware_vendor`, `lv_is_gambling_operator`) exist live, as do all verdict-carrying
  outputs. Staleness is keyed off input-side `lv_org_type_verified_at` /
  `lv_produces_content_verified_at` (both exist), per the deployed workflow's own
  "Approach C" note: SJ-1/2/3 predicates never reference ICP outputs. The missing five
  output properties are audit/convenience only.

## Operator decisions (2026-08-11)

- Fix shape: **boundary translation**, not a rename. Confirmed by the operator.
- `lv_icp_scoring_version`: **will not be created.** The no-new-properties constraint stands.
  Consequence accepted and noted: rubric-version segmentation is not possible in HubSpot
  lists/views, so identifying records scored under a superseded rubric requires re-scoring
  the population rather than filtering. Not to be explored further.

## Constraints for the fix

1. Do NOT rename keys inside `build_merge_result` / `status_patch`. Bare names stay.
2. Translate at the live-write boundary (where merge output meets `patch_record`), not inside
   `hubspot_client.patch_record` — `tests/test_scoring_parity.py` calls `patch_record`
   directly with already-correct `lv_` names, and changing its semantics would corrupt those
   ~20 call sites.
3. Drop orphan keys rather than inventing properties, and LOG every dropped key. This matches
   CLAUDE.md §26.4's own prescription: "Validation error — remove invalid field and retry
   safe subset."
4. Stringify booleans to `"true"`/`"false"` in translation.
5. No new HubSpot properties.

## Resolution

root_cause: `build_merge_result`'s `status_patch` (11 bare `enrichment_*`/`last_*` keys) was
  emitted verbatim to a live HubSpot PATCH at both live-write boundaries (`main.py:72`,
  `src/ingest.py:87`), with no translation between the oracle-internal bare-name contract
  and the deployed `lv_`-prefixed schema. 3 keys have a real `lv_`-prefixed live property
  (`enrichment_requested`/`enrichment_status`/`enrichment_needs_review`); the other 8
  (`last_enrichment_run_id`, `last_enriched_at`, `enrichment_confidence`,
  `enrichment_last_sources`, `enrichment_primary_source`, `enrichment_source_count`,
  `enrichment_validation_path`, `enrichment_last_decision`) were spec'd in CLAUDE.md §4.1
  but never created as HubSpot properties. canonical_patch and metadata_patch were largely
  NOT part of the blast radius — Phase 15's provenance-blob refactor (commit `9451f4b`)
  already left those fully `lv_`-prefixed/native and live-matched; this was measured, not
  assumed. ONE additional instance of the same defect class was found by empirically
  running the CSV-contact-ingest path (not by the field_policy-name sweep alone, which
  missed it): `src/ingest.py`'s `_UPLOAD_FIELDS` emits bare `linkedin_url` (matching
  `config/column_mapping.yaml`'s canonical prop name), but PN-1 already renamed the
  live/policy property to `lv_linkedin_url` — a CSV row with a LinkedIn column promotes
  bare `linkedin_url` into `canonical_patch` on a blank-current contact, which would 400
  under the bare name via the same `src/ingest.py:87` boundary.

fix: Added `src/live_patch.to_live_patch(patch)` — a small boundary-translation function
  (not touching `build_merge_result`, `status_patch`, or `hubspot_client.patch_record`).
  Renames the 3 status keys plus `linkedin_url` (4 total) to their real live counterparts,
  drops (and prints a log line for) the 8 status_patch orphans, stringifies Python `bool`
  values to `"true"`/`"false"`, passes every other key through unchanged. Wired in at all
  THREE live-write boundaries: `main.py`'s `patch_record(...)` call now passes
  `to_live_patch(patch)` as `properties=` (the returned/printed `patch` itself stays
  untranslated, preserving `tests/test_main.py`'s bare-name assertions); `src/ingest.py`'s
  matched-contact `patch_record(...)` call does the same (the report's `"payload"` key
  stays untranslated, preserving `tests/test_contact_ingest.py`/`test_e2e_ingest.py`'s
  bare-name assertions); and `src/ingest.py`'s net-new `create_record(...)` call (the third
  boundary, closed after operator review — `create_props` is built directly from candidate
  `canonical_field` names and bypasses `build_merge_result`/`full_patch` entirely, but
  carries the identical bare-`linkedin_url` risk) now passes `to_live_patch(create_props)`,
  with the report's `"payload"` result likewise left untranslated.

verification:
  - Live repro (before fix): direct `patch_record("companies", 9604614548, status_patch,
    dry_run=False)` with the raw bare-name status_patch → 400 `PROPERTY_DOESNT_EXIST` for
    all 11 keys (rejected either by name, or — for the list-valued
    `enrichment_primary_source` — by the prior array-value deserialization error observed
    on the first repro attempt).
  - Offline regression suite: `tests/test_live_patch.py` (6 tests, added this session,
    including the `linkedin_url` rename) + full existing suite —
    `.venv/bin/python -m pytest tests/ -q`: 1165 passed, 116 skipped, 0 failed (includes
    `tests/test_scoring_parity.py`). `node --test tests/n8n/*.test.mjs`: 658 passed, 0
    failed (untouched by this change, run for completeness — shares the parity contract
    with the Python oracle). `operator-claude-plugin/tests/` (exercises the ingest path
    this session modified): 1332 passed, 5 skipped, 0 failed.
  - Live end-to-end (after fix), `main.py` with `DRY_RUN=false`: dry-run preview confirmed
    the translated PATCH payload contains only `lv_enrichment_provenance`,
    `lv_enrichment_requested="false"`, `lv_enrichment_status="needs_review"`,
    `lv_enrichment_needs_review="true"`, with a log line naming all 8 dropped orphans. A
    genuine `DRY_RUN=false` run against the fixture's placeholder company id "789" 404'd
    (that id does not exist in the portal — an unrelated, pre-existing MVP-fixture
    condition, not this bug) — critically, it did NOT 400 on property names, confirming the
    fix eliminated the original failure mode.
  - Live end-to-end, direct against `TEST_COMPANY_IDS` (9604614548): `patch_record(
    "companies", 9604614548, to_live_patch(status_patch), dry_run=False)` → HTTP 200.
    Read-back via `get_record` confirmed `lv_enrichment_requested="false"`,
    `lv_enrichment_status="complete"`, `lv_enrichment_needs_review="true"` landed exactly
    as sent. **Test-record state after this session:** left with
    `lv_enrichment_status="complete"`, `lv_enrichment_requested="false"`,
    `lv_enrichment_needs_review="false"` (explicitly reset after verification so no phantom
    needs-review item appears in the weekly review-queue scan).
  - Offline, direct `build_merge_result()` call reproducing the real CSV-ingest shape
    (alice's row from `tests/fixtures/uploads/contacts.csv`, `promote_fake` haiku):
    confirmed `canonical_patch` contains bare `linkedin_url`, and confirmed
    `to_live_patch(full_patch)` correctly emits `lv_linkedin_url` with `linkedin_url`
    absent from the translated output.

  All THREE live-write boundaries are now closed: `main.py:72`, `src/ingest.py:87`
  (matched-contact patch), and `src/ingest.py:117` (net-new create).

files_changed:
  - src/live_patch.py (new — `to_live_patch()`)
  - main.py (translate at the `patch_record` call only; return value unchanged)
  - src/ingest.py (translate at both the `patch_record` call AND the `create_record` call;
    report payload unchanged in both branches)
  - tests/test_live_patch.py (new — 6 offline regression tests)
  - tests/test_contact_ingest.py (new —
    `test_net_new_create_payload_uses_live_property_names`; asserts `lv_linkedin_url`
    present, bare `linkedin_url` absent, native `email` passes through untranslated)

verification (create-path fix, added after operator review):
  - Red-before-green: `git stash` roundtrip on `src/ingest.py` —
    `test_net_new_create_payload_uses_live_property_names` fails without the fix
    (bare `linkedin_url` in the create payload) and passes with it.
  - `.venv/bin/python -m pytest tests/test_contact_ingest.py::test_net_new_create_payload_uses_live_property_names -q`:
    1 passed.
  - Corrected full-suite counts (the earlier "1165 passed/116 skipped" reported only the
    `tests/` directory, not the full Python suite — `operator-claude-plugin/tests/`'s 1332
    passed/5 skipped is a separate suite that was run but not summed):
    `.venv/bin/python -m pytest tests/ -q`: 1166 passed, 116 skipped (the +1 over the prior
    1165 is the new create-path test). `operator-claude-plugin/tests/`: 1332 passed, 5
    skipped. **Combined: 2498 passed, 121 skipped, 0 failed.**
    `node --test tests/n8n/*.test.mjs`: 658 passed, 0 failed.
  - All counts independently re-verified by the session-manager (not taken on trust) before
    sealing.

not_committed: Per session instructions (operator-gated), no `git commit`/`git push` was run
  until operator sign-off (see below).

discovered_but_out_of_scope (2 of original 3 — the create-path item was closed above):
  - `enrichment_primary_source`'s value is a Python `list` (all contributing providers), not
    a scalar — even under a correct name it would fail HubSpot's `Map<String,String>` PATCH
    deserialization. Currently moot: it is one of the 8 dropped orphans. Flagging in case a
    future `lv_enrichment_primary_source` property is ever created — the assignment at
    `src/merge_policy.py:377` would need to change too (e.g. take the first/highest-priority
    source, or join with `,` like its sibling `enrichment_last_sources`).
  - `config/field_policy.yaml`'s contacts section has no `linkedin_url` entry (only
    `lv_linkedin_url`, per PN-1), so a CSV-sourced `linkedin_url` candidate silently falls
    through to the generic default policy (`fill_blank_only`, `min_confidence: 80`) instead
    of `lv_linkedin_url`'s actual policy (`min_confidence: 85`,
    `protect_if_current_present: true`). This session's fix only corrects the PATCH-time
    property NAME (`to_live_patch` renames bare `linkedin_url` → `lv_linkedin_url`) — it does
    NOT correct which confidence threshold/protection rule gets applied during merge
    (`build_merge_result` is out of scope per this session's constraints). A CSV row could
    therefore promote a LinkedIn URL at confidence 80 that the intended policy would have
    required 85 for, or overwrite a present value the intended policy would have protected.
    Separate bug, not touched.

## Current Focus

hypothesis: CONFIRMED — `build_merge_result`'s `status_patch` (11 bare `enrichment_*`/
  `last_*` keys) is emitted verbatim to a live HubSpot PATCH at BOTH live-write boundaries
  (`main.py:72`, `src/ingest.py:87`), with no translation layer, so a live run 400s.
  canonical_patch/metadata_patch keys were NOT part of the blast radius (measured: already
  fully live-matched).
test: Fix implemented and verified — live PATCH of the translated status_patch against
  `TEST_COMPANY_IDS` (9604614548) returned 200 and read back correctly.
expecting: n/a — fix confirmed working.
next_action: none — operator confirmed fixed 2026-08-11, requested the create-path gap
  (previously deferred as out-of-scope) be closed in the same seal, which was done and
  independently re-verified (red-before-green, corrected suite counts). Session closed.
