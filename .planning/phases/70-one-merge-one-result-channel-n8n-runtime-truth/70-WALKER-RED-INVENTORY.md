# 70-09 Task 3: the RED inventory under the corrected walker

Which offline suites go RED once `tests/n8n/lib/walkWorkflow.mjs` models what the live
engine actually did (D-70-20, plan 70-09 Tasks 1–2), so Wave 2 and Wave 3 open on a
named list rather than a guess. Every count below is read straight off a fresh run of
the exact command the plan's own verify step runs.

## Fresh full-suite run (recorded verbatim)

Command: `node --test tests/n8n/*.test.mjs` (93 files, includes this task's two new
synthetic cases in `walkWorkflow.test.mjs`).

This environment's `node --test` (v24.10.0) prints its summary using the spec
reporter's info-symbol lines even when stdout is redirected — not the TAP `# pass` /
`# fail` comment lines the plan's verify grep names. Both forms are recorded below,
captured from the SAME run (`--test-reporter=tap` re-run against the identical file
set, byte-identical counts confirmed against the default-reporter run), so the grep
matches regardless of which reporter format the grading environment's default turns
out to be:

Default (spec) reporter, this environment:

```
ℹ tests 1045
ℹ suites 0
ℹ pass 1019
ℹ fail 26
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
```

TAP reporter (`node --test --test-reporter=tap tests/n8n/*.test.mjs`), same files, same run:

```
# tests 1045
# suites 0
# pass 1019
# fail 26
# cancelled 0
# skipped 0
# todo 0
```

**1045 tests, 1019 pass, 26 fail.** Before this task's two synthetic pricing cases were
added, the corrected walker (Tasks 1–2, commit `062154b`) already stood at 1043/1017/26 —
adding the two `D-70-20 mechanism price` cases to `walkWorkflow.test.mjs` (both pass)
accounts for the whole tests/pass delta; the fail count is unchanged because those two
cases are synthetic graphs built inline, not a real committed workflow.

## Failing suites (26 tests across 9 files) — one root cause, two symptom shapes

Every failing test is downstream of ONE generator function:
`splice_carry_merge_after` (`scripts/build_cloud_workflows.py:9346`). It splices a
`mode="combine"`/`combineByPosition` Merge immediately after an HTTP/identity-search
node, with input 0 fed by the HTTP node's own output and input 1 fed by a **second fan-out
edge off the SAME routing node's branch that already feeds the HTTP node** (the
`carry_source` parameter). That design assumed the two inputs always arrive together or
never at all. They do not: a Merge accepts a zero-item delivery on a direct edge
unconditionally (input 1, fed straight from the routing node's branch, always arrives —
even when that branch is empty for this batch), but a non-Merge node fed zero items
never runs at all (input 0, fed only if the HTTP node itself ran, never arrives when the
branch was empty). The asymmetry is invisible when both inputs are "wired the same way"
on paper; it is exactly the gap D-70-20 opens Wave 2 to close by never sharing a Merge
input between a sentinel/routing-branch delivery and a real producer's own delivery.

### Shape A — identity-lane carry-merge starvation (21 of 26 tests, 7 files)

A batch that legitimately does not exercise every identity lane (single-lane batches,
refusal-only batches, a batch missing one object type entirely) leaves that lane's
routing branch empty. Under the corrected walker the carry merge for that lane now
reports `merge_input_never_fired` and the stall cascades to every merge downstream of it
(`trace.stalled` is non-empty where the test asserts `[]`).

| File | Failing tests | Merge(s) named in the failure | Generator site |
|---|---|---|---|
| `enrichmentBatchRefusal.test.mjs` | 3 | `List By Name Carry Merge`, `HubSpot Company Fetch By Id Carry Merge` | `splice_carry_merge_after` calls at `build_cloud_workflows.py:7524`, `:7570` |
| `enrichmentConvergenceMerge.test.mjs` | 7 | `HubSpot Fetch By Id Carry Merge`, `List By Name Carry Merge`, `HubSpot Company Fetch By Id Carry Merge` | same calls, `:7524`, `:7530`, `:7570` |
| `enrichmentGateRunRecoveryFlow.test.mjs` | 1 | `List By Name Carry Merge` | `:7524` |
| `enrichmentMixedBatch.test.mjs` | 5 | `HubSpot Fetch By Id Carry Merge`, `List By Name Carry Merge`, `HubSpot Search Carry Merge` | `:7524`, `:7530`, `:7533` |
| `reviewConvergenceMerge.test.mjs` | 2 | `Review Queue Contact Search Carry Merge`, `Review Queue Search Carry Merge` | `splice_carry_merge_after` calls at `:10722`, `:10725` |
| `writeGateShape.test.mjs` (line 286 only) | 1 | `HubSpot Company Fetch By Id Carry Merge`, `List By Name Carry Merge` | `:7570`, `:7524` |

(`ingestCarryMerge.test.mjs` line 119 also names no merge in its failure text but is
the ingest-side instance of a *different* shape — see Shape B below; it is listed there,
not here.)

### Shape B — the Associate/refusal-lane race, same mechanism, a wider batch (5 of 26 tests, 4 files)

