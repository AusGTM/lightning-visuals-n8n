---
status: partial
phase: operator-autonomous-batch
source: docs/OPERATOR-AUTONOMOUS-BATCH-UAT.md
run_id: a254d1eda71246a2a964922cdf5c2bd2
client: operator-claude-plugin 0.45.0 (installed_plugins.json gitCommitSha e6594548; cache scripts byte-identical to repo; 2903 passed / 5 skipped)
backend: A — v1 bodies (287/69/55/43/30), committed and live level per Phase 70 Gates 10-12; both write flags "false" before and after
date: 2026-09-11
executions: 12365-12376
hubspot_writes: 0
---

# UAT — first live supervised batch, 2026-09-11

## Headline

Zero HubSpot writes in either batch. The lane under test, `enrich-before-ingest`, cannot
produce an ingest write on THIS input: matched rows hand off to `enrich-records` by id (never
ingested), and every create is held `no_match` by design (D-70-11), with no path from an
approved hold to a send (pending design todo
`2026-09-11-no-plugin-path-turns-an-approved-held-row-into-a-sent-row`). So the ingest send
was 0 rows on the mixed batch, and batch 2 (two exact-email matches) sent nothing at all.
Tests 7, 8 and the D-70-17 "every row back exactly once across two chunks" assertion were
NOT exercised. The UAT doc's §1d expectations for rows 2 and 3 (create refused to review at
`Decide Action`; create written + associated) were wrong against the shipped flow; they
belong to `contact-upload`.

## Inputs

`~/Desktop/uat-2026-09-11/uat-batch-2026-09-11.csv` (rows: John Miller 3601 SCTC; Katie
Poggioli, Atherton Turf Club absent; Jimmy Busteed, ATC, no email; Craig Sheppard 3501
Ipswich, no email) and `uat-single-lane-2026-09-11.csv` (Grant Dewsbury 7101 Darwin; Nathan
Exelby 37400807974 Ipswich). Selection record in the UAT doc §1d.

## Tests

### 1. client 0.45.0, autonomy ON
- expected: step 1 says the batch will not ask before spending/writing; names `autonomy.write` as the off switch.
- result: pass (partial wording). Step 1: "autonomy.write is on. So this round proceeds without a deliberate ask — it states the grant price, pauses briefly for an interrupt, then opens the grant and continues." Did not name `operator.local.json` as the place to switch it off.

### 2. Guardrail A sees a clean backend
- expected: no dirty-backend refusal; both flags "false" before.
- result: pass. Pre-run read (this session, 2026-09-11): both workflows `ALLOW_HUBSPOT_RECORD_WRITES`/`ALLOW_HUBSPOT_CREATE` "false". No refusal at step 5.

### 3. match gate preserved
- expected: one numbered table, waits; nothing spends before the answer.
- result: pass. One table for Craig Sheppard vs 3501; operator answered `4. approve`. First enrichment (waterfall) execution is 12372 at 10:03:02Z, after the approve. BUT see finding F1: the unarmed match itself was sent six times.

### 4. chunk plan matches the cap
- expected: 2 chunks for 3-4 rows at cap 2.
- result: n/a as written. Only 2 rows reached enrichment (the 2 unmatched), so 1 chunk of 2. The 4-row batch never spans chunks on this lane because matched rows are removed before chunking.

### 5. state, pause, open, proceed
- expected: grant block, `Execution ceiling:`, Apollo `unconfirmed`, ~7 s pause, opens with no question.
- result: pass on the ask/pause/open. Ceiling `ok` — 245 spent, 2255 remaining of 2500, 7 projected (run_audit: 247/2253 at report time). Grant scope: 0 record ids + 1 domain (`athertonturfclub.com.au`), allow-create on. Timestamps of the pause not captured (operator did not record them). Deviation: ALL THREE provider balances read `unconfirmed`, not only Apollo — see F3.

### 6. interrupt window
- not attempted.

### 7. write armed per send, disarmed after
- expected: each send opens its own record-scoped window; both flags "false" after.
- result: NOT EXERCISED — no ingest send was made, so no ingest arming happened. Enrichment: run_audit `disarm.outcome: disarmed`, observed `ALLOW_HUBSPOT_CREATE/RECORD_WRITES/REVIEW_WRITES` "false", `TEST_RECORD_DOMAINS` "" `TEST_RECORD_IDS` "" on 950HPb7a1GgSAIyZ after the run. Post-run read (this session): both workflows "false". Execution 12372 ran in `mode: propose`; no write-gate node ran.

### 8. outcomes per row
- result: NOT EXERCISED as specified. John Miller 3601 and Craig Sheppard 3501: matched, handed off to `enrich-records`, nothing written. Katie Poggioli: enriched thin (title only, "Club Contact"), held `no_match`. Jimmy Busteed: enriched rich (`jbusteed@australianturfclub.com.au`, phone, mobile, LinkedIn, Sydney), held `no_match`. Batch 2: both matched by email, nothing sent. HubSpot post-run check: see "HubSpot after" below.

