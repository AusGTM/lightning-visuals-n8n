---
status: passed_with_findings
phase: 72-enrichment-extras-land-in-hubspot
source: [72-08-PLAN.md Task 1, 72-08-PLAN.md Task 2, 72-12-PLAN.md Task 2, docs/OPERATOR-AUTONOMOUS-BATCH-UAT.md §6]
started: 2026-09-12T00:00:00Z
updated: 2026-09-13T00:00:00Z
---

# Phase 72 — D-72-17 live gate (UAT)

This is the phase's one end-of-phase live gate. Task 1 (properties verify + level live with
committed, disarmed) is recorded below. Task 2 (the one armed window) ran live on 2026-09-13
and is recorded below with findings.

## Task 1 — verify slot properties exist, level live with committed (disarmed)

Operator ran, in one chain, 2026-09-12 (exact clock not captured by the operator's paste; date
recorded from the run, no finer-grained timestamp available — noted as a gap below):

1. `scripts/sync_hubspot_properties.py` (default dry run)
2. `scripts/sync_hubspot_properties.py` with `DRY_RUN=false ALLOW_HUBSPOT_PROPERTY_WRITES=true`
3. `scripts/build_cloud_workflows.py`
4. `scripts/deploy_n8n_workflows.py` with `DRY_RUN=false ALLOW_N8N_DEPLOY=true`
5. `scripts/bounce_n8n_workflows.py`

### Step 1 — three overflow-slot properties (D-72-23 amendment: verify-exists, not create)

| Property | Object | Dry-run pending? | Armed-run pending? |
|---|---|---|---|
| `lv_phone_2` | contacts | no (0 pending) | no (0 pending) |
| `lv_mobilephone_2` | contacts | no (0 pending) | no (0 pending) |
| `lv_phone_2` | companies | no (0 pending) | no (0 pending) |

Both the dry run and the armed run reported `Properties to create (0): []` for both `companies`
and `contacts` groups — i.e. all three properties already exist live (created in plan 05 per
D-72-23), and no new schema write occurred in this task.

**Honest gap:** the operator did NOT run the three individual property GETs
(`GET /crm/v3/properties/contacts/lv_phone_2`, `.../lv_mobilephone_2`,
`GET /crm/v3/properties/companies/lv_phone_2`) to record `type`/`fieldType`/`readOnlyValue`
directly in this task. The sync tool's 0-pending result on both objects proves the three
properties EXIST live (the tool diffs against declared vs. actual schema). Their
`type: string` / `fieldType: text` / `readOnlyValue: false` was last confirmed live by plan
05's post-create re-GET — see `72-05-SUMMARY.md`. Recorded here as observed-via-sync,
type-confirmed-in-plan-05, not as a fresh direct GET in this task.

### Step 2 — regenerate, deploy, bounce every changed workflow, disarmed

`build_cloud_workflows.py` wrote all 8 workflow JSON files with no git diff (tree stayed
clean) — confirms committed and generated are already level, per plan 06/07.

Deploy plan: `Workflows to create: []`, `Workflows to update:` all 5 cloud workflows (`LV
Backend Status (Cloud template)`, `LV Contact Ingest (Cloud template)`, `LV Enrichment (Cloud
template)`, `LV Review Decision (Cloud)`, `LV Scheduled Maintenance (Cloud)`). All 5 PUT at
200. Bounce (deactivate/activate) ran across all 5 per script design (§6 arm/disarm summary:
"Leave the bounce script bouncing all five").

Post-bounce read-back:

| Workflow | id | active | live nodes | committed nodes | match? | `ALLOW_HUBSPOT_RECORD_WRITES` | `ALLOW_HUBSPOT_CREATE` | executionOrder |
|---|---|---|---|---|---|---|---|---|
| LV Backend Status (Cloud template) | `Cj83mOgrIm59oxcX` | True | 30 | 30 | yes | `-` (no write path) | `-` (no write path) | v1 |
| LV Contact Ingest (Cloud template) | `AwbBeShdPgV48eiY` | True | 78 | 78 | yes | `false` | `false` | v1 |
| LV Enrichment (Cloud template) | `950HPb7a1GgSAIyZ` | True | 287 | 287 | yes | `false` | `false` | v1 |
| LV Review Decision (Cloud) | `WBJwoZOo63wzeP69` | True | 55 | 55 | yes | `false` | `false` | v1 |
| LV Scheduled Maintenance (Cloud) | `1fXPuIabz3RsAHgn` | True | 43 | 43 | yes | `false` | `false` | v1 |

