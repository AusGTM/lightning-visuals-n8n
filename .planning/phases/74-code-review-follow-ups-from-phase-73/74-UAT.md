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


| Call     | `--only` file                  | Workflows to create | Workflows to update                      | Result                                                                     |
| ---------- | -------------------------------- | --------------------- | ------------------------------------------ | ---------------------------------------------------------------------------- |
| 1 (dry)  | `wf_contact_ingest_cloud.json` | `[]`                | `['LV Contact Ingest (Cloud template)']` | DRY RUN,`deploy_rc=0`                                                      |
| 1 (live) | `wf_contact_ingest_cloud.json` | `[]`                | `['LV Contact Ingest (Cloud template)']` | `updated workflow LV Contact Ingest (Cloud template) (200)`, `deploy_rc=0` |
| 2 (dry)  | `wf_enrichment_cloud.json`     | `[]`                | `['LV Enrichment (Cloud template)']`     | DRY RUN,`deploy_rc=0`                                                      |
| 2 (live) | `wf_enrichment_cloud.json`     | `[]`                | `['LV Enrichment (Cloud template)']`     | `updated workflow LV Enrichment (Cloud template) (200)`, `deploy_rc=0`     |

**Only these two workflows were deployed.** Neither call's create/update list ever named
`LV Backend Status (Cloud template)`, `LV Review Decision (Cloud)`,
`LV Scheduled Maintenance (Cloud)`, or `LV Suggest Discovery (Cloud template)` — the other four
cloud workflows are untouched by this plan.

### Bounce + read-back (one bounce call, per D-74-11's amended text; covers all six per

`bounce_n8n_workflows.py`'s own design — deactivate/activate never alters node body content)


| workflow                              | id                 | active | live nodes | committed nodes | write flags                           | execution order |
| --------------------------------------- | -------------------- | -------- | ------------ | ----------------- | --------------------------------------- | ----------------- |
| LV Backend Status (Cloud template)    | `Cj83mOgrIm59oxcX` | True   | 33         | 33              | (none declared)                       | v1              |
| LV Contact Ingest (Cloud template)    | `AwbBeShdPgV48eiY` | True   | 101        | 101             | RECORD_WRITES=[false], CREATE=[false] | v1              |
| LV Enrichment (Cloud template)        | `950HPb7a1GgSAIyZ` | True   | 289        | 289             | RECORD_WRITES=[false], CREATE=[false] | v1              |
| LV Review Decision (Cloud)            | `WBJwoZOo63wzeP69` | True   | 55         | 55              | RECORD_WRITES=[false], CREATE=[false] | v1              |
| LV Scheduled Maintenance (Cloud)      | `1fXPuIabz3RsAHgn` | True   | 43         | 43              | RECORD_WRITES=[false], CREATE=[false] | v1              |
| LV Suggest Discovery (Cloud template) | `VJJBZ2oJ0079MSzG` | True   | 26         | 26              | (none declared)                       | v1              |

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

**Running total: 2 executions consumed by this plan.** Ceiling held.

### Send 1 — ingest lane, all-update batch (zero create-routed rows)

- **Company/contacts used:** 3 real, pre-existing HubSpot contacts (found read-only via a
  contacts search), sent by email only: `kerynthogan@bigpond.com`,
  `stefanie@triplesdata.com`, `alex.h@lightningvisuals.com`.
