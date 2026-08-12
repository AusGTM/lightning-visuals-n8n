# ORG-TYPE-ENUM-MIGRATION.md — `lv_org_type` text → enumeration rollback runbook

You are probably reading this because a migration went wrong, or you are about to arm
one and want to know what happens if it does. Rollback comes first; the migration's
happy path is `scripts/migrate_org_type_enum.py` — read that, not a re-description of it
here.

## Machine-read markers

`scripts/migrate_org_type_enum.py` parses these four lines verbatim before it will arm
the forward migration. Do not rename a key or leave its value blank/placeholder — doing
so disarms the gate silently, which is the one thing this file exists to prevent.

```
MIGRATION-SHAPE: in place (cheap reverse-PATCH rollback confirmed) -- verbatim `recommended_migration_shape` line from 21-03-SUMMARY.md's operator VERDICT block, 2026-07-30
ROLLBACK-COMMAND: DRY_RUN=false ALLOW_HUBSPOT_PROPERTY_WRITES=true .venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); import runpy; runpy.run_path('scripts/migrate_org_type_enum.py', run_name='__main__')" --rollback
VERDICT-SOURCE: .planning/phases/21-transport-schema-hygiene/21-03-SUMMARY.md (commit b55fc45)
REFERENCE-ARTIFACTS: baseline=config/hubspot_migration/baseline/portal-schema-companies-pre-orgtype-enum.json inventory=config/hubspot_migration/org_type_inventory-20260730T071919Z.json
```