Deploy tool's own verdict line: `OK — all active, node counts match, write flags false,
execution order v1.`

The `-` write-flag entries on `LV Backend Status (Cloud template)` are expected — that
workflow has no HubSpot write path to gate (read-only status reporting), consistent with
CLAUDE.md §13.0.2/§13.0.3.

**Comparison against CLAUDE.md §13.0.2's last recorded live counts (pre-Phase-72, the
`59812be` pre-Phase-70-rollback bundle CLAUDE.md's history shows as the last state before
Phase 72 began work):** node counts above (78/287/55/43/30) reflect Phase 72's changes on top
of the Phase 70 v1 baseline (69/287/55/43/30 committed as of Phase 70's close per CLAUDE.md —
ingest lane grew 69→78 for Phase 72's widened fields, others unchanged from Phase 70's
committed counts). This is consistent with plan 01/02/03/04's SUMMARY tables of changed
workflow bodies; no discrepancy found.

**`ALLOW_N8N_ARM` was not set at any point during this task** — the deploy/bounce used only
`ALLOW_N8N_DEPLOY` and the disarmed default state. No workflow was armed before, during, or
after this task.

**No file under `src/`, `n8n/`, `scripts/`, `config/` or `operator-claude-plugin/` was edited**
as part of recording this checkpoint result — the deploy/bounce operated on already-committed,
already-regenerated artifacts from plans 01-07.

### Confirmations (per plan 72-08 Task 1 resume-signal)

- (a) Three properties exist live, confirmed via sync tool's 0-pending result on both objects.
  Type/fieldType/readOnlyValue confirmed in plan 05, not re-GET'd fresh in this task (gap noted
  above).
- (b) All 5 deployed workflows report `active: true`, node counts matching committed JSON,
  `settings.executionOrder: "v1"`, and every write-safety constant `false` (or `-` where no
  write path exists).
- (c) No workflow is armed (`ALLOW_N8N_ARM` never set).

**Task 1 result: PASS**, with the one honest gap noted above (no fresh individual property GET
in this task — relying on the sync tool's diff result plus plan 05's earlier direct GET).

---

## Task 2 — one armed window, one record

Run live 2026-09-13, portal 22617666 (see F72-4 on the wrong-portal MCP caveat). HEAD at start
`19d7dbfa`.

### Pre-check

Telfer (contact `1251`): `phone` = `+61 409 390 022` (non-blank, wrapped in U+202D…U+202C bidi
marks in the portal's rendering), `firstname` Colin, `lastname` Telfer, `company` Australian
Turf Club. Busteed confirmed absent (0 active results; a prior restorable-delete record
existed archived, not active).

### CREATE row — Jimmy Busteed, via `enrich-before-ingest`

One armed contacts window (domain-scoped), disarmed clean afterward. Created contact id
**`352455353810`**, associated to company `9605284724` (Primary).

| Field | Waterfall returned | Landed on re-read (GET) | Match |
|---|---|---|---|
| email | `jbusteed@australianturfclub.com.au` | same | yes |
| mobilephone | `+61 419 212 580` | `+61 419 212 580` | yes |
| phone | `+61 2 9663 8460` | `+61296638460` | yes (normalized) |
| jobtitle | `General Manager of Sales` | same | yes |
| seniority | `Manager` | `Manager` | yes |
| city | `Sydney` | same | yes |
| state | `New South Wales` | same | yes |
| country | `Australia` | same | yes |
| hs_country_region_code | `AU` | `AU` | yes |
| hs_state_code | (none returned) | null | n/a — not returned |
| hs_linkedin_url | `http://www.linkedin.com/in/jimmybusteed` | same | yes |
| **lv_linkedin_url** | `jimmybusteed` (in provenance) | **null** | **NO — F72-1** |
| lv_persona_group | `Sales` | `Sales` | yes |
| lv_phone_2 / lv_mobilephone_2 | (no runner-up returned) | null / null | n/a — not returned |
| hs_additional_emails | (no second email returned) | null | n/a — not exercised, see below |
| lv_contact_enrichment_provenance | — | full JSON present | yes |

