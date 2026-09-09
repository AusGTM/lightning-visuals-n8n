---
phase: 70-one-merge-one-result-channel-n8n-runtime-truth
plan: 07
subsystem: acceptance-tests-and-operator-documents
status: complete
tags: [acceptance, mixed-batch, walker, operator-docs, plugin-release, deferred-gate]
requires:
  - "70-05: IF-shaped write gates emitting refusals as rows; per-refusal Merge inputs"
  - "70-06: the client's single poll site (watch.recover_dispatch) and the runData channel"
  - "70-01: tests/n8n/lib/walkWorkflow.mjs, the offline instrument and its CLI"
provides:
  - "tests/n8n/enrichmentMixedBatch.test.mjs — D-70-17 acceptance, enrichment lane"
  - "tests/n8n/ingestMixedBatch.test.mjs — D-70-17 acceptance, ingest lane"
  - "scripts/prove_phase70_runtime.py — the D-70-19 disarmed live driver (offline half done)"
  - "tests/test_prove_phase70_runtime.py — 17 offline tests for that driver"
  - "70-RUNTIME-VERDICT.json — predicted-only, shapes_equal null, awaiting Gate 3"
  - "70-DEFERRED-GATES.md Gate 3 — the live half, verbatim"
  - "operator-claude-plugin 0.43.0"
affects:
  - "CLAUDE.md §13.0 / §13.0.1 / §13.0.2 — three request-level flags, moved node counts"
  - "docs/OPERATOR-AUTONOMOUS-BATCH-UAT.md — mixed batch by default, plus a single-lane send"
  - "operator-claude-plugin skills: enrich-before-ingest, enrich-records, suggest-contacts"
actuals:
  tokens: 28498
  tasks: 3
  commits: 4
plan_head_before: b77986491aa0776f892686875b9c596ea0602030
tech-stack:
  added: []
  patterns:
    - "acceptance-by-walker: an acceptance test drives the COMMITTED workflow JSON, never a hand-authored graph"
    - "bijection-by-identity: input rows and returned rows compared as a set keyed on each row's own identity, never by position"
    - "predict-only verdict: an offline run of a live driver writes shapes_equal: null, never true"
key-files:
  created:
    - tests/n8n/enrichmentMixedBatch.test.mjs
    - tests/n8n/ingestMixedBatch.test.mjs
    - scripts/prove_phase70_runtime.py
    - tests/test_prove_phase70_runtime.py
    - .planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-RUNTIME-VERDICT.json
  modified:
    - CLAUDE.md
    - README.md
    - CHANGELOG.md
    - docs/OPERATOR-AUTONOMOUS-BATCH-UAT.md
    - tests/n8n/lib/walkWorkflow.mjs
    - operator-claude-plugin/CHANGELOG.md
    - operator-claude-plugin/.claude-plugin/plugin.json
    - operator-claude-plugin/README.md
    - operator-claude-plugin/skills/enrich-before-ingest/SKILL.md
    - operator-claude-plugin/skills/enrich-records/SKILL.md
    - operator-claude-plugin/skills/suggest-contacts/SKILL.md
    - operator-claude-plugin/tests/test_enrich_skill_contract.py
    - .planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-DEFERRED-GATES.md
key-decisions:
  - "The enrichment 2x2 rides a PROPOSE batch, not a write batch: Parse HubSpot Event caps a write request at MAX_WRITE_EVENTS = 2 and refuses an oversize one WHOLE, so a 4-row write 2x2 is refused by the backend's own ceiling and proves nothing. The write-node half is covered by one armed 2-row send per identity lane."
  - "The ingest lane's two identity lanes are the two COMPANY-resolution keys (domain, name), not two contact-identity keys: that lane has no contact name or LinkedIn search, so a name-only row can never reach an update."
  - "async_ack is retired repo-wide in the operator-facing documents, including suggest-contacts/SKILL.md which the plan did not list — the same retired flag in a step an operator follows."
  - "The predicted-only verdict deliberately writes shapes_equal: null. An offline run must never be able to fabricate the field the live gate turns on."
  - "The walker CLI gained --trigger. Its single-trigger auto-detect refused wf_enrichment_cloud.json (two trigger nodes), which made the CLI unusable against the very lane the driver has to predict."
