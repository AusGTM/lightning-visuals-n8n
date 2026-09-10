---
phase: quick-260911-0tz
reviewed: 2026-09-11T00:00:00Z
depth: quick+ (walker read in full, findings proved by running the walker)
files_reviewed: 6
files_reviewed_list:
  - tests/n8n/lib/walkWorkflow.mjs
  - tests/n8n/walkWorkflow.test.mjs
  - tests/n8n/walkerEngineFidelityV1.test.mjs
  - tests/n8n/creditsSummaryUnderV1.test.mjs
  - tests/n8n/fixtures/frozen/README.md
  - tests/n8n/fixtures/frozen/wf_enrichment_cloud.v1.2026-09-10.json
findings:
  critical: 2
  warning: 2
  info: 8
  total: 12
status: issues_found
---

# Quick task 260911-0tz: Code Review Report

**Severity vocabulary:** the body uses the four tiers the orchestrator asked for —
**blocker / major / minor / nit**. Frontmatter maps them for the pipeline:
blocker → `critical`, major → `warning`, minor + nit → `info`.

**Depth:** quick, with the walker (`tests/n8n/lib/walkWorkflow.mjs`) read in full and every
finding below proved by *running* the shipped walker against the frozen graph, the frozen
recordings, or a minimal synthetic graph — not by reading alone.

## Confirmations (things that hold)

- **Frozen graph identity: PASS.** `sha256(tests/n8n/fixtures/frozen/wf_enrichment_cloud.v1.2026-09-10.json)`
  = `77a4e8c0137580c1b1d827586a2d600d1fbf2942e883596caeb58f77318eab7d` = `git show ec102a4:n8n/wf_enrichment_cloud.json`
  = the current working copy. Byte-identical, as claimed.
- **Suite: PASS.** `node --test tests/n8n/*.test.mjs` → 1087/1087, 0 fail (matches the SUMMARY).
- **`walkerEngineFidelity.test.mjs` zero diff: PASS.** `git diff --stat 55d26dc0..HEAD -- tests/n8n/walkerEngineFidelity.test.mjs` is empty; its three legacy cases pass unmodified.
- **Rule (c) is load-bearing, not decorative: PASS.** Reverting only
  `if (order === "v1" && outItems.length === 0) return;` in a scratch copy and re-walking 12354
  puts `Merge Company` back into `Decide Company Action Merge`'s sources — the plan's stated
  failing direction reproduces.
- **Orchestrator check (1) — a Merge whose inputs only ever saw zero-item/sentinel output must
  NOT drain: PASS.** Synthetic v1 graph, both producers `return []` → the Merge never fires
  (`runData.M === undefined`). Correct — but see BL-01 for what is now invisible.
- **Orchestrator check (5) — the credits test really does exercise three live provider lanes:
  PASS.** Re-running that scenario against the committed `n8n/wf_enrichment_cloud.json`:
  `Lusha Usage [1]`, `Apollo Usage [1]`, `ZoomInfo Usage [1]`, `Collect Credits [3]` (one run,
  three items), all three `X Credit Skipped` absent. Not skipped by `provider_enabled`.
- **Node-count fidelity on the frozen walk is otherwise exact.** Comparing the walker's run/item
  counts to `exec_12354.runData.json` across all 93 recorded nodes: 0 nodes missing, 0 extra, and
  the only 12 count differences are all `n8n-nodes-base.if` nodes, explained by the walker's
  documented "record the pre-split input for an IF" convention — not divergences.

---

## Blockers

### BL-01: `trace.stalled` is unreachable under v1 — 27 starvation assertions across 11 files are now structurally vacuous

**File:** `tests/n8n/lib/walkWorkflow.mjs:673-675, 705-717` (and every consumer listed below)

**Issue:** Under v1 `trace.stalled` can never be non-empty, so every
`assert.deepEqual(trace.stalled, [])` in the suite is now a no-op. Two facts combine:

1. `mergeState[name]` is only created *on a delivery* (line 580). A Merge that receives **zero**
   deliveries never enters `mergeState` and is therefore never examined by the stall pass.
2. Every Merge that *does* enter `mergeState` has ≥1 filled input by construction, and
   `requiredInputsFor()` returns `1` — so the end-of-run drain fires it. `state.runs.length > 0`
   is always true at line 713, and the `trace.stalled.push` at line 716 is dead code.

The comment at 673-675 states the opposite: *"`trace.stalled` therefore now only ever reports a
Merge that received ZERO deliveries"* — that Merge is precisely the one that can never be
reported.

