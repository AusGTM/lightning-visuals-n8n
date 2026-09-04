# Phase 54 Plan 03 Task 1: Contacts review-family live property check

**Date:** 2026-08-27
**Command run (read-only, GET only, no HubSpot writes):**

```bash
.venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); import runpy, sys; \
sys.argv = ['snapshot_hubspot_schema.py', '--label', '54-03-contacts-check']; \
runpy.run_path('scripts/snapshot_hubspot_schema.py', run_name='__main__')"
```

This is `scripts/snapshot_hubspot_schema.py`'s default (non-`--probe`) mode: `GET
/crm/v3/properties/contacts` (and the same for `companies`), written verbatim to disk. No
`POST`/`PATCH`/`DELETE` call is made anywhere in this script's default mode (confirmed by
reading the file before running it — the only write path, `_run_probe`, requires the
`--probe` flag plus `DRY_RUN=false`, neither of which was passed here).

Snapshots written this run:
- `config/hubspot_migration/baseline/portal-schema-contacts-54-03-contacts-check.json`
- `config/hubspot_migration/baseline/portal-schema-companies-54-03-contacts-check.json`

(Both companies-side snapshot is a byproduct of the script running both object types in one
invocation — not itself needed by this check, kept per this repo's existing convention that
`baseline/` snapshots are committed, versioned evidence, not scratch output.)

## Result: all seven properties are PRESENT on the live contacts object

| Property | Verdict |
|---|---|
| `lv_enrichment_needs_review` | PRESENT |
| `lv_enrichment_review_reason` | PRESENT |
| `lv_enrichment_review_approved` | PRESENT |
| `lv_enrichment_review_candidate_json` | PRESENT |
| `lv_enrichment_reviewed_at` | PRESENT |
| `lv_enrichment_reviewed_by` | PRESENT |
| `lv_contact_enrichment_provenance` | PRESENT |

Verified by parsing the live-fetched `portal-schema-contacts-54-03-contacts-check.json`
against this exact list of seven names — all seven names appear in the live response's
`results[].name` set.

## Consequence for Task 3's clear patch

No property from this list needs to be omitted from the contacts clear patch: all seven are
live and reachable. `config/hubspot_properties.yaml` lines 463-560 (the declared `contacts:`
section) matches the live portal for this family — the CLAUDE.md §4.0 "declared is not live"
warning does not apply to any of these seven names.

## Confirming this was a pure read

`git status --porcelain config/hubspot_properties.yaml` shows no change — the check made no
edit to the declared-property config, only a live GET against the portal.
