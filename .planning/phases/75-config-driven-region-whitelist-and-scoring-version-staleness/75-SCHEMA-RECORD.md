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

