# Phase 15: HubSpot Property Migration - Research

**Researched:** 2026-07-21
**Domain:** HubSpot CRM v3 Properties API — live mutation of portal 22617666
**Confidence:** MEDIUM overall — API contract sections are HIGH/CITED (official docs);
current-state code references are HIGH (grep-verified this session); the "what does the
live portal actually contain" facts are inherited from the 2026-07-20 portal audit
recorded in `docs/WEB-RESEARCH-SPEC.md` / `STATE.md` and were **not** re-queried live this
session (no HubSpot credentials available to the researcher) — flagged throughout as
`[CITED: STATE.md/spec]` rather than `[VERIFIED]`. **Task 1 of the plan MUST open with a
live `GET /crm/v3/properties/companies` + `/contacts` call to confirm these before any
write**, per §5.7 below.

---

<phase_requirements>
## Phase Requirements (ROADMAP Phase 15, 6 criteria — re-verified against current files)

| # | Criterion | Research Support |
|---|-----------|------------------|
| 1 | Missing metadata properties created; sync script dry-runs by default, emits an undo manifest | §2 (API contract), §4 (safe-migration design), §6 (manifest) |
| 2 | Research caching by domain, 180-day TTL, becomes possible (unblocks RT-5) | §6 confirms the exact properties RT-5 needs (`lv_org_type_verified_at`, `lv_produces_content_verified_at`) are in the manifest |
| 3 | `lv_org_type` text→enumeration NOT performed without explicit sign-off | §1 current-state confirms it is still `string/text`; §3 classifies a type change as a one-way door and the task order in §7 puts it nowhere in this phase |
| 4 | `lv_icp_fit_score`/`lv_icp_tier` write paths retired (5 exact call sites + 2 test assertions) | §1 table re-verifies every line number; 3 of 5 code refs have drifted, both test refs are exact |
| 5 | PN-1..PN-5 naming applied to code-generated property names | §1, §8 — including two additional PN-3/PN-1 gaps found in code that ROADMAP's line list did not name |
| 6 | 4 missing contact properties created (`lv_linkedin_url`, `lv_persona_group`, `lv_jobtitle_verified_at`, `lv_mobilephone_verified_at`) | §1, §6, §8 — plus the discovery that 2 of the 4 are canonical-field **renames**, not just new metadata |
</phase_requirements>

---

## 0. Reading order for the planner

This phase is a one-way door risk, not a feature. Read in this order:

1. §1 Current-state map — what's real vs. what ROADMAP's line numbers claim (several drifted).
2. §2 HubSpot Properties API contract (cited).
3. §3 **Reversibility & rollback design** (new first-class section — read before writing any task).
4. §4 Safe-migration design (dry-run/manifest/idempotency for the *forward* migration).
5. §5 Ordering/dependency risk and the proposed task sequence.
6. §6 The full property manifest, derived from code, not the CLAUDE.md spec text.
7. §7 PN-3/PN-4 naming impact — three separate findings, only one of which ROADMAP named.
8. §8 The `lv_icp_tier` bug verdict.
9. §9 Risk register, §10 test plan, §11 out of scope, §12 assumptions.

---

## 1. Current-state map (code vs. portal, file:line re-verified 2026-07-21)

### 1.1 ROADMAP criterion 4 — ICP write-path retirement, line-by-line

| ROADMAP reference | Current content at that line | Status |
|---|---|---|
| `src/merge_policy.py:303` | `"lv_icp_fit_score": icp_score.score,` | **Exact match.** Line 302-313 is the `canonical_patch.update({...})` block writing all 10 ICP-derived keys. |
| `main.py:60` | `"lv_icp_fit_score",` (inside the `allow_icp_score_writes` fallback list, `run_local_mvp`) | **Exact match.** |
| `config/field_policy.yaml:86` | `lv_icp_fit_score:` (the `score_output` policy block) | **Exact match.** |
| `n8n/code/mergeCompanies.js:35` | `lv_produces_content: { class: "system_owned", min_confidence: 85,` | **DRIFTED.** The `lv_icp_fit_score` policy entry this criterion means is now at **line 40** (`DEFAULT_COMPANY_POLICY.lv_icp_fit_score`, `class: "score_output"`) and `lv_icp_tier` at line 41. Phase 12/14 comment insertions shifted the block down 5 lines. |
| `tests/test_merge_policy.py:196` | `assert "lv_icp_fit_score" in mr.canonical_patch` (line 196), `assert "lv_icp_tier" in mr.canonical_patch` (line 197) | **Exact match**, function `test_integ_wires_icp_scorer`. |
| `tests/test_main.py:60` | `assert "lv_icp_fit_score" in patch` (line 60), `assert "lv_icp_tier" in patch` (line 61) | **Exact match**, function `test_sc2_promotes_only_icp_stages_firmographics`. **A third, unnamed assertion exists**: `tests/test_main.py:85`, `assert "lv_icp_tier" in patch` inside `test_sc3_staging_flag_toggles` — ROADMAP's list is incomplete; all three must flip together or the suite goes red on a false positive/negative pairing. |

**Net:** 4 of 6 line references are exact; `mergeCompanies.js:35` has drifted to line 40 (and the `lv_icp_tier` sibling to 41); one additional test assertion (`test_main.py:85`) exists that ROADMAP's criterion 4 text did not enumerate. The **fix itself is trivial** in every case — flip `class` from `score_output`/direct-write to something that never promotes (e.g. drop the keys from `DEFAULT_COMPANY_POLICY` and the `canonical_patch.update` block entirely, since Approach C means the pipeline computes `icp_score` only for internal routing, never for a HubSpot write) — but the plan must use the corrected line numbers.

### 1.2 ROADMAP criterion 5 — PN-1..PN-5 naming, line-by-line

| ROADMAP reference | Current content | Status |
|---|---|---|
| `n8n/code/mergeCompanies.js:154` | Blank line (the `if (field === "domain" ...)` guard is line 153) | **DRIFTED.** The actual unprefixed metadata stamper (`` `${field}_source` ``, `` `${field}_confidence` ``, `` `${field}_verified_at` ``, `` `${field}_validation_status` ``, conditional `` `${field}_evidence_url` ``) is at **lines 158–164**. |
| `n8n/code/mergeContacts.js:115` | `` [`${field}_source`]: source, `` | **Exact match** — inside the `meta` object, lines 114-119. |
| `src/merge_policy.py:44` | `` f"{field}_source": candidate.provider, `` | **Exact match** — inside `source_metadata()`, lines 38-57 (Python emits 3 extra suffixes JS does not — see §7.3). |
| `n8n/code/enrichmentGate.js:76` | `` const verifiedAt = existingRecord[`${field}_verified_at`]; `` | **Exact match.** |
| `scripts/build_cloud_workflows.py:686/692/694/1059` | None of these 4 lines contain a hardcoded metadata property name today (686 is a comment about `mergeContacts.js`; 692/694 sit inside a comment block about the domain guard; 1059 is unrelated companies-branch identity code) | **STALE — the real hardcoded references are elsewhere**, found by grep: line **1081** (`HS_SEARCH_BODY_EXPR`, contacts search property list: `"jobtitle_verified_at","mobilephone_verified_at"`), and lines **708/714/716** (`ENRICH_HUBSPOT_SEARCH_MOCK` canned fixture using the same two unprefixed names). See §7 for the full rename list — this criterion's exact line numbers must be redrawn by the plan, not copied from ROADMAP. |

**Net:** 2 of 5 references are exact; 3 have drifted or moved to different lines entirely. The **substance** of criterion 5 is correct (these are the right functions to touch), but a plan that literally opens `build_cloud_workflows.py:686` expecting to find a property name will fail immediately. Re-grep at task-execution time, don't trust the line numbers as anchors — use the string anchors given in §7 instead.

### 1.3 ROADMAP criterion 6 — 4 missing contact properties

Confirmed by code trace (`config/field_policy.yaml:133,144`, `config/provider_priority.yaml:29,31`, `n8n/code/mergeContacts.js:20,22`, `scripts/build_cloud_workflows.py:224,629,687`, `:645-646`, `:1081`):