Proved by running the shipped walker:

```
P1 (both producers `return []`):   runData.M = undefined  stalled = []  merges = {}
P2 (Merge's input-1 lane never runs): runData.M = undefined  stalled = []  merges = {}
12354 walk on the frozen v1 graph: stalled = []; 20 of the graph's 33 Merge nodes received no
  delivery at all and appear in NEITHER trace.stalled NOR trace.merges
  (List By Name Carry Merge, HubSpot Fetch By Id Carry Merge, Research Carry Merge, …)
```

Consumers whose assertions became vacuous — **27 `trace.stalled` assertion sites across 11 files**,
none of them touched or reported: `enrichmentConvergenceMerge` (7), `reviewConvergenceMerge` (4),
`writeGateShape` (4), `ingestMixedBatch` (3), `zoominfoLaneFlow` (3), `enrichmentMixedBatch` (2),
`ingestTracerFlow` (2), `mergeInputContract` (2), `enrichmentBatchRefusal`,
`enrichmentGateRunRecoveryFlow`, `ingestCarryMerge` (1 each).

Why this is a blocker and not bookkeeping: the drain itself is engine-correct (12354 run 1 really
did fire on one input), so *nothing broke* — which is exactly why it went unnoticed. Plan Step 5
said "For every OTHER file: STOP and report"; the SUMMARY reports nothing, because a silently
vacuous assertion does not fail. A green suite that can no longer see starvation is the Phase 70
failure class (Gate 8 / G-70-3) reintroduced into the instrument built to detect it.

**Fix:** keep the drain, replace the detector with the v1-native one the drain already has data
for, and re-derive the 27 sites against it:

```js
// walkWorkflow.mjs — v1 half of the stall pass
// A Merge cannot "stall" under v1 (requiredInputs 1 drains it). The v1 starvation shapes are:
//   (a) a Merge that received no delivery at all — it is absent from mergeState, so enumerate
//       the graph's merge nodes, not mergeState;
//   (b) a Merge that FIRED with an unfilled input (the 12354 run-1 shape) — silent row loss.
for (const n of (wf.nodes || []).filter((x) => x.type === "n8n-nodes-base.merge")) {
  const st = mergeState[n.name];
  const numberInputs = (n.parameters && n.parameters.numberInputs) || 2;
  if (!st) { trace.stalled.push({ node: n.name, reason: "merge_never_delivered_to", missingInputs: [...Array(numberInputs).keys()] }); continue; }
  st.runs.forEach((r, i) => {
    const missing = [...Array(numberInputs).keys()].filter((k) => r.sources[k] === undefined);
    if (missing.length) trace.stalled.push({ node: n.name, reason: "merge_fired_with_unfilled_input", run: i, missingInputs: missing });
  });
}
```

If that is too big for a quick task, the minimum acceptable alternative is to **say so in the
docstring** (`trace.stalled` is dead under v1, do not read it as evidence) and open a todo — a
vacuous assertion left undocumented in 11 files is worse than a removed one.

---

### BL-02: `walkerEngineFidelityV1.test.mjs` omits the one recorded fact the walker actually gets wrong — per-input source attribution

**File:** `tests/n8n/walkerEngineFidelityV1.test.mjs:86-105`; walker `tests/n8n/lib/walkWorkflow.mjs:580-606`

**Issue:** The file's header claims it "proves the walker's v1 branch reproduces what the live
engine ACTUALLY DID on executions 12354, 12355 and 12356". It reproduces run counts, item counts
and the `null`-on-the-drained-input. It does **not** assert which producer claimed which input —
and that is exactly where the walker diverges from the recording.

Recording (`exec_12354/12355/12356`, already pinned as engine truth by
`tests/n8n/v1RuntimeRecordings.test.mjs:65-66`):

```
run 0: source = [Companies Absent Sentinel Gate, Companies Absent Sentinel Gate]
run 1: source = [Recompute Not Requested Sentinel Gate, null]
```

Shipped walker, same graph, same recorded trigger/stubs:

```
run 0: sources = {0: "Recompute Not Requested Sentinel Gate", 1: "Companies Absent Sentinel Gate"}
run 1: sources = {0: "Companies Absent Sentinel Gate"}
```

Both runs are attributed to the wrong producers. The `[2, 1]` item split matched only because
each delivery happened to carry one item.

