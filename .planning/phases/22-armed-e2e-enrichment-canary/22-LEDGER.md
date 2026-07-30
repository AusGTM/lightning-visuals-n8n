# Phase 22 Armed Canary Ledger

This document is filled DURING the armed operator window (22-04's runbook), not before. Every
row starts `not-yet-observed` and stays that way until the corresponding command has actually
been run against the live armed canary — an unobserved outcome is visibly blank here, never
silently absent. Shape follows `.planning/milestones/v0.4-phases/19-verification-debt-closure/19-LEDGER.md`'s
evidentiary bar: a claim, the exact command whose output is the evidence, and a status from a
fixed vocabulary.

## Criterion Ledger

One row per ROADMAP.md Phase 22 success criterion (`.planning/ROADMAP.md` "Phase 22: Armed E2E
Enrichment Canary" section).

| # | Claim | Evidence (exact command) | Status |
|---|-------|---------------------------|--------|
| 1 | One armed end-to-end enrichment on the allowlisted record lands staged fields, source metadata, and promoted canonical writes in HubSpot, produced by the complete chain: provider waterfall + Haiku web research (`claude-haiku-4-5`) + Sonnet judge (`claude-sonnet-5`). | `python scripts/canary_record_snapshot.py compare --snapshot <pre-canary snapshot path>` (post-fire) showing the target record's staged/canonical/source-metadata fields populated, plus the fired n8n execution's node list (`python scripts/enrichment_cost_ledger.py extract --execution-id <id>`) showing `Claude Web Research`/`Judge Call` both `status=ran`. | not-yet-observed |
| 2 | The run live-validates Phases 20-21: Lusha data arrives via v3 (no reveal paid for an already-held field), and writes succeed against the migrated schema (`lv_org_type` accepted by the enumeration; `lv_country_region_normalized` promoted under its policy entry). | The fired execution's `Lusha Enrich`/`Lusha Company` node bodies (from the same `extract --execution-id` run, or a direct read of the execution's `runData`) showing a v3 URL and, for a matched record, `billing.creditsCharged` consistent with `docs/LUSHA-V3-CONTRACT.md`; plus a live HubSpot read-back of the target company/contact confirming `lv_org_type`/`lv_country_region_normalized` landed without a 400. | not-yet-observed |
| 3 | Neighbor (non-allowlisted) records are byte-untouched after the run. | `python scripts/canary_record_snapshot.py compare --snapshot <pre-canary snapshot path>` — exit code and `neighbors_changed` field (compare mode's exit code is driven only by `neighbors_changed`, per 22-01-SUMMARY.md's key-decisions). | not-yet-observed |
| 4 | The run closes disarmed and audited: read-back shows every write flag `"false"` and the allowlist cleared. | `python scripts/verify_live_write_safety.py` (disarmed-expectation mode, post-disarm redeploy) — per 22-02-SUMMARY.md. | not-yet-observed |
| 5 | A cost ledger records actual spend — provider credit balances before/after and Anthropic tokens per call — against the 2026-07-30 estimates, producing a calibrated per-record cost figure. | `python scripts/enrichment_cost_ledger.py report --before <pre-canary credits snapshot> --after <post-canary credits snapshot, --settle> --execution-id <fired execution id> --record-count <N>` — the "Totals" block's per-record USD figure and `partial` flag. | not-yet-observed |

## Cost Table

One row per `scripts/enrichment_cost_ledger.py` `ESTIMATES` entry (module is the single source —
see its module docstring/table for the full citation and confidence marker per row). Fill
`Actual`/`Delta` from the `report` command's printed blocks; `Evidence` names the exact command.

| Estimate entry | Estimate | Actual | Delta | Evidence (exact command) |
|---|---|---|---|---|
| `lusha_contacts_first_time_enrich` | 1 credit/contact | not-yet-observed | not-yet-observed | `python scripts/enrichment_cost_ledger.py report --before <pre> --after <post>` — "Provider credits" block, `lusha` row |
| `lusha_companies_match` | 2 credits/company | not-yet-observed | not-yet-observed | same `report` run — cross-check against the fired execution's `Lusha Company` node `billing.creditsCharged` |
| `lusha_contacts_stored_id_reuse` | 0 credits/contact | not-yet-observed | not-yet-observed | applies only if the allowlisted contact already carried a `lusha_contact_id` staging value before this run — check the pre-canary snapshot |
| `zoominfo_per_match` | 1.08 credits/match | not-yet-observed | not-yet-observed | same `report` run — "Provider credits" block, `zoominfo` row |
| `apollo_per_match` | unknown (this account's key is non-master, 403) | not-yet-observed (expected: unknown, unchanged) | not-yet-observed | same `report` run — "Provider credits" block, `apollo` row (should print `actual=unknown estimate=unknown delta=unknown`) |
| `anthropic_research_model_input_per_mtok` | $1.00 / MTok (`claude-haiku-4-5`) | not-yet-observed | n/a (priced-in, not diffed) | same `report` run — "Anthropic usage per call" block, `Claude Web Research`/`Contact Web Research` rows |
| `anthropic_research_model_output_per_mtok` | $5.00 / MTok (`claude-haiku-4-5`) | not-yet-observed | n/a (priced-in, not diffed) | same `report` run — "Anthropic usage per call" block |
| `anthropic_judge_model_input_per_mtok` | $2.00 / MTok intro (`claude-sonnet-5`, thru 2026-08-31) | not-yet-observed | n/a (priced-in, not diffed) | same `report` run — "Anthropic usage per call" block, `Judge Call`/`Contact Judge Call` rows |
| `anthropic_judge_model_output_per_mtok` | $10.00 / MTok intro (`claude-sonnet-5`, thru 2026-08-31) | not-yet-observed | n/a (priced-in, not diffed) | same `report` run — "Anthropic usage per call" block |
| `haiku_research_call_allin_estimate` | $0.07/company research call, all-in | not-yet-observed | not-yet-observed | sum the `Claude Web Research`/`Contact Web Research` `cost_usd` values from the same `report` run and compare to $0.07 × (number of research calls fired) |
| **Per-record total** | — (no baseline exists; this run establishes it) | not-yet-observed | — | same `report` run — "Totals" block, `per-record USD` line; also record whether it printed `[PARTIAL]` |

## How To Fill This Document

1. Capture the pre-canary credit snapshot: `python scripts/enrichment_cost_ledger.py credits --label pre-canary`.
2. Fire the canary per `22-04`'s runbook.
3. Capture the settled post-canary credit snapshot: `python scripts/enrichment_cost_ledger.py credits --label post-canary --settle`.
4. Find the fired execution id: `python scripts/enrichment_cost_ledger.py list`.
5. Run the report: `python scripts/enrichment_cost_ledger.py report --before <pre-canary snapshot path> --after <post-canary snapshot path> --execution-id <id> --record-count <N>`.
6. Paste the report's three printed blocks' relevant figures into the tables above; flip each
   Status/Actual/Delta cell from `not-yet-observed` to the real observed value (or an explicit
   `unknown` if the run itself reported one) — never delete a row, never leave a cell blank
   without the `not-yet-observed` placeholder if it genuinely was not run.
