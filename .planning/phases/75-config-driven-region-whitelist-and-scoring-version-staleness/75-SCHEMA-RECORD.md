# Phase 75 — Live HubSpot schema + flow window record (plan 75-05)

Window authorised by the operator at the plan 75-05 Task 0 `checkpoint:decision`
(`gate="blocking-human"`), 2026-09-20. Every live call below was run BY THE OPERATOR from the
interactive shell (`!` prefix, `.env` sourced inline) — the orchestrator and executor subagents
cannot read `.env` and made no live call. No company record was written at any step.

## Task 1 — property create + enum-option update

### Pre-write dry-run (operator, `set -a; source .env; set +a; .venv/bin/python scripts/sync_hubspot_properties.py --dry-run`)

```
DRY RUN (default) — no writes will be made. Set DRY_RUN=false AND ALLOW_HUBSPOT_PROPERTY_WRITES=true to create.

=== companies ===
Groups to create: []
Properties to create (1): ['lv_icp_scoring_version']
Properties to update (add/hide options, never drop) (1): ['lv_country_region_normalized']

=== contacts ===
Groups to create: []
Properties to create (0): []
```

Classification matched plan 05's gate: `lv_icp_scoring_version` under `create`,
`lv_country_region_normalized` under `update` (not `drift`).

Note: a first attempt without `.env` sourced printed
`skipped (no credentials): HUBSPOT_PRIVATE_APP_TOKEN must be set to run this sync.` and made no
call — the script reads the token from the environment only (no dotenv).

### Live write (operator, `set -a; source .env; set +a; DRY_RUN=false ALLOW_HUBSPOT_PROPERTY_WRITES=true .venv/bin/python scripts/sync_hubspot_properties.py`)

```
=== companies ===
Groups to create: []
Properties to create (1): ['lv_icp_scoring_version']
Properties to update (add/hide options, never drop) (1): ['lv_country_region_normalized']
created property companies/lv_icp_scoring_version (201)
updated property companies/lv_country_region_normalized options (200)
undo manifest: /Users/robertli/Desktop/consulting/lightning-visuals/lv-n8n-poc/config/hubspot_migration/undo-manifest-7ee513f4-644d-4788-8b1f-fcda558fb767.json

=== contacts ===
Groups to create: []
Properties to create (0): []
```

| Call | Status |
| --- | --- |
| `POST /crm/v3/properties/companies` (`lv_icp_scoring_version`, `type: string`, `fieldType: text`, group `lv_enrichment`) | 201 |
| `PATCH /crm/v3/properties/companies/lv_country_region_normalized` (options) | 200 |

Undo manifest run id: `7ee513f4-644d-4788-8b1f-fcda558fb767`
Path: `config/hubspot_migration/undo-manifest-7ee513f4-644d-4788-8b1f-fcda558fb767.json`

Manifest `pre_update_options` (8): `AU, NZ, ANZ, US, UK, EU, Other, Unknown`
Manifest `request_body.options` (16): `AU, NZ, ANZ, US, UK (hidden), EU, Other, Unknown, GB, IE, CA, ZA, HK, SG, AE, IN`
No option removed; `UK` hidden, not deleted (forward-only: the only undo for the hide is a second
update with `hidden: false`; the eight additions are permanent).

### Independent read-back

**Post-write dry-run** (operator, same sourced shell): zero pending on both objects —

```
=== companies ===
Groups to create: []
Properties to create (0): []

=== contacts ===
Groups to create: []
Properties to create (0): []
```

**Independent GET** — `scripts/snapshot_hubspot_schema.py --label phase75` (read-only, portal id
asserted pre-call) wrote `config/hubspot_migration/baseline/portal-schema-companies-phase75.json`
(and the contacts sibling). Parsed from that file, not from the sync script's exit:

- `lv_country_region_normalized`: 16 options, in order
  `AU, NZ, ANZ, US, UK (hidden: true), EU, Other, Unknown, GB, IE, CA, ZA, HK, SG, AE, IN`.
  `EU` unchanged; no pre-write option absent.
- `lv_icp_scoring_version`: `{"type": "string", "fieldType": "text", "groupName": "lv_enrichment", "label": "LV ICP Scoring Version"}`.
- Snapshot script's drift line vs the 2026-07-20 audit lists `lv_icp_scoring_version` under
  `added` — consistent.

No company record was written by any call in Task 1.


## Task 2 — snapshot repointed, enum module regenerated

`scripts/gen_hubspot_enums_js.py` `SNAPSHOT` → `config/hubspot_migration/baseline/portal-schema-companies-phase75.json`
(previous pin kept as a dated comment; old baseline retained). Regenerated
`n8n/code/hubspotEnums.generated.js` carries all sixteen region values; `build_cloud_workflows.py`
re-run leaves `git status --porcelain -- n8n/` empty. Commit `e220bf61`. Plan 02's inert window
for `GB, IE, CA, ZA, HK, SG, AE, IN` is closed. `tests/test_hubspot_schema_coverage.py`, red since
plan 01 because `lv_icp_scoring_version` was not live, is green again.

## Task 3 — geography flow PUT

Pre-PUT disclosure (printed to the operator before the write): the committed body
`config/hubspot_flows/4626722240-geography-score.after.json` differs from its phase-start state
in ONLY the geography branch `operation.values`, `["AU","NZ","ANZ"]` → the 12 `regions.home`
codes (verified by structural comparison with `values` stripped: identical). The live body
fetched immediately before the PUT (`4626722240-geography-score.pre75.json`, read-only) equals
the committed body except those same three values — it IS the rollback body.
`4626722240-geography-score.before.json` (Phase 40's archive, filtering native `country` by
name) is NOT a valid rollback for this phase and was left byte-unchanged.

PUT (operator, `DRY_RUN=false ALLOW_HUBSPOT_FLOW_WRITE=true .venv/bin/python scripts/put_hubspot_flow.py --flow-id 4626722240 --file config/hubspot_flows/4626722240-geography-score.after.json`):
response body returned (2xx) with `revisionId` 13 → 14, `updatedAt` `2026-09-20T08:50:43.543Z`
(`createdAt` `2026-08-04T18:54:17.151Z`), `isEnabled: true`, `shouldReEnroll: true`, score actions
unchanged (`geography_score` = 10 on the branch, 0 on default).

Independent read-back `scripts/fetch_hubspot_flow.py --flow-id 4626722240 --label post75` →
`4626722240-geography-score.post75.json`; geography branch `values`:
`["AU","NZ","ANZ","US","GB","IE","CA","ZA","HK","SG","AE","IN"]`. Equal to the committed body
except `revisionId` (14 vs 13).

`scripts/check_schema_drift.py --out .../75-schema-drift.json`:
- first run: `geography_flow_drift.status = ambiguous_branch, "found 0"` on a live flow that
  carried exactly one branch — a plan-04 comparator defect (it walked the v4 flows LIST
  response, which has no `actions`). Fixed root-cause in `0221804a` (RED `4a73ae7a`): main()
  now GETs the single flow body.
- second run (post-fix): `geography_flow_drift = {"status": "in_sync", "detail": "live branch
  values match regions.home"}`, `do_not_archive.ok = True`, `summary {in_sync: 55,
  documented_gap: 3}` (the three CLAUDE.md §4.0 never-created properties `lv_icp_confidence`,
  `lv_icp_scored_at`, `lv_recommended_motion`), **exit 0**.

`gen_geography_flow.py && git diff --quiet -- config/hubspot_flows/` → `BODY_CURRENT`.
No company record was written; nothing on n8n was deployed, bounced or armed.