`hs_additional_emails`: **NOT OBSERVED** — the waterfall returned no second email for this
person, so D-72-10's provenance-only path was never exercised live. Record as not-observed,
not as pass.

### UPDATE row — Colin Telfer `1251`

One armed enrichment window (id-scoped), disarmed clean afterward. Auto-matched by exact
email (no proposal table). n8n execution `12406`.

| Field | Before | CSV row supplied | After | Result |
|---|---|---|---|---|
| phone | `+61 409 390 022` | `+61 2 9663 8400` | `+61 409 390 022` | **UNCHANGED — SAFE-01 met** |
| firstname/lastname/company | Colin / Telfer / Australian Turf Club | (CSV corrections) | unchanged | not applied — plan 01's flagged consequence, observed live, no operator ruling given this sitting (see F72-3) |
| mobilephone | null (blank) | — | `+61 409 390 022` | filled (fill_blank_only) — **duplicates his own `phone`** (see F72-3) |
| jobtitle | (existing) | `Technical Manager` (waterfall) | unchanged | held `human_review_required`, not promoted |
| lv_linkedin_url | null | — | `http://www.linkedin.com/in/colin-telfer-10539120` | landed (waterfall/85) — **UPDATE path met, unlike CREATE path (F72-1)** |
| lv_contact_enrichment_provenance | — | — | populated | yes |
| hs_additional_emails | null | — | null | unchanged — not exercised (no second email) |

### Flags after final disarm (live read)

| Workflow | id | RECORD_WRITES | CREATE | REVIEW_WRITES |
|---|---|---|---|---|
| LV Enrichment (Cloud template) | `950HPb7a1GgSAIyZ` | `false` | `false` | n/a |
| LV Contact Ingest (Cloud template) | `AwbBeShdPgV48eiY` | `false` | `false` | n/a |
| LV Review Decision (Cloud) | `WBJwoZOo63wzeP69` | `false` | n/a | `false` (review lane never armed) |

### Burst watch

Executions: `12398` Enrichment 13:43:20Z, `12401` Enrichment 13:49:27Z, `12402` Ingest
13:52:32Z (create), `12403` Enrichment 13:53:02Z, `12404` Enrichment 13:55:19Z, `12406`
Enrichment 13:57:22Z (update). After the last disarm at 13:57:30Z: **0 new executions.**

### Confirmations (per plan 72-08 Task 2 resume-signal)

- (a) Created contact carries `mobilephone` and `hs_linkedin_url` — but **NOT**
  `lv_linkedin_url` (F72-1). Every geo field the waterfall returned landed
  (`hs_state_code` correctly null, as none was returned).
- (b) Update row's pre-existing non-blank `phone` is unchanged — met.
- (c) `lv_contact_enrichment_provenance` carries a full entry — met.
- (d) Every `ALLOW_*` flag reads `false` after the send — met.
- (e) The created contact `352455353810` is being hand-deleted by the operator (restorable
  archive) — see Clean-up.

### Findings