Mechanism: the *rule* (earliest pending run whose input `i` is unfilled) matches the engine; the
**arrival order** does not. `dequeue()` is LIFO under v1 (`queue.pop()`, pre-existing at
`55d26dc0:383`), which was harmless while a Merge fired at most once and became load-bearing the
moment multi-fire landed. The engine let `Companies Absent Sentinel Gate`'s single node-run fill
*both* inputs of run 0; the walker has no notion that two deliveries from one producer-run belong
to the same run, so LIFO ordering split them across runs 0 and 1.

This is a D-70-19 violation in its cleanest form: the assertions that would have gone RED were the
ones left out, and `trace.merges`'s own docstring says *"which node took input 0 IS the finding"*.
The SUMMARY (lines 113-114) then states the divergence backwards — "run 1 input 1 unfilled,
claimed by `Recompute Not Requested Sentinel Gate`" — which is true of the recording and false of
the walker it is describing.

**Fix:** add the two omitted assertions, visibly RED rather than absent, using the plan's own
`{ todo: true }` convention (node:test runs a todo test and prints the failure without failing the
exit code), plus a known-divergence header in the `walkerEngineFidelity.test.mjs` 12316 style:

```js
// KNOWN DIVERGENCE (quick task 260911-0tz): the walker's v1 pending-run RULE matches the engine,
// but its delivery ORDER (LIFO queue.pop()) does not, so a producer that filled two inputs of one
// engine run is split across two walker runs. Item counts reproduce; source names do not.
test(`execution ${id}: per-input source attribution (recorded)`, { todo: true }, () => {
  const { trace } = walkRecording(id);
  const runs = trace.merges["Decide Company Action Merge"].runs;
  assert.deepEqual([runs[0].sources[0], runs[0].sources[1]],
    ["Companies Absent Sentinel Gate", "Companies Absent Sentinel Gate"]);
  assert.equal(runs[1].sources[0], "Recompute Not Requested Sentinel Gate");
});
```

and correct the SUMMARY's claim. The real repair (model the engine's arrival order, or group
deliveries by producer-run) is a modelling change and belongs in its own task — but it must not
stay invisible.

---

## Major

### MJ-01: the legacy branch is NOT unchanged — an unfired legacy Merge loses its partial source/itemCount attribution

**File:** `tests/n8n/lib/walkWorkflow.mjs:534-536` (comment), `739-759` (the actual change)

**Issue:** The comment says *"LEGACY arrival state machine — UNCHANGED (byte-identical to the
pre-70-16 behaviour save for calling the extracted `mergeBuffers` maths helper)"*, and the SUMMARY
repeats it. The arrival state machine is indeed unchanged; **`trace.merges` is not.** Previously
`sources`/`itemCounts` were built from `state.sources`/`state.buffers` regardless of `fired`; now
they are derived from `runs[0]`, and an unfired legacy Merge has `runs === []`.

Old vs new walker on the same legacy graph (`allowLegacy: true`, input 1 never delivers):

```
OLD merges = {"M":{"fired":false,"sources":{"0":"A"},"itemCounts":{"0":1}}}
NEW merges = {"M":{"fired":false,"sources":{},"itemCounts":{},"runs":[]}}
```

`trace.stalled` still names the missing input, so nothing in the suite breaks — but the "who
claimed input 0 before it starved" diagnostic, which is the whole point of `trace.merges` for the
12203/12206 defect class, is gone for the legacy starvation case.

**Fix:** either preserve the pre-existing partial view for an unfired legacy Merge, or delete the
"byte-identical" claim from the comment and the SUMMARY:

```js
} else {
  runs = state.fired ? [{ sources: {...state.sources}, itemCounts: /* … */ }] : [];
}
trace.merges[name] = {
  fired: runs.length > 0,
  // legacy: a Merge that never fired still reports which inputs HAD arrived — the
  // 12203/12206 finding is "who claimed input 0", and starvation is when it matters most.
  sources: runs[0] ? {...runs[0].sources} : {...(state.sources || {})},
  itemCounts: runs[0] ? {...runs[0].itemCounts} : Object.fromEntries(
    Object.entries(state.buffers || {}).map(([i, it]) => [i, it.length])),
  runs,
};
```

### MJ-02: `fired` collapsed to "present in `trace.merges`" under v1, leaving tautological assertions and a now-impossible comment

**File:** `tests/n8n/lib/walkWorkflow.mjs:753-757`; consumers `tests/n8n/ingestMixedBatch.test.mjs:315-324`, `tests/n8n/zoominfoLaneFlow.test.mjs:192, 215-219`, `tests/n8n/mergeInputContract.test.mjs:271`

