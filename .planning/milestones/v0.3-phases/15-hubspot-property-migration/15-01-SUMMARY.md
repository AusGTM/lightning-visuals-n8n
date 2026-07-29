---
phase: 15-hubspot-property-migration
plan: 01
subsystem: hubspot-schema-migration
tags: [hubspot, provenance, safety, reversibility, pn-naming, icp-write-retirement]
dependency-graph:
  requires:
    - src/hubspot_client.py (hs_headers/BASE_URL reused, unchanged)
    - config/field_policy.yaml, config/provider_priority.yaml (Milestone 1/2)
    - n8n/code/mergeCompanies.js, n8n/code/mergeContacts.js, n8n/code/enrichmentGate.js (Phase 11/M2)
    - scripts/build_cloud_workflows.py (Phase 10-14 build pipeline)
  provides:
    - config/hubspot_properties.yaml (33-property/2-group desired-state manifest)
    - scripts/snapshot_hubspot_schema.py (read-only baseline + probe)
    - scripts/sync_hubspot_properties.py (two-key-gated forward create)
    - scripts/rollback_property_migration.py (reverse-direction archive)
    - scripts/rollback_canary_proof.py (live archive-mechanics proof)
    - src/merge_policy.py: serialize_provenance(), COMPANY_/CONTACT_PROVENANCE_KEY, COMPANY_/CONTACT_CACHE_KEY_FIELDS
    - n8n/code/mergeCompanies.js, n8n/code/mergeContacts.js: stableStringify() export
  affects:
    - main.py, tests/test_merge_policy.py, tests/test_main.py, tests/test_contact_ingest.py,
      tests/test_e2e_ingest.py, tests/test_service.py, tests/test_scaffold.py,
      tests/test_architecture_guard.py, tests/n8n/parity.test.mjs, tests/n8n/enrichment.test.mjs,
      n8n/wf_contact_ingest_local.json, n8n/wf_contact_ingest_cloud.json,
      n8n/wf_enrichment_local.json, n8n/wf_enrichment_cloud.json, n8n/wf_enrichment_local_live.json
tech-stack:
  added: []
  patterns:
    - "two-key write gate (DRY_RUN=false AND ALLOW_HUBSPOT_PROPERTY_WRITES=true) for the
      first schema-mutating scripts in the repo, stronger than hubspot_client's single
      DRY_RUN gate"
    - "provenance blob model: ONE JSON text property per object + 4 carve-out _verified_at
      cache-key datetimes, replacing ~121-145 flat per-field suffix properties"
    - "byte-identical cross-language serialization: Python json.dumps(sort_keys=True,
      separators=(',',':'),ensure_ascii=False) == JS recursive sorted-key stringify"
    - "per-property individual POST creates instead of a single batch/create call, to keep
      the undo manifest's confirmed-201-only guarantee unambiguous"
key-files:
  created:
    - scripts/snapshot_hubspot_schema.py
    - scripts/sync_hubspot_properties.py
    - scripts/rollback_property_migration.py
    - scripts/rollback_canary_proof.py
    - config/hubspot_properties.yaml
    - tests/test_snapshot_hubspot_schema.py
    - tests/test_sync_hubspot_properties.py
    - tests/test_rollback_property_migration.py
    - tests/test_hubspot_properties_config.py
  modified:
    - src/merge_policy.py
    - main.py
    - config/field_policy.yaml
    - config/provider_priority.yaml
    - n8n/code/mergeCompanies.js
    - n8n/code/mergeContacts.js
    - n8n/code/enrichmentGate.js
    - scripts/build_cloud_workflows.py
    - n8n/wf_enrichment_local.json
    - n8n/wf_enrichment_local_live.json
    - n8n/wf_enrichment_cloud.json
    - n8n/wf_contact_ingest_local.json
    - n8n/wf_contact_ingest_cloud.json
    - tests/test_merge_policy.py
    - tests/test_main.py
    - tests/test_contact_ingest.py
    - tests/test_e2e_ingest.py
    - tests/test_service.py
    - tests/test_scaffold.py
    - tests/test_architecture_guard.py
    - tests/n8n/parity.test.mjs
    - tests/n8n/enrichment.test.mjs
    - docs/WEB-RESEARCH-SPEC.md
    - .env.example
    - .planning/STATE.md
    - .planning/ROADMAP.md
    - .planning/REQUIREMENTS.md
