# 54-01 Task 2: G-3's saving, measured out of live execution history

**Date:** 2026-08-27
**Method:** `operator-claude-plugin/scripts/measure_dispatch.py` (Task 1), run read-only
against the `LV Enrichment (Cloud template)` workflow (`950HPb7a1GgSAIyZ`) — no arming, no
dispatch, 0 new n8n executions, 0 provider credits, 0 Anthropic calls spent by this task.
Every execution id below is an execution that already ran before this task started.

## Figures

| Figure | Before (pre-F2) | After (post-F2) | Basis |
|---|---|---|---|
| n8n executions, one record | 3 (all refused) | 1 (see verdict below) | **measured** — both sides read from live execution history via `get_execution`/`executions_in_window` |
| Provider credits | — | — | **unmeasured** — no balance snapshot was captured immediately before and after either send; a live balance read taken now would not be attributable to a specific past send, so this task does not report a delta it cannot support |
| Anthropic dollars/record | $0.0686 | $0.0686 | **projected** — a floor derived from `config/cost_rates.json`'s `anthropic_usd_per_record` rate, dated `measured_on: 2026-07-30`. No code path in this repo reads back Anthropic's `msg.usage` for a real execution, so this figure is a static rate-table multiplication, never a captured actual (OP-54-05). |

The Anthropic row's basis word (`projected`) is deliberately not the word used for the
executions row (`measured`) — the two figures are established by different means and must
not read the same.

## BEFORE: the pre-F2 double-pass, read directly by execution id

Three executions, read via `get_execution`, all touching contact `347569451461` (John
Tsatsimas), all on 2026-08-25, all before F2 landed:

| Execution | `startedAt` | `Decide Action` output | Match |
|---|---|---|---|
| `11934` | 2026-08-25T00:40:35.774Z | `action: write_blocked` | tier `high`, auto `true`, `matched by fetch_by_id` |
| `11935` | 2026-08-25T00:49:24.229Z | `action: write_blocked` | tier `high`, auto `true`, `matched by fetch_by_id` |
| `11937` | 2026-08-25T02:05:53.065Z | `action: write_blocked` | tier `high`, auto `true`, `matched by fetch_by_id` |

Every one of these three executions ran the full pipeline (fetch → provider waterfall →
normalize/score → `Decide Action`) and correctly matched the record by id — and every one
returned `write_blocked`, because before F2 the ungranted send's `armed=True` authorized
only the client's own POST, never the backend's write-safety flags
(`.planning/debug/resolved/walk-write-path-defects.md`, "F2"). This is the double-pass (in
fact triple-pass, here) G-3 names: full cost spent, nothing written, on every one of the
three tries.

## AFTER: the post-fix send, read directly by execution id

Reading the same workflow's history for the days immediately following F1/F2/F3
(2026-08-25/26), contact `347569451461` was touched by three further executions:

| Execution | `startedAt` (UTC) | `Decide Action` output | What it wrote |
|---|---|---|---|
| `11956` | 2026-08-25T15:06:23.877Z | `action: enrich` | `jobtitle`, `phone`, `mobilephone`, `seniority` — the pre-location-fields property set |
| `11958` | 2026-08-25T16:12:53.296Z | `action: write_blocked` | nothing — a genuinely refused send, in between the two writes below |
| `11960` | 2026-08-25T21:01:12.008Z | `action: enrich` | `email`, `firstname`, `lastname`, `city`, `country` — the location-fields property set added by the 2026-08-26 permissive-contact-lane deploy |

These three executions are **not** three passes of one ask. `11956` predates the
location-fields deploy (its `Decide Action` output carries no `email`/`city`/`country`
keys at all) and `11960` postdates it — they are two distinct operator requests, each
touching a different property set, roughly six hours apart. `11958`, in between, is a
genuinely refused send (a real `write_blocked`, per 54-RESEARCH.md's §3 finding that this
outcome stays real and reachable after F2 whenever a send is outside the current grant's
scope or the admin has not enabled write grants) — not evidence of a lingering two-pass
defect.