**Issue:** Same structural cause as BL-01: under v1 every Merge in `mergeState` fires, so
`trace.merges[x].fired` is `true` whenever `x` is present and the key carries no information.
Consequences already in the tree:

- `ingestMixedBatch.test.mjs:315` comments that *"Associate Carry Merge may still appear in
  `trace.merges` UNFIRED"* — impossible under v1; the following
  `assert.notEqual(trace.merges["Associate Carry Merge"] && ….fired, true)` now passes only
  because the Merge is *absent* (`undefined !== true`), i.e. for a different reason than written.
- `zoominfoLaneFlow.test.mjs:215-219`'s `assert.ok(!merge || !merge.fired, …)` reduces to
  "the Merge is absent"; the `!merge.fired` half is unreachable.

**Fix:** where the intent is "this Merge never ran", assert it directly and unambiguously —
`assert.equal(runData["Associate Carry Merge"], undefined)` — and update the stale comments. If
`fired` is to stay, document in the walker docstring that under v1 it is equivalent to key
presence.

---

## Minor

### MN-01: the drain fires *multiple* pending runs of the same Merge — an extrapolation past both the observation and CLAUDE.md's own cited rule

**File:** `tests/n8n/lib/walkWorkflow.mjs:676-703`

Two partially-filled pending runs on one Merge at end of run both fire:

```
graph: A and B both deliver to input 0 of a 2-input Merge; input 1 never fed
walker: runData.M = [[{id:"b"}], [{id:"a"}]]   (two drained runs)
```

12354-12356 only ever observed **one** drained run, and CLAUDE.md §13.0.3's `requiredInputs` row
says *"at end-of-run every node still `waitingExecution` executes **once** with whatever inputs
arrived"*. The plan's own standing rule is "no walker behaviour changes here without its own
fidelity case against a frozen recording"; this behaviour has none. It may well be engine-true
(n8n re-enters the main loop after each waiting node), but the code comment presents it as
observed. **Fix:** state it as INFERRED-NOT-OBSERVED in the drain comment and record the open
question in the builder-contract todo, or cap the drain at one run per Merge until observed.

### MN-02: the drain loop is unbounded — a feedback edge into a Merge input hangs the walker forever

**File:** `tests/n8n/lib/walkWorkflow.mjs:677-702`

`while (progressed)` with `propagate` + `processQueue()` inside has no cycle guard and no
iteration cap. Synthetic graph `A → M.input0`, `M → Loop → M.input1`: the walker never returns
(killed after 8s). The pre-change walker terminated on that shape (a Merge fired at most once).
No committed workflow has a cycle today (checked all eight `n8n/wf_*.json`: 0 cycles), so this is
latent — but a hung `node --test` gives no diagnostic at all. **Fix:** a cheap guard, e.g. count
total drained runs and throw by node name past `nodes.length * 4`:

```js
let drained = 0;
// … inside the drain, after each fire:
if ((drained += 1) > (wf.nodes || []).length * 4) {
  throw new Error(`walkWorkflow: end-of-run drain did not converge at "${name}" — feedback edge into a Merge input?`);
}
```

### MN-03: the drain-order comment overclaims engine fidelity

**File:** `tests/n8n/lib/walkWorkflow.mjs:663-666`

*"scanning `mergeState` in `Object.entries` insertion order (i.e. first-delivery order) … never
left to accident"* — insertion order is deterministic but it is the **walker's own LIFO traversal**
order, not the engine's (this is the same mechanism BL-02 catches red-handed). Deterministic ≠
engine-faithful. **Fix:** reword to "deterministic, but derived from this walker's queue order, not
from any observed engine ordering", and cross-reference BL-02's divergence.

### MN-04: `creditsSummaryUnderV1` counts response rows with `nodeItems`, the exact shape its sibling refuses

**File:** `tests/n8n/creditsSummaryUnderV1.test.mjs:131-132`

`nodeItems(runData, "Build Response").length === 2` passes on a 1+1 run split — the collapse shape
`walkerEngineFidelityV1.test.mjs:112-117` explicitly declines to assert that way. The walk does
produce one run of two items (verified), so tightening is free. **Fix:**

```js
assert.equal(runData["Build Response"].length, 1, "Build Response runs exactly once");
assert.equal(runData["Build Response"][0].length, 2, "both rows in that one run");
```

### MN-05: `creditsSummaryUnderV1` asserts object identity, a walker artifact the engine does not guarantee

**File:** `tests/n8n/creditsSummaryUnderV1.test.mjs:133-136`

