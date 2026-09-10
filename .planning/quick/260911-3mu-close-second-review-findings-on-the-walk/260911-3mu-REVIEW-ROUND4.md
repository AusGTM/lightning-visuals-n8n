---
phase: quick-260911-3mu
reviewed: 2026-09-11T00:00:00Z
depth: quick+ (round-4 diff read in full; every verdict below produced by RUNNING the walker)
files_reviewed: 8
files_reviewed_list:
  - tests/n8n/lib/walkWorkflow.mjs
  - tests/n8n/walkWorkflow.test.mjs
  - tests/n8n/writeGateShape.test.mjs
  - tests/n8n/enrichmentConvergenceMerge.test.mjs
  - tests/n8n/enrichmentMixedBatch.test.mjs
  - CHANGELOG.md
  - .planning/quick/260911-3mu-close-second-review-findings-on-the-walk/260911-3mu-PLAN.md
  - .planning/quick/260911-3mu-close-second-review-findings-on-the-walk/260911-3mu-SUMMARY.md
findings:
  critical: 0
  warning: 0
  info: 6
  total: 6
status: issues_found
---

VERDICT: no blocker, no major

# Quick task 260911-3mu: Code Review Report (fourth pass, round-4 closure)

**Severity vocabulary:** body uses **blocker / major / minor / nit**. Frontmatter maps them:
blocker → `critical`, major → `warning`, minor + nit → `info`. Round 4 introduces **1 minor and
5 nits**; nothing blocking, nothing major.