| # | Severity | Finding | Evidence |
|---|---|---|---|
| F72-1 | **defect** | `lv_linkedin_url` does not land on the ingest **CREATE** path (it lands correctly on the **UPDATE**/enrich-records path, per Telfer above). Root cause, confirmed in `scripts/build_cloud_workflows.py`: the D-72-22 derivation loop (lines 479-483) builds `confidenceByField` keyed on whatever `source_by_field` names — the CSV canonical key `linkedin_url` — but the candidate object (lines 487-494) writes the value under the PN-1-renamed keys `lv_linkedin_url`/`hs_linkedin_url`. `mergeContacts.js` line 400 looks up `confidenceByField["lv_linkedin_url"]`, which was never set (only `confidenceByField["linkedin_url"]` exists), so the lookup misses and falls back to the flat `csv`/80 confidence — below `lv_linkedin_url`'s `fill_blank_only`@85 threshold, so it is withheld even into a blank field. `hs_linkedin_url` is unaffected because its key is never renamed. Step 2 (deploy+bounce, Task 1) ran before this gate, so this is a defect in already-deployed code, not an undeployed fix. D-72-04's dual write is therefore incomplete on the create path. Not fixed in this gate per the plan's own prohibition — closed by a gap-closure plan. | Contact `352455353810`, provenance JSON (`lv_linkedin_url: jimmybusteed, source: csv, confidence 80, validation_status: human_review_required`), `scripts/build_cloud_workflows.py:479-483,487-494`, `n8n/code/mergeContacts.js:400` |
| F72-2 | doc defect (fixed in Task 3) | `docs/OPERATOR-AUTONOMOUS-BATCH-UAT.md` line 513 names `lv_enrichment_provenance` for a contact; the contact property is `lv_contact_enrichment_provenance` (`config/hubspot_properties.yaml:506`) — `lv_enrichment_provenance` (`config/hubspot_properties.yaml:192`) is the COMPANY property. | `docs/OPERATOR-AUTONOMOUS-BATCH-UAT.md:513`, `config/hubspot_properties.yaml:192,506` |
| F72-3 | note | Telfer's `mobilephone` landed as `+61 409 390 022` — the exact same number as his own `phone` (fill_blank_only correctly filled a blank field, but the filled value duplicates an existing field on the same record). Also: the `firstname`/`lastname`/`company` non-application plan 01 flagged was observed live exactly as predicted; the operator did not give an explicit ruling this sitting on whether that's acceptable — plan 01's two "Operator confirm:" items stand open. | Telfer `1251` re-read, `72-01-SUMMARY.md:186,188,243` |
| F72-4 | note | The gate session's HubSpot MCP connector pointed at portal `443043042` (wrong portal). Its initial MCP pre-check was discarded and every read/write in this gate went through the plugin's portal `22617666` instead. No data crossed portals. | operator report |

## Clean-up

- [x] created contact `352455353810` — hand-deleted by operator 2026-09-13 (restorable archive)
- [x] every `ALLOW_*` flag confirmed `false` after the send
- [x] review lane confirmed never armed (`REVIEW_WRITES: false` throughout)
- [ ] scratch/driver scripts written during the session — not reported by the operator; not
      ticked (unlike Phase 71's Round 2, no script name was named in the report)

## Verdict

**PASS-with-findings.** D-72-17's must-have truths are met on the UPDATE path
(non-clobber/SAFE-01, `lv_linkedin_url` waterfall promotion) and partially met on the CREATE
path: `mobilephone` and `hs_linkedin_url` land correctly, but **`lv_linkedin_url` does NOT
land on create** (F72-1) — the exact "BOTH `hs_linkedin_url` and `lv_linkedin_url`" clause the
plan's must_haves required is not fully met. `hs_additional_emails`'s D-72-10 path was not
exercised live (no second email returned by the waterfall for either row) — recorded as NOT
OBSERVED, not as pass. Nothing was armed before or left armed after the gate; the created
contact was deleted. F72-1 is a real code defect requiring a gap-closure plan before D-72-04's
create-path dual write can be considered complete; it is recorded here, not patched inside the
gate, per the plan's own prohibition.

## Test 3 — gap closure live read-back

Run live 2026-09-13 (executions ran 2026-09-12 22:12-22:15 UTC), per `72-12-PLAN.md` Task 2. This
is the one live gate for the three offline gap closures landed in plans 72-09 (G1, CANDIDATE_ALIASES
fix), 72-10 (G2, local-live fetch widening / CR-01), and 72-11 (G3, case-insensitive overflow dedup
/ WR-02). Operator's full report: transcribed verbatim below from
`/Users/robertli/Desktop/uat-2026-09-12/phase72-test3-report.md`.

**Portal:** 22617666 (plugin private-app key; confirmed via record URL
`app-ap1.hubspot.com/contacts/22617666/...`). HubSpot MCP connector (443043042) was NOT used — all
HubSpot reads went through the plugin's own key (F72-4's wrong-portal caveat honored).

**CSV:** `uat-phase72-gate-create-2026-09-12.csv` (1 row: Jimmy Busteed, Australian Turf Club, no
email, company_id `9605284724`). **match_run_id:** `51678012dec541ada338c5933f8c7812`.
**enrichment run_id:** `b394fc576123450c94ccaeb7ff44d6c7`.

### Step 1 — deploy + bounce, disarmed (verbatim operator stdout)