patterns-established:
  - "A live-proof driver ships with a --predict-only mode and an offline test suite, so the automatable half lands and is verified before the human gate is ever reached."
  - "A refusal guard takes its environment as a parameter; a guard reading ambient process state cannot be tested."
requirements-completed: [D-70-17, D-70-07, D-70-11, D-70-08a]
# D-70-19 and D-70-02 are the plan's two LIVE requirements and are deliberately NOT
# listed as completed: both are deferred to 70-DEFERRED-GATES.md Gate 3 and must be
# closed by /gsd-verify-work 70 against that run's result, never inherited from here.
requirements-deferred: [D-70-19, D-70-02]
coverage:
  - deliverable: "D-70-17 — one mixed-batch acceptance test per lane, 2 identity lanes x 2 actions, every row exactly once"
    human_judgment: false
    verification: "node --test tests/n8n/enrichmentMixedBatch.test.mjs tests/n8n/ingestMixedBatch.test.mjs — 8 pass, 0 fail; node --test tests/n8n/*.test.mjs — 1040 pass, 0 fail"
    result: pass
  - deliverable: "D-70-17 addendum — a single-lane-only case and a fully-refused case on each lane"
    human_judgment: false
    verification: "both cases present and named in each file; trace.stalled asserted empty in every case; node suite green"
    result: pass
  - deliverable: "D-70-07 — the operator-facing documents state three request-level flags, not four, and an ack-only body on both row-outcome lanes"
    human_judgment: false
    verification: "CLAUDE.md §13.0.2 table lists exactly recompute / scale_up / source_by_field; the 5 remaining async_ack mentions all record its retirement; grep -c async_ack on enrich-before-ingest/SKILL.md prints 0; .venv/bin/python -m pytest -q — 4664 pass"
    result: pass
  - deliverable: "D-70-11 / D-70-08a — under autonomy a new person is never created without the operator's end-of-run approval; the runData channel is what step 9 relays"
    human_judgment: false
    verification: "stated in both READMEs; enrich-records step 9 rewritten; operator-claude-plugin pytest 2864 pass including the moved test_enrich_skill_contract pin"
    result: pass
  - deliverable: "moved pins updated as expected consequences (node counts, flag counts, the F3 skill-contract pin)"
    human_judgment: false
    verification: "node counts in CLAUDE.md compared against a count over the committed JSON — 218/50/45/43/30/70/10/13, exact match; all three suites green"
    result: pass
  - deliverable: "D-70-19 — a DISARMED live mixed batch whose recovered runData rows are shape-equal to the walker's prediction, zero writes, zero arming"
    human_judgment: true
    rationale: "deferred to end-of-phase UAT per operator ruling 2026-09-09 — see 70-DEFERRED-GATES.md Gate 3"
    verification: "automatable half done and committed: scripts/prove_phase70_runtime.py + 17 offline tests; 70-RUNTIME-VERDICT.json written with shapes_equal: null, status predicted_only_awaiting_gate_3. The live half is Gate 3."
    result: deferred
  - deliverable: "D-70-02 — the live settings.executionOrder read, the observed-live upgrade for a fact this phase has only documented evidence for"
    human_judgment: true
    rationale: "deferred to end-of-phase UAT per operator ruling 2026-09-09 — see 70-DEFERRED-GATES.md Gate 3"
    verification: "the driver reads settings.executionOrder from each LIVE workflow body before sending and records it per workflow; the committed JSON sets no executionOrder at all on any of the eight n8n/wf_*.json, so the live value is whatever the instance defaults to and must be recorded as observed"
    result: deferred
---

# Phase 70 Plan 07: The Proof — Mixed-Batch Acceptance, the Operator Contract, and the Deferred Live Run

Two mixed-batch acceptance tests that drive the committed JSON through the walker and assert a
bijection between input and returned rows; every operator-facing document brought to the contract
Phase 70 landed; and the disarmed live proof built, tested offline, and recorded as Gate 3.

## Performance