`Associate Carry Merge` and `Update Carry Merge` are the SAME `splice_carry_merge_after`
mechanism (`build_cloud_workflows.py:1378`, `:1386`; the surrounding hand-wired sentinel
block at `:1246`–`:1420`, and `wire_gate_refusal_lane` at `:9431` / `_add_starved_lane_sentinel`
at `:9502` for the refusal lane's own dedicated input). This is the EXACT mechanism Task
1's execution-12203 reproduction already diagnosed for the narrowest possible shape (one
of two contacts armed). These five failures show the same diagnosed defect recurring
under wider batches (2 and 4 armed rows, a 2×2 mixed batch, an all-refused batch) that
the 12203 reproduction alone did not cover — not a new bug class, the same one at more
scale.

| File | Failing tests | Symptom | Generator site |
|---|---|---|---|
| `ingestCarryMerge.test.mjs` | 1 (line 119) | `association: "not_confirmed"` where `"associated"` expected, 4-row batch, 2 armed rows | `:1378`/`:1386` (`Associate Carry Merge`), sentinel block `:1246`–`:1420` |
| `ingestMixedBatch.test.mjs` | 2 (lines 165, 207) | same symptom, 2×2 and single-lane armed batches | same |
| `ingestTracerFlow.test.mjs` | 1 (line 121) | same symptom, 2-row armed batch | same |
| `writeGateShape.test.mjs` | 2 (lines 409, 463) | line 409: `action: "update"` where `"write_blocked"` expected on an all-refused batch (the refusal lane's OWN dedicated input, `wire_gate_refusal_lane`); line 463 is literally the 12203 shape re-asserted here | `:9431` (`wire_gate_refusal_lane`), `:9502` (`_add_starved_lane_sentinel`) |

## Stayed-green suites — and why that is expected, not suspicious

**82 of 93 test files never import `tests/n8n/lib/walkWorkflow.mjs` at all** (confirmed:
`grep -l walkWorkflow tests/n8n/*.test.mjs` returns exactly 11 files). Those 82 files
exercise pure JS functions directly — `mergeCompanies.js`, `normalizeProviders.js`,
`providerConflict.js`, `judge.js`, and so on — with no dependency on the walker's Merge
delivery model. The walker correction cannot affect a suite that never drives a
workflow graph through it; their green is structural, not incidental.

Of the 11 files that DO import `walkWorkflow`, two stayed fully green:

- **`walkWorkflow.test.mjs`** — its own unit suite (plus this task's two new pricing
  cases) builds small SYNTHETIC graphs by design (D-70-18's own header note: "NOT the
  committed JSON — so these cases stay stable while the real workflows are refactored
  under them"). None of its graphs reproduce the `splice_carry_merge_after` shared-branch
  wiring pattern, so none of them can exercise Shape A or B.
- **`walkerEngineFidelity.test.mjs`** — the two live reproductions this plan's Tasks 1–2
  added (executions 12203, 12206). Task 2 already corrected the walker until both PASS;
  they are the fixed point this inventory measures everything else against, not a suite
  still awaiting a fix.

The remaining 9 imported-and-failing files are exactly Shapes A and B above.

## The 15-input `Build Response Merge` — recorded as confounded, not settled

`70-UAT.md` § Test 3 records that on execution 12206 the 15-input `Build Response Merge`
never fired, and separately notes that n8n's own published docs describe 2–10 inputs for
a Merge node (`70-UAT.md:64`, `:80`, `:88`) — flagged, not verified against the live
engine. That observation is **confounded by starvation**: on the SAME execution, several
of that Merge's OTHER inputs also received no delivery at all (the same
`Contacts Absent Sentinel`-vs-real-producer race this inventory's Shape A/B entries
reproduce offline). A Merge with even one permanently-unfed input never fires regardless
of how many inputs it declares, so 12206 cannot distinguish "the input-count guidance
matters live" from "the Merge was starved for an unrelated reason and never got the
chance to prove anything about its own input count." The documented 10-input guidance
remains an independent reason to split `Build Response Merge` for Wave 2 — it is not, on
this evidence, a PROVEN cause of the 2026-09-10 UAT's failure.

## What Wave 2 and Wave 3 inherit

- **Fix once, at the generator, not per call site**: `splice_carry_merge_after`'s
  `carry_source` fan-out must stop sharing a Merge input with a lane whose own
  producer can independently starve — D-70-20's "no Merge input is shared between a
  sentinel and a real producer" rule, applied to ALL fourteen-plus call sites listed
  above, not hand-patched per site.
- **The Associate/refusal-lane sentinel block** (`:1246`–`:1420`, `wire_gate_refusal_lane`,
  `_add_starved_lane_sentinel`) needs the SAME fix under wider batches than the single
  12203 shape it was built against — Shape B is evidence the fix must generalise past
  "exactly one armed row," not merely reproduce 12203.
- **`Build Response Merge`'s split to ≤10 inputs** stays independently justified by the
  documented input-count guidance; it is not excused by resolving Shape A/B, and Shape
  A/B is not excused by splitting it.