decisions:
  - "Provenance model (coordinator decision): 1 JSON blob per object + 4 cache-key
    datetimes, superseding RESEARCH's 121-145 flat-suffix design; staging folds into the
    blob (no lv_waterfall_*/lv_claude_web_* properties)."
  - "Per-property individual HTTP creates instead of HubSpot's batch/create endpoint —
    undocumented partial-failure semantics made the undo manifest's confirmed-201-only
    guarantee unverifiable at the batch level."
  - "ensure_ascii=False is load-bearing for Python/JS blob byte-parity on any non-ASCII
    value; proven with a fixture row + a genuine one-time break-and-restore against the
    real source file."
metrics:
  duration: ~95m
  completed: 2026-07-22
status: complete
---

# Phase 15 Plan 01: HubSpot Property Migration Tooling + Provenance Model + ICP Write-Path Retirement Summary

Built and offline-proved the entire safety-first HubSpot property migration toolchain
(snapshot, sync, rollback, canary), the single-JSON provenance model (Python + JS,
byte-identical), the Approach-C ICP write-path retirement, and the PN-1 contact-field
rename — without making a single live call to the HubSpot API.

## What Shipped

**Safety tooling (Tasks 1, 3, 7, 8):**
- `scripts/snapshot_hubspot_schema.py` — read-only `GET` of both object types' property
  schema, written verbatim to `.planning/phases/15-hubspot-property-migration/baseline/`;
  portal-ID assert before any call; `--probe` mode (two-key gated) to settle the
  unknown-property-PATCH silent-no-op-vs-400 question live; drift print vs the
  2026-07-20 audit's 5 known custom company properties.
- `scripts/sync_hubspot_properties.py` — dry-run-by-default diff (desired config vs live
  GET); drift report-only, never auto-fixed; `hubspotDefined` properties never proposed;
  idempotent (always re-derives "missing" from a fresh GET); two-key write gate
  (`DRY_RUN=false` AND `ALLOW_HUBSPOT_PROPERTY_WRITES=true`); undo manifest records only
  confirmed 201 responses; post-write re-GET confirmation. Uses per-property `POST`
  calls rather than the `batch/create` endpoint — see Deviations.
- `scripts/rollback_property_migration.py` — refuses without BOTH the undo manifest and a
  baseline snapshot; refuses to archive anything absent from the manifest (enforced
  structurally — only iterates the manifest, never a live schema); reverse-creation-order
  archive (properties before their group; a group only if a live re-check finds it
  empty); belt-and-braces `hubspotDefined` check immediately before every archive;
  post-archive diff against the baseline. Module docstring carries the human runbook.
- `scripts/rollback_canary_proof.py` — the one live archive-mechanics proof: creates,
  archives, and asserts-archived a single throwaway `lv_rollback_canary_<UTC>` property.

**Desired-state manifest (Task 2):** `config/hubspot_properties.yaml` — 19 company + 14
contact = 33 properties + 2 groups under the provenance model. `lv_org_type` /
`lv_produces_content` (already exist) are deliberately not listed.

**ICP write-path retirement (Task 4, Approach C):** `src/merge_policy.py`, `main.py`,
`config/field_policy.yaml`, `n8n/code/mergeCompanies.js` no longer write
`lv_icp_fit_score`/`lv_icp_tier`; the scoring engine still computes both internally for
in-pipeline routing and the audit breakdown. Three test assertions flipped to assert
absence — these ARE the regression proof.

**Provenance stamper rewrite (Task 5, the atomic centerpiece):** Both stampers
(`src/merge_policy.py`, `n8n/code/mergeCompanies.js`+`mergeContacts.js`) now emit ONE
provenance object per field (`source, confidence, verified_at, evidence_url?,
validation_status, value`) instead of flat `{field}_*` suffix properties, plus 2 cache-key
datetimes per object type. Both sides serialize with the SAME rule — Python
`json.dumps(sort_keys=True, separators=(",", ":"), ensure_ascii=False)`, JS a recursive
sorted-key `stableStringify()` — proven byte-identical, including a non-ASCII fixture row
("Ngā Puna Wai"). `scripts/build_cloud_workflows.py`'s 5 decide/echo nodes are now the
single serialization point (the stampers themselves return the parsed object, never a
string). `enrichmentGate.js` staleness reads the real `lv_<field>_verified_at` cache-key
property, never the blob.

