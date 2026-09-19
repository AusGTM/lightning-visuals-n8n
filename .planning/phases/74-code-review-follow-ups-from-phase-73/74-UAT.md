---
phase: 74-code-review-follow-ups-from-phase-73
plan: 06
status: testing
created: 2026-09-19
---

# Phase 74 Plan 06 — UAT Addendum

End-of-phase live gate per D-74-11 (amended): two scoped disarmed deploys, one bounce, two
proof sends (ceiling 2 executions), two freezes. Nothing armed at any point.

## Task 1 — Two scoped disarmed deploys and bounces, flags read back false

### Deploy calls

Both calls made through an in-process dotenv scratchpad driver
(`plan74_06_driver.py`, session-scratchpad only, never committed), setting
`DRY_RUN=false ALLOW_N8N_DEPLOY=true` and calling `deploy_n8n_workflows.main(["--only", <file>])`.
A dry-run (`DRY_RUN` unset) preceded each live call and reported the identical single-workflow
diff, confirming the scoped `--only` argument narrows correctly before any write.

| Call | `--only` file | Workflows to create | Workflows to update | Result |
|---|---|---|---|---|
| 1 (dry) | `wf_contact_ingest_cloud.json` | `[]` | `['LV Contact Ingest (Cloud template)']` | DRY RUN, `deploy_rc=0` |
| 1 (live) | `wf_contact_ingest_cloud.json` | `[]` | `['LV Contact Ingest (Cloud template)']` | `updated workflow LV Contact Ingest (Cloud template) (200)`, `deploy_rc=0` |
| 2 (dry) | `wf_enrichment_cloud.json` | `[]` | `['LV Enrichment (Cloud template)']` | DRY RUN, `deploy_rc=0` |
| 2 (live) | `wf_enrichment_cloud.json` | `[]` | `['LV Enrichment (Cloud template)']` | `updated workflow LV Enrichment (Cloud template) (200)`, `deploy_rc=0` |

**Only these two workflows were deployed.** Neither call's create/update list ever named
`LV Backend Status (Cloud template)`, `LV Review Decision (Cloud)`,
`LV Scheduled Maintenance (Cloud)`, or `LV Suggest Discovery (Cloud template)` — the other four
cloud workflows are untouched by this plan.

### Bounce + read-back (one bounce call, per D-74-11's amended text; covers all six per
`bounce_n8n_workflows.py`'s own design — deactivate/activate never alters node body content)

| workflow | id | active | live nodes | committed nodes | write flags | execution order |
|---|---|---|---|---|---|---|
| LV Backend Status (Cloud template) | `Cj83mOgrIm59oxcX` | True | 33 | 33 | (none declared) | v1 |
| LV Contact Ingest (Cloud template) | `AwbBeShdPgV48eiY` | True | 101 | 101 | RECORD_WRITES=[false], CREATE=[false] | v1 |
| LV Enrichment (Cloud template) | `950HPb7a1GgSAIyZ` | True | 289 | 289 | RECORD_WRITES=[false], CREATE=[false] | v1 |
| LV Review Decision (Cloud) | `WBJwoZOo63wzeP69` | True | 55 | 55 | RECORD_WRITES=[false], CREATE=[false] | v1 |
| LV Scheduled Maintenance (Cloud) | `1fXPuIabz3RsAHgn` | True | 43 | 43 | RECORD_WRITES=[false], CREATE=[false] | v1 |
| LV Suggest Discovery (Cloud template) | `VJJBZ2oJ0079MSzG` | True | 26 | 26 | (none declared) | v1 |

`bounce_n8n_workflows.py`'s own row-verdict: **"OK — all active, node counts match, write flags
false, execution order v1."** `bounce_rc=0`.

Live node counts equal the committed generated counts recorded in `74-04-SUMMARY.md`
(enrichment: 289) and `74-05-SUMMARY.md` (ingest: 101 — 98 base → 99 after Task 1's stamp node
→ 101 after Task 3's sentinel).

### Burst watch (post-bounce)

Baseline (immediately before the bounce, `list-executions`):
- Ingest (`AwbBeShdPgV48eiY`) max execution id: `12663` (2026-09-18)
- Enrichment (`950HPb7a1GgSAIyZ`) max execution id: `12662` (2026-09-18)

Re-checked after the bounce, following a 125-second background sleep plus the additional wall
time spent on Task 1's write-up and verification work (well over two minutes elapsed total):
- Ingest max execution id: **still `12663`** — no new execution.
- Enrichment max execution id: **still `12662`** — no new execution.

**Zero executions fired during the watch.** No burst; the deactivate-workflow stop was never
needed.

### A false-positive in Task 1's own inline `<verify>` command (documented, not a defect)

Task 1's `<automated>` verify command greps each committed body's full stringified node
`parameters` for the co-occurrence of `/ALLOW_(HUBSPOT|N8N)/` and `/=\s*true/` anywhere in the
SAME node, not scoped to the same declaration. It flagged the ingest workflow's `Decide Action`
node as an "armed literal". Manual inspection of that node's `jsCode` shows the two matches are
unrelated:
- `ALLOW_HUBSPOT_CREATE` appears once, in its own disarmed declaration:
  `const ALLOW_HUBSPOT_CREATE = "false";`
- The `=\s*true` match is `row.lookup_failed === true` — an identity-lookup comparison with no
  relationship to write-safety arming.

A rigorous, declaration-scoped re-check (`const\s+(ALLOW_HUBSPOT_[A-Z_]+|ALLOW_N8N_[A-Z_]+)\s*=\s*("[^"]*"|true|false)\s*;`)
over every node in both committed bodies found **every single declaration reads the `"false"`
literal**, with no exceptions:

- **Ingest** (`wf_contact_ingest_cloud.json`): `ALLOW_HUBSPOT_RECORD_WRITES` declared in 4 nodes
  (`HubSpot Update Write Gate`, `HubSpot Create Write Gate`, `Associate Lane Sentinel`,
  `Create Failure Row Sentinel`) — all `"false"`. `ALLOW_HUBSPOT_CREATE` declared in 5 nodes (the
  same 4 plus `Decide Action`) — all `"false"`. `ALLOW_HUBSPOT_REVIEW_WRITES` declared in the
  same 4 gate/sentinel nodes — all `"false"`. Declaration counts (4 and 5) match
  `74-05-SUMMARY.md`'s own record of `test_control_flag_parity.py`'s updated literal counts.
- **Enrichment** (`wf_enrichment_cloud.json`): all three flags declared in 4 nodes
  (`HubSpot Create Write Gate`, `HubSpot Update Write Gate`,
  `HubSpot Company Create Write Gate`, `HubSpot Company Update Write Gate`) — all `"false"`.

This confirms Task 1's real acceptance criterion ("every write-safety constant declared in
either live body reads the false literal") independently of the inline verify command's naive
regex, and independently of `bounce_n8n_workflows.py`'s own scoped `_flag_values()` extraction
(which agrees — see the bounce table above). **Nothing is armed.**

## Task 2 — Two proof sends, two freezes

(populated below once Task 2 runs)
