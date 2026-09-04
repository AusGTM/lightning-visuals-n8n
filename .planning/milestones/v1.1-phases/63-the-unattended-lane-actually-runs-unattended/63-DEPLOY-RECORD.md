# Phase 63 Plan 05 — Deploy Record

**Date:** 2026-09-02

**Branch of 63-04 this deploy carried:** **DROP.** Per `63-04-SUMMARY.md`, the cheaper-model judge
routing (D-63-05) was evaluated by offline replay and rejected on 2026-09-02 — nothing was ever
committed for it, `scripts/build_cloud_workflows.py` and every `n8n/wf_*.json` file stayed
byte-identical to their pre-63-04 state for that lever. **This deploy therefore carries Phase 62's
already-committed-but-undeployed changes ALONE** — `num_associated_contacts` (companies branch,
`HubSpot Company Search`) and `sourceByField` provenance wiring (`Merge Contacts`,
`wf_contact_ingest_cloud.json`) — not two phases' worth of change. This is the correct outcome per
D-63-08: the divergence between committed and live JSON, open since Phase 62 regenerated all six
workflows on 2026-09-02 without deploying them (CLAUDE.md §13.0.2), had to close regardless of which
branch 63-04 took.

## What was deployed

`.venv/bin/python scripts/deploy_n8n_workflows.py` (dry run) named all five `wf_*_cloud.json`
workflows for update, zero for create, and printed no `REFUSED` line. `_requested_overlay_flags()`
returned `{}` — no `ENABLE_BAKED_FLAGS` overlay requested, so the deployed JSON is byte-for-byte
the committed JSON the test suites ran against. No baked flag was enabled at deploy time.

`DRY_RUN=false ALLOW_N8N_DEPLOY=true .venv/bin/python scripts/deploy_n8n_workflows.py` **[observed
live]** PUT all five workflows, each returning HTTP 200:

| Workflow | id | PUT status |
|---|---|---|
| LV Backend Status (Cloud template) | `Cj83mOgrIm59oxcX` | 200 |
| LV Contact Ingest (Cloud template) | `AwbBeShdPgV48eiY` | 200 |
| LV Enrichment (Cloud template) | `950HPb7a1GgSAIyZ` | 200 |
| LV Review Decision (Cloud) | `WBJwoZOo63wzeP69` | 200 |
| LV Scheduled Maintenance (Cloud) | `1fXPuIabz3RsAHgn` | 200 |

## The bounce

**[observed live]** A bare PUT does not reload a running workflow (project memory
`n8n-stored-vs-running-content`). Each of the five workflows above was deactivated then
reactivated (`POST /workflows/{id}/deactivate` → `POST /workflows/{id}/activate`), following
`prove_scale_up_runtime._bounce_and_verify`'s shape, and re-read independently afterward:

| Workflow | id | post-bounce active | post-bounce nodes | expected nodes | OK |
|---|---|---|---|---|---|
| LV Backend Status (Cloud template) | `Cj83mOgrIm59oxcX` | True | 17 | 17 | yes |
| LV Contact Ingest (Cloud template) | `AwbBeShdPgV48eiY` | True | 29 | 29 | yes |
| LV Enrichment (Cloud template) | `950HPb7a1GgSAIyZ` | True | 123 | 123 | yes |
| LV Review Decision (Cloud) | `WBJwoZOo63wzeP69` | True | 26 | 26 | yes |
| LV Scheduled Maintenance (Cloud) | `1fXPuIabz3RsAHgn` | True | 39 | 39 | yes |

Every affected workflow is active and its node count matches the locally built JSON exactly —
this plan edits `jsCode`/`jsonBody` strings only and adds no node, and the enrichment workflow's
node count is unchanged at 123, matching CLAUDE.md §13.0.2's record.

## The stored read-back (post-bounce, via a fresh GET — proves what was uploaded, not what is
## running; the proof execution below supplies that)

**[observed live]**

- `Build Judge Request` (`LV Enrichment (Cloud template)`, re-GET post-bounce) carries
  `const ANTHROPIC_JUDGE_MODEL = "claude-sonnet-5";` and no reference to a cheaper model —
  matches the DROP branch exactly (the SHIP branch would carry a second, cheap-model constant and
  a conditional select; DROP carries the single pre-existing constant unchanged).