Five PUTs at 200 (`LV Backend Status`, `LV Contact Ingest`, `LV Enrichment`, `LV Review Decision`,
`LV Scheduled Maintenance`; Backend Status body was byte-identical so its PUT was a no-op).

| Workflow | id | active | live nodes | flags | executionOrder |
|---|---|---|---|---|---|
| LV Backend Status (Cloud template) | `Cj83mOgrIm59oxcX` | True | 30/30 | `-` (no write path) | v1 |
| LV Contact Ingest (Cloud template) | `AwbBeShdPgV48eiY` | True | 78/78 | `ALLOW_HUBSPOT_RECORD_WRITES=false`, `ALLOW_HUBSPOT_CREATE=false` | v1 |
| LV Enrichment (Cloud template) | `950HPb7a1GgSAIyZ` | True | 287/287 | `ALLOW_HUBSPOT_RECORD_WRITES=false`, `ALLOW_HUBSPOT_CREATE=false` | v1 |
| LV Review Decision (Cloud) | `WBJwoZOo63wzeP69` | True | 55/55 | `ALLOW_HUBSPOT_RECORD_WRITES=false`, `ALLOW_HUBSPOT_CREATE=false` | v1 |
| LV Scheduled Maintenance (Cloud) | `1fXPuIabz3RsAHgn` | True | 43/43 | `ALLOW_HUBSPOT_RECORD_WRITES=false`, `ALLOW_HUBSPOT_CREATE=false` | v1 |

Deploy tool's own verdict line: "OK — all active, node counts match, write flags false, execution
order v1." Node counts match Task 1 exactly (78/287/55/43/30 — this batch moved jsCode strings and
one properties list only, never a node), confirming committed and live are level for these four
workflows plus the unchanged Backend Status.

### Step 2 — one armed window, one CREATE

Pre-check: search `lastname EQ Busteed` returned `total: 0` — confirmed absent (environment was
reset since the prior D-72-17 session, which had created id `352455353810`, since hand-deleted).

Ran `enrich-before-ingest` for the one-row CSV above. Match groups: auto_matched 0, proposed 0,
**unmatched 1** (Busteed), unchecked 0. No proposed matches to confirm. After the enrichment
waterfall the row was held as a new person; operator answered "create all 1". One grant opened
over all three lanes (enrichment, contacts, review), record_domains =
`australianturfclub.com.au`, allow_create = true. Each send opened its own record-scoped armed
window and disarmed immediately after.

### Step 3 — read-back of created contact

- **contact id:** `352522004980`
- **lv_linkedin_url:** `http://www.linkedin.com/in/jimmybusteed` — **shape: full URL** (http + www
  + `/in/` path)
- **hs_linkedin_url:** `http://www.linkedin.com/in/jimmybusteed` — **shape: full URL, identical to
  lv_linkedin_url**
- **mobilephone:** `+61 419 212 580`
- **provenance LinkedIn entry** (`lv_contact_enrichment_provenance`, both `lv_linkedin_url` and
  `hs_linkedin_url`): source `waterfall`, confidence 85, validation_status `provider_only` —
  provider-grade, **not `csv`** (the pre-fix fallback that withheld the value in the original
  D-72-17 gate).
- **association to `9605284724`:** yes — contact→company, HUBSPOT_DEFINED typeId 279 + typeId 1
  (Primary).

**F72-5 check (value-shape regression):** the original D-72-17 gate's UPDATE-path `lv_linkedin_url`
landed as a full URL (`http://www.linkedin.com/in/colin-telfer-10539120`, see Task 2 above) and
this CREATE-path value is also a full URL, identical in shape to `hs_linkedin_url` on the same
contact. **No shape regression — F72-5 not opened.**

### Step 4 — flags after disarm

| Workflow | ALLOW_HUBSPOT_RECORD_WRITES | ALLOW_HUBSPOT_CREATE |
|---|---|---|
| LV Enrichment (Cloud template) | false | false |
| LV Contact Ingest (Cloud template) | false | false |
| LV Review Decision (Cloud) | false | false |
| LV Scheduled Maintenance (Cloud) | false | false |
| LV Backend Status (Cloud template) | null (no write nodes) | null |

Every touched workflow reads `false` on both flags.

### Burst watch