`rows[0].remaining_credits === rows[1].remaining_credits` pins "the same array **reference**",
which is true only because this offline walker never clones items between nodes. n8n serializes
item data across node boundaries, so the live engine gives no such guarantee — and a future
fidelity improvement (cloning, to model that) would turn this RED for a reason unrelated to
credits. **Fix:** `assert.deepEqual(rows[0].remaining_credits, rows[1].remaining_credits)`, with
the "one shared summary, not a per-row recomputation" intent carried by the comment.

### MN-06: nothing keeps the frozen v1 graph honest after the next regeneration

**File:** `tests/n8n/fixtures/frozen/wf_enrichment_cloud.v1.2026-09-10.json`, `tests/n8n/fixtures/frozen/README.md:16`

The copy's entire value is that it is byte-identical to what executions 12354-12356 ran (it is,
verified). Nothing asserts that, so a future regeneration of `n8n/wf_enrichment_cloud.json` leaves
a silently divergent 1.1MB duplicate whose README row still claims commit `ec102a4`. **Fix:** one
assertion in `walkerEngineFidelityV1.test.mjs`, e.g. compare `nodes.length === 287` and
`settings.executionOrder === "v1"` at minimum, or a digest pinned in the README row.

### MN-07: `requiredInputsFor`'s `chooseBranch` refusal only guards the drain

**File:** `tests/n8n/lib/walkWorkflow.mjs:459-467, 684`

The throw fires only from the end-of-run drain. A `chooseBranch` Merge reached in the main loop
(lines 580-606) is silently modelled as `append`/`combine` and fires normally when all inputs
fill — the guard's stated purpose ("THROW rather than guess") is bypassed on the common path.
**Fix:** call `requiredInputsFor(node)` once when the merge state is created, so the refusal is
unconditional.

---

## Nits

### NT-01: dead defensive branch in the drain

`tests/n8n/lib/walkWorkflow.mjs:681` — `if (!state.pending) continue; // not a v1-shaped state —
should not happen here`. Under v1 every state is v1-shaped (the two shapes are keyed on `order`,
fixed for the whole walk). Drop it, or make it throw so an impossible state is loud.

### NT-02: `httpStubsFromRecording`'s refusal is narrower than its comment

`tests/n8n/walkerEngineFidelityV1.test.mjs:43-56` — the fallback throws only when the node ran
more than once live. A node that ran **once** live but is called five times by the walk silently
replays run 0 five times. Harmless on these three recordings (walker call counts match the
recording exactly, verified), but the header reads as if all misalignment is refused.

### NT-03: `260911-0tz-SUMMARY.md` is untracked

`git status` shows the SUMMARY as `??` — the task's own deliverable was never committed, while the
three code commits were. Process, not code.

---

## Orchestrator's five checks — direct answers

1. **Does the drain fire a Merge whose inputs all received only sentinel `[]`/zero-item output?**
   No — correct. Such a Merge gets no delivery, never enters `mergeState`, never fires. But it is
   now completely invisible to the trace (BL-01).
2. **Is the legacy code path actually unchanged, not just the tests?** The *arrival state machine*
   is (maths correctly extracted to `mergeBuffers`, `(buffers[i] || [])` is a no-op when legacy
   fires only on full arrival; three legacy fidelity cases pass with zero diff to the file).
   `trace.merges` for an **unfired** legacy Merge is not (MJ-01).
3. **Ordering — drain once after the main loop, no re-drain?** Yes: `processQueue()` runs to
   exhaustion first, and a fired pending run is spliced out so it cannot re-fire. It *can* fire
   several pending runs of one Merge (MN-01), and it has no termination guard (MN-02).
4. **`trace.merges` shape — do the six flat-shape consumers read a stale run 0?** Not today: the
   only multi-firing Merge in any walked graph is `Decide Company Action Merge`, which no flat-shape
   consumer reads. It is in the enrichment lane, so the trap is live for the next consumer. The
   companion damage is `fired` losing meaning (MJ-02).
5. **Does the credits test really run all three provider lanes?** Yes — `Lusha Usage`,
   `Apollo Usage`, `ZoomInfo Usage` each ran once, all three `X Credit Skipped` sentinels absent,
   `Collect Credits` one run of three items claimed by the three `Adapt X Usage` nodes. The
   two-producers-per-input shape is exercised, though only in its mutually exclusive direction —
   which the test and SUMMARY both state honestly.

---

_Reviewed: 2026-09-11_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: quick (walker read in full; findings reproduced by executing the shipped walker)_