- `HubSpot Company Search` (`LV Enrichment (Cloud template)`, re-GET post-bounce) names
  `num_associated_contacts` in its `jsonBody` properties list — Phase 62's divergence, closed.
- `Merge Contacts` (`LV Contact Ingest (Cloud template)`, re-GET post-bounce) carries
  `sourceByField` in its `jsCode` — Phase 62's other divergence, closed.
- `Build Research Request` (`LV Enrichment (Cloud template)`, re-GET post-bounce) carries
  `const WEB_RESEARCH_MAX_SEARCHES = 5;`, feeding `max_uses: parseInt("5", 10)` on the
  `web_search_20250305` tool spec. **This is the lever-3 observed value** (todo item 3,
  "confirm what `max_uses` is actually in effect in the deployed workflow") — recorded here as a
  starting fact for a later phase. Not changed by this plan; not a deliverable.

All three read-back expectations match the DROP branch and Phase 62's change. If the SHIP/DROP
expectation and the read-back had disagreed, this plan would have halted — they agree.

## The proof execution — what the RUNNING instance actually did

**[observed live]** One disarmed recompute POST was sent for Melbourne Racing Club,
HubSpot company id `9604614548`, via
`scripts.remediate_veto_companies.post_webhook_event(..., recompute=True)` (300s read timeout).
No allowlist was armed on either side of this request.

**Response:** HTTP 200, body `action: "write_blocked"` — a write-blocked gate reason, not a bare
200 and not a reported write. This response IS the proof: the request reached the live workflow,
ran the recompute lane, derived its answer (`lv_anti_icp_flag: "false"`), and refused to write it.

**Execution read back with `includeData=true`:**

- **Execution id:** `12070`
- **Status:** `success`
- **Mode:** `webhook` (a real HTTP-triggered parent run, not a self-dispatched child)
- **Terminal node:** `Build Response`, output `action: "write_blocked"` (matches the HTTP
  response body byte-for-byte)
- **Nodes that ran (22 total):** `Webhook Trigger`, `Parse HubSpot Event`, `IF Scale Up Route`,
  `IF Object Type Supported`, `Route By Object Type`, `IF Company Bare Event`,
  `HubSpot Company Fetch By Id`, `Adapt Company Fetch By Id`, `Build Company Identity`,
  `IF List Input`, `IF Company Recompute`, `Company Gate`, `IF Company Enrich`,
  `IF Company Create`, `Decide Company Action`, `Credit Request`,
  `IF Apollo Credit Requested`, `IF Lusha Credit Requested`, `IF ZoomInfo Credit Requested`,
  `Build Async Ack`, `Build Response`, `Respond to Webhook`.
- **No provider, write, or Anthropic node ran.** Checked against the marker set
  (`HubSpot Update`, `HubSpot Create`, `HubSpot Associate`, `Lusha Enrich`, `Lusha Reveal`,
  `Apollo Enrich`, `Apollo Match`, `ZoomInfo Enrich`, `ZoomInfo Search`, `Sonnet`, `Haiku`,
  `Claude Web`, `Judge Call`, `Research`): zero matches in the 22 nodes that ran. This is the
  same evidence that this proof cost zero credits and zero Anthropic calls — `Decide Company
  Action` ran and derived the veto state, but nothing upstream of it that spends money ever fired.

## What this does not prove

**The judge routing's live behaviour is deliberately unproven by this deploy — and on the DROP
branch, there is nothing new on that surface to prove.** The recompute lane reaches
`Decide Company Action` with no provider, research, judge, or merge node on the path (CLAUDE.md
§13.0), so it cannot exercise judge model routing even in principle. On this branch that limitation
is moot: 63-04 never changed the judge model constant, so `Build Judge Request`'s stored content
(confirmed above) is identical to what was live before this deploy. Proving judge-routing adequacy
was never this plan's job — D-63-06 assigned that to 63-03's offline replay, which is the adequacy
evidence of record and returned DROP. This execution proves deployment reached the running
instance, and nothing more.

## Cost line

**One n8n execution, zero provider credits, zero Anthropic calls, zero HubSpot writes, nothing armed.**

## What was NOT touched

The write allowlist (`TEST_RECORD_IDS` / `TEST_RECORD_DOMAINS`) stayed empty throughout — the
`write_blocked` response and the empty overlay both confirm this independently. No
`ENABLE_BAKED_FLAGS` value was ever set. The first live UNATTENDED, credit-spending batch
remains un-run, per D-63-09.