All times UTC, 2026-09-12. Now-at-check: 22:16:10.

- **LV Enrichment (`950HPb7a1GgSAIyZ`):** `12411` started 22:12:47 -> success (step-2 match lookup,
  unarmed, empty provider list, no write); `12413` started 22:13:33 -> success (enrichment
  waterfall, armed window #1); `12415` started 22:14:32 -> success (step-4c confirm re-read
  lookup, unarmed, no write).
- **LV Contact Ingest (`AwbBeShdPgV48eiY`):** `12414` started 22:14:02 -> success (the create,
  armed window #2).

**Zero-after-disarm: YES for writes.** The single execution after the final (create) disarm is
`12415` — the post-create confirm re-read on LV Enrichment, an unarmed lookup this verification
itself triggered (empty provider list, no HubSpot write path), fired while both flags already read
`false`. It is a read, not a backend-initiated write.

### Confirmations (per `72-12-PLAN.md` Task 2 resume-signal)

- (a) All five cloud workflows: `active`, node counts, `executionOrder: v1`, and every `ALLOW_*`
  flag `false` after deploy+bounce — met (Step 1 table above).
- (b) Created contact `352522004980` carries BOTH `lv_linkedin_url` AND `hs_linkedin_url`,
  non-null, full-URL shape — **met (the gate)**.
- (c) `lv_contact_enrichment_provenance` for the LinkedIn field: source `waterfall` (provider-grade,
  not `csv`) — met, with a granularity note: the provenance `source` field records the
  provider-waterfall label rather than a specific vendor name (ZoomInfo/Apollo/Lusha); this is
  provider-grade and distinct from `csv`, satisfying the requirement, though the specific vendor
  is not surfaced in that field.
- (d) n8n execution ids `12411`/`12413`/`12414`/`12415`, burst-watch list above, zero new
  executions after the final disarm, every `ALLOW_*` flag `false` — met.
- (e) Created contact `352522004980`: restorable-delete command handed to the operator 2026-09-13; no `204` was reported back in this session (the operator's Test 3 report states "No deletes"). Deletion REQUESTED, not confirmed — the operator confirms or re-runs the DELETE before this row is counted met.

### Findings

**GAP CLOSURE CONFIRMED — F72-1 is CLOSED.** On the CREATE path, `lv_linkedin_url` AND
`hs_linkedin_url` both landed non-null (full-URL shape, provenance source `waterfall`/confidence
85). This closes the D-72-17 defect where `lv_linkedin_url` was null on CREATE and the dual-LinkedIn
write only worked on UPDATE. Evidence: contact `352522004980`, n8n execution `12414` (the create),
2026-09-13.

No STOP conditions were hit: plan_grant verdict OK (ceiling 7 projected vs 2219 sampled
remaining); both windows armed and disarmed cleanly; no disarm failures; no written_records
failures; create accepted.

**Honest gaps (not re-observed in this test, standing exactly as recorded in Task 2):**
- F72-2 (doc defect, `lv_enrichment_provenance` vs `lv_contact_enrichment_provenance`), F72-3
  (Telfer mobilephone/phone duplication + the open firstname/lastname/company operator-ruling
  question), and F72-4 (the wrong-portal MCP connector note) are unchanged by this test — this
  test's scope was F72-1 only, per `72-12-PLAN.md`.
- `hs_additional_emails`'s D-72-10 provenance-only path was again NOT exercised — the waterfall
  returned no second email for this row either. Still not-observed, not pass.
- No deletes beyond the created contact, no code edits, no Webhook Trigger runData pasted, per the
  operator's own report.

## Verdict (Test 3)

**PASS.** F72-1 is closed live: a newly created contact carries both `lv_linkedin_url` and
`hs_linkedin_url`, non-null, matching full-URL shape, provider-grade provenance. All four changed
cloud workflows (contact ingest, enrichment, review decision, scheduled maintenance) plus the
unchanged backend status workflow are deployed, bounced, and read back disarmed at v1 with node
counts matching committed. G2 (CR-01) and G3 (WR-02) were proven offline in plans 72-10/72-11 and
were not separately re-exercised by this live gate (their fixes touch fetch-list widening and
overflow-dedup case-folding, neither of which this CREATE/read-back scenario exercises); no
contradicting live evidence was observed against either.
