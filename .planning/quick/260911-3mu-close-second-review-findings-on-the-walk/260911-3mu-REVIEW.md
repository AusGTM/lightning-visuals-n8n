---
phase: quick-260911-3mu
reviewed: 2026-09-11T00:00:00Z
depth: quick+ (walker read in full; every verdict below produced by RUNNING the walker)
files_reviewed: 16
files_reviewed_list:
  - tests/n8n/lib/walkWorkflow.mjs
  - tests/n8n/walkWorkflow.test.mjs
  - tests/n8n/walkerEngineFidelityV1.test.mjs
  - tests/n8n/enrichmentConvergenceMerge.test.mjs
  - tests/n8n/enrichmentMixedBatch.test.mjs
  - tests/n8n/ingestMixedBatch.test.mjs
  - tests/n8n/ingestTracerFlow.test.mjs
  - tests/n8n/ingestCarryMerge.test.mjs
  - tests/n8n/mergeInputContract.test.mjs
  - tests/n8n/writeGateShape.test.mjs
  - tests/n8n/fixtures/frozen/README.md
  - CHANGELOG.md
  - CLAUDE.md
  - .planning/todos/pending/2026-09-11-merge-input-contract-allows-many-producers-per-input.md
  - n8n/wf_enrichment_cloud.json
  - n8n/wf_contact_ingest_cloud.json
findings:
  critical: 1
  warning: 1
  info: 9
  total: 11
status: issues_found
---

# Quick task 260911-3mu: Code Review Report (third pass)

**Severity vocabulary:** body uses **blocker / major / minor / nit**. Frontmatter maps them for
the pipeline: blocker → `critical`, major → `warning`, minor + nit → `info`.