**PN-1 contact rename (Task 6):** `linkedin_url`/`persona_group` → `lv_linkedin_url`/
`lv_persona_group` everywhere either is used as a HubSpot property (policy configs, JS
default policy, merge-candidate arrays), decoupled from the RAW read-side field name
(`row.linkedin_url`, `winners.linkedin_url`) which stays unprefixed since it is not
itself a property. A new architecture guard (14 parametrized cases) proves no bare
canonical-key or cache-key survives anywhere in the build script or built workflows, and
no flat per-field metadata template literal survives the provenance collapse.

**Finalization (Task 9):** Full offline suite green, rebuild deterministic,
`docs/WEB-RESEARCH-SPEC.md` records RT-5 unblocked + the provenance model, STATE/ROADMAP/
REQUIREMENTS hand-edited, this SUMMARY written.

## Verification Evidence

- `pytest -q`: **199 passed** (baseline 148 + 51 new/changed, 0 regressions).
- `node --test tests/n8n/*.test.mjs`: **77 passed** (baseline 74 + 3 new, 0 regressions).
- `python scripts/build_cloud_workflows.py` run twice → `git diff --quiet -- n8n/` →
  **byte-no-op confirmed** (both via `git diff` post-commit and via direct file-diff of
  two consecutive build outputs mid-task).
- `test_top_level_is_exactly_the_deployable_set`: green throughout.
- Every live script's default/no-credentials invocation exits 0 with **zero network
  calls** — confirmed by `requests.get/post/patch/delete` sentinel monkeypatches in every
  offline test file that raise `AssertionError` if a live call ever leaks through a guard.

### Blob-parity deliberate-break proofs (both fired genuinely)

**Break 1 (value-change, permanent regression test,** `tests/n8n/parity.test.mjs`**):**
changing `lv_org_type.value` from `"governing_body_league"` to `"content_producer"`
changes the serialized blob string, and Python/JS still agree on the new value:
```
jsBase   != jsChanged   -> true  (blob changed)
jsChanged == pyChanged  -> true  (parity holds after the change)
```

**Break 2 (ensure_ascii=False, one-time manual proof against the real source file):**
temporarily removed `ensure_ascii=False` from `src/merge_policy.py`'s
`serialize_provenance()`, ran `node --test --test-name-pattern="provenance blob"
tests/n8n/parity.test.mjs`, and it failed exactly as predicted, naming the non-ASCII
case:
```
AssertionError [ERR_ASSERTION]: provenance blob byte-parity (Python json.dumps vs JS stableStringify)
+ actual (JS):     ...\"value\":\"Ngā Puna Wai Sports Hub live_broadcast\"...
- expected (Python, broken): ...\"value\":\"Ng\\u0101 Puna Wai Sports Hub live_broadcast\"...
```
Restored the file via `cp` from a pre-edit copy; re-ran green (10/10 merge-policy tests,
3/3 provenance-blob node tests). A THIRD, permanent regression test in
`tests/n8n/parity.test.mjs` ("DELIBERATE-BREAK 2") reproduces the same failure mode by
calling a deliberately-broken inline Python snippet (never touching real source), so this
proof re-fires on every CI run without requiring a manual break-and-restore each time.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `tests/test_scaffold.py::test_configs_load` hardcoded "exactly 7
config YAMLs"** — Task 2 added `config/hubspot_properties.yaml`, an 8th. Updated the
count + comment. Commit: `6d64da7`.

**2. [Rule 1 - Bug] `tests/test_contact_ingest.py`, `tests/test_e2e_ingest.py`,
`tests/test_service.py` referenced the old flat `csv_email`/`csv_linkedin_url` staging
keys** — `src/ingest.py`'s `run_contact_ingest` calls the same `build_merge_result()` the
Task 5 stamper rewrite touched, so its output shape changed identically even though
`src/ingest.py` itself is outside this plan's declared file list. Updated the 3 test
files' assertions to parse `lv_contact_enrichment_provenance` instead. Commit: `e8c9369`.