`REFERENCE-ARTIFACTS`'s baseline path names the snapshot the operator takes at
Operator Runbook Section C1, immediately before arming — it will not exist on disk until
that step runs. That is expected; the gate that reads this document checks the four
marker *lines*, not filesystem existence of everything they name. The inventory path is
already committed (Plan 03 Task 2) and is what the migration's separate pre-flight gate
re-reads (the newest `config/hubspot_migration/org_type_inventory-*.json` on disk, not
literally this pinned filename — see `scripts/migrate_org_type_enum.py`'s docstring).

## WHEN to roll back

Roll back if any of these hold after arming:

- Operator Runbook Section C5's independent post-migration schema diff shows anything
  other than `lv_org_type`'s `type`, `fieldType` and `options` changed — any other field
  moving is evidence the PATCH did something broader than intended.
- Section C6's inventory re-run shows an in-vocabulary value count that changed from the
  pre-migration artifact — a value was lost or mutated during conversion.
- Section C7's smoke test does not behave as expected: a canonical write is rejected, or
  an out-of-vocabulary write is silently accepted (no 400) — the enum is not actually
  enforcing.
- The migration script's own post-write read-back assertion already failed and exited
  non-zero — in this case the live property may be in an inconsistent state and rollback
  is not merely advisable, it may be necessary to get back to a known-good schema.

> **AMENDED 2026-08-12 — the cheap window described in the next paragraph is CLOSED.**
> "All 712 live companies blank on `lv_org_type`" was true on 2026-07-30 and is no longer.
> Phase 47 (2026-08-11/12) wrote real enum values onto real companies, and Phase 48 will
> write more. Populated records now exist, so a rollback lands squarely in the "decide fast /
> unverified round-trip" case described below, **not** the unconditionally-cheap one. Re-run
> the inventory before arming anything in either direction; do not read the paragraph below
> as a current statement of risk.

**The point past which this stops being cheap:** ~~right now, it is unconditionally cheap.~~
The committed pre-migration inventory (`org_type_inventory-20260730T071919Z.json`) shows
all 712 live companies blank on `lv_org_type` — there is no existing record data to lose
in either direction. That changes the moment real enrichment writes start landing on the
converted property (ordinary pipeline operation, always vocabulary-constrained through
`src/taxonomy.py::normalize_org_type()`). Once populated records exist, decide fast: a
rollback then reverts the property's *definition* but this repo has no independently
verified evidence of what a text→enum→text round trip does to a record's *value* in this
portal (see "What rollback cannot restore" below) — the safe window is before that data
accumulates, not after.

## WHAT to run

Exactly the `ROLLBACK-COMMAND` marker above:

```bash
.venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); import runpy; runpy.run_path('scripts/migrate_org_type_enum.py', run_name='__main__')" --rollback
```

This is the dry run — it prints the reverse PATCH body (`type: string`, `fieldType:
text`, `options: []`) against the real `lv_org_type` property and makes zero HTTP calls.
Read it, then arm with both keys in the same invocation exactly as the marker states:

```bash
DRY_RUN=false ALLOW_HUBSPOT_PROPERTY_WRITES=true \
  .venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); import runpy; runpy.run_path('scripts/migrate_org_type_enum.py', run_name='__main__')" --rollback
```

Answer the typed confirmation. The script re-GETs the property afterward and asserts the
live type/fieldType/options match the reverted shape; a failed assertion exits non-zero
and says so loudly rather than reporting success.

## HOW to verify the rollback worked

1. `.venv/bin/python scripts/snapshot_hubspot_schema.py --label post-rollback` and diff
   the companies snapshot against the pre-migration baseline
   (`portal-schema-companies-pre-orgtype-enum.json`, captured at Operator Runbook Section
   C1). An empty diff on `lv_org_type` (back to `string`/`text`/`[]`) is the bar.
2. Re-run `scripts/inventory_org_type_values.py` and diff its `value_counts` against the
   pre-migration committed artifact
   (`config/hubspot_migration/org_type_inventory-20260730T071919Z.json`). Every
   in-vocabulary value's count should be unchanged from before the forward migration ran
   (in the current state that means: still all blank).

## What rollback cannot restore

Be plain about this, because the probe that was supposed to settle it did not cleanly
answer the record-value question:

- The property **definition** (type `string`, fieldType `text`, empty options) comes back
  from the reverse PATCH — this part is proven live (Plan 03's probe verdict:
  `reverse_patch_allowed: yes`, a real 200 on the disposable probe property).
- What happens to a record's **value** that was written while the property was an
  enumeration, once the property is reverted to text, is **not independently proven for
  this portal**. The probe ladder's steps 2/4/5 (which were designed to observe exactly
  this) hit a stale `TEST_COMPANY_IDS=789`, a company that does not exist — the 404
  those steps returned is "record not found," not evidence about value handling on
  conversion. This migration does not need that answer today because the pre-migration
  inventory proves zero existing values are at stake in the forward direction. But if you
  are rolling back *after* real data has accumulated on the enum property, do not assume
  a reverse PATCH is lossless for those values — verify with the inventory diff in
  step 2 above before trusting the record data survived, and if it did not, the recovery
  path is re-populating from whatever audit trail exists (HubSpot property history, or
  the pipeline's own `lv_enrichment_provenance` JSON blob on the affected companies),
  by hand.
- If the reverse PATCH itself is ever refused live (contradicting the probe verdict —
  HubSpot behavior changing between the probe and a later rollback attempt is not
  impossible), there is no in-place recovery: the path becomes archive `lv_org_type`,
  recreate it as `string`/`text`, and backfill every company's value from the
  most recent committed inventory artifact, by hand. State this cost plainly if it
  happens: it is the "archive-and-recreate" shape the probe ruled out as the primary
  plan, not a rehearsed fallback.

## Blast radius — code paths that read `lv_org_type` mid-migration

- **Merge policy** (`src/merge_policy.py`): `COMPANY_CACHE_KEY_FIELDS["lv_org_type"] =
  "lv_org_type_verified_at"` — the provenance cache-key mirror for this field. A merge
  decision that attempts to PATCH `lv_org_type` during the brief window the property's
  type is actually changing could receive a transient 400 from HubSpot; it does not
  corrupt anything, it just needs a retry (already the pipeline's default behavior on
  non-2xx HubSpot responses).
- **ICP scoring** (`src/icp_scoring.py::compute_icp_score`): reads `lv_org_type` via
  `get_signal()` for the org-type score component (`config/icp_scoring.yaml
  base_score.org_type`) and gates evidence requirements through
  `taxonomy.EVIDENCE_GATED_ORG_TYPES` / `config/field_policy.yaml
  lv_org_type.require_evidence_url_for`. A read during migration sees whatever string
  value is currently stored regardless of the property's live schema type, so scoring
  itself does not break mid-migration — only a concurrent *write* can 400.
- **HubSpot search property lists on both lanes:** `n8n/wf_enrichment_cloud.json`'s
  enrichment-lane fetch-property lists (the `["...", "lv_org_type", "lv_produces_content",
  ...]` arrays) and `n8n/wf_scheduled_maintenance_cloud.json`'s ICP-unscored scheduled
  scan, which both names `lv_org_type` in its own fetch list and filters on it with a
  `NOT_HAS_PROPERTY` operator. A property-type PATCH does not rename the property, so
  these lists keep resolving unmodified after the migration. The narrower risk is a
  concurrent n8n write racing the single PATCH call itself (a sub-second window); this
  repo's precedent (the Lusha id staging property creates, Operator Runbook Section A)
  ran with n8n live and had no incident, so this runbook does not require pausing
  deploys, but the race exists and is worth knowing about if a write 400s during the
  exact minute the migration is armed.

## What this document does not repeat

The migration's own happy path — pre-flight gates, dry-run output, the typed
confirmation, the manifest it writes, and its post-write read-back assertion — lives in
`scripts/migrate_org_type_enum.py` and is exercised end to end by Operator Runbook
Section C. Read the script; do not expect this document to restate it, and do not let
the two drift apart by editing one without the other.