**Method.** Round-4 diff (`git diff 42d8442e..HEAD -- tests/n8n/ CHANGELOG.md`) read in full;
`walkWorkflow.mjs`'s stall pass (`:832-895`), `starvedWithData` (`:957-1003`), `mergeBuffers`
(`:401-456`), `propagate` (`:512-556`) and both caps (`:571-595`) read in full. Every verdict
below was produced by EXECUTING the shipped walker. Two surgical reverts were taken in a
path-faithful scratch mirror (`<scratch>/mirror/tests/n8n` with `n8n/ config/ scripts/ src/`
symlinked beside it so every test file's `path.resolve(…,"..","..")` root resolves). Mirror
baseline on the five affected files: **74/74 green** unpatched. Full-suite baseline at HEAD:
**`node --test tests/n8n/*.test.mjs` → 1100 tests, 1100 pass, 0 fail** (1098 + round 4's 2).
Scratch deleted at the end. Files EXECUTED but not themselves reviewed (round 4 does not touch
them): `walkerEngineFidelityV1.test.mjs`, `creditsSummaryUnderV1.test.mjs`, `ingestTracerFlow.test.mjs`,
and the eight committed `n8n/wf_*.json` graphs — they are fixtures for the probes, not subjects of
the verdicts.

---

## 1. Closure verification table

Every `NF3-*` id from `260911-3mu-REVIEW.md` §2.

| Finding | Verdict | Fix at | Test that goes RED on regression (proved) |
|---|---|---|---|
| **NF3-BL-01** (`Math.min` unequal-count drop invisible; committed graph reaches it) | **CLOSED** | stall pass `walkWorkflow.mjs:868-885`; filter arm `:1000`; the old `outputCount === 0`/`trace.merges` cross-lookup REPLACED, as the finding demanded | **Revert A** (delete the `merge_dropped_rows` push, `:878-885`) → **2 RED / 72 green** on the mirror, and they are exactly the two intended regression tests: `writeGateShape.test.mjs:588` (`actual: 0, expected: 1` on `lost.length`) and `walkWorkflow.test.mjs:651-654` (`trace.stalled` deepEqual, second entry missing). See §1.1 for the re-run reproduction. |
| **NF3-MJ-01** (NF-MN-06 accepted on a false unobservability claim) | **CLOSED** (one nit on the retraction's own wording — NF4-NT-02) | PLAN `260911-3mu-PLAN.md:36-44` retracted; test `walkWorkflow.test.mjs:750-773` | **Revert B** (delete the creation-site `requiredInputsFor(node)` at `:678`, leaving the drain site at `:808`) → **1 RED**: `NF3-MJ-01 (MN-07 earliness)`, `actual: [ 2 ], expected: []`. The failure is on `assert.deepEqual(calls, [])`, **not** on `assert.throws` — the drain still throws `/chooseBranch/`, so the test pins EARLINESS specifically, which is what NF3-MJ-01 asked for. The pre-existing `MN-07` test at `:775` stayed green under the same revert, confirming it never pinned earliness. |
| **NF3-MN-01** (header + both test names promised the opposite of the assertion) | **CLOSED** | header `enrichmentConvergenceMerge.test.mjs:279-283`; names `:315`, `:329` | Naming/documentation, no assertion change. `grep "does not stall"` over `tests/n8n/*.test.mjs` returns only two unrelated sites (`ingestTracerFlow:155`, `writeGateShape:500`), both of which genuinely assert no stall. |
| **NF3-MN-02** (snapshot message oversold as a starvation detector) | **CLOSED** | `:321-323`, `:333-334` | Message now says "snapshot … a lane starting to starve MAY move it — some starvation shapes leave this set unchanged and are caught by the `starvedWithData` / row-count assertions instead". That matches the third pass's own measured table exactly. |
| **NF3-MN-03** (loss arm failed OPEN on a cross-field lookup) | **CLOSED** | `starvedWithData` `:998-1001` — the `trace.merges[s.node].runs[s.run]` lookup and its `if (!run) return false` are gone; the entry carries its own `itemCounts` + `outputCount` | Structural: `grep "trace.merges" tests/n8n/lib/walkWorkflow.mjs` finds no reference inside `starvedWithData`. **New, smaller fail-open introduced in its place — NF4-NT-01.** |
| **NF3-MN-04** (CHANGELOG silent on round 3, describing the pre-widening predicate) | **CLOSED** | `CHANGELOG.md:38-46` | Clause added covering rounds 3 AND 4. Literal-truth audit in §3(c); one dormant caveat as NF4-NT-03. |
| **NF3-NT-01** (`FIRE_CAP` size-coupling / second magic multiplier) | **PARTIAL** | `:571-576` (shared rationale), `:578` (`FIRE_CAP = max(1000, nodes*4)`), `:595` (`DELIVERY_CAP = max(FIRE_CAP*4, nodes*50)`) | The mechanical part IS closed: the `max(1000, …)` floor removes the small-graph/high-fan-in coupling NF-NT-06 named, and both caps now carry one shared rationale. **But the rationale itself contains a claim a probe falsifies (NF4-MN-01) and measured figures that understate the true suite maximum by ~72% (NF4-NT-05).** |
| **NF3-NT-02** (`nodeItems` flattens runs, so the reworded claim was unasserted) | **CLOSED** | `enrichmentMixedBatch.test.mjs:213` — `runData["Build Response"].length === 1` | A real per-node run-count assertion now exists; the overselling clause was deleted from the message. Same accessor discipline `walkerEngineFidelityV1` uses. |
| **NF3-NT-03** (BL-02 comment's stated *reason* was wrong) | **CLOSED** | `:529-538` and the legacy mirror at `:616-620` | Verified against the code, not just read: `dequeue()` is `queue.pop()` under v1 (`:394`) and `propagate` enqueues every non-Merge edge inside the loop, every Merge group after it (`:539-555`). The corrected text — "a Merge delivery moves to the end of its producer's batch (under v1's `queue.pop()` that means dequeued FIRST)" — is accurate. |
| **NF3-NT-04** (MJ-01 pin asserted cardinality, not the choice) | **CLOSED** | `walkWorkflow.test.mjs:704-705` | `assert.deepEqual(runData.M, [[{id:"q"},{id:"q"}]])` — exactly the assertion the third pass specified. Green at HEAD; a different grouping model producing `(p,p,q)` now fails. |
| **NF3-NT-05** (SUMMARY frontmatter placeholder) | **PARTIAL** | `260911-3mu-SUMMARY.md:6` | Now `commits: [dbb987e5, 42d8442e, 5ca774a0, see git log]`. The unfilled placeholder is still there in a new form (`see git log` is not a hash) and it omits `c007734a` and `c3539ce7` — including the commit that wrote the line. See NF4-NT-04. |

### 1.1 Directly re-run probes (all at HEAD, all required by the brief)

| Probe | Result |
|---|---|
| **NF3-BL-01 reproduction** — armed two-row ingest batch, `HubSpot Associate Company` returns nothing | **PASS, exactly as specified.** `starvedWithData(trace)` = `[{node:"Associate Carry Merge", reason:"merge_dropped_rows", run:0, itemCounts:{"0":1,"1":2}, outputCount:1}]` — one entry, `{0:1,1:2}` → 1. `Build Ingest Response` still returns both rows (`111` "associated", `444` "not_confirmed"), so the loss really is a WRONG outcome rather than a missing row, as the test's own message says. |
| **12354 / 12355 / 12356 walks** | **PASS on all three.** `merge_dropped_rows` = `[]`; `starvedWithData(trace)` = `[]`; `trace.stalled` = 20 × `merge_never_delivered_to` + exactly 1 × `merge_fired_with_unfilled_input`; `Decide Company Action Merge` runs = `[{in:{0:1,1:1},out:2},{in:{0:1},out:1}]` — **the run-1 append drain (1 in, 1 out) is still NOT flagged**; `Build Response` one run of 2 items. The narrowing the round set out to protect survived the second widening. |
| **`append` can never produce `merge_dropped_rows`** | **PASS — reasoned from `mergeBuffers`, then probed.** The append path (`:453-456`) is `for each input: merged.push(...(buffers[i] \|\| []))`, so `outputCount = Σ counts ≥ max(counts)` for non-negative counts; `outputCount < maxIn` is unsatisfiable. Probed a **3-input append with unequal counts** `[3,1,2]` → out **6**, `merge_dropped_rows` **absent**, both with `mode` absent and `mode:"append"` explicit; and a **5-input** `[1,7,2,0,3]` → out **13**, absent. Same counts under `combineByPosition` → out **1**, **flagged**. Under `combineAll` → out **6** (cartesian ≥ max whenever every input is non-empty), **not** flagged — so `combineAll` only reaches the arm on a genuinely empty input, which is the annihilation case. |
| **NF3-MJ-01 test goes RED when `:678` is removed** | **PASS.** `calls` = `[2]` vs expected `[]`, on the `deepEqual` and not on the `throws`. |
| **RED-first claim in `writeGateShape.test.mjs:586`** (independent of Revert A) | **PASS.** Checked out `42d8442e:tests/n8n/lib/walkWorkflow.mjs` into a second mirror and ran the file unmodified: 28 pass / **1 fail**, `actual: 0, expected: 1` — literally the `starvedWithData(trace) === []` the comment claims. |

---

## 2. New findings introduced by round 4

### Minor

#### NF4-MN-01: the DELIVERY_CAP rationale asserts an ordering between the two caps that a probe falsifies — and the runtime message states the falsified conclusion as fact

**File:** `tests/n8n/lib/walkWorkflow.mjs:593-595` (comment), `:604-608` (the thrown message),
`260911-3mu-SUMMARY.md` NF3-NT-01 row.

The comment reads: *"Strictly above FIRE_CAP: a Merge-driven cycle must trip the Merge-naming
guard first, so this one only ever names a cycle with NO Merge on it."* The SUMMARY repeats it:
*"`DELIVERY_CAP = max(FIRE_CAP*4, nodes*50)` so a Merge cycle trips the Merge-naming guard
first."* The runtime message states the conclusion outright: *"— feedback cycle with no Merge on
it?"*

`DELIVERY_CAP = 4 × FIRE_CAP` only implies that ordering when a Merge cycle costs **at most 4
deliveries per fire**. That assumption is unstated and false in general. Probed by extending the
existing MN-02 guard graph's feedback path (self-referencing `numberInputs: 1` Merge, `n`
pass-through hops between `M` and its own input):

```
hops 1  → walkWorkflow: v1 Merge fires did not converge at "M" (…) — feedback edge into a Merge input?
hops 2  → walkWorkflow: v1 Merge fires did not converge at "M" (…) — feedback edge into a Merge input?
hops 3  → walkWorkflow: 4001 deliveries processed without the queue draining (last: "L3") — feedback cycle with no Merge on it?
hops 4  → 4001 deliveries … "feedback cycle with no Merge on it?"
hops 5  → 4001 deliveries … "feedback cycle with no Merge on it?"
hops 10 → 4001 deliveries … "feedback cycle with no Merge on it?"
```

From three hops on, DELIVERY_CAP wins and tells the reader there is no Merge on a cycle that
runs **through Merge `M`** — the single most useful fact for finding the bug, stated backwards.
Both caps still terminate in ~6 ms, so nothing hangs; the defect is purely diagnostic.

Severity is minor, not nit, because of the class: this is the same failure round 4 itself
retracted in NF3-MJ-01 — an unverified claim written up as settled, in a repo whose §13.0.3
discipline exists precisely to stop that. It is not major because it justifies no skipped
coverage and blocks nothing.

**Fix:** drop the falsified conclusion from the message — `"— feedback cycle?"` — and either
delete the "strictly above" rationale or state its real precondition (*"…tripped first only when
a Merge cycle costs ≤ 4 deliveries per fire; a longer feedback path trips this one instead"*).

### Nits

- **NF4-NT-01: the new loss arm carries a fail-open of exactly the class NF3-MN-03 removed.**
  `walkWorkflow.mjs:879` guards with `typeof r.outputCount === "number" && …` — when the field is
  missing the arm silently reports *no loss*, the same silent `false` NF3-MN-03 was raised about,
  in the one predicate ~30 assertions delegate to. It is unreachable today (the only two writers
  of a v1 `runs` entry, `:708` and `:820`, both set `outputCount`), but the shape it guards
  against **already exists in the trace**: the legacy synthesis path at `:930-933` builds a `runs`
  entry with `sources` + `itemCounts` and **no `outputCount`**. Nit rather than minor only because
  the v1 stall pass reads `mergeState[…].runs`, never `trace.merges`. **Fix:** `throw` on the
  impossible state (the NT-01 precedent at `:789-793` does exactly this), or assert the field at
  the two fire sites.

- **NF4-NT-02: the PLAN's retraction claims the retracted reasoning "stays visible"; the operative
  sentence was deleted, not struck through.** `260911-3mu-PLAN.md:36-44` says *"Kept here, struck
  through in effect, so the retracted reasoning stays visible."* Diffing against `c007734a`, the
  original two-sentence acceptance was **replaced**, not annotated. The quoted fragment *"is not
  observable from outside the walker"* is verbatim ✓, but the sentence NF3-MJ-01 actually named as
  false — *"no test can distinguish it without instrumenting the walker"* — is gone from the file
  entirely. The substantive retraction is honest (it names the claim false, gives the `[2]` vs
  `[]` evidence, and cites the landed test); only the self-description overstates. **Fix:** quote
  both sentences, or say "replaced" rather than "stays visible".

- **NF4-NT-03: `combineByFields` is modelled as concatenation, so the CHANGELOG's "any fired
  `combine`-mode run" is not true of the model for one of the three combine modes.**
  `mergeBuffers` (`:415-421`) tests only `combineByPosition` and `combineAll`; a `mode:"combine",
  combineBy:"combineByFields"` Merge falls through to the append branch. Probed: counts `[3,1,2]`
  → out **6**, `merge_dropped_rows` absent — while real n8n `combineByFields` is a join that
  genuinely drops unmatched rows. Dormant (`grep -c combineByFields` over all eight
  `n8n/wf_*.json` → **0/0/0/0/0/0/0/0**), and the gap predates round 4 — but round 4 is the round
  that made "does the merge maths drop rows" a first-class predicate, and its new comment at
  `:868-877` enumerates two modes without saying the third is unmodelled. **Fix:** one clause in
  that comment naming `combineByFields` as modelled-as-append and therefore out of the arm's
  reach.

- **NF4-NT-04: NF3-NT-05 is PARTIAL — the placeholder changed form rather than being filled.**
  `260911-3mu-SUMMARY.md:6` reads `commits: [dbb987e5, 42d8442e, 5ca774a0, see git log]`. `see git
  log` is not a commit hash, and the list omits `c007734a` (the docs commit that landed the
  1z5/3mu artifacts) and `c3539ce7` (the commit that wrote this very line). This is the third
  consecutive round in which the SUMMARY frontmatter of the round that closed the bookkeeping
  finding fails the bookkeeping finding. **Fix:** `commits: [dbb987e5, 42d8442e, c007734a,
  5ca774a0, c3539ce7]`.

- **NF4-NT-05: the shared cap rationale's measured figures understate the true suite maximum, and
  the two cap comments disagree with each other.** `:573` says *"the committed 287-node enrichment
  graph dequeues ~111 deliveries and fires ~13 Merges per batch"*; `:589-590`, eighteen lines
  later, says *"a real walk … dequeues a few hundred deliveries"*. Measured by instrumenting
  `deliveriesProcessed`/`v1FiresCount` in the mirror and logging **every walk in the entire
  suite** (74 walks): the true maximum on the 287-node graph is **191 deliveries and 19 fires**,
  not 111 and 13 — the round carried the third pass's single-probe figure forward as if it were
  the population maximum. The conclusion is unaffected (75× headroom, see §3(b)), so this is a
  nit; but the number a future reader will trust when re-tuning the cap is wrong by ~72%.

---

## 3. Answers to the brief's three targeted questions

**(a) Does `merge_dropped_rows` false-positive on any committed-graph walk in the suite, or on a
legitimate `combineByPosition` shape — specifically a carry-Merge whose HTTP side is BATCHED?**

**No, on either count — and the batched case is answered mechanically, not just observationally.**

- *Suite-wide:* the full suite is **1100/1100 green** at HEAD across ~30 `starvedWithData`
  assertion sites in 13 files (enrichment, ingest, review, credits, refusal, tracer, write gate,
  zoominfo lane, gate-run recovery, both fidelity files, all three Gate 11 recordings). Not one
  committed-graph walk reports a dropped row except the one the new test deliberately induces.
- *The batched carry the brief names:* `Verify Emails (batch)` is carried by **`Verify Email Carry
  Merge`** (`combine/combineByPosition`, `numberInputs: 2`), input 0 from the batched HTTP node,
  input 1 from `Build Verify Batch`. Measured on the same two-row armed ingest walk: `{0:1, 1:1}`
  → out **1**. **No drop, and it cannot drop:** `Build Verify Batch`'s jsCode ends
  `return [{ json: { emails, _rows: rows.map(it => it.json) } }];` — it collapses N rows to
  exactly ONE item, and its own comment says *"still 1-item, matching the HTTP response's own
  1-item count"*. The batched request and its carry are 1:1 **by construction**, so the shape the
  brief worried about does not exist on this graph.
- *Every other carry on that walk* was measured equal-count: `Search By Email` `{2,2}`→2,
  `Company Domain` `{2,2}`→2, `Company Name` `{2,2}`→2, `Update Carry` `{2,2}`→2. The
  `combineAll` broadcast `Source By Field Broadcast` was `{0:2, 1:1}` → **2** (cartesian ≥ max,
  never flagged).
- *Degenerate inputs probed for completeness, all clean:* zero-row ingest (`Source By Field
  Broadcast` never delivered to at all, `starvedWithData` `[]`), one-row ingest, a 3-member list
  expansion, and the list-expansion / oversize-batch / `scale_up` refusals — `merge_dropped_rows`
  empty on every one.
- *The only walk that produced a report outside the new test* was a deliberately nonsensical
  probe (every HTTP node stubbed to return `{}` per input): `Credits Broadcast` `{1:1}`→0 and
  `Build Response Merge` undrained with 7 items. That walk genuinely loses every row (`Build
  Response` = `[]`), so the predicate was right, not wrong.

**(b) Is `DELIVERY_CAP = max(FIRE_CAP*4, nodes*50)` still measured-safe?**

**Yes — re-measured, on a wider sample than the third pass used, and round 4 moved the bound in
the safe direction.** Instrumented `deliveriesProcessed`/`v1FiresCount` and logged every walk in
the suite (74 walks), plus row-count sweeps:

| graph | nodes | max deliveries (suite) | DELIVERY_CAP | headroom | max fires | FIRE_CAP |
|---|---|---|---|---|---|---|
| `wf_enrichment_cloud` (committed) | 287 | **191** | 14350 | 75× | 19 | 1148 |
| frozen v1 enrichment copy | 218 | 84 | 10900 | 130× | — | 1000 |
| `wf_contact_ingest_cloud` | 69 | 63 | 4000 | 63× | 9 | 1000 |
| `wf_review_decision_cloud` | 55 | 24 | 4000 | 167× | 3 | 1000 |
| `wf_scheduled_maintenance_cloud` | 43 | 2 | 4000 | 2000× | 0 | 1000 |
| synthetic test graphs | 3–6 | 2–6 | 4000 | ≥667× | 0–1 | 1000 |

Row-independence re-confirmed by direct sweep: the ingest graph dequeues **54 deliveries at 1, 2,
10 and 50 rows** — flat — because a delivery is a per-edge-run event and no committed workflow
contains a `splitInBatches` node. Round 4's change (`max(1000, nodes*50)` → `max(FIRE_CAP*4,
nodes*50)`) **raises** every cap for graphs under 250 nodes (ingest 3450 → 4000, review 2750 →
4000, small synthetics 1000 → 4000) and leaves the 287-node enrichment cap unchanged at 14350 —
strictly more headroom, never less. Residuals: NF4-MN-01 (the ordering rationale is false) and
NF4-NT-05 (the comment's own numbers understate the measured max).

**(c) Is the retraction wording in the PLAN honest, and is the CHANGELOG clause literally true of
the code?**

*Retraction:* **substantively honest, with one overstatement.** It names the claim false, quotes
it verbatim, gives the observable evidence (`[2]` vs `[]`), and cites the test that landed. The
overstatement is the self-description — see NF4-NT-02.

*CHANGELOG `:38-46`, clause by clause:*

| Clause | Literally true of the code? |
|---|---|
| "`starvedWithData` now also reports `merge_dropped_rows`" | **YES** — `:1000`. |
| "any fired `combine`-mode run whose output is smaller than its largest input" | **YES extensionally, with one dormant caveat.** The code checks EVERY fired run, mode-agnostically (`:879`), so combine-mode runs are a subset and `append` provably cannot satisfy it. The caveat is `combineByFields`, modelled as append and therefore also unable to satisfy it — NF4-NT-03. Zero committed uses. |
| "annihilation on an unfilled input, AND the unequal-count `Math.min` drop with every input filled" | **YES** — both proved live: the NF-BL-01 synthetic (`{0:2}`→0) and the ingest repro (`{0:1,1:2}`→1). |
| "which the committed ingest graph reaches when `HubSpot Associate Company` returns nothing against a two-row carry lane" | **YES** — reproduced at HEAD on the unmodified committed `wf_contact_ingest_cloud.json`. |
| "pinned RED-first in `writeGateShape.test.mjs`" | **YES** — verified independently of Revert A by running the unmodified test against `42d8442e`'s walker: 1 fail, `actual: 0, expected: 1`. |
| "a feedback cycle with no Merge on it now throws instead of hanging" | **YES as written** (it does not claim exclusivity). Note the runtime message DOES claim exclusivity and is wrong to — NF4-MN-01. |
| "the walker's producer-run grouping rule is documented as consistent with, not established by, the Gate 11 recordings, with its divergent shape pinned and carried as an open question" | **YES** — comment `:516-527` reads "CONSISTENT WITH … but was NOT isolated by"; the pin is `walkWorkflow.test.mjs:695-710` (now asserting the CHOICE, per NF3-NT-04); the todo path is cited in the comment. |

---

## 4. What holds (verified, not assumed)

- The widened predicate closes NF3-BL-01 as specified: `{0:1,1:2}` → 1 on the committed ingest
  graph, one entry, self-contained, no cross-field lookup; **Revert A turns both intended tests
  RED and nothing else.**
- `starvedWithData` is still `[]` on 12354/12355/12356, and the run-1 append drain is still not
  flagged. The widening did not cost the narrowing.
- `append` cannot reach the arm — proved from `mergeBuffers`'s concatenation branch and probed at
  3 and 5 inputs with unequal counts. `combineAll` reaches it only on an empty input.
- **No false positive found anywhere**: 1100/1100 green, and the batched-carry shape the brief
  named is 1:1 by construction in `Build Verify Batch`, not by luck.
- NF3-MJ-01's test pins earliness specifically (RED on the `calls` deepEqual, green on the
  `throws`), which the pre-existing MN-07 test did not.
- `n8n/`, `scripts/`, `src/`, `config/` untouched by round 4; the diff is `tests/n8n/` +
  `CHANGELOG.md` only.

---

_Reviewed: 2026-09-11_
_Reviewer: Claude (gsd-code-reviewer), fourth pass_
_Depth: quick+ (round-4 diff and the walker's stall pass / `starvedWithData` / `mergeBuffers` / both caps read in full; every closure verdict proved by a surgical revert in a scratch mirror, every new finding reproduced by executing the shipped walker)_