**3. [Rule 1 - Bug] `tests/n8n/enrichment.test.mjs`'s two gate-staleness tests silently
tested the wrong branch** — they passed a bare `jobtitle_verified_at` key directly as a
record property; after `enrichmentGate.js`'s cache-key rewrite this key is never read
(`lv_jobtitle_verified_at` is), so both tests would have kept passing for the WRONG
reason (treating "key format mismatch" as indistinguishable from "genuinely stale").
Fixed the fixture keys to `lv_jobtitle_verified_at` so the TTL/age-arithmetic branch is
actually exercised. Commit: `e8c9369`.

**4. [Rule 1 - Bug] `ENRICH_HUBSPOT_SEARCH_MOCK`'s canned LOCAL fixture used bare
`jobtitle_verified_at`/`mobilephone_verified_at`** — a direct, immediate consequence of
rewriting `enrichmentGate.js` in the SAME task: without this fix the LOCAL enrichment
demo's "sam.fresh@... -> SKIP (fresh)" scenario would have silently broken (every
"fresh" contact reading as stale). Renamed to the `lv_`-prefixed cache-key forms.
Commit: `e8c9369`.

### Scope clarifications (not deviations — plan-anchor precision)

**5. Did NOT rename `identity_keys.linkedin_url`** (`ENRICH_BUILD_IDENTITY` in
`scripts/build_cloud_workflows.py`, feeding `add("linkedinUrl", id.linkedin_url)` in the
Lusha/ZoomInfo request-shape builder). Task 6's own anchor text ("LOCAL mock fixture
field, anchor: `linkedin_url: row.linkedin_url || null`") happens to cite the exact same
line as the request-shape field the SAME task explicitly excludes ("DO NOT rename
`id.linkedin_url`/`linkedinUrl`"). Grep confirmed this is the ONLY match for that literal
string in the file — there is no separate "LOCAL mock fixture" occurrence distinct from
the identity-keys builder. Renaming it would break the live provider lookup and directly
contradicts the task's own carve-out two sentences later, so it was left untouched.

**6. `tests/test_contact_ingest.py`/`tests/test_e2e_ingest.py` required no NEW Task-6
changes** — persona_group/jobtitle_verified_at/mobilephone_verified_at do not appear in
either file (grep-confirmed); the only affected reference (linkedin_url) was already
fixed as Deviation 2 above, in Task 5.

**7. `src/ingest.py`'s own canonical field names (`_UPLOAD_FIELDS`, `_CONTACT_PROPS`,
`_SEARCH_PROPS`) still use bare `linkedin_url`/`persona_group`** — this file is not in
the plan's declared `files_modified` list, and RESEARCH.md's own rename-impact analysis
(§7.2) never named it. Left untouched to respect the declared scope boundary; the
Python CSV-ingest path is a local dev-oracle harness (DRY_RUN-gated, never live in this
phase), so the gap is inert today. Carried forward as a discovered-not-fixed item
alongside the two latent copy-loop bugs (see STATE.md).

## Out of Scope (explicitly, per plan)

- C3 one-way door: `lv_org_type` text→enumeration NOT performed anywhere.
- `icp_scoring.py:116` precedence bug + `lv_icp_tier` A/B/C/D enum bug — now dead-bound
  (Approach C retires the only write path that could reach them), not fixed.
- Two latent copy-loop bugs (`lv_sponsorship_reliant` companies, `persona_group`/
  `lv_persona_group` contacts) — properties created for both, wrapper gap carried
  forward.
- `lv_country_region_normalized` has no explicit `field_policy.yaml` entry (falls to
  default `fill_blank_only`) — property created, policy question flagged not resolved.
- Phase 16 scope: SJ-1/SJ-2/SJ-3 wiring, §22.2 review-surface wiring (9 properties
  created here, not wired), the cloud-template companies-branch port.
- HubSpot-side tier-formula authoring — downstream, out of milestone.

## Known Stubs