### 9. end-of-run report is the whole account
- result: partial. Report persisted (`run_report-a254d1e….md`), `run_id` consistent across run_state, run_audit, run_manifest, held_queue. Row accounting 2/2. Banner `REPORT INCOMPLETE — 2 gap(s)`: (a) `written_records: absent` — nothing was written, so absence is the true account, yet it is reported as a gap (cf. quick task 260911-ao0's rule that a leg writing nothing is reported as such, not as failed); (b) held_queue "carries no run attribution". Per-record outcomes "(no records)". Provider balances: all three "unreadable (not_reported_by_status_endpoint)" — spend bounded for none. `contactability` counts absent (no ingest).

### 10. declines round
- not attempted.

## Findings

- **F1 (major, budget): the unarmed match is re-sent on every later step.** Executions 12365, 12366, 12368, 12370, 12373, 12374 are SIX `propose`-mode sends of the same four rows (fresh `run_id` each: 61c41631…, 92ddf4f1…, 26a4cf28…, 279a2274…, 0c2c24ac…, 6aa8b0d7…), and 12375/12376 are TWO sends of batch 2. Cause, traced in `skills/enrich-before-ingest/SKILL.md` lines 180-200 and 650-668: `outcome = preingest.match_batch(plan, cfg)` lives in a Python variable inside one fence; every later fence that needs `classified` (candidate detail, approval, ids, partition, report) is a fresh process and re-POSTs. Nothing persists the step-2 match outcome. 8 executions for what should be 2. On Starter (2.5K/month) this is a 4x amplification per batch before any write.
- **F2 (major, design, is the pending todo): no create can leave this lane.** Matched → handoff, unmatched → held, so `partition_for_ingest` always returns 0 sendable on a batch like this. The D-70-17 mixed shape cannot be produced by `enrich-before-ingest`; it needs `contact-upload`.
- **F3 (major): plugin reads no provider balance at all.** `run_audit.balances`: apollo/lusha/zoominfo all `not_reported_by_status_endpoint`; ceiling bounded nothing. `scripts/check_provider_credits.py` (repo, `.env` keys) read Lusha 3860 and ZoomInfo 9367 the same morning. The UAT doc's premise ("Lusha and ZoomInfo print a number; Apollo unconfirmed") holds for the repo script, not for the plugin's report.
- **F4 (minor): step 6 asked a question** ("how do you want to handle batch 1's two held rows?") on a lane the doc says does not ask at step 6. Consequence of F2, not of autonomy.
- **F5 (minor): `timeout` absent on macOS** — a driver the operator's Claude wrote used GNU `timeout`; re-ran without it. Not in any SKILL.md fence.
- **F6 (minor, hygiene): `held_queue.json` is global and stamped with the latest run_id.** After this run it holds row-1 and row-4 = Barry Milton, Devonport Racing Club (a prior run, duplicated), under `run_id: a254d1e…` and the same `resume_fingerprint` as Katie/Jimmy. Report already declares the missing attribution; the row-id namespace collision across runs is new.
- **F7 (info): 267 stale local state files pruned** at step 1. 3 backend-status executions (12367, 12369, 12371) interleaved with the match sends.
- **F8 (info): the grant's record scope could not cover Jimmy Busteed** (no email, no domain); the assistant flagged it rather than widening. Moot because nothing was sent.

## HubSpot after
- pending: read-only probe (contacts 3601/3501/7101/37400807974 `lastmodifieddate`; Katie/Jimmy/Atherton absent).

## Execution census (n8n API, 2026-09-11 09:56Z-10:18Z)
| id | workflow | mode | run_id | rows |
| --- | --- | --- | --- | --- |
| 12365 | enrichment | propose | 61c41631… | row-1..4 |
| 12366 | enrichment | propose | 92ddf4f1… | row-1..4 |
| 12367 | backend status | — | — | — |
| 12368 | enrichment | propose | 26a4cf28… | row-1..4 |
| 12369 | backend status | — | — | — |
| 12370 | enrichment | propose | 279a2274… | row-1..4 |
| 12371 | backend status | — | — | — |
| 12372 | enrichment (waterfall, 125 nodes) | propose | a254d1ed… | row-2, row-3 |
| 12373 | enrichment | propose | 0c2c24ac… | row-1..4 |
| 12374 | enrichment | propose | 6aa8b0d7… | row-1..4 |
| 12375 | enrichment | propose | 4235377f… | row-1, row-2 (batch 2) |
| 12376 | enrichment | propose | a1bf5f7e… | row-1, row-2 (batch 2) |

All `success`, all settled (no `running`). 16.9 SC-3 (companies-lane update at 2xx) not discharged.

## Clean-up
Nothing to delete in HubSpot. Held-queue entries for Katie Poggioli and Jimmy Busteed remain in the review queue.

## Next
1. Decide the F2 design (the todo's `decision_needed`) — now with real held rows.
2. Fix F1 (persist the match outcome per run_id) before any batch that costs credits; it is the cheapest budget leak found so far.
3. Re-run the write half of this UAT through `contact-upload` with the same 6 rows, Jimmy's revealed email included: that is the D-70-17 shape on the lane that actually creates.