- `linkedin_url` and `persona_group` are used **unprefixed** as canonical field keys everywhere in code today, and **neither appears in the PN-2 verified-native list** (`email, firstname, lastname, jobtitle, phone, mobilephone, seniority, company, domain, industry, annualrevenue, numberofemployees, name, website, country`). They are not HubSpot-native. This means criterion 6 is **not just "create 2 missing properties"** — it is a **canonical-field rename** (`linkedin_url` → `lv_linkedin_url`, `persona_group` → `lv_persona_group`) touching every file above, in addition to property creation. See §7.2.
- `jobtitle_verified_at` / `mobilephone_verified_at` are read by the contacts staleness gate (`scripts/build_cloud_workflows.py:645-646` `REQUIRED = ["email","jobtitle","mobilephone"]` / `POLICY = { jobtitle: {stale_after_days:180}, mobilephone: {stale_after_days:180} }`) and by the live HubSpot search property list at `:1081`. These are exactly the PN-4 rename targets (`lv_jobtitle_verified_at`, `lv_mobilephone_verified_at`).
- **Confirmed no data migration needed for the 4**: none of the 4 names appear in any `tests/fixtures/*.json` live-shaped fixture with actual data, and the portal audit (spec §0.6) states these ~40 control/staging/metadata properties "do not exist yet" — grep of the fixtures directory turned up no record of these as populated HubSpot properties. Treat as `[CITED: docs/WEB-RESEARCH-SPEC.md §0.6]` pending the live confirmation call in §5.7.

### 1.4 `src/hubspot_client.py` — current API surface

Only 4 functions exist: `get_record` (GET), `patch_record` (PATCH, dry-run gated), `create_record` (POST, dry-run gated), `search_records` (POST search). **No property-schema methods exist** (`get_properties`, `create_property`, `batch_create_properties`, `create_property_group`). This module is a `dev-oracle`/local-harness client (AR-3) — it is not what n8n Cloud calls at runtime, but per the STATE.md exposure note it **is** capable of live writes when a human runs `main.py` with `DRY_RUN=false` and real credentials. The property-migration script needed for this phase is new code (§4), likely `scripts/sync_hubspot_properties.py`, using the same `hs_headers()`/`BASE_URL` pattern but a new set of HTTP calls against `/crm/v3/properties/{objectType}` (not `/crm/v3/objects/...`).

---

## 2. HubSpot CRM v3 Properties API contract

### 2.1 Create a property

`POST /crm/v3/properties/{objectType}` — required fields: `groupName`, `name` (internal identifier), `label` (display name), `type` (`string`|`number`|`date`|`datetime`|`bool`|`enumeration`), `fieldType` (`text`|`textarea`|`select`|`checkbox`|`radio`|`date`|…). For `type: enumeration`, an `options` array is required; each option has `label`, `value`, `displayOrder`, `hidden` (bool), optional `description`. [CITED: developers.hubspot.com/docs/api-reference/crm-properties-v3/guide]

### 2.2 Batch create

`POST /crm/v3/properties/{objectType}/batch/create` — creates many properties in one call. Batch endpoints are capped at 100 records per request; counts as **one** request against rate limits regardless of batch size. [CITED: developers.hubspot.com/docs/api-reference/crm-properties-v3/batch/post-crm-v3-properties-objectType-batch-create] With ~45-65 properties needed (§6), this is 1 batch call per object type, comfortably under the cap.

### 2.3 Property groups

`POST /crm/v3/properties/{objectType}/groups` — body: `name` (unique id), `label` (display name), `displayOrder` (`-1` lets HubSpot choose). [CITED: developers.hubspot.com/docs/api-reference/crm-properties-v3/groups/post-crm-v3-properties-objectType-groups] Recommend one new group per object type, e.g. `lv_enrichment` (companies) and `lv_enrichment_contacts` (contacts), so the ~45-65 new properties don't scatter into `contactinformation`/`companyinformation`.

### 2.4 Read

`GET /crm/v3/properties/{objectType}` (all properties) or `GET /crm/v3/properties/{objectType}/{propertyName}` (one). This is the call the dry-run diff (§4) uses to fetch the actual portal schema. [CITED: same guide]

### 2.5 Field-type change — confirmed irreversible in effect

"Changing an existing property's field type can invalidate current values stored in the property" — official HubSpot knowledge base guidance is to **export all data before editing a field type**. A field type cannot be edited to `Score` or `Calculation`, and vice versa. No documented "undo" for a type change beyond restoring from your own pre-change export. [CITED: knowledge.hubspot.com/properties/create-and-edit-properties] This directly supports criterion 3: `lv_org_type` string→enumeration must **not** happen in this phase.

### 2.6 Archive vs. delete — the load-bearing distinction for rollback

- The API's "delete" operation (`DELETE /crm/v3/properties/{objectType}/{propertyName}`) is documented in HubSpot's own reference as moving the property "to the trash" (German-locale doc text: *"Verschieben Sie eine Eigenschaft... in den Papierkorb"*) — **this is an archive, not a hard delete**, despite the HTTP verb. [CITED: developers.hubspot.de/docs/api-reference/latest/crm/properties/delete-property]
- Archived properties and their **values are retained for 90 days** in an "Archived" tab. Within that window, an admin can restore the property via the UI, or — confirmed by community-reported behavior — **by re-creating a property with the identical internal `name` via the API**: "if you recreate the property using the original property definition within that 90-day period, HubSpot will effectively restore the property along with any previously assigned property values." [CITED: knowledge.hubspot.com/properties/organize-and-export-properties; community-reported API behavior, MEDIUM confidence]
- After 90 days, archived properties are **permanently deleted and cannot be restored** — "properties archived 90+ days ago have been deleted and cannot be restored."
- A true, immediate, irrecoverable delete ("delete permanently" in the UI) is a **separate, explicit action** from archiving, and is documented as non-recoverable.
- **Enumeration option archival** is separate again: archiving an *option* on an enumeration property "prevents those values from being used moving forward, but... doesn't affect records that already contain the value" — i.e., archiving an option is safe for existing data; it just closes the option to future writes.

**Bottom line for this phase:** every property this migration creates can be safely archived (not permanently deleted) if it turns out to be wrong, and — critically — **re-created under the exact same internal name within 90 days restores its data**. This is the mechanism the rollback design in §3 is built on. It is NOT guaranteed by an explicit "restore" API endpoint (none was found in developer docs); it is an empirically-reported side effect of the create endpoint touching an archived-but-not-yet-purged internal record. Treat this as `[CITED, MEDIUM confidence]`, not `[VERIFIED]` — the verification plan in §3.6 proves it empirically against this specific portal before relying on it operationally.

### 2.7 Rate limits

Professional-tier burst limit: **190 requests / 10 seconds** (~19/sec), daily cap ~650,000 requests/day; Search API is separately capped at 4 req/sec. [CITED: developers.hubspot.com/docs/developer-tooling/platform/usage-guidelines] Irrelevant at this migration's scale (1-2 batch calls total) but worth noting for the `search_records` calls the dry-run diff and any per-record backfill will make.

### 2.8 Not found / unresolved in docs