None. This phase's deliverable is tooling + code, not a UI or data-flow feature — there
is no rendering path that could be silently fed placeholder data. The 33 properties do
not yet exist in the live portal by design (that's the operator's next step, not a stub).

---

## OPERATOR RUNBOOK (the live steps a human runs, in order)

Nothing below ran during this execution — every live script's no-credentials skip path
is what actually ran. This is the exact sequence the operator runs next, with real
credentials, per `scripts/rollback_property_migration.py`'s own module-docstring runbook
and the plan's `<operator_runbook>`.

**Preconditions:** `HUBSPOT_PRIVATE_APP_TOKEN` + `HUBSPOT_PORTAL_ID=22617666` set; the
private app has schema-management scope (`crm.schemas.companies.write` +
`crm.schemas.contacts.write` — existing `crm.objects.*.write` does NOT cover property
creation; a missing scope surfaces as a 403 on step 1's `GET`, before any write).

1. **BASELINE (before any mutation):**
   ```bash
   python scripts/snapshot_hubspot_schema.py
   ```
   Commit the `baseline/*.json` files produced. This IS the rollback target.

2. **PROBE (settle the silent-drop assumption):**
   ```bash
   DRY_RUN=false python scripts/snapshot_hubspot_schema.py --probe
   ```
   Confirm the unknown-property PATCH against a `TEST_COMPANY_IDS` entry is a silent
   no-op (200/204), not a 400.

3. **DRY-RUN DIFF (review before creating anything):**
   ```bash
   python scripts/sync_hubspot_properties.py
   ```
   Review the printed create-list (33 properties + 2 groups) + drift report against
   `config/hubspot_properties.yaml`.

4. **LIVE CREATE (the one forward mutation):**
   ```bash
   DRY_RUN=false ALLOW_HUBSPOT_PROPERTY_WRITES=true python scripts/sync_hubspot_properties.py
   ```
   Creates the groups + properties (per-property POST calls), writes the undo manifest
   to `.planning/phases/15-hubspot-property-migration/undo-manifest-<run_id>.json`.
   Commit the undo manifest + a post-migration snapshot:
   ```bash
   python scripts/snapshot_hubspot_schema.py --label post
   ```

5. **CONFIRM:** the PN-provenance code (Tasks 5/6, already committed) now matches the
   created names. Do **not** activate `ALLOW_CANONICAL_WRITES`/`ALLOW_STAGING_WRITES` or
   any Phase-16 write workflow this phase — creation lands strictly before any write
   activation (coupled-rollback gate); reverting code never orphans data because no data
   is written yet.

6. **CANARY PROOF (the one reverse-direction mutation):**
   ```bash
   DRY_RUN=false ALLOW_HUBSPOT_PROPERTY_WRITES=true python scripts/rollback_canary_proof.py
   ```
   Assert it prints `PASS`.

**ROLLBACK** (only if step 3/4's diff is unexpected, or a downstream phase finds the
schema wrong BEFORE real data accumulates):
```bash
python scripts/rollback_property_migration.py                 # dry-run, review the list
DRY_RUN=false ALLOW_HUBSPOT_PROPERTY_WRITES=true \
  python scripts/rollback_property_migration.py --live         # requires typed "yes"
python scripts/snapshot_hubspot_schema.py --label post-rollback   # verify: empty diff vs baseline
```
Coupled-rollback recovery: if code was reverted but properties remain, they are inert —
do NOT reflexively archive data-bearing properties; check fill rate first.

## Self-Check: PASSED

- `FOUND: scripts/snapshot_hubspot_schema.py`
- `FOUND: scripts/sync_hubspot_properties.py`
- `FOUND: scripts/rollback_property_migration.py`
- `FOUND: scripts/rollback_canary_proof.py`
- `FOUND: config/hubspot_properties.yaml`
- `FOUND: tests/test_snapshot_hubspot_schema.py`
- `FOUND: tests/test_sync_hubspot_properties.py`
- `FOUND: tests/test_rollback_property_migration.py`
- `FOUND: tests/test_hubspot_properties_config.py`
- Commits `6c65f79`, `cba5b0e`, `6d64da7`, `305b10e`, `e8c9369`, `f00c7b5`, `584302f`,
  `f27eb0a` all present in `git log --oneline`.