**Method.** `tests/n8n/lib/walkWorkflow.mjs` read in full (1033 lines). Every closure verdict was
produced by executing the shipped walker; every RED claim was proved by a **surgical revert of the
one hunk under test** in a scratch mirror of `tests/n8n/` (not a wholesale revert to `7f573285` —
that walker OOMs on the new NF-NT-04 case and takes the whole file down with it, which would have
masked the other three REDs). The mirror is path-faithful (`<scratch>/mirror/tests/n8n` with
`n8n/`, `config/`, `scripts/`, `src/` symlinked beside it) so every test file's `path.resolve(…,
"..", "..")` root resolves; on that mirror the 17 test files that drive `walkWorkflow` are
**160/160 green** unpatched, which is the baseline every revert and the proposed blocker fix were
measured against. Two of the SUMMARY's own rows do not survive that treatment.

**Baselines confirmed:**

- `node --test tests/n8n/*.test.mjs` → **1098 tests, 1098 pass, 0 fail, 0 todo** (matches the
  SUMMARY: 1093 + 5 new).
- `git diff 7f573285..HEAD --stat -- tests/n8n/walkerEngineFidelity.test.mjs n8n/ scripts/` is
  **empty** — the legacy fidelity file and all runtime trees are untouched, as claimed.
- Frozen v1 graph digest = `77a4e8c0…eab7d` = `git show ec102a4:n8n/wf_enrichment_cloud.json` =
  today's `n8n/wf_enrichment_cloud.json`. All three identical, so the reworded MN-06 message is
  literally true today.
- NF-NT-08's corrected count checks out: `git grep -c "trace\.stalled" cfdea665 --
  'tests/n8n/*.test.mjs'` → **38 lines across 12 files**.
- All deliverables tracked and committed: the 1z5 SUMMARY, the 3mu PLAN/SUMMARY and the CHANGELOG
  edit are all in `git ls-files` / `git diff HEAD` clean. NF-NT-07 does not recur (one residual
  below).

---

## 1. Closure verification table

Every NF-* id from `260911-1z5-REVIEW.md`, including the two the SUMMARY does not list.

| Finding | Verdict | Fix at | Test that goes RED on regression (proved) |
|---|---|---|---|
| **NF-BL-01** (`starvedWithData` blind to combine-mode annihilation) | **CLOSED** | arm at `walkWorkflow.mjs:970-975`; `outputCount` recorded at both fire sites `:697` and `:809` | `walkWorkflow.test.mjs` "NF-BL-01: a combine/combineByPosition Merge …". **Revert A** (delete the arm, mirror) → **1 RED**, 22 others green. Direct probe, `combineByPosition` **and** `combineAll`, HEAD vs `7f573285`: both modes `runData.M = [[]]`, `Sink` never ran, `stalled` = one `merge_fired_with_unfilled_input`; `starvedWithData` = **non-empty at HEAD**, `[]` at `7f573285`. `combineAll` was probed as asked and behaves identically. Also fires on the **real** graph: silencing `Contacts Judge None Needed Sentinel Gate` in `wf_enrichment_cloud.json` makes the arm report `Credits Broadcast` (combineAll, 1 item in / 0 out) while `Build Response` drops to 0 rows. |
| **NF-MJ-01** (grouping rule was an inference presented as an observation) | **CLOSED** | comment demoted `walkWorkflow.mjs:516-528`; todo appended (15 lines); pin `walkWorkflow.test.mjs` "NF-MJ-01 (KNOWN-UNOBSERVED, pinned)" | The pin is the test. It asserts cardinality only — see NF3-NT-04 for what it does **not** pin. |
| **NF-MJ-02** (CLAUDE.md claimed a `trace.stalled` pin that did not exist) | **CLOSED** | `walkerEngineFidelityV1.test.mjs:109-116` | **Revert B** (delete the `merge_fired_with_unfilled_input` push, `walkWorkflow.mjs:852-856`) → **3 RED**, one per execution, `actual: []` vs the expected single entry. The assertion is load-bearing, not decorative. Re-run of the 12354/12355/12356 walk at HEAD: 20 × `merge_never_delivered_to` + exactly one `{Decide Company Action Merge, merge_fired_with_unfilled_input, run 1, missingInputs:[1]}`, `starvedWithData === []`, run 1 `outputCount: 1` — **the append drain is NOT flagged**, exactly as required. |
| **NF-MN-01** (two near-empty convergence tests) | **CLOSED (body), NOT CLOSED (header/name)** | `enrichmentConvergenceMerge.test.mjs:282-331` | The three added assertions are the test. Header at `:278-280` and both test names still promise "does not stall any contacts-side merge input" while the test itself now pins 20 stalled entries — see NF3-MN-01. |
| **NF-MN-02** (guard message named the wrong site) | **CLOSED** | `recordV1Fire(nodeName, site)` `walkWorkflow.mjs:570-577`, call sites `:699` / `:812` | Probed: the MN-02 self-loop graph now throws `… did not converge at "M" (fired from the **main-loop arrival**) — feedback edge into a Merge input?`. The existing test's `/"M"/` + `/feedback edge/` matchers still hold, and the message is now factually right at the one site proven reachable. |
| **NF-MN-03** (five messages promising a claim the assertion cannot make) | **CLOSED** | `mergeInputContract:269`, `ingestTracerFlow:174`, `writeGateShape:487-489`, `ingestMixedBatch:239-241`, `enrichmentMixedBatch:214-215` | All five reworded; three gained a real per-node `runData`/`ran()` assertion. One of the five now claims something still not asserted — NF3-NT-02. |
| **NF-MN-04** (digest message described a different guard) | **CLOSED** | `walkerEngineFidelityV1.test.mjs:157-161` | Message reworded to what the test does; independently verified that the frozen copy really is byte-identical to `ec102a4`'s graph (three matching `shasum -a 256`). |
| **NF-MN-05** (MJ-01's restored legacy diagnostic had no test) | **CLOSED** | `walkWorkflow.test.mjs` "NF-MN-05 (MJ-01 coverage)" | **Revert C** (fallback back to `sources: {}` / `itemCounts: {}`, `walkWorkflow.mjs:919-921`) → **1 RED**, the new legacy case, 22 others green. Confirmed exactly as the brief asked. |
| **NF-MN-06** (MN-07 earliness untested) | **ACCEPTED — and the acceptance rationale is FALSE** | `walkWorkflow.mjs:667` | **I disagree.** The PLAN says "no test can distinguish it without instrumenting the walker". It can, in five lines, with no instrumentation: a `chooseBranch` Merge with **both** inputs filled, feeding an HTTP node whose stub records its calls. HEAD: throws, `calls = []`. Mirror with `:667` removed: throws (from the drain) but `calls = [2]` — the Merge fired as `append` and drove a downstream side effect before the refusal. The difference is a downstream node run, i.e. externally observable. See NF3-MJ-01. |
| **NF-NT-01** (`total >= 1` vacuous under v1) | **CLOSED** (documented in place) | `walkWorkflow.mjs:947-950` | N/A — documentation, as the finding asked. |
| **NF-NT-02** (legacy pass-through is a trap) | **CLOSED** (documented in place) | `walkWorkflow.mjs:961-963` | N/A — documentation. |
| **NF-NT-03** (two tautological `fired === true`) | **CLOSED** | `walkWorkflow.test.mjs:489,494` → `runData.Merge.length === 1` | `grep -rn "\.fired, true\|fired === true" tests/n8n/*.test.mjs` → **no hits**. |
| **NF-NT-04** (Merge-free cycle hangs forever) | **CLOSED** | `DELIVERY_CAP` `walkWorkflow.mjs:583-597` | Direct timing at HEAD: the `T→A→B→A` graph throws **in 4 ms** (`1001 deliveries processed without the queue draining (last: "A")`). Well inside the 2 s bar. Against `7f573285` the same file **OOM-crashed the whole test process after 91 s** — that is the RED, and it is why the other three REDs had to be taken surgically. |
| **NF-NT-05** (frozen README pointer) | **CLOSED** | `tests/n8n/fixtures/frozen/README.md:84` | Target `.planning/todos/completed/2026-09-11-walker-rule-c-…md` exists; no `todos/pending` reference left in that file. |
| **NF-NT-06** (`FIRE_CAP = nodes * 4` couples fan-in to graph size) | **NOT CLOSED — unaddressed** | — | `walkWorkflow.mjs:569` is byte-unchanged. The id appears in neither the PLAN, the SUMMARY, nor the diff. See NF3-NT-01: this round added a **second** size-coupled magic multiplier next to it. |
| **NF-NT-07** (deliverables untracked/uncommitted) | **CLOSED** (one residual) | — | 1z5 SUMMARY, 3mu PLAN + SUMMARY all tracked; CHANGELOG committed; working tree clean but for `.DS_Store`. Residual: NF3-NT-05. |
| **NF-NT-08** (CHANGELOG said 14 files) | **CLOSED** | `CHANGELOG.md:26` | Independently recomputed: 38 lines across **12** files at `cfdea665`. |

### Directly re-run probes

| Probe | Result |
|---|---|
| Second pass's NF-BL-01 probe (`Real -> M.input0 (2 rows) \| Dead -> M.input1 (returns [])`) | **PASS.** `combineByPosition`: `starvedWithData` non-empty at HEAD, `[]` at `7f573285`. **`combineAll` probed the same way: identical**, both walkers. `run.outputCount === 0`, `runData.Sink === undefined`. |
| The 12354/12355/12356 walk | **PASS.** `starvedWithData(trace) === []` on all three; the run-1 append drain carries `outputCount: 1` and is **not** flagged; per-input `sources` still `{0:CA,1:CA}` / `{0:RNR}`; `Build Response` one run of 2 items. |
| NF-MN-05 legacy partial view, fallback reverted to `{}` | **PASS — RED**, exactly one test. |
| NF-NT-04 cycle | **PASS — throws in 4 ms.** |
| NF-MN-06 earliness | **PASS — and it IS observable.** See the table row and NF3-MJ-01. |

---

## 2. New findings introduced (or left standing) by this round

### Blocker

#### NF3-BL-01: the widened loss predicate still cannot see the OTHER half of the same loss mode — `Math.min` dropping rows when both inputs are filled with UNEQUAL counts — and a committed graph reaches it

**File:** `tests/n8n/lib/walkWorkflow.mjs:965-977` (`starvedWithData`), `:407-457` (`mergeBuffers`),
`:850-857` (the stall pass).

NF-BL-01 was closed for the special case `outputCount === 0`. But `combineByPosition` destroys rows
whenever the counts differ at all — `n = Math.min(...counts)` — and the round's own arm only fires
when the minimum happens to be zero. Between `outputCount === 0` and `outputCount === max(counts)`
lies every partial loss, and **none of it produces a `trace.stalled` entry at all**: the stall pass
pushes `merge_fired_with_unfilled_input` only when an input's `sources[k]` is `undefined`, and here
every input is filled.

Reproduced on the **committed** `n8n/wf_contact_ingest_cloud.json`, no synthetic graph, no walker
patch — a two-row armed ingest batch where `HubSpot Associate Company` (which carries
`alwaysOutputData: true`) returns nothing, so its AOD substitution contributes ONE marker item
against the carry lane's TWO rows:

```
Associate Carry Merge  [combine / combineByPosition, numberInputs 2]
  in0 <- HubSpot Associate Company   (alwaysOutputData: true)
  in1 <- Build Association Request

run 0: itemCounts {"0":1,"1":2}   outputCount 1     <-- 2 carried rows in, 1 out
trace.stalled                    = []               <-- nothing reported at all
starvedWithData(trace)           = []               <-- "no Merge lost a row"
Build Ingest Response            : row 111 "associated", row 444 "not_confirmed"
```

Row 444's association result was annihilated at the Merge. Because `Ingest Merge Response` is
`append`, the row still *returns* — carrying a **wrong outcome** (`not_confirmed` for a write that
may well have happened) rather than going missing. That is worse than a dropped row for an operator
reading the run report, and it is exactly the outcome-truth class Phase 70 exists to close
(D-70-05: "every row's real outcome is read from the settled execution's runData").

**The graph's own defensive default is what hides it.** `Build Ingest Response`'s jsCode derives
`association: "not_confirmed"` from the ABSENCE of a matching `action: "enrich"` item, and its own
comment says so: *"association: 'not_confirmed' is the correct report — nothing ever tried to
associate it"*. So a row whose association result was **destroyed at the Merge** is byte-identical,
in the response, to a row that was **never attempted**. No operator, and no downstream report, can
tell the two apart. The walker is the only place in the system where this loss is visible at
all — which is precisely why the loss predicate has to see it.

Scale: `wf_enrichment_cloud.json` has 22 `combineByPosition` + 1 `combineAll` Merges, every one a
carry-merge; `wf_contact_ingest_cloud.json` supplies the one AOD-producer instance above. All
~30 class-(a) `starvedWithData` sites and both new convergence snapshots stay green through it.

This is a blocker on the same grounds the second pass used for NF-BL-01, not merely by symmetry: the
round installed `starvedWithData` as **the** shared definition of "a row was lost", widened it once,
and the widened predicate is still blind to a loss shape a committed graph produces — while the
docstring at `:939-950` now reads as though the mode question is settled.

**Fix (one comparison, data already recorded at both fire sites):**

```js
// walkWorkflow.mjs — the stall pass, alongside the two existing v1 shapes:
state.runs.forEach((r, i) => {
  const maxIn = Math.max(0, ...Object.values(r.itemCounts));
  if (r.outputCount < maxIn) {
    trace.stalled.push({ node: n.name, reason: "merge_dropped_rows", run: i,
      itemCounts: r.itemCounts, outputCount: r.outputCount });
  }
});
// starvedWithData, v1 branch:
if (s.reason === "merge_dropped_rows") return true;
```

This is semantically a `combineByPosition`/`combineAll` rule and trivially never fires for
`append` (append's output is the SUM of its inputs, so `outputCount < max` is impossible) — no
mode-independence is being claimed. It subsumes the existing `outputCount === 0` arm (`0 < max`),
so land it as a REPLACEMENT for that arm, not beside it.

**Verified by execution, not by reading.** The snippet was applied to a path-faithful mirror of
`tests/n8n/` and every one of the 17 test files that drive `walkWorkflow` was re-run:

```
baseline (mirror, unpatched):   160 tests, 160 pass, 0 fail
with the proposed arm:          160 tests, 159 pass, 1 fail
```

The single RED is **the round's own NF-BL-01 synthetic case**, and only because it
`deepEqual`s `trace.stalled` to exactly one entry and asserts `starvedWithData(...).length === 1` —
under an added arm the annihilation shape reports twice. That is the double-report the
"REPLACEMENT, not beside" note above removes; it is **not** a false positive. Zero other tests move:
no committed-graph walk in the suite — enrichment, ingest, review, credits, refusal, tracer, write
gate, zoominfo lane, both fidelity files, all three Gate 11 recordings — reports a dropped row under
the widened predicate. And the arm does catch the blocker's own reproduction:

```
same two-row ingest batch, HubSpot Associate Company returns nothing
  HEAD walker:          starvedWithData = []
  with the arm:         starvedWithData = [{node:"Associate Carry Merge",
                          reason:"merge_dropped_rows", run:0,
                          itemCounts:{"0":1,"1":2}, outputCount:1}]
```

Land the two-row ingest case above as the RED-first test, and update the NF-BL-01 case's expected
`trace.stalled` shape in the same commit.

### Major

#### NF3-MJ-01: NF-MN-06 was accepted on a claim of unobservability that is false, and the PLAN records that claim as a decision

**File:** `.planning/quick/260911-3mu-close-second-review-findings-on-the-walk/260911-3mu-PLAN.md:36-41`;
code at `tests/n8n/lib/walkWorkflow.mjs:664-668`.

The PLAN's "Accepted without a test" section states: *"the difference is not observable from outside
the walker … no test can distinguish it without instrumenting the walker."* Disproved with no
instrumentation at all:

```
chooseBranch Merge, BOTH inputs filled, downstream HTTP node whose stub records its calls

HEAD (creation-site requiredInputsFor at :667):   throws;  stub calls = []
mirror with :667 removed:                          throws;  stub calls = [2]
```

Without the early refusal the Merge is modelled as `append`, fires in the main loop, and **drives a
downstream node run** before the drain's refusal ever happens. A downstream node run is the most
externally observable thing this walker produces. The second pass's own suggested test (inspect
`runData` after catching) genuinely cannot work — `walkWorkflow` returns nothing on a throw — but
that is a property of *that* suggestion, not of the finding.

Severity is major rather than nit because of where the false claim lives: a committed planning
artifact, in a repo whose §13.0.3 discipline is that an unverified claim must not be written up as
settled, used to justify skipping coverage on a guard whose whole value is refusing early.

**Fix:** land that shape as a test — `assert.throws(() => walkWorkflow(...))` plus
`assert.equal(calls.length, 0)`, where `httpStubs.Sink` pushes to `calls`. (`assert.throws` does not
swallow a closure's side effect, so it observes the same divergence the probe above did; the probe
used a bare `try`/`catch` and was not itself run under `node --test`.) Correct the PLAN's acceptance
note either way — the reason recorded there for skipping coverage is false.

### Minor

#### NF3-MN-01: `enrichmentConvergenceMerge`'s section header and both test NAMES still promise the property NF-MN-01 said they could not check

**File:** `tests/n8n/enrichmentConvergenceMerge.test.mjs:278-280`, `:312`, `:324`

The body was fixed; the framing was not. The header still reads *"every contacts-side merge input
must still be satisfied by a starved-lane sentinel, never left stalled"*, and the two tests are still
named *"a companies-only batch does not stall any contacts-side merge input"* / *"…any companies-side
merge input"* — while the tests they name now **assert** that the batch leaves exactly 20 Merges
`merge_never_delivered_to` and one or two more `merge_fired_with_unfilled_input`. A reader who greps
the name gets the opposite of what the assertion says.

**Fix:** rename to what is now checked — e.g. "a companies-only batch loses no row, and the set of
Merges it never reaches is exactly this" — and reword the header the same way.

#### NF3-MN-02: the never-delivered snapshot's own assertion message is false for at least one real starvation shape

**File:** `tests/n8n/enrichmentConvergenceMerge.test.mjs:318`, `:328`

Message: *"a contacts-side Merge starting to starve moves it"*. Tested by silencing sentinels in a
mirror of the committed graph:

| silenced sentinel | `neverDelivered` set | `firedUnfilled` | `starvedWithData` | `Build Response` |
|---|---|---|---|---|
| `Companies Absent Sentinel Gate` | **moved** (20 → 23) | moved | `[]` | 1 row (no loss) |
| `Contacts Judge None Needed Sentinel Gate` | **unchanged (20)** | moved | non-empty | **0 rows — real loss** |
| `Contacts Research None Needed Sentinel Gate` | unchanged | unchanged | `[]` | unchanged (inert on this batch) |

So the snapshot detects some starvation shapes and not the worst one in the sample; what caught row 2
was the *other* two assertions in the same test. The test as a whole is sound — the message is the
part that is wrong, and it is the part a future reader will trust.

On the brief's question — faithful pin or brittle fixture: **both, and acceptable given the stated
purpose**, with one caveat worth recording. The lists are a true byte-level snapshot of the walk on
today's committed graph, and the comment says exactly that. But **18 of the 20 names are identical
between the two lists** (only `Contact Research Carry Merge` + `HubSpot Search Carry Merge` vs
`HubSpot Company Name Search Carry Merge` + `HubSpot Company Search Carry Merge` differ), so the
discriminating power per test is two names against eighteen of shared, batch-independent noise — and
any builder change that renames, adds or removes a carry Merge breaks both lists for a reason that
has nothing to do with the engine. That is an acceptable price for a snapshot whose header promises a
snapshot; it is not acceptable to sell it as a starvation detector, which the message does.

#### NF3-MN-03: the new annihilation arm fails OPEN when it cannot find the run it needs

**File:** `tests/n8n/lib/walkWorkflow.mjs:971-972`

```js
const run = ((trace.merges[s.node] || {}).runs || [])[s.run];
if (!run) return false;                     // "not a loss"
```

The loss detector now depends on a second trace field (`trace.merges`) staying index-aligned with
`trace.stalled`, and when that alignment fails it reports *no loss* rather than throwing. Today the
two are built from the same `state.runs` in the same order so it cannot misfire — but this is the one
predicate ~30 assertions delegate to, and a silent `false` is precisely the failure mode BL-01 was
raised about. The legacy synthesis path at `:902-908` builds `runs` entries **without** `outputCount`,
so the shape the arm needs is already not universal within `trace.merges`.

**Fix:** `throw` on the impossible state (the NT-01 precedent, four lines away at `:789-793`, does
exactly this), or record `outputCount` on the entry in `trace.stalled` itself and drop the
cross-field lookup.

#### NF3-MN-04: CHANGELOG describes round 2 and is silent on round 3, including the change to the loss definition it documents

**File:** `CHANGELOG.md:23-35`

The docs commit `42d8442e` edited this paragraph (the 14 → 12 correction) and used the edit to add a
full description of quick task **260911-1z5**. It says nothing about **260911-3mu**, and the
paragraph it leaves standing describes `starvedWithData(trace)` as *"one shared loss filter … which a
synthetic case proves NON-empty on a genuine loss"* — the pre-widening definition. This round changed
what "a genuine loss" means (annihilation is now one) and added a second termination guard
(`DELIVERY_CAP`). A reader taking the CHANGELOG at face value has the wrong predicate.

**Fix:** one clause on the same paragraph: the filter now also reports a `combine`-mode run that
consumed rows and emitted none, and a Merge-free feedback cycle now throws instead of hanging.

### Nits

- **NF3-NT-01:** NF-NT-06 is unaddressed (`FIRE_CAP = nodes * 4`, `walkWorkflow.mjs:569`) and this
  round parked a **second** size-coupled magic multiplier beside it — `DELIVERY_CAP = max(1000,
  nodes * 50)` at `:584` — with no shared rationale for 4 vs 50 and both throws blaming a "feedback
  edge/cycle". On the brief's question: **the cap cannot be exceeded by a legitimate large batch, and
  this is measured, not estimated.** Instrumenting `deliveriesProcessed` and walking the committed
  287-node `wf_enrichment_cloud.json` gives **111 deliveries at 1, 2, 4, 10 and 20 rows** (flat — 50
  rows and 100 rows are refused by `Parse HubSpot Event`'s own ceiling and dequeue 50) against a cap
  of **14350**: 129× headroom, and row-independent because a delivery is a per-edge-run event and no
  committed workflow contains a `splitInBatches` node (`grep` over all eight `n8n/wf_*.json`: zero).
  The residual is the shared one — a small graph with a genuinely high-fan-in Merge trips a
  size-derived bound with a misleading message.
- **NF3-NT-02:** `enrichmentMixedBatch.test.mjs:214-215`'s reworded message says *"the Build Response
  fire itself is asserted above"*. What is above is `rows.length === 2` where `rows =
  nodeItems(runData, "Build Response")` — `nodeItems` **flattens every run**, so a 1+1 run split
  passes. That is the exact accessor MN-04 was raised about and which `walkerEngineFidelityV1`
  deliberately avoids (`runData[...].length === 1` **then** `[0].length === 2`). Four of the five
  NF-MN-03 rewordings gained a real per-node assertion; this one gained a claim instead.
- **NF3-NT-03:** the BL-02 comment's stated *reason* is still wrong, at `walkWorkflow.mjs:529-534`
  and mirrored at `:608-610`: *"these edges are always enqueued directly adjacent to each other
  (nothing else can interleave within one connectionsFrom() loop)"*. They are not — `propagate` now
  enqueues every non-merge edge inside the loop and every merge group **after** it, so a merge
  delivery is deliberately moved to the end of its batch (and under v1, where `dequeue` is
  `queue.pop()`, that means popped **first**). The conclusion holds for legacy (FIFO preserves the
  batch's relative order), and the round correctly demoted the *observation* claim two paragraphs
  above; it left the second-pass Q1 correction unmade.
- **NF3-NT-04:** the NF-MJ-01 pin asserts cardinality, not the choice its own name promises to pin —
  `runData.M.length === 1`, `undrained.length === 1`, `starvedWithData(...).length === 1`. The
  walker actually produces `runData.M = [[{id:'q'},{id:'q'}]]`: **P's row is entirely lost and Q's is
  duplicated**. A different grouping model with the same cardinality passes unchanged. One
  `assert.deepEqual(runData.M, [[{id:"q"},{id:"q"}]])` would pin what the header claims.
- **NF3-NT-05:** `260911-3mu-SUMMARY.md`'s frontmatter still reads `commits: [dbb987e5, <docs
  commit>]` — an unfilled placeholder in the deliverable of the round that closed NF-NT-07, which was
  about exactly this class of bookkeeping. The docs commit is `42d8442e`.

---

## 3. Answers to the orchestrator's five targeted questions

**(a) Can the annihilation arm false-positive on a legitimate shape?** **No, on any shape the
committed graphs can produce — checked structurally, not assumed.** Every one of the 23 `combine`
Merges in `wf_enrichment_cloud.json` has both inputs wired (zero unwired inputs), and every one is a
carry-merge in one of two wirings: (i) `HTTP -> in0` with `IF -> …Pass-Through -> in1` off the *same*
IF branch, or (ii) a single producer feeding **both** the HTTP node and `in1` from one output
(`Build Research Request`, `Build Judge Request`, `Stash Name Primary Search`, `Adapt Company
Search`). In both wirings, a lane the batch never drives leaves *both* inputs unfilled — which the
walker reports as `merge_never_delivered_to`, an arm the filter deliberately excludes. Confirmed on
the real graph: the base companies-only and contacts-only walks each leave 20 carry-merges
never-delivered-to and `starvedWithData` empty. The scenario the brief names (a carry-merge whose
HTTP hop was skipped) therefore **cannot** reach the arm: skipping the hop also skips its carry. The
only way to fill `in1` and not `in0` is an HTTP node that RAN and emitted zero items — which under
v1 is a genuine engine-level annihilation, not a design intent. Edge batches probed for
completeness, all clean (`starvedWithData === []`): empty `events`, unsupported `objectType`
refusal, `scale_up` refusal. Every committed-graph walk in the suite still passes (1098/1098). The
real gap is the *other* direction — see NF3-BL-01.

**(b) Can a legitimate large batch exceed `DELIVERY_CAP`?** **No — measured.** 111 deliveries, flat
from 1 to 20 rows on the 287-node enrichment graph, cap 14350. Deliveries are per edge-run and no
committed workflow fans out per row. Details and the residual in NF3-NT-01.

**(c) Are the never-delivered snapshot constants a faithful pin or a brittle fixture?** Both, and
acceptable for a test whose comment promises exactly a snapshot — with the two caveats in NF3-MN-02:
18 of 20 names are shared between the two lists (two names of discriminating power each), and the
assertion *message* oversells the snapshot as a starvation detector, which it demonstrably is not for
every starvation shape.

**(d) Does the NF-MJ-01 pin make clear it pins a walker CHOICE?** **Yes.** The test name carries
"KNOWN-UNOBSERVED, pinned … This pins the walker's CURRENT choice so the divergence is visible, not a
claim that the engine does this", the assertion message says "a walker artifact OR a real engine
loss" and cites the todo by path, the walker comment at `:516-528` is demoted to "CONSISTENT WITH …
but was NOT isolated by", and the todo carries a matching 15-line "Open question" section. This is
the cleanest closure in the round. One weakness, NF3-NT-04: it pins the cardinality, not the choice.

**(e) Is every claim about `walkerEngineFidelityV1.test.mjs` in CLAUDE.md §13.0.3 now literally
true?** **Yes, for all three claims, verified against the committed file.**
- `:2711` — "reports this exact shape … as a `merge_fired_with_unfilled_input` entry in
  `trace.stalled`, pinned live by `tests/n8n/walkerEngineFidelityV1.test.mjs` against
  `12354`/`12355`/`12356`": the assertion now exists at `:109-116` and **Revert B turns all three
  executions RED**. The rest of the row (run 0 = 2 marker items both from `Companies Absent Sentinel
  Gate`; run 1 = 1 item, input 0 from `Recompute Not Requested Sentinel Gate`, input 1 null;
  `Decide Company Action` ran twice with 0 items each) is asserted line by line in the same test.
- `:2712` — rule (c) "pinned live by `walkerEngineFidelityV1.test.mjs`": the `Merge Company`-never-a-
  source assertion is at `:125-129`, and the first pass independently proved it RED on revert.
- `:2741` — "`walkerEngineFidelityV1.test.mjs` (v1, `12354`/`12355`/`12356`)": the file's
  `EXECUTIONS` is exactly `[12354, 12355, 12356]`.

One wording caveat, not a defect: `:2711`'s "**pinned live** by" pins a *walker-derived diagnostic*
against a frozen recording; `merge_fired_with_unfilled_input` is a walker concept the engine never
emitted. The row is in an `[observed live]` table, so "pinned live" reads stronger than what the test
does. `grep` finds no other `starvedWithData` / stall-reason reference anywhere in CLAUDE.md, so
nothing else in that document went stale under this round's widened predicate.

---

## 4. What holds (verified, not assumed)

- The annihilation arm is real, mode-agnostic (`combineByPosition` **and** `combineAll` probed), RED
  on revert, and fires on the committed enrichment graph under an injected sentinel defect.
- `starvedWithData` is still `[]` on all three Gate 11 recordings, and the run-1 append drain is
  still not flagged — the narrowing the plan set out to protect survived the widening.
- NF-MJ-02's new assertion is load-bearing on all three recordings; NF-MN-05's is load-bearing on the
  legacy fallback; NF-NT-04's cycle throws in 4 ms where the old walker OOM'd after 91 s.
- The frozen v1 graph, `ec102a4`'s graph and today's committed graph are byte-identical, so the
  reworded MN-06 message is true and the digest needs no change.
- `walkerEngineFidelity.test.mjs`, `n8n/` and `scripts/` are zero-diff. Suite 1098/1098. CLAUDE.md is
  untouched by this round and its three walker claims are now true of the committed file.

---

_Reviewed: 2026-09-11_
_Reviewer: Claude (gsd-code-reviewer), third pass_
_Depth: quick+ (walker read in full; every finding reproduced by executing the shipped walker, every closure verdict proved by a surgical revert of the hunk under test in a scratch mirror)_