- **run_id:** `f3eea95ccf9f4912834863eff4fc0895`
- **execution_id:** `12676`
- **Consent gate:** the dispatch call's own `armed=True` (the plugin's per-send consent that
  the POST should be made) — a DIFFERENT thing from the backend's write-safety flags, which
  stayed false throughout (see Task 1's bounce table and the post-send re-read below).
- **Result:** all 3 rows came back `action=write_blocked`, `outcome=write_blocked`, reason
  `"allowlist denied this write (test-record allowlist empty or non-matching)"` — the expected
  disarmed-refusal shape. `written_records_failures=[]`.

**runData proof (execution 12676, all nodes ran exactly once — no double-fire on this
execution):**

- `Ingest Merge Response` (6 declared input slots) **fired once**, with `source` showing
  exactly one delivery per input index: index 0 `Decide Action Snapshot` (the 3 real rows),
  index 1 `Set Review` (0 items — no review-routed rows), index 2 `Associate Lane Sentinel Gate` (association lane unreached — refused before any association attempt), index 3
  `HubSpot Update Refusal Pass-Through` (the 3 `write_blocked` update refusals), index 4
  `HubSpot Create Gate Unreached Sentinel Gate` (create lane never reached — zero create rows),
  index 5 `Create Failure Row Sentinel Gate` (the D-74-02 sentinel: fired because the
  decided-row set contained zero create-routed rows). Total 10 items across the 6 inputs — a
  mix of the 3 real rows and 3 one-item sentinel markers.
- `Build Ingest Response` **produced exactly 3 items** — matching the 3 sent rows exactly.
  **No row lost.**
- `Build Ingest Ack` / `Respond to Webhook` each ran once with 1 item — the D-70-07
  unconditional ack, not a row-outcome carrier.

**A documented divergence from D-74-11's literal wording ("confirm the create carry merge
fires once"), corrected on re-review (the sentinel attribution below was wrong in this
document's first cut — `Create Carry Merge`'s own consumer chain and `Ingest Merge Response`
input 5 are covered by TWO DIFFERENT sentinels, not one):** the node literally named `Create Carry Merge` **did not run at all** in this execution — it has zero entries in `runData`.
Tracing why: its three declared producer inputs (`HubSpot Create` output 0, `HubSpot Create Permitted Pass-Through`, `Create Error Stamp`) are all downstream of `HubSpot Create Write Gate IF`, which itself never ran because the whole create branch received **zero items** upstream
(an all-update batch routes 0 rows down the create lane) — per the platform fact already
recorded in CLAUDE.md §13.0.3 ("a node fed zero items does not run at all, and so contributes
no delivery to anything it feeds"), `Create Carry Merge` never received ANY delivery on any of
its 3 inputs and is therefore fully starved, not a v1-drain candidate. Three separate facts,
not one:

1. **`Create Carry Merge` itself is fully starved** and never runs on this batch shape —
   consistent with, and predicted by, D-74-03's index-0-only padding correction (74-04).
2. **`Build Association Request Merge` input 1** — the merge `Create Carry Merge`'s own
   consumer chain (`Pair Create Outcome To Row`) would otherwise feed — is instead covered by
   `HubSpot Create Carry Unreached Sentinel Gate`, a **pre-existing Phase 70 (D-70-23 idiom)
   starved-lane sentinel**, unrelated to this phase's D-74-02 work. It fired
   (`item_counts=[1]`) and delivered directly to that input, bypassing `Create Carry Merge` and
   `Pair Create Outcome To Row` entirely.
3. **`Ingest Merge Response` input 5** — the input D-74-02 actually added a sentinel for — is
   covered by `Create Failure Row Sentinel Gate` (already named in the `Ingest Merge Response`
   paragraph above), which fired because the decided-row set contained zero create-routed rows.
   **This is the first live proof that D-74-02's own sentinel works correctly** for exactly the
   batch shape it was built for.

Traced `Build Association Request Merge` (2 declared inputs) and confirmed it fired once with
both inputs accounted for: input 0 from `HubSpot Update Carry All Refused Sentinel Gate` (all 3
updates were refused, so the "all refused" sentinel fired rather than a real association
attempt), input 1 from `HubSpot Create Carry Unreached Sentinel Gate` (fact 2 above). **The
create-carry lane completed normally with no starvation and no row lost — via two dedicated
bypass sentinels (one pre-existing, one this phase's own) rather than via `Create Carry Merge`
itself executing.** The underlying correctness goal D-74-11 names (no starvation, the lane
completes normally on an all-update batch) is proven true, even though the literal node name in
the plan's prediction did not run — the same class of plan-vs-observed-mechanism divergence
74-04-SUMMARY.md already recorded for D-74-14.

**Bonus `[observed live]` note for 74-04's topological drain-order rule:** in this same
execution, `Build Response Merge Stage 2` — upstream of `Build Response Merge` — drained its
second (partial) run before `Build Response Merge`'s own second run, matching the drain-order
preference 74-04 fixed (the drain prefers the most-upstream qualifying Merge). See the
enrichment send's double-fire analysis below for the full trace.

### Send 2 — enrichment lane, zero-cost recompute request

- **Company used:** Melbourne Racing Club, HubSpot id `9604614548` — a real, pre-existing
  company confirmed (read-only GET, before and after the send) to carry a non-blank
  `lv_org_type` (`individual_club_team`) and `lv_icp_tier` (`C`), unchanged by the send.
- **Shape used:** the `recompute` request-level boolean against this single company
  (`scripts/remediate_veto_companies.post_webhook_event(..., recompute=True)`), the shape
  CLAUDE.md §13.0 records as costing 0 provider credits / 0 Anthropic calls / 1 execution. The
  fallback (an already-complete company whose gate skips) was not needed.
- **run_id:** `5d84ca096fe24cac869b49bbebfe46d0`
- **execution_id:** `12677`
- **Ack:** `{"run_id": "5d84ca096fe24cac869b49bbebfe46d0", "accepted": true, "row_ids": []}`

**Zero provider/Anthropic spend — proven from the node list, not assumed.** The full list of
71 nodes that ran (counted from `tests/n8n/fixtures/frozen/exec_12677.runData.json`'s own
`runData` key count) contains **no** `ZoomInfo Mint Company`, `Apollo Org`, `Lusha Company`,
`Claude Web Research`, or `Judge Call` — only the three credit-skip nodes (`Apollo Credit Skipped`, `Lusha Credit Skipped`, `ZoomInfo Credit Skipped`), which are bypass markers, not
provider calls. **Positive half (the intended lane was actually taken):** `IF Company Recompute` ran and its true-branch pass-through (`IF Company Recompute -> Decide Company Action Merge Pass-Through`) ran, routing straight to `Decide Company Action` — bypassing the
entire provider waterfall.

**Response merge stages converged.** `Build Response Merge Stage 1` (1 run, 6 items), `Build Response Merge Stage 3` (1 run, 2 items), `Filter Build Response Rows` (2 runs — see below),
and `Build Response` (1 run, **exactly 1 item** — the single company sent) all completed.
`HubSpot Company Update Write Gate` refused the write (disarmed), routing through `HubSpot Company Update All Refused Sentinel` rather than the real `HubSpot Company Update` node (which
never ran — 0 credits, 0 writes, matching the post-send re-read below).

**A double-fire on two Merge nodes — the ALREADY-DOCUMENTED v1 pattern, not a new one.**
`Build Response Merge` and `Build Response Merge Stage 2` each ran **twice**
(`item_counts=[15,1]` and `[7,1]` respectively). Traced both runs' `source` arrays: run 0 on
each is a genuine full completion (every declared input delivered from its real producer in
one pass); run 1 on each has **exactly one** input filled (by `Build Response Merge Stage 2`'s
own second run, and by `Recompute Requested Sentinel Gate` respectively) with every other
input `null` — the same shape CLAUDE.md §13.0.3 already records for `Decide Company Action Merge`'s Gate-11 double-fire (a v1 end-of-run drain firing on a single arrived input,
`requiredInputs: 1` under `append` mode). This execution's own `Decide Company Action Merge`
shows the identical pattern in miniature: it ran once with both its 2 inputs filled together
(`IF Company Recompute -> ... Pass-Through` and `Recompute Requested Sentinel Gate`, both
delivering in the SAME run because `Recompute Requested Sentinel Gate`'s single firing fans out
to multiple consumers simultaneously). **`Filter Build Response Rows` ran twice
(`item_counts=[1, 0]`)** — its second run correctly emitted **zero** items, so the drained
marker from `Build Response Merge`'s second run never reaches `Build Response` a second time.
**No undrained pending run, no row lost, no phantom row in the final response** (`Build Response` = 1 item, matching the 1 company sent).

**MN-01 (the folded todo) — reconfirmed, not resolved; correctly stays open.** This execution's
double-fires are ANOTHER live instance of the walker's already-modelled "one full completion +
one single-input end-of-run drain" shape (pinned since Gate 11), not the genuinely different
"two independently partially-filled pending runs" shape MN-01's own trigger asks for. No change
to the todo's disposition — `.planning/todos/pending/2026-09-11-merge-multi-run-drain-and-grouping-unobserved.md`
stays open, trigger unchanged, per D-74-12/Task 3's explicit instruction ("stay pending... unless
74-04's search produced evidence" — 74-04's search found nothing, and this plan's own new
evidence reconfirms rather than contradicts the existing model).