**The single-record, single-ask measurement is isolated to `11960` alone.** Its own
`Parse HubSpot Event` output shows a bare single-object dispatch (`event_id:
"sub:347569451461:undefined"`, no list/chunk wrapper), and no other execution in a
window bracketing it (`2026-08-25T20:59:00Z` .. `2026-08-25T21:03:00Z`) exists for this
workflow. `measure_dispatch.executions_in_window` + `passes_for_record` against that
window, enriched with each candidate's `Decide Action` `hs_object_id` (the per-record key
`executions_client`'s bare list items do not themselves carry), returns:

```
{"count": 1, "execution_ids": ["11960"], "basis": "measured"}
```

**One record, one ask, one execution.** This is the concrete, execution-id-traceable
proof that F2 closed the accidental double-pass mechanism for the documented interactive
lanes — not two full-cost passes (one refused, one re-armed and re-sent), but exactly one.

## `compare_to_projection`: what `envelope()` projected vs what actually ran

For this same record set (`record_ids=["347569451461"]`, `object_type="contacts"`),
`chunking.plan_chunks` (the pure, no-I/O formula `write_grant.envelope()` itself calls,
never re-derived) resolves `chunk_count=1` at the configured `max_records_per_chunk=2`
ceiling. `envelope()`'s `projected_executions` formula (`chunk_count + record_count`)
therefore projects **2** executions for this send.

```
measure_dispatch.compare_to_projection(
    {"count": 1, "execution_ids": ["11960"], "basis": "measured"},
    {"projected_executions": 2, "basis": {"projected_executions": "projected"}},
) == {
    "measured_executions": 1,
    "projected_executions": 2,
    "projection_basis": "projected",
    "delta": -1,
    "verdict": "differs",
}
```

**Verdict: `differs`.** The measured single-record count (1) is *lower* than
`envelope()`'s projected figure (2) — the `+1 sub-execution per record` half of the
formula's own comment (`write_grant.py:120-126`, "one webhook execution per chunk, plus
one sub-execution per record... nobody has counted executions for a multi-chunk grant end
to end") does not hold for a single-chunk, single-record, bare-object send: the entire
pipeline (fetch, provider waterfall, `Decide Action`, `HubSpot Update`) ran inside `11960`
alone — n8n's own execution list shows no second, sub-workflow execution spawned for this
record. `envelope()` is not corrected by this task (Task 3 only relabels its basis, per
this plan's scope); the discrepancy is recorded here as the first real data point against
the formula, for whoever revisits it.

## The residual this task does NOT close: the multi-chunk case

WINDOWS.md id 26's complaint is specifically that **nobody has counted a MULTI-CHUNK
grant end to end.** The single-record send measured above exercises `envelope()`'s
formula only at `chunk_count == 1`. This task has no live multi-chunk send in reachable
history to read (the BEFORE/AFTER pairs above are the only enrichment-workflow sends this
plan's budget names, per its own execution-budget line: "0 new n8n executions... If
history no longer holds them, Task 2 stops and says so rather than spending a send to
manufacture a number"), so the multi-chunk case — `chunk_count > 1`, several webhook
executions in one grant — **stays open, unmeasured.** Task 3 narrows WINDOWS id 26's
description to this exact residual rather than closing it: the single-chunk formula now
has one real data point (and it disagrees with the projection); the multi-chunk formula
still has none.

## Cross-reference: 54-05's live write proof

`54-LIVE-PROOF.md` (this phase's Plan 05) is the companion live measurement to this
report: one real flagged contact (`347569451461`) taken through an operator-authorized,
record-scoped armed window on `LV Review Decision (Cloud)` — the clear-and-stamp branch
only, 10 n8n executions across the whole plan, exactly 1 write (`12000`), 0 provider
credits, 0 Anthropic calls, disarm independently verified (`VERDICT: disarmed PASS`). Read
it for the review-decision endpoint's own execution accounting; this file's accounting
above is the enrichment-workflow envelope only and does not include it.

## Escalation

Both reads above succeeded — no row in this report is blocked on a pruned or unreadable
execution window, so this task does not stop short of Task 3. Had either read failed, this
report would say `unmeasured` with the reason and escalate rather than manufacture a
number with a fresh send; that path was not needed here.