- No documented `PATCH .../restore` or `archived=false` un-archive endpoint at the v3 CRM properties path — restoration is a UI action or the re-create-by-name side effect above.
- No documented hard cap on options-per-enumeration property, or on total custom properties per portal (varies by subscription tier, not stated numerically).
- **PATCH with an unknown property name**: community reports are consistent that this returns 200 and **silently no-ops** rather than erroring — this is the mechanism behind the "HubSpot silently drops unprefixed metadata today" claim used throughout `STATE.md`/spec. [CITED, MEDIUM confidence — re-confirm live in §5.7's baseline call, since a 400 instead would change the risk profile of doing the PN-4 rename before property creation.]

---

## 3. Reversibility & rollback design (first-class section)

This section answers: *if this migration goes wrong, or a later phase needs to undo it, what
exactly can be recovered, in what order, and how do we prove it works without a second live
experiment on the production portal?*

### 3.1 Pre-migration baseline snapshot

Before any mutation, capture the full current schema as a versioned, committed file — this
**is** the rollback target, independent of the undo manifest (which only records what *this
run* created).

- **Format:** `.planning/phases/15-hubspot-property-migration/baseline/portal-schema-{companies,contacts}-{UTC-timestamp}.json` — the raw JSON body of `GET /crm/v3/properties/{objectType}` for both object types, committed to git as-is (no transformation). One file per object type per snapshot run.
- **Capture call:** `GET /crm/v3/properties/companies` and `GET /crm/v3/properties/contacts`, no query params (default excludes HubSpot-internal sensitive properties, which is fine — this project creates none of those). Each property object in the response already includes `name`, `label`, `type`, `fieldType`, `groupName`, `options` (array, empty for non-enumeration), `hubspotDefined` (bool), `createdAt`, `updatedAt`, `archived` (bool) — everything needed to diff against later.
- **When captured:** once, immediately before the first write in this phase, by a `scripts/snapshot_hubspot_schema.py` (read-only, same `_has_credentials()` skip-if-absent idiom as `smoke_closed_won_research.py`). Re-run it again immediately *after* the migration completes, as `...-post.json`, so the diff between pre/post is also committed evidence of exactly what changed.
- **Why committed, not just local:** the baseline is what a rollback script diffs against (§3.4) and what the "prove it worked" step (§3.6) uses. If it lives only on a dev machine, a rollback run six months later by someone else has no baseline.

### 3.2 Per-step reversibility classification

| Step | Classification | Why |
|---|---|---|
| Create a new property group (`lv_enrichment`, `lv_enrichment_contacts`) | **REVERSIBLE** | No data. Archive/delete a group with no properties in it is a clean no-op undo. |
| Create a new custom property (any type, no existing data) | **REVERSIBLE within 90 days** | Archiving it and letting the 90-day window lapse without recreating = true delete. Archiving + recreate-by-name inside 90 days = full restore per §2.6. Classify as reversible, not one-way, but with a **time-boxed** reversibility window — the rollback script (§3.4) must not be shelved for months. |
| Add enum options to an *existing* enumeration property that has no data in those specific new options yet | **REVERSIBLE** | Archiving an unused option does not touch any record's existing value (§2.6). Safe to add speculatively; safe to retract. |
| PN-4 code rename (unprefixed metadata names → `lv_`-prefixed) | **REVERSIBLE in git**, but see §3.3 — coupled to property creation | The code change alone is a plain git revert. The coupling risk is data written under the new names, not the code diff itself. |
| Retiring the ICP write-path (criterion 4) | **REVERSIBLE in git** | Pure code change (policy class + removed dict keys), no schema mutation, no data mutation. A `git revert` fully undoes it. Zero interaction with the property-creation steps — this can be reverted independently at any time. |
| `lv_org_type` text→enumeration type change | **ONE-WAY DOOR — NOT PERFORMED** | Per §2.5, HubSpot's own guidance says a field-type change can invalidate existing values with no documented API-level undo beyond restoring your own pre-change export. Criterion 3 already forbids this in-phase; this research confirms that prohibition is correct, not merely cautious. If ever done later: mandatory full property export first (not just the schema snapshot — the **values**, via `search_records`/export, for every record with a non-blank `lv_org_type`), and explicit human sign-off, per criterion 3. |
| Any other property-type change on an existing property (e.g., changing `lv_produces_content` if it turns out not to already be boolean) | **ONE-WAY DOOR** | Same reasoning as above; not needed by this phase's manifest (§6), which only creates *new* properties and never edits an existing one's `type`. |

**Ordering rule this classification implies:** every step above the "ONE-WAY DOOR" rows is
reversible or time-boxed-reversible; the one-way-door rows are **not scheduled in this
phase at all** — they are explicitly out of scope (criterion 3) and the task sequence in §5
should not even present them as a disabled/gated step, since "not performed" is stronger
than "gated and skipped." If a future phase needs the type change, it inherits this
classification and must run its own export-first procedure — that is out of scope here.

### 3.3 The coupled-rollback trap

The failure mode: properties get created under `lv_`-prefixed names (or the PN-4-renamed
`lv_linkedin_url`/`lv_persona_group`), the pipeline starts writing data to them, and then
*only one side* of the change gets reverted — e.g., a `git revert` of the PN-4 code commit
lands, but the created properties and any data already written to them remain. Now the
portal holds `lv_jobtitle_verified_at` data that nothing in the reverted code reads anymore
(the reverted code reads bare `jobtitle_verified_at` again), and new writes silently start
missing the freshness check again (the exact bug this phase fixes, reintroduced).

**The two partial-failure orderings and their correct recovery:**

1. **Code reverted, properties still exist (most likely accidental state — a bad code
   deploy gets rolled back faster than anyone remembers the portal side).** Recovery: do
   **not** touch the properties. They are inert (nothing writes to them with the old code
   active) and harmless. Either re-apply the code forward again once it's fixed, or run the
   property rollback script (§3.4) to archive them cleanly. Never delete data-bearing
   properties as a reflex — check `GET` on each property's fill rate first.
2. **Properties rolled back (archived), code still writes the new names (the more
   dangerous ordering — this is a live data-loss path).** Recovery: this must be
   **prevented, not recovered from** — see the gate below. If it happens anyway: every
   write to an archived property name is a silent no-op (§2.8), so no new data is lost, but
   any writes made in the gap between archival and detection are gone forever (archiving
   does not queue-and-replay). Immediately halt the pipeline (flip `ALLOW_CANONICAL_WRITES`
   / `ALLOW_STAGING_WRITES` to `false`), THEN restore the properties by re-creating them
   under the identical names from the baseline snapshot (§2.6's 90-day mechanism), THEN
   re-enable writes.

**The gate that keeps this coupling from ever binding:** sequence property creation
strictly **before** the PN-4 code deploy, never the reverse, and treat "properties exist
and are confirmed via a post-creation `GET`" as a hard precondition the code-deploy task
checks (or is simply ordered after, per §5). Additionally, keep `ALLOW_CANONICAL_WRITES=
false` and `ALLOW_STAGING_WRITES=false` (or the n8n Cloud production workflows left
un-activated) for the **entire duration** of this phase's tasks — this phase is schema-only;
no task in it should flip those gates to `true` against the live portal. That single rule
means the coupling window (properties exist + code writes to them) never opens during this
phase at all; it only opens later, when Phase 16 or a production rollout turns writes on
against an already-stable, already-verified schema.

### 3.4 Rollback runbook + script

`scripts/rollback_property_migration.py` — same idiom as `scripts/smoke_closed_won_research.py`
(env-gated, non-gating, dry-run-by-default, `_has_credentials()` skip-to-exit-0 when
credentials are absent so it is safe in CI/no-key environments):

```
Usage:
    python scripts/rollback_property_migration.py [--live] [--manifest PATH] [--baseline PATH]

Behavior:
    1. Load the undo manifest (§4.2) written by the forward migration — the list of
       property names + object types + property group names THIS RUN created.
    2. Load the baseline snapshot(s) from §3.1.
    3. Refuse to run if either file is missing (no manifest = nothing to safely undo;
       guessing from a schema diff alone risks archiving something another workflow
       created independently in the interim).
    4. For each property in the manifest: confirm live GET still shows it exists and
       is NOT hubspotDefined (belt-and-braces — never touch a native property even if
       a manifest were somehow corrupted to list one).
    5. Report a would-archive list (dry run, default). Only with --live and a second
       explicit "yes" typed at a confirmation prompt does it call DELETE (archive) on
       each property in the manifest, in REVERSE creation order (metadata properties
       before their parent canonical property, staging before canonical — mirrors
       §5's forward order, reversed).
    6. Re-fetch GET /crm/v3/properties/{objectType} and diff against the baseline
       snapshot; print any remaining discrepancy (should be empty — anything left
       over was not created by this migration and is out of scope for this script
       to touch).
    7. Never touches property GROUPS unless they end up with zero remaining
       properties after the property archival — then archives the empty group too.
    8. Refuses (hard error, not a warning) to archive anything not present in the
       manifest, even if --live is passed — this is the "refuses to touch anything
       not in the manifest" requirement, enforced structurally, not by convention.
```

**Human runbook (the operational decision, not just the script):**

1. **Decide to roll back when:** the post-migration `GET` diff (§3.6) shows an unexpected
   shape (wrong type landed, wrong option set, a property the manifest didn't intend), OR
   a downstream phase discovers the schema is wrong before any real enrichment data has
   been written to the new properties (the "no data yet" condition is what keeps this
   cheap — once real data accumulates, rolling back destroys work, so decide fast).
2. **What to run:** `python scripts/rollback_property_migration.py` (dry run) first, read
   the printed diff, confirm it matches expectations, then re-run with `--live`.
3. **How to verify:** re-run `scripts/snapshot_hubspot_schema.py` and diff the output
   against the pre-migration baseline file — an empty diff is the acceptance bar.

### 3.5 What is genuinely NOT reversible, stated plainly

- A property-**type** change on a property that already has data (§2.5, §3.2) — not
  attempted by this phase, and this research is the citation for why it must stay that way
  without explicit sign-off.
- Any write that lands during the narrow coupled-rollback window described in §3.3(2) —
  archiving a property does not retroactively recover writes made to it in the seconds
  before archival if the write itself never reached HubSpot (e.g., it 400'd and was
  swallowed) — though ordinary successful writes to an about-to-be-archived property ARE
  retained per §2.6 and do come back on restore. The genuinely unrecoverable case is data
  that a **currently-broken** write path failed to persist in the first place, which
  rollback tooling cannot help with by definition.
- Permanent deletion (the UI's explicit "delete permanently", or an archived property left
  past 90 days) — by design, and this script never performs it.

### 3.6 Verifying rollback works, without destroying the portal

Two-tier proof, matching the instruction to prove it without a destructive test:

1. **Offline (no live call):** unit tests for `rollback_property_migration.py`'s manifest
   parsing, the "refuse if manifest/baseline missing" guard, the "refuse to touch anything
   not in the manifest" guard, and the reverse-order archival sequencing — all pure
   function tests against fixture manifests/baselines, no network. Mirrors the existing
   pattern in `tests/test_merge_policy.py`/`tests/test_main.py` (monkeypatch `requests.*`
   to raise if ever called, proving no live call happens in dry-run).
2. **Live canary (the one genuinely necessary live proof):** create exactly one throwaway
   property, `lv_rollback_canary_{timestamp}`, on the `companies` object type, of type
   `string` — the cheapest, most inert type — with no data written to it. Run the rollback
   script's `--live` path against a manifest containing only that one property. Assert via
   `GET /crm/v3/properties/companies/lv_rollback_canary_{timestamp}` that it now reports
   archived (or is absent from the default non-archived listing). This single canary proves
   the archive-call mechanics work against this specific portal without touching any
   property this phase actually needs, and without waiting 90 days to prove the "recreate
   restores data" claim (that specific claim stays `[CITED, MEDIUM confidence]` — it is
   consistent with official docs and community reports, and low-risk to rely on given the
   90-day safety margin, but proving it definitively would require creating a canary with
   real data, archiving it, waiting, and recreating it, which is out of proportion to this
   phase's timeline; document as an accepted residual risk, not a blocking unknown).

---

## 4. Safe-migration design (forward migration)

`scripts/sync_hubspot_properties.py` — the tool that performs the actual creation, built on
the same idioms as `hubspot_client.py`'s dry-run gating and `smoke_closed_won_research.py`'s
credential-gating:

- **Desired schema, in code, not guesswork:** a new `config/hubspot_properties.yaml`
  (or reuse `field_policy.yaml`'s structure with an added `hubspot_type`/`hubspot_field_type`/
  `options` per entry) is the single source of truth for what SHOULD exist — generated once
  from the manifest in §6, then hand-maintained going forward exactly like `taxonomy.yaml`
  is for org types (same "edit config, rebuild, resync" idiom already established in this
  repo, per `docs/WEB-RESEARCH-SPEC.md` §2's "Adding a value later" pattern).
- **Dry-run diff:** default mode. `GET` the actual portal schema for both object types,
  compute `desired - actual` (properties to create), `actual ∩ desired with a type/options
  mismatch` (drift to report, never auto-fix — this is where a human decides whether e.g. an
  existing `lv_produces_content` really is boolean), and print both, changing nothing.
- **Idempotency:** re-running with no schema changes must be a pure no-op — the diff against
  live `GET` output makes this automatic (nothing to create if everything already matches),
  rather than requiring a separate "already ran" flag. This also means the script is safe to
  re-run after a partial failure (network blip mid-batch) — it picks up exactly where it left
  off because it always re-derives "missing" from a fresh `GET`, never from local state.
- **Undo manifest:** every property/group actually created during a `--live` run is appended
  to `.planning/phases/15-hubspot-property-migration/undo-manifest-{run_id}.json` — object
  type, property name, group name, and the exact request body sent — write manifest entries
  only for confirmed 201 responses (never before the API call returns), so the manifest
  never claims something exists that doesn't. This file, plus the baseline (§3.1), are the
  two inputs `rollback_property_migration.py` needs.
- **Confirmation gate for anything irreversible:** since this phase's manifest (§6) contains
  zero type changes and zero edits to existing properties, no task in this phase needs a
  destructive-action confirmation prompt at all — every create-only action is reversible per
  §3.2. Reserve the confirmation-gate pattern (explicit typed "yes", per `ALLOW_*` env flag
  off by default) for the rollback script's `--live` archive path instead (§3.4), where the
  action, while reversible, is still a live mutation with a 90-day clock.
- **Env-gate idiom, consistent with `.env.example`:** add
  `ALLOW_HUBSPOT_PROPERTY_WRITES=false` (new, off by default) and reuse the existing
  `DRY_RUN=true` default. The script refuses to make any `POST`/`DELETE` call unless BOTH
  `DRY_RUN=false` AND `ALLOW_HUBSPOT_PROPERTY_WRITES=true` are set — a deliberate two-key
  gate (stronger than the single `DRY_RUN` gate `patch_record` uses today) because this is
  the first schema-mutating script in the repo, not a record-data write.

---

## 5. Ordering / dependency risk and task sequence

### 5.1 Does retiring the ICP write paths (criterion 4) interact with property creation (criterion 1)?

**No structural interaction.** Criterion 4 is a pure code change (policy classes + a dict
literal), touching zero HubSpot schema. It can be sequenced anywhere relative to property
creation without risk — including first, since it shrinks the property manifest (nothing
needs to be created for `lv_icp_fit_score`/`lv_icp_tier`/etc. metadata, because they're
already-existing placeholder properties per the portal audit and the pipeline is about to
stop writing to them anyway).

### 5.2 Does the PN-4 rename need to land before or after property creation?

**After — property creation first, code rename second**, for the reason in §3.3: if the
rename lands first, the code starts requesting writes to `lv_jobtitle_verified_at` etc.
before those properties exist, and every one of those writes silently no-ops (§2.8) — not
dangerous, but it means the staleness gate (`enrichmentGate.js`) reads `undefined` for the
new name too, functionally identical to today's bug, just renamed. Creating the properties
first means the rename, when it lands, immediately starts working correctly with no gap.

### 5.3 Proposed task order (schema-only phase; no live writes flipped on)

1. **Task 0 (safety):** Snapshot the live portal schema, both object types → commit as the
   baseline (§3.1). Read-only; can run before anything else, at any time, repeatably.
2. **Task 1:** Build `config/hubspot_properties.yaml` (or extend `field_policy.yaml`) from
   the manifest in §6 — the desired-state config. Pure code, offline, fully testable.
3. **Task 2:** Build `scripts/sync_hubspot_properties.py` with the dry-run diff (§4). Test
   offline against a fixture "actual portal" JSON and the fixture desired-state config.
4. **Task 3:** Retire the 5 ICP write-path call sites + 3 test assertions (criterion 4,
   §1.1's corrected line numbers). Pure code + tests, zero portal interaction, zero
   dependency on tasks 1-2 — can run in parallel with them.
5. **Task 4:** Run the dry-run diff live (read-only `GET` calls) against the real portal;
   human reviews the printed create-list against §6 before proceeding.
6. **Task 5 (the one live-mutating task):** Run `sync_hubspot_properties.py --live` (gated
   by the two-key env gate, §4) to create the property groups + all new properties in one
   or two batch calls (§2.2). Confirms writes via a fresh `GET`, writes the undo manifest.
7. **Task 6:** PN-3/PN-4 code rename — the metadata stampers, `enrichmentGate.js` reads, the
   `build_cloud_workflows.py` hardcoded search-property lists, and the `linkedin_url`/
   `persona_group` canonical-field rename (§7). This is the **first task allowed to depend
   on Task 5 having succeeded** — sequence it strictly after.
8. **Task 7:** Build `scripts/rollback_property_migration.py` (§3.4) + its offline tests.
   Can technically happen any time after Task 5 produces a manifest shape to test against,
   but doing it as its own task keeps the diff reviewable and keeps Task 5 from growing into
   "creation + rollback tooling" as one unreviewable unit.
9. **Task 8 (verification):** Live canary rollback proof (§3.6) — create/archive
   `lv_rollback_canary_*`, assert it worked. The only other live-mutating task in this phase,
   deliberately isolated from the real property set.
10. **Task 9:** Full test suite green, `git diff` review of every renamed identifier,
    `docs/WEB-RESEARCH-SPEC.md`/`STATE.md` updated to reflect RT-5 unblocked and the
    write-path retirement, ROADMAP Phase 15 checked off.

**Never left half-migrated:** at every task boundary above, the portal is in a
self-consistent state — either "old properties, old code" (before Task 5) or "new properties
exist, old code still uses old names" (between Task 5 and Task 6, functionally identical to
today, just with more unused properties sitting empty) or "new properties exist, new code
uses new names" (after Task 6). There is no state where code writes to names that don't
exist yet, because Task 6 never runs before Task 5 completes.

### 5.4 The one-way doors stay last, individually gated — but there are none in this phase

Per §3.2's classification, this phase's manifest contains no type changes and no edits to
existing properties — every task above is reversible or time-boxed-reversible. The
one-way-door row (`lv_org_type` enumeration conversion) is not scheduled at all (criterion
3), consistent with "one-way doors last and individually gated" degenerating to "not present
in this phase's task list."

### 5.5 Live confirmation call required before Task 0 is trusted

Task 0's snapshot is only as good as the assumption that the portal still matches the
2026-07-20 audit (5 existing custom company properties, 11 third-party contact properties,
`lv_org_type` as string/text). Confirm this with the live `GET` in Task 0 itself — if the
snapshot disagrees with the cited STATE.md facts, halt and report before Task 1 builds a
desired-state config against stale assumptions.

---

## 6. Full derived property manifest (grouped, counted)

Derived from the **actual production call sites**, not the CLAUDE.md §7/§8 spec tables
(which describe a per-raw-provider staging design the companies branch no longer uses — see
§7.1 for why). Traced to: `scripts/build_cloud_workflows.py` `ENRICH_MERGE_CO` (companies,
lines ~1504-1583), `ENRICH_MERGE` (contacts enrichment, lines ~679-693), `MERGE_CONTACTS`
(contacts ingest, lines ~217-230), `n8n/code/mergeCompanies.js`/`mergeContacts.js` metadata
stampers, and `field_policy.yaml`/`provider_priority.yaml` for policy-declared but
not-yet-wired fields (flagged separately, §6.4).

### 6.1 Companies — canonical INPUT fields (Approach C, pipeline-writable)

| Field | Portal state today | Action |
|---|---|---|
| `lv_org_type` | Exists (text/string) | none — already present |
| `lv_produces_content` | Exists (type unconfirmed — verify in Task 0) | none — already present |
| `lv_content_type` | Missing | **CREATE** (recommend `enumeration`/checkbox — multi-select, taxonomy-driven, brand new so no type-change risk) |
| `lv_revenue_band` | Missing | **CREATE** (`enumeration`/select) |
| `lv_employee_band` | Missing | **CREATE** (`enumeration`/select) |
| `lv_country_region_normalized` | Missing | **CREATE** (`enumeration`/select) — **note:** no explicit `field_policy.yaml` entry exists for this field (falls through to the default `fill_blank_only` policy at merge time in both `merge_policy.py` and `mergeCompanies.js`) — flagged as an open question, §12. |
| `lv_is_hardware_vendor` | Missing | **CREATE** (`bool`/checkbox) |
| `lv_is_gambling_operator` | Missing | **CREATE** (`bool`/checkbox) |
| `lv_sponsorship_reliant` | Missing | **CREATE** (`bool`/checkbox) — **note:** field_policy/provider_priority declare it, but the production `ENRICH_MERGE_CO` researchData loop (`build_cloud_workflows.py` ~line 1575) does NOT copy `lv_sponsorship_reliant` from the research candidate into the merge call — it is requested from Claude web research (`web_research.py` REQUIRED_FIELDS) but never actually reaches HubSpot today. Creating the property now is still correct (batch it in) but the wrapper bug is a separate, cheap follow-up flagged in §9. |

**New canonical company properties: 7.**

### 6.2 Companies — staging properties (PN-3), traced to actual `source` values used

The companies branch does **not** stage per-raw-provider (`zoominfo`/`apollo`/`lusha`)
values directly — `ENRICH_MERGE_CO` calls `scoreCandidates` first (winner-take-all across
the 3 firmographic providers), then calls `mergeCompanies(...)` **twice**: once with
`source: "waterfall"` for the scored firmographic winner, once with `source: "claude_web"`
for the research candidate. So the actual staging property namespace is:

| Staging property | Populated from |
|---|---|
| `lv_waterfall_domain` | scored winner across zoominfo/apollo/lusha |
| `lv_waterfall_industry` | scored winner (native `industry` field) |
| `lv_waterfall_revenue_band` | scored winner |
| `lv_waterfall_employee_band` | scored winner |
| `lv_waterfall_country_region_normalized` | scored winner |
| `lv_claude_web_org_type` | research candidate |
| `lv_claude_web_produces_content` | research candidate |
| `lv_claude_web_content_type` | research candidate |
| `lv_claude_web_is_hardware_vendor` | research candidate |
| `lv_claude_web_is_gambling_operator` | research candidate |

**New staging company properties: 10** (not the 36-property raw-provider cross-product a
literal reading of CLAUDE.md §7.1/PN-3's example table would suggest — see §7.1). Note
`lv_claude_web_sponsorship_reliant` is absent from this list for the same wrapper-bug
reason as §6.1's last row — add it only if that wrapper bug is fixed in the same phase
(recommend: yes, one-line addition to the `researchData` field loop, cheap to batch in now
rather than a third live migration later; flagged as a discretionary addition, §9).

### 6.3 Companies — metadata properties (PN-4), per canonical INPUT field

Production (`n8n/code/mergeCompanies.js`) emits **5 suffixes** per field with a chosen
candidate: `_source`, `_confidence`, `_verified_at`, `_validation_status`, and
`_evidence_url` (conditional on an evidence map entry existing for that field — in practice
populated for `lv_org_type`/`lv_produces_content` only, since those are the two fields
`field_policy.yaml` marks `require_evidence_url`/`require_evidence_url_for`, and
`ENRICH_MERGE_CO` is the only call site that passes an `opts.evidence` map).

Recommend creating `_evidence_url` for **all 9** input fields uniformly rather than a 2-field
carve-out — it's a cheap, empty, harmless property for the 7 fields that never populate it
today, and it means a future field_policy edit adding evidence-gating to e.g.
`lv_is_hardware_vendor` doesn't require a second property-creation cycle.

9 fields × 5 suffixes = **45 metadata properties** (companies).

The Python oracle (`src/merge_policy.py source_metadata()`) additionally emits
`_source_detail` and `_evidence_summary` — 2 suffixes PN-4's own spec text doesn't name and
the JS production stamper doesn't emit. Since the Python harness is capable of live writes
(§1.4), recommend creating these 2 extra suffixes for the 9 fields too (+18), so the two
code paths (n8n Cloud production, Python local harness) never diverge on what the portal
accepts — flagged as a discretionary batch-now decision, §12.

**Total company metadata properties: 45 (spec-minimum) or 63 (including the Python-only
suffixes) — recommend 63, batched now.**

### 6.4 Contacts — canonical field renames + metadata (PN-1/PN-4)

| Field | Portal state | Action |
|---|---|---|
| `lv_linkedin_url` (renamed from unprefixed `linkedin_url`) | Missing under either name | **CREATE + code-wide rename** (§7.2) |
| `lv_persona_group` (renamed from unprefixed `persona_group`) | Missing under either name | **CREATE + code-wide rename** (§7.2) — **note:** like `lv_sponsorship_reliant`, `persona_group` is declared in `field_policy.yaml`/`mergeContacts.js` policy but the production `ENRICH_MERGE` wrapper's candidate loop (`build_cloud_workflows.py` ~line 687) does not copy it from `winners` — same class of wrapper gap, same recommendation (create the property regardless; fixing the wrapper is a one-line follow-up). |
| `lv_jobtitle_verified_at` | Missing (unprefixed `jobtitle_verified_at` read today) | **CREATE + PN-4 rename** — this is criterion 6's exact target, confirmed live-read by the staleness gate (`build_cloud_workflows.py:645-646`) and the HubSpot search property list (`:1081`). |
| `lv_mobilephone_verified_at` | Missing (unprefixed `mobilephone_verified_at` read today) | **CREATE + PN-4 rename** — same confirmation. |

**These are the exact 4 properties ROADMAP criterion 6 names — confirmed correct, with the
added finding that 2 of the 4 require a canonical-field-name code change, not merely a new
metadata property.**

Full contact metadata set (all 7 contact fields with a `field_policy.yaml` entry — `phone`,
`mobilephone`, `jobtitle`, `linkedin_url`→`lv_linkedin_url`, `seniority`,
`persona_group`→`lv_persona_group`, plus `email` which is `manual_protected`/stage-only but
still gets staged+metadata per `mergeContacts.js`'s uniform stamper) × the same 5 JS-emitted
suffixes = **35 metadata properties** (contacts), of which criterion 6 explicitly names 2
(`_verified_at` for jobtitle/mobilephone) as currently missing and blocking. The other 33
follow the same "doesn't exist yet, HubSpot silently drops today" pattern per the portal
audit.

### 6.5 Contacts — staging properties (PN-3)

Two `source` values in production: `"csv"` (`MERGE_CONTACTS`, ingest path, fields `email`,
`firstname`, `lastname`, `jobtitle`, `linkedin_url`, `company`, `phone`) and `"waterfall"`
(`ENRICH_MERGE`, enrichment path, fields `email`, `mobilephone`, `phone`, `jobtitle`,
`seniority`, `linkedin_url`). Union of fields across both paths: `email`, `firstname`,
`lastname`, `jobtitle`, `linkedin_url`, `company`, `phone`, `mobilephone`, `seniority` — 9
fields × 2 sources = up to **18 staging properties**, though `firstname`/`lastname`/`company`
staging (raw CSV passthrough of identity fields already captured natively) is low-value —
flagged as a discretionary trim in §12 rather than assumed necessary.

### 6.6 Total new property count (recommended, batched)

| Group | Count |
|---|---|
| Company canonical (new) | 7 |
| Company staging | 10 (+1 if `lv_claude_web_sponsorship_reliant` wrapper fix lands same-phase) |
| Company metadata | 45–63 (recommend 63) |
| Contact canonical rename+create | 2 (`lv_linkedin_url`, `lv_persona_group`) |
| Contact metadata | 35 |
| Contact staging | up to 18 (recommend trimming `firstname`/`lastname`/`company`, landing ~12) |
| Property groups | 2 (`lv_enrichment`, `lv_enrichment_contacts`) |
| **Total** | **~121–145 properties + 2 groups**, comfortably inside one or two `batch/create` calls (100/request cap, §2.2) |

This is meaningfully larger than the "~40+" the task brief estimated — the difference is
almost entirely the metadata-suffix multiplication (9 company + 9 contact fields × 5-7
suffixes each), which the brief's "40+" language likely under-counted. Batching in one or
two calls per object type keeps this cheap regardless of the exact final count.

---

## 7. PN-3 / PN-4 naming rename impact — three distinct findings

### 7.1 Finding 1: PN-3's spec example doesn't match the companies branch's actual design

`docs/WEB-RESEARCH-SPEC.md` §0.6 PN-3 gives `lv_zoominfo_revenue_band` as the canonical
example of a staging property name. The actual companies pipeline (Phase 11's
`scoreCandidates`/winner-take-all design) never stages a raw per-provider value under its
own provider name for company fields — it stages the **scored winner** under
`source: "waterfall"`, and the **research candidate** under `source: "claude_web"` (§6.2).
"Waterfall" is not a registered source in `config/source_registry.yaml` (which only lists
`hubspot, zoominfo, apollo, lusha, claude_web, haiku, sonnet_5, human`). This is not a bug —
it is a legitimate design choice (conflict detection needs a single scored winner, not 3
raw candidates fighting for the same canonical slot) — but the spec's own example doesn't
describe the shipped system. Recommend: either (a) treat `waterfall` as an accepted 9th
source-registry entry (one-line YAML addition, essentially free to include in this phase's
code-rename task), or (b) leave `source_registry.yaml` as pure documentation of provider
trust ranks (not an enforced enum) and note the gap. Flagged as an open question for the
planner to resolve with the user, §12.

### 7.2 Finding 2: `linkedin_url`/`persona_group` need a canonical rename, not just new metadata

Confirmed in §1.3/§6.4 — full list of files touched by this rename:
`config/field_policy.yaml:133,144` (dict keys), `config/provider_priority.yaml:29,31` (dict
keys), `n8n/code/mergeContacts.js:20,22` (`DEFAULT_CONTACT_POLICY` keys),
`scripts/build_cloud_workflows.py:224` (`MERGE_CONTACTS` candidate field-name array),
`:629` (LOCAL mock fixture property name), `:687` (`ENRICH_MERGE` candidate field-name
array), and the HubSpot search property list at `:1081`/`:645-646`-adjacent code (add
`lv_linkedin_url`/`lv_persona_group` alongside the two `_verified_at` renames if a staleness
policy is ever added for them — none exists today, so no staleness read to rename for these
two specifically). **Not touched:** `scripts/build_cloud_workflows.py:1062`
(`id.linkedin_url` inside `identity_keys` — this is a request-shape field feeding the Lusha
lookup query, not a HubSpot property; leave unprefixed, it never round-trips to the CRM).

### 7.3 Finding 3: Python oracle emits 2 metadata suffixes the JS production stamper does not

`src/merge_policy.py`'s `source_metadata()` emits `_source_detail` (a JSON blob of match
basis + evidence URLs + model trace) and `_evidence_summary`, neither of which
`n8n/code/mergeCompanies.js`/`mergeContacts.js`'s `meta` object produces. PN-4's own spec
text lists only the 5 suffixes JS emits. This is either (a) an intentional scope difference
(the Python harness is richer because it's a dev/audit tool, not because production needs
the extra fields) or (b) a JS stamper gap that should eventually get the same 2 fields for
feature parity. Recommend creating the properties for both (§6.3) since the Python harness
can write live (§1.4) and an un-created property there means the identical silent-drop
failure mode this whole phase exists to fix — but do not change either stamper's code in
this phase (out of scope; a stamper-parity change is a Phase-13/14-style code change, not a
migration).

---

## 8. `lv_icp_tier` enum-options bug — verdict

**Moot for this phase.** The bug (`lv_icp_tier`'s HubSpot enum only allows `A/B/C/D`, but
`icp_scoring.py` can emit `Unscored`/`Needs Review`) only manifests when something writes
`lv_icp_tier` to HubSpot with one of those two out-of-enum values. Criterion 4 retires the
pipeline's write path to `lv_icp_tier` entirely (Approach C — HubSpot derives it). After
this phase, nothing in the pipeline ever attempts that write, so the enum-mismatch 400
never fires in production. **No enum-options fix is needed in this phase.**

It remains a live fact worth carrying forward (already recorded in `STATE.md`) for whoever
eventually authors the real HubSpot-side tier formula: if that formula is ever expressed in
a way that can produce `Unscored`/`Needs Review` as a tier value, it will hit this same
400 unless the enum is widened first, or the formula is designed to only ever emit
`A/B/C/D` (e.g., treating "insufficient data" as a 5th explicit option added at that time,
or simply defaulting to a blank/unscored state rather than a labeled tier). That is squarely
downstream, out-of-milestone work per the existing scope fence — not touched here.

Similarly, the separately-tracked **scoring-precedence bug**
(`src/icp_scoring.py:116` — a fired hard veto's tier label can be overwritten by the
confidence-downgrade block) is now **provably inert in production** once criterion 4 lands:
the STATE.md note itself says the only live exposure was via `main.py`'s
`ALLOW_ICP_SCORE_WRITES`-gated promotion of `canonical_patch["lv_icp_tier"]`, which criterion
4 removes. Recommend: **do not fix it in this phase either.** The one-line fix is safe and
zero-blast-radius per the existing analysis, but fixing dead code inside a phase whose whole
purpose is "touch the live portal safely" adds an unrelated diff to review under time
pressure, for a bug that (per this phase's own criterion 4) is about to stop being
reachable. Leave the STATE.md note as-is, pointing future authors of the HubSpot-side
formula at the correct precedence rule (hard-veto label wins over confidence downgrade) as
a **spec-by-example** requirement, exactly as the existing note already frames it.

---

## 9. Risk register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| ROADMAP line-number references are stale (confirmed 3 of 11 references drifted, §1) | Confirmed | Plan tasks miss their target if line numbers are trusted literally | Re-grep at execution time using the string anchors in §1/§7, not line numbers |
| PN-3 "waterfall"/"claude_web" source naming isn't in `source_registry.yaml` | Confirmed gap | Low — cosmetic/documentation drift, not a runtime bug | One-line addition to `source_registry.yaml`, bundle into the rename task or flag as a follow-up |
| `lv_sponsorship_reliant` / `persona_group` requested/declared but never wired into the production merge candidate loop | Confirmed (code-verified) | Medium — property gets created but stays permanently empty until the wrapper is fixed | Flag to user; cheap one-line fix in `build_cloud_workflows.py`'s field-name arrays, but it's a Phase-13/14-style logic change, arguably out of this migration phase's scope — decide explicitly rather than silently bundling |
| No explicit `field_policy.yaml` entry for `lv_country_region_normalized` | Confirmed gap | Low-medium — falls to default `fill_blank_only` policy, may behave unexpectedly since `icp_scoring.py` reads it directly for the geography/hard-veto calculation | Flag as an open question; likely wants `system_owned` like its sibling ICP inputs |
| "Silently drops unknown PATCH properties" is `[CITED, MEDIUM]`, not independently re-verified live this session | Low | High if wrong — if HubSpot instead 400s on an unknown property in a batch PATCH, the *entire* patch for that record could fail today, a worse bug than assumed | Task 0's live snapshot call should also include a one-record live PATCH-with-unknown-property probe (using a designated test record, `TEST_COMPANY_IDS`) before relying on "it's just silently dropped" |
| The 90-day archive-then-recreate restore mechanism is community-reported, not an explicit documented API guarantee | Low (this phase never actually needs to invoke it in anger — no task creates data before this phase ends) | Medium if it doesn't work as described during a real future rollback | Canary proof (§3.6) validates the archive mechanics; the specific "recreate restores data" claim is accepted as residual risk, clearly labeled, not blocking |
| Manifest size (~121-145 properties) is much larger than the task brief's "~40+" estimate | Confirmed | Low — batch/create's 100-per-call cap means 2 calls instead of 1, no real cost increase | Note the corrected count to the user; doesn't change the design, just the batch count |

---

## 10. Test plan

**Offline (no credentials required, run in every CI pass):**
- `config/hubspot_properties.yaml` (or extended `field_policy.yaml`) parses and every entry
  has a valid `type`/`fieldType` pair; enumeration entries have a non-empty `options` list.
- `sync_hubspot_properties.py`'s diff function: given a fixture "actual portal" JSON and the
  desired-state config, correctly computes the create-list, correctly identifies drift on
  matching-name-mismatching-type entries, and never proposes touching a `hubspotDefined`
  property.
- `sync_hubspot_properties.py` dry-run mode never calls `requests.post`/`requests.delete`
  (monkeypatch to raise, mirroring `tests/test_main.py`'s `no_http` pattern).
- Undo-manifest writer: only records entries for confirmed 201 responses (fixture a mixed
  201/400 batch response, assert the manifest only contains the 201 half).
- `rollback_property_migration.py`: refuses without both manifest+baseline present; refuses
  to touch a property absent from the manifest even when it's present in a supplied "actual
  portal" fixture; reverse-order archival sequencing test; the diff-against-baseline
  reporting function.
- Criterion 4's 3 test-assertion flips (`test_merge_policy.py:196-197`,
  `test_main.py:60-61,85`) — updated to assert `lv_icp_fit_score`/`lv_icp_tier` are **absent**
  from `canonical_patch`/`patch`, proving the write path is actually gone, not just that the
  policy YAML changed.
- PN-4 rename: `enrichmentGate.js` staleness test fixtures updated to use
  `lv_jobtitle_verified_at`/`lv_mobilephone_verified_at`; a regression test asserting the OLD
  unprefixed keys are no longer read anywhere (grep-based architecture guard, consistent
  with the existing `tests/test_architecture_guard.py` pattern in this repo).

**Requires live credentials (human-run, non-gating, `_has_credentials()`-skipped in CI):**
- Task 0's baseline snapshot itself (read-only `GET`).
- The unknown-property-PATCH probe (§9's risk mitigation) against one designated test
  record.
- The dry-run diff against the real portal (Task 4) — still read-only.
- The actual `--live` property/group creation (Task 5) — the one truly necessary live
  mutation in the forward direction.
- The canary rollback proof (Task 8, §3.6) — the one truly necessary live mutation in the
  reverse direction.

---

## 11. Explicitly out of scope (this phase)

- **SJ-1/SJ-2/SJ-3 scheduled-job wiring** and their acceptance tests — `docs/WEB-RESEARCH-SPEC.md`
  §0.7 explicitly defers these to Phase 16, and this phase only needs to make the properties
  those predicates will key on **exist** (which it does, §6.1/§6.3's `_verified_at` fields).
- **§22.2 review-loop wiring** (flag → decision JSON → RevOps approve → apply → clear) — Phase
  16 per ROADMAP. Whether Phase 15 should nonetheless pre-create the 9 review-surface
  properties (`enrichment_needs_review`, `enrichment_review_reason`,
  `enrichment_review_candidate_json`, `enrichment_review_approved`, `enrichment_reviewed_by`,
  `enrichment_reviewed_at`, `lv_icp_needs_review`, `lv_anti_icp_reason`,
  `lv_icp_score_breakdown`) as inert schema now — batching all live-portal touches into one
  migration rather than two — is a genuine open question for the user, not resolved by this
  research (ROADMAP Phase 16 criterion 3 itself is ambiguous: "created in Phase 15 or here").
  Recommend batching them into this phase's manifest since 3 of the 9 are HubSpot-derived
  outputs the pipeline will never write (so creating them now is zero-risk placeholder
  schema, not a premature commitment to Phase 16's wiring logic) — but this is Claude's
  discretion to raise, not a decision this research makes unilaterally.
- **Cloud-template companies-branch port** — out of scope per the task brief; this research
  treats `scripts/build_cloud_workflows.py` purely as a read source for what property names
  the shipped workflows actually reference, not as something this phase edits structurally.
- **HubSpot-side tier-formula authoring** (`lv_icp_fit_score`/`lv_icp_tier`'s real
  calculation, currently the `1+1` placeholder) — explicitly downstream, out of Milestone 3
  per the existing Approach C decision.
- **The `lv_org_type` text→enumeration type change** — explicitly forbidden without sign-off
  by criterion 3; this research confirms why (§2.5) and does not design around it.
- **Fixing the `lv_sponsorship_reliant`/`persona_group` merge-wrapper gaps** (§6.1, §6.4) —
  flagged as a discovered issue, not fixed here; it's a `build_cloud_workflows.py` logic
  change (Phase-13/14 territory), not a schema-migration task.

---

## 12. Assumptions log

| # | Claim | Section | Risk if wrong |
|---|---|---|---|
| A1 | Portal 22617666 still has exactly the 5 custom company properties / 11 third-party contact properties the 2026-07-20 audit recorded, and `lv_org_type` is still string/text | §1, §5.5 | If the portal has since changed (e.g., someone manually added a property), the dry-run diff will simply show it — self-correcting by design (Task 0), but the desired-state config built in Task 1 should be reviewed against Task 0's fresh snapshot, not blindly against this document |
| A2 | Unknown-property PATCH calls are silently ignored (200/204, no error), not rejected | §2.8, §9 | If wrong, a batch PATCH containing an unrecognized property name could fail the entire request today — a worse bug than the codebase currently assumes; verify with a live single-record probe in Task 0 |
| A3 | Archiving a HubSpot property, then re-creating it with the identical internal name within 90 days, restores its prior values | §2.6, §3.6 | This is the entire mechanism the rollback design leans on; if false, "rollback" only restores schema, never data — mitigated by never letting real data accumulate on these properties during this phase (§3.3's gate) |
| A4 | `options` array schema for enumeration properties is `{label, value, displayOrder, hidden, description}` | §2.1 | Sourced from a search-engine synthesis of community/blog content, not a direct doc fetch (the official page's redirect prevented a direct read); low risk since Task 2's offline tests will fail immediately against a real API error if the shape is wrong, before any live call |
| A5 | Recommending 63 (not 45) company metadata properties and ~12 (not 18) contact staging properties, trimming low-value CSV-identity-passthrough staging | §6.3, §6.5 | Purely a scope-sizing judgment call for the planner to accept or override; either choice is reversible (§3.2) so the cost of guessing wrong is low |
| A6 | `waterfall` is an acceptable PN-3 `<provider>` token even though it's undocumented in `source_registry.yaml` | §7.1 | Cosmetic; if the user wants strict PN-3 compliance, this becomes a small additional rename task (map `waterfall`→ one of the 3 real provider names per-record, which the current winner-take-all design deliberately does NOT preserve) |

---

## Validation Architecture

### Test framework

| Property | Value |
|---|---|
| Framework | pytest (existing, `tests/`) |
| Config file | none dedicated — repo runs `pytest` from root (see `tests/test_scaffold.py` for the convention) |
| Quick run command | `pytest tests/test_merge_policy.py tests/test_main.py -x` (the 3 flipped assertions) |
| Full suite command | `pytest` |

### Phase requirements → test map

| Req | Behavior | Test type | Command | File exists? |
|---|---|---|---|---|
| Criterion 1 | Dry-run diff computes correct create-list; undo manifest records only confirmed creates | unit | `pytest tests/test_sync_hubspot_properties.py -x` | ❌ Wave 0 |
| Criterion 3 | No task performs a type change on `lv_org_type` | architecture guard | `pytest tests/test_architecture_guard.py -k hubspot_property -x` | ❌ Wave 0 (extend existing guard file) |
| Criterion 4 | `lv_icp_fit_score`/`lv_icp_tier` absent from `canonical_patch`/patch | unit (flip existing) | `pytest tests/test_merge_policy.py tests/test_main.py -x` | ✅ (assertions need inverting, §1.1) |
| Criterion 5 | Metadata stampers emit `lv_`-prefixed names; `enrichmentGate.js` reads the same names | unit + parity | `pytest tests/n8n/parity.test.mjs`-equivalent + a new JS unit test | ❌ Wave 0 for the new JS unit test |
| Criterion 6 | The 4 named contact properties are read/written under `lv_`-prefixed names | unit | extend `tests/test_contact_ingest.py`/`test_contact_normalizer.py` | ⚠️ extend existing |
| Rollback (coordinator addition) | Manifest/baseline-missing refusal; touch-nothing-outside-manifest guard; reverse-order archival | unit | `pytest tests/test_rollback_property_migration.py -x` | ❌ Wave 0 |

### Sampling rate
- **Per task commit:** the quick-run command above.
- **Per wave merge:** full `pytest` suite.
- **Phase gate:** full suite green, plus the live Task-0 baseline snapshot committed, before `/gsd-verify-work`.

### Wave 0 gaps
- [ ] `tests/test_sync_hubspot_properties.py` — dry-run diff logic, idempotency, undo-manifest correctness (offline, fixture-based)
- [ ] `tests/test_rollback_property_migration.py` — manifest/baseline guards, reverse-order sequencing (offline, fixture-based)
- [ ] A JS unit test for the renamed metadata-stamper output (new — no existing JS test file covers `mergeCompanies.js`'s `meta` object directly; `tests/n8n/parity.test.mjs` covers taxonomy normalization, not metadata naming)
- [ ] Extend `tests/test_architecture_guard.py` with a grep-based check that no code path reads/writes the pre-PN-4 unprefixed metadata names (`jobtitle_verified_at`, `mobilephone_verified_at`, `linkedin_url`, `persona_group`) after Task 6 lands

---

## Security Domain

### Applicable ASVS categories

| ASVS Category | Applies | Standard control |
|---|---|---|
| V2 Authentication | No | No new auth surface — reuses existing `HUBSPOT_PRIVATE_APP_TOKEN` bearer auth |
| V4 Access Control | Yes | The private-app token's scopes (`crm.schemas.companies.write`/`crm.schemas.contacts.write` or portal-equivalent property-management scope) must be present for the `sync_hubspot_properties.py` script to succeed — verify scopes are granted before Task 5, not discovered as a 403 mid-batch |
| V5 Input Validation | Yes | The desired-state config (§4) is the only input to the property-creation calls; validate every entry's `type`/`fieldType`/`options` shape offline (Wave 0 test) before any live call, so a malformed config entry fails fast, not as a live 400 |
| V6 Cryptography | No | No new cryptographic material — same token handling as the rest of the repo (`hs_headers()`, never logged) |

### Known threat patterns for this stack

| Pattern | STRIDE | Standard mitigation |
|---|---|---|
| Overprivileged/incorrect private-app scope silently no-ops instead of erroring, masking a partial migration | Tampering/Repudiation | Task 0/Task 4's dry-run `GET` calls double as a scope-sufficiency check — a 403 there surfaces the gap before any write is attempted |
| Undo manifest or baseline snapshot committed with a live token embedded (copy-paste error from a `hs_headers()`-adjacent debug print) | Information Disclosure | Both files are pure schema JSON (property definitions), never request headers or env values — Wave 0 test should assert neither file's serializer ever includes the word "Authorization" or the token env var name |
| Rollback script run against the wrong portal (multi-portal credential mixup) | Tampering | `HUBSPOT_PORTAL_ID` should be read and asserted against an expected value at the top of both `sync_hubspot_properties.py` and `rollback_property_migration.py` before any call, refusing to proceed on a mismatch |

---

## Environment Availability

No new external dependencies beyond what's already established (`requests`, `python-dotenv`,
`HUBSPOT_PRIVATE_APP_TOKEN`) — all present and gated per `.env.example` since Phase 0. The
one net-new requirement is confirming the private-app token's **scopes** include property
management (schema write), which existing scopes (`crm.objects.*.write`) do not necessarily
cover — this is a live-portal check, not a local-environment gap, and is folded into Task 0.

---

## 13. Sources

### Primary (HIGH confidence — official HubSpot docs)
- [CRM API | Properties guide](https://developers.hubspot.com/docs/api-reference/crm-properties-v3/guide) — create-property required fields, field types, retrieval endpoints
- [Create a batch of properties](https://developers.hubspot.com/docs/api-reference/crm-properties-v3/batch/post-crm-v3-properties-objectType-batch-create) — batch/create endpoint, 100-record cap
- [Create a property group](https://developers.hubspot.com/docs/api-reference/crm-properties-v3/groups/post-crm-v3-properties-objectType-groups) — groups endpoint contract
- [Archive a property (delete-property reference)](https://developers.hubspot.de/docs/api-reference/latest/crm/properties/delete-property) — confirms DELETE = archive/trash, not hard delete
- [API usage guidelines and limits](https://developers.hubspot.com/docs/developer-tooling/platform/usage-guidelines) — Professional tier rate limits
- [Create and edit properties (knowledge base)](https://knowledge.hubspot.com/properties/create-and-edit-properties) — field-type-change irreversibility, export-first guidance
- [Organize, delete, and export properties (knowledge base)](https://knowledge.hubspot.com/properties/organize-and-export-properties) — 90-day archive/recovery window
- [Manage enumeration property options (knowledge base)](https://knowledge.hubspot.com/properties/manage-enumeration-property-options) — option-level archive doesn't affect existing record values

### Secondary (MEDIUM confidence — community-reported, consistent with official docs)
- HubSpot Community threads (via WebSearch synthesis) on: unknown-property PATCH behavior
  (silent no-op), the recreate-by-name restore mechanism, and `options` array field shape
  (`label`/`value`/`displayOrder`/`hidden`/`description`)

### Tertiary (this session's code verification — HIGH confidence, grep/read-verified)
- `src/merge_policy.py`, `main.py`, `config/field_policy.yaml`, `config/provider_priority.yaml`,
  `n8n/code/mergeCompanies.js`, `n8n/code/mergeContacts.js`, `n8n/code/enrichmentGate.js`,
  `n8n/code/normalizeProviders.js`, `n8n/code/webResearch.js`, `src/web_research.py`,
  `src/hubspot_client.py`, `scripts/build_cloud_workflows.py`, `scripts/smoke_closed_won_research.py`,
  `tests/test_merge_policy.py`, `tests/test_main.py`, `docs/WEB-RESEARCH-SPEC.md`, `.planning/STATE.md`,
  `.planning/ROADMAP.md`

---

## Metadata

**Confidence breakdown:**
- HubSpot Properties API contract (create/read/groups/batch/archive semantics): HIGH — official docs, directly cited
- Current portal contents (what already exists vs. missing): MEDIUM — inherited from the 2026-07-20 audit, not independently re-queried live this session; Task 0 of the plan must confirm
- Code current-state (file:line references, wrapper gaps, naming issues): HIGH — every claim grep/read-verified this session
- Reversibility/rollback design: MEDIUM-HIGH — the archive/90-day mechanics are well-documented; the specific recreate-restores-data behavior is community-reported, not an explicit guaranteed API contract, and is treated accordingly (§3.6, §12/A3)
- Property manifest completeness: HIGH for the "what does the code currently emit" derivation; MEDIUM for "is this the complete right set to create" (two discretionary sizing calls flagged in §12/A5)

**Research date:** 2026-07-21
**Valid until:** Re-verify the current-state map (§1) and portal contents (Task 0) at execution
time if this research is more than ~7 days old before planning starts — this phase's whole
risk profile depends on line numbers and portal contents that other phases' commits can shift.