### Freezing

Both executions frozen via `scripts/freeze_execution_rundata.py 12676 12677` (its own
`load_dotenv()`, no scratchpad driver needed for this read-only step):

- `tests/n8n/fixtures/frozen/exec_12676.runData.json`
- `tests/n8n/fixtures/frozen/exec_12677.runData.json`

`node --test tests/n8n/frozenFixtureSecrets.test.mjs tests/n8n/walkerEngineFidelityV1.test.mjs tests/n8n/v1RuntimeRecordings.test.mjs` → **13/13 pass**, 0 fail. The D-74-09 guard's in-scope
file count picked up both new files automatically (directory is read at test-load time); no raw
item, header, or token value survived redaction (spot-checked: `headers` keys read the fixed
placeholder string).

### Post-send burst watch

Re-listed executions for both workflows well over 3 minutes after the enrichment send (the
2026-09-10-runaway workflow), after the freeze/commit/analysis work above had already consumed
that much wall time:

- Ingest (`AwbBeShdPgV48eiY`) max execution id: **`12676`** — exactly the one send, nothing
  after it (baseline before Task 1's bounce was `12663`; `12676` is the only new execution).
- Enrichment (`950HPb7a1GgSAIyZ`) max execution id: **`12677`** — exactly the one send, nothing
  after it (baseline was `12662`; `12677` is the only new execution).

**Running total confirmed empirically, not merely asserted: exactly 2 new executions across
this whole plan (12676 + 12677).** No burst; the deactivate-workflow stop was never needed on
either send.

### Post-send state

- Both live bodies re-read AFTER both sends: `ALLOW_HUBSPOT_RECORD_WRITES=['false']`,
  `ALLOW_HUBSPOT_CREATE=['false']` on both `LV Contact Ingest (Cloud template)` and
  `LV Enrichment (Cloud template)` — **unchanged from Task 1's pre-send read.**
- Melbourne Racing Club (`9604614548`) re-read AFTER the send: `lv_org_type` and `lv_icp_tier`
  byte-identical to the pre-send read. **No HubSpot record was created or updated by either
  send.**
- The enrichment lane's research-error branch (`IF Research Errored` /
  `Companies Research Errored Sentinel`, D-74-14) was **not exercised** by either send — the
  recompute lane bypasses the entire provider/research path by design. It **stays
  `[documented]` only**, exactly as D-74-14 and the plan's own success criteria require.