| Metric | Value |
|---|---|
| Duration | ~1h |
| Tasks | 3 of 3 (Task 3's live half deferred to Gate 3) |
| Commits | 4 (measured: `git rev-list --count b779864..HEAD` — 3 task commits + this summary's own metadata commit) |
| Files created | 5 |
| Files modified | 13 |
| Node suite | 1040 pass, 0 fail (was 1032 — the 8 new acceptance cases) |
| Root pytest | 4664 pass, 154 skip (was 4647 — the 17 new driver tests) |
| Plugin pytest | 2864 pass, 5 skip |

## Accomplishments

**Task 1 — the two mixed-batch acceptance tests (D-70-17).** Both drive the COMMITTED workflow
JSON through `tests/n8n/lib/walkWorkflow.mjs`, never a hand-authored graph. Each file carries
three shapes, named so the shape is readable from the test output: the 2-identity-lane × 2-action
batch, a single-lane-only batch, and a fully-refused batch. Every case asserts `trace.stalled` is
empty, the responder fires exactly once with the ack shape and nothing else, and — the point of
the whole plan — that the returned rows are a *bijection* onto the input rows, keyed on each row's
own identity rather than its position.

Two shape decisions were forced by the backend's own contract rather than chosen:

- **Enrichment.** `Parse HubSpot Event` caps a WRITE request at `MAX_WRITE_EVENTS = 2` and refuses
  an oversize request WHOLE (never truncates). A 4-row write-mode 2×2 is therefore refused by the
  backend before it proves anything. So the 2×2 rides a `mode: "propose"` batch (ceiling 20),
  covering all four cells at once, and the write-node half is covered by one armed 2-row send per
  identity lane. This is the real contract, not a workaround — the live Gate 3 send is bound by
  the same ceiling.
- **Ingest.** The two identity lanes are the two COMPANY-resolution keys CLAUDE.md §13.0.1 names —
  exact email-domain match and exact company-name match — not two contact-identity keys. That lane
  has no contact name or LinkedIn search, so a name-only row can never reach an `update` and
  cannot supply the second half of a 2×2. The shape mirrors the real supervised batch in
  `.planning/uat/UAT-autonomous-batch-2026-09-09.md` (Natalie, domain-resolved and written,
  alongside Barry, company absent by name and held).

Per D-70-18, recorded by the operator in 70-CONTEXT.md, these are GREEN on the refactored JSON
with no historical RED. The evidence that this instrument can SEE the defect class lives in
`tests/n8n/walkWorkflow.test.mjs`, which is the walker's own RED.

**Task 2 — the operator contract.** `async_ack` is retired: CLAUDE.md §13.0.2's table goes from
four request-level flags to three, and the flag survives only in sentences recording its
retirement. `enrich-before-ingest`'s F5b paragraph — which described the synchronous body as a
data channel returning one lane's worth of items — is rewritten, because that shape cannot occur
against a body that carries no rows at all. `enrich-records` step 9's per-record relay rule is
unchanged in substance; its noun moved from "the body" to "the rows", meaning the recovered
runData rows. Both READMEs now state D-70-11 plainly: a new person is never created without the
operator's end-of-run approval, as a consequence of the confidence rule rather than a caveat.
`docs/OPERATOR-AUTONOMOUS-BATCH-UAT.md`'s batch shape becomes mixed lanes × mixed actions by
default, matching the acceptance tests, and gains the single-lane send. Plugin `0.42.0 → 0.43.0`
with its CHANGELOG entry in the same commit.

**Task 3 (automatable half) — the proof driver.** `scripts/prove_phase70_runtime.py` follows
`prove_async_recovery.py`'s precedent: refusal before any transport is constructed, cross-package
import of the plugin's own modules, verdict JSON out. Three gates, all before anything is sent —
`ALLOW_PHASE70_RUNTIME_PROOF` exactly `"true"`, the wrong-instance guard, and (T-70-19) every
write flag in every LIVE body reading exactly `"false"`, where a *missing* declaration refuses
too. Observed rows come from `watch.recover_dispatch`, the client's one poll site; predicted rows
come from SUBPROCESSING the committed walker CLI, deliberately (T-70-20) so the prediction comes
from the frozen instrument and not from anything the driver could tune after seeing the live
answer.

## Task Commits

| Task | Name | Commit | Files |
|---|---|---|---|
| 1 | The two mixed-batch acceptance tests | `52e1472` | `tests/n8n/enrichmentMixedBatch.test.mjs`, `tests/n8n/ingestMixedBatch.test.mjs` |
| 2 | Operator-facing documents and moved pins | `830c3e4` | CLAUDE.md, both READMEs, both CHANGELOGs, `plugin.json`, 3 SKILL.md, UAT doc, 1 test pin |
| 3 | The proof driver (offline half) + Gate 3 | `8ba4c8b` | `scripts/prove_phase70_runtime.py`, `tests/test_prove_phase70_runtime.py`, `walkWorkflow.mjs`, `70-RUNTIME-VERDICT.json`, `70-DEFERRED-GATES.md` |

## Files Created / Modified

Created: `tests/n8n/enrichmentMixedBatch.test.mjs`, `tests/n8n/ingestMixedBatch.test.mjs`,
`scripts/prove_phase70_runtime.py`, `tests/test_prove_phase70_runtime.py`,
`70-RUNTIME-VERDICT.json`.

Modified: `CLAUDE.md`, `README.md`, `CHANGELOG.md`, `docs/OPERATOR-AUTONOMOUS-BATCH-UAT.md`,
`tests/n8n/lib/walkWorkflow.mjs`, `operator-claude-plugin/{CHANGELOG.md, README.md,
.claude-plugin/plugin.json, skills/enrich-before-ingest/SKILL.md, skills/enrich-records/SKILL.md,
skills/suggest-contacts/SKILL.md, tests/test_enrich_skill_contract.py}`, `70-DEFERRED-GATES.md`.

## Decisions Made

1. **The enrichment 2×2 is a propose batch.** The backend refuses a 4-row write request whole; a
   test that sends one measures the ceiling, not row alignment. Documented at length in the test
   file's header so the next reader does not "fix" it into a write batch.
2. **The ingest lane's identity lanes are the company-resolution keys.** Contact identity on that
   lane is email-only.
3. **`async_ack` retired everywhere it is documented, including one file the plan did not list.**
   `suggest-contacts/SKILL.md` quoted the same retired kwarg in two places. Same defect class the
   plan names: an operator following a stale step passes a flag that opts into nothing.
4. **The predicted-only verdict writes `shapes_equal: null`, and a test pins that it can never
   write `true`.** A driver that can fabricate the field the live gate turns on is worse than no
   driver (T-70-20).
5. **The walker CLI gained `--trigger`.** Not cosmetic: the auto-detect refused the enrichment
   workflow outright, so the CLI could not be run against the lane the driver must predict.

## Deviations from Plan

**1. [Rule 3 - Blocking] The walker CLI could not run against the enrichment workflow**
- **Found during:** Task 3, first `--predict-only` run
- **Issue:** the CLI's trigger auto-detect throws unless a workflow has exactly one trigger node;
  `wf_enrichment_cloud.json` has two (`Webhook Trigger`, `Execute Workflow Trigger`). The
  prediction half of the driver was unbuildable.
- **Fix:** added an optional `--trigger <nodeName>`. Omitted, the single-trigger auto-detect path
  is unchanged, and its error message now names the candidates it found.
- **Files:** `tests/n8n/lib/walkWorkflow.mjs`
- **Verification:** `node --test tests/n8n/*.test.mjs` — 1040 pass; the CLI smoke command from
  70-VALIDATION still works without `--trigger`; the driver's own pytest exercises the CLI
  end-to-end against both lanes.
- **Commit:** `8ba4c8b`

**2. [Rule 3 - Blocking] The walker refuses an unstubbed HTTP node, so the driver's fixtures could not be empty**
- **Found during:** Task 3, first `--predict-only` run (`Error: unstubbed HTTP node: HubSpot Search`)
- **Issue:** a JSON fixture cannot carry stub *functions*, and an unstubbed hop is a deliberate
  throw (a silent hole in a prediction is worse than a loud failure).
- **Fix:** `_neutral_stubs()` derives the stub set from the workflow's own HTTP nodes and returns
  one neutral "nothing resolved" body per call — empty `results`, `matched: false`, a mint token.
  That is the honest model of the live sends: synthetic `.invalid` identities resolve nothing and
  every provider is disabled, so every hop returns nothing on BOTH sides of the comparison.
- **Files:** `scripts/prove_phase70_runtime.py`
- **Verification:** all four sends predict one row per input row; pinned by
  `test_every_send_predicts_one_row_per_input_row`.
- **Commit:** `8ba4c8b`

**3. [Rule 1 - Bug] The driver's wrong-instance guard read ambient process state**
- **Found during:** Task 3, full root pytest run
- **Issue:** `require_gates(env=...)` took an env dict but `_instance_ok()` read `os.environ`
  directly. `test_gates_refuse_a_wrong_instance` passed standalone and FAILED in the full suite,
  where another test had set `N8N_URL`. A guard whose answer depends on ambient state is a guard
  that cannot be tested — and this one is a mitigation for T-70-19.
- **Fix:** `env` threaded through `_instance_ok`.
- **Files:** `scripts/prove_phase70_runtime.py`
- **Verification:** `.venv/bin/python -m pytest -q --tb=short` — 4664 pass, 0 fail.
- **Commit:** `8ba4c8b`

**4. [Rule 2 - Missing critical] `suggest-contacts/SKILL.md` still quoted the retired `async_ack`**
- **Found during:** Task 2
- **Issue:** two call sites quoting `chunking.dispatch_plan(..., async_ack=True, ...)`. Not in the
  plan's `files_modified`, but the identical defect the plan's own action text names — an operator
  following it passes a kwarg that opts into nothing.
- **Fix:** both call sites corrected.
- **Files:** `operator-claude-plugin/skills/suggest-contacts/SKILL.md`
- **Verification:** `grep -rc async_ack operator-claude-plugin/skills/` — zero across all skills;
  plugin pytest 2864 pass.
- **Commit:** `830c3e4`

**5. [Moved pin, expected] `test_enrich_skill_contract`'s F3 assertion**
- **Found during:** Task 2, after rewriting `enrich-records` step 9
- **Issue:** the pin asserts the literal `"never invent what the body does not carry"`. "The body"
  names a channel that no longer carries rows.
- **Fix:** the pin now asserts `"never invent what the result channel does not carry"` plus a new
  assertion on `"never guess beyond what the rows say"`. The F3 property is unchanged and both
  halves are still asserted verbatim — the noun moved, not the rule.
- **Files:** `operator-claude-plugin/tests/test_enrich_skill_contract.py`
- **Verification:** 21 pass in that file; plugin suite 2864 pass.
- **Commit:** `830c3e4`

**6. [Deferral, operator ruling] Task 3's LIVE half**
- **Found during:** Task 3 (the task is `checkpoint:human-verify gate="blocking-human"`)
- **Issue:** the plan's Task 3 requires the operator to deploy, bounce and send four disarmed live
  batches. The operator's standing ruling of 2026-09-09 defers live probes to the end-of-phase
  UAT.
- **Fix:** every automatable part built, tested and committed; the live part recorded verbatim as
  **Gate 3** in `70-DEFERRED-GATES.md` with the `<how-to-verify>` block, the single-lane sends, the
  `settings.executionOrder` read, the live invocation, and the carried 15-input-Merge caveat.
  `70-RUNTIME-VERDICT.json` is written in predicted-only form and deliberately does NOT claim
  `shapes_equal: true`.
- **Files:** `scripts/prove_phase70_runtime.py`, `tests/test_prove_phase70_runtime.py`,
  `70-RUNTIME-VERDICT.json`, `70-DEFERRED-GATES.md`
- **Verification:** 17 offline tests pass, including a refusal on an armed live body and a
  comparator proven able to fail.
- **Commit:** `8ba4c8b`

**Total deviations:** 6 (2 × Rule 3, 1 × Rule 1, 1 × Rule 2, 1 moved pin, 1 operator-ruled
deferral).
**Impact on plan:** none on scope. Three of the plan's Task 3 acceptance criteria
(`shapes_equal: true`, four settled execution ids, the CLAUDE.md `[observed live]` upgrade) are
not met and cannot be met offline; all three now live in Gate 3 and are recorded as `deferred` in
this summary's `coverage`.

## Issues Encountered

- **`Build Response Merge` has 15 inputs; n8n documents 2–10.** Carried forward from 70-05's Next
  Phase Readiness, deliberately not resolved offline — the walker models 15 inputs without
  complaint, and whether the live engine accepts one is a Gate 3 observation. Recorded as a
  `[documented]`-only caveat in CLAUDE.md and as the first thing Gate 3 looks at.
- **`scripts/prove_async_recovery.py` is now stale against this contract.** It still passes
  `async_ack=True` and expects an ack shaped `{run_id, accepted, row_id}` (singular). Left in
  place — it is out of this plan's scope, and its own verdict file remains the record of what it
  proved — but it would produce a false STOP verdict if run today.
  `scripts/prove_phase70_runtime.py` supersedes it. Worth a follow-up deletion.
- An armed enrichment-lane update row returns the raw HubSpot response and carries no `row_id`:
  `HubSpot Update` wires straight into `Build Response Merge` input 2 with no carry merge. That is
  the as-built contract on that lane, not something this plan introduced; the acceptance test
  matches such a row by the HubSpot `id` its identity lane resolved.

## User Setup Required

None for the work in this plan. **Gate 3 needs the operator**: deploy with
`scripts/deploy_n8n_workflows.py`, bounce with `scripts/bounce_n8n_workflows.py` (a stored update
never reloads a running workflow), then run the driver with `ALLOW_PHASE70_RUNTIME_PROOF=true`.
All disarmed. Full steps in `70-DEFERRED-GATES.md` Gate 3.

## Next Phase Readiness

**This is the last plan of Phase 70. The phase is complete pending the end-of-phase UAT of three
gates**, all of them live and all of them the operator's step:

| Gate | What it proves | Where |
|---|---|---|
| Gate 1 | a Merge with an un-fired input SETTLES on this n8n build (ingest lane, one single-lane send) | `70-DEFERRED-GATES.md` |
| Gate 70-05-A | the first ARMED batch with a MIXED verdict on one write gate reports 2 rows, never 4 | `70-DEFERRED-GATES.md` |
| Gate 3 | the finished graph's live rows are shape-equal to the walker's prediction; the live `settings.executionOrder` | `70-DEFERRED-GATES.md` |

**Standing facts for whoever picks this up:**

- **Nothing is deployed and nothing is armed.** The committed JSON is ahead of the live instance by
  the whole of Phase 70 plus Phase 66 and the two 2026-09-04 quick tasks. No committed workflow in
  this repo has ever had a native Merge node observed on the real engine.
- **CLAUDE.md's Merge claims stay `[documented]`.** The `[observed live]` upgrade is Gate 3's job
  and must not be made before the run. The follow-on edits are spelled out at the end of Gate 3.
- **`requirements.mark-complete` was passed only the four offline-verified IDs** (D-70-17, D-70-07,
  D-70-11, D-70-08a). **D-70-19 and D-70-02 were deliberately NOT ticked** — they are the two live
  ones, and `/gsd-verify-work 70` should close them against Gate 3's result rather than inherit a
  tick nobody earned.
- Follow-up worth filing: delete `scripts/prove_async_recovery.py`, now superseded and stale.

## Self-Check: PASSED

- `tests/n8n/enrichmentMixedBatch.test.mjs` — FOUND (tracked)
- `tests/n8n/ingestMixedBatch.test.mjs` — FOUND (tracked)
- `scripts/prove_phase70_runtime.py` — FOUND (tracked); `git ls-files` prints the path
- `tests/test_prove_phase70_runtime.py` — FOUND (tracked)
- `70-RUNTIME-VERDICT.json` — FOUND (tracked), parses as JSON, `shapes_equal: null`
- Task commits `52e1472`, `830c3e4`, `8ba4c8b` — all present in `git log`; the fourth
  measured commit is this summary's own metadata commit (its hash is deliberately not
  quoted here — a self-reference cannot be written before the commit that contains it)
- `git rev-list --count b779864..HEAD` = 4 (3 task commits + the metadata commit), matching `actuals.commits`
- Node counts stated in CLAUDE.md verified against a count over the committed JSON:
  `wf_enrichment_cloud 218, wf_contact_ingest_cloud 50, wf_review_decision_cloud 45,
  wf_scheduled_maintenance_cloud 43, wf_backend_status_cloud 30, wf_enrichment_local_live 70,
  wf_enrichment_local 10, wf_contact_ingest_local 13` — exact match
- All three suites green: node 1040/0, root pytest 4664 pass, plugin pytest 2864 pass
- No deploy, no bounce, no arming, no live n8n call, no hand-edited `n8n/wf_*.json`, no `git push`