### Process notes (for the SUMMARY)

- **Task 1's inline `<verify>` false positive should have been surfaced before Task 2's
  proof sends spent the plan's two-execution budget**, not just before Task 3. It was caught
  and analyzed correctly (see Task 1's write-up above), but the sequencing — verify, analyze,
  THEN proceed to Task 2 — is the right order for any future plan carrying an inline
  verify-then-expand gate; here the analysis happened concurrently with, not strictly before,
  moving on. No harm resulted (the underlying bodies were genuinely disarmed throughout), but
  the discipline gap is worth naming rather than silently smoothing over.
- **One bounce, not two.** D-74-11 (amended, `74-CONTEXT.md`) says "bounce" (singular) after
  both scoped deploys; the PLAN.md Task 1 action text says "Call the bounce entry point after
  each deploy". This execution took the CONTEXT.md reading (one bounce call after both
  deploys) since `bounce_n8n_workflows.py` has no per-workflow scoping and bounces all six
  every call regardless — a second call would have been a no-op repeat with identical end
  state (both target workflows already active, node counts matched, flags false, v1). Recorded
  as a literal-wording divergence, not a defect: the acceptance criteria that actually matter
  (node counts match, flags false, active, v1, zero-execution watch) were all independently
  verified after the single bounce.
- **A concurrent commit (`4eca4197`, author `Robert Li`, real operator account) landed on
  `master` between this session's initial `git log` check (which showed `74853870` as HEAD)
  and this plan's first commit.** Verified before proceeding: it touches
  `tests/n8n/ingestCreateErrorLane.test.mjs`, `74-05-SUMMARY.md`, `CLAUDE.md`, and
  `.planning/WINDOWS.md` only — **no `n8n/wf_*.json` file** — so the node counts, deploy
  targets, and everything this plan verified against the committed graph bodies are unaffected.
  The plan's commit ledger (`gsd-plan-head-before-74-06`) was created retroactively, backdated
  to `4eca4197` (the true parent of this plan's first commit), so `actuals.commits` in the
  eventual SUMMARY correctly counts from that base.
- **This document's first cut misattributed `Build Association Request Merge` input 1's
  sentinel to D-74-02** (it is a pre-existing Phase 70 mechanism); corrected in a follow-up
  commit rather than amending the commit that shipped the error, per this run's no-amend
  git-safety rule. Commit `fbe6491a`'s own message carries the original misattribution and is
  left as-is (git history is not rewritten); this file is the corrected record.

## Task 4 — Operator confirmation

**Operator replied "confirmed" on 2026-09-19.** Per the task's `<resume-signal>`, all six items
from `<how-to-verify>` are confirmed:

1. **Two execution ids, running total 2.** `12676` (ingest) and `12677` (enrichment) — exactly 2
   for this plan.
2. **Live node counts equal committed generated counts.** Ingest 101 = 101 (`74-05-SUMMARY.md`);
   enrichment 289 = 289 (`74-04-SUMMARY.md`).
3. **Write-safety flags read false after both sends.** `ALLOW_HUBSPOT_RECORD_WRITES=['false']`,
   `ALLOW_HUBSPOT_CREATE=['false']` on both live bodies, unchanged from the pre-send read.
4. **Only two workflows deployed.** Neither deploy call's create/update list ever named the
   other four cloud workflows (Task 1's deploy table).
5. **No HubSpot record created or updated by either send.** Melbourne Racing Club
   (`9604614548`) re-read byte-identical after the send; the three ingest contacts all returned
   `write_blocked`.
6. **Research-error branch not exercised live, stays documented-only.** The recompute lane
   bypassed the entire provider/research path by design; `IF Research Errored` /
   `Companies Research Errored Sentinel` (D-74-14) never ran.

**Independent re-verification (read-only, 2026-09-19, performed by the orchestrator after the
checkpoint was returned, before the operator's "confirmed" reply) — cited here as corroborating
evidence, not a substitute for the operator's own confirmation:**

- **Item 1:** instance-wide execution list, ids > 12663 (the pre-Task-1 baseline) on 2026-09-19:
  only `12676` (ingest, 10:00:09Z) and `12677` (enrichment, 10:02:13Z); nothing after 12677.
  Total exactly 2.
- **Item 2:** live node counts ingest 101 / enrichment 289 equal committed; node-name sets equal;
  the other four workflows also equal committed (33/55/43/26).
- **Item 3:** every `ALLOW_HUBSPOT_RECORD_WRITES` / `ALLOW_HUBSPOT_CREATE` /
  `ALLOW_HUBSPOT_REVIEW_WRITES` declaration on both live bodies reads the `"false"` literal.
- **Item 4:** only ingest (`updatedAt` 2026-09-19T09:54:45Z) and enrichment (09:54:58Z) changed
  today; the other four workflows' `updatedAt` are 2026-09-18.
- **Item 5:** contacts `701`/`951`/`901` `lastmodifieddate` 2026-09-07 / 2026-07-17 / 2026-09-18
  — all before send 1; company `9604614548` `hs_lastmodifieddate` 2026-09-17T21:46Z — before
  send 2; `lv_org_type`/`lv_icp_tier` unchanged. Frozen `12676`/`12677` runData contain no
  `HubSpot Update`, `HubSpot Create`, or `HubSpot Company Update` run.
- **Item 6:** frozen `12677` has no `IF Research Errored` / `Companies Research Errored Sentinel`
  run and zero provider/judge/research nodes.
- **Extras:** `node --test tests/n8n/frozenFixtureSecrets.test.mjs` 2 pass / 0 fail;
  `plugin.json` carries `"version": "0.52.0"` once; CHANGELOG newest entry
  `## [0.52.0] - 2026-09-19`.

No secret, token, header, or credential value is reproduced above — only execution ids,
timestamps, node counts, and property values already stated elsewhere in this document.

**The plan is closed.**
