---
phase: "61"
slug: "autonomous-batch-runs"
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
status: validated
nyquist_compliant: false
wave_0_complete: true
created: "2026-09-03"
---

# Phase 61 — Validation Strategy

> Reconstructed from artifacts (State B) on 2026-09-03, **after** the phase closed. Phase 61 ran
> without a VALIDATION.md — `workflow.nyquist_validation` was absent from `.planning/config.json`
> and therefore defaulted to **enabled**, so the `verify:post` nyquist hook was active and was
> silently skipped for ~60 phases. The key is now set explicitly to `true`. Phase 63's own
> VALIDATION.md records that "Phase 61 shipped the same way"; this file closes 61's half.
>
> The audit pass that produced this map ran **read-only** and escalated two gaps. Both were
> **filled and perturbation-proved** by the orchestrator immediately afterward — see the
> Validation Audit.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (Python) + `node --test` (n8n code nodes) |
| **Config file** | none — tests are discovered by convention |
| **Quick run command** | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_confidence.py operator-claude-plugin/tests/test_held_queue.py operator-claude-plugin/tests/test_run_state.py operator-claude-plugin/tests/test_write_grant.py -q && node --test tests/n8n/asyncAck.test.mjs tests/n8n/scaleUpFanOutFlow.test.mjs tests/n8n/pairPipelineAssociationFlow.test.mjs tests/n8n/enrichmentLaneContactCreateRefusal.test.mjs` |
| **Full suite command** | `.venv/bin/python -m pytest -q` and `node --test tests/n8n/*.test.mjs` |
| **Measured runtime** | quick ~1.5s · full python ~19s · node ~4s |

**Two invocation traps, both load-bearing:** use `.venv/bin/python`, never bare `python3` — the
system interpreter lacks this project's dependencies. And use the **glob** form
`node --test tests/n8n/*.test.mjs`; the directory form is broken on node 24.

---

## Sampling Rate

- **After every task commit:** the quick run command above
- **After every plan wave:** full suite
- **Before `/gsd-verify-work`:** full suite must be green
- **Max feedback latency:** ~1.5s for the quick set

At this validation pass, after both gap-fills, the suites read **3983 passed / 154 skipped**
(pytest) and **867 pass / 0 fail** (node). Phase 61's own verification (2026-08-30) recorded
3539/154 and 844/844; the growth is later phases (62, 63) and this sweep, not drift.

---

## Per-Task Verification Map

Phase 61's requirement set is **INPUT-05, RUN-01, RUN-02, RUN-03, RUN-04, AFTER-02** — all in
`.planning/milestones/v1.1-REQUIREMENTS.md`, **not** the root `.planning/REQUIREMENTS.md`
(v1.0's). RUN-05, AFTER-01 and AFTER-03 were explicitly deferred to Phase 57 per D-61-08 and are
out of scope here. (AFTER-01 remains only partially implemented, with a known join gap in row
tracking — recorded, not closed by this phase.)

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 61-01 T1–T3 | 01 | 1 | RUN-03 — every claim in `61-SPIKE-VERDICT.md` carries exactly one basis token (`[documented]` vs `[observed live]`); execution arithmetic is stated, not assumed | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_spike_verdict_61.py -q` | ✅ | ✅ green (13 tests) |
| 61-01 T4 | 01 | 1 | RUN-03 — run-state location DECIDED by the operator at a checkpoint (HubSpot object + client-side manifest) | checkpoint (human) | — | n/a | ✅ resolved (see Manual-Only) |
| 61-02 T1–T2 | 02 | 1 | INPUT-05 — `linkedin` is a dedicated match lane ranked between `email` and weak `name`; a mixed batch yields one item per row and the linkedin row is never `unknown` | unit (n8n) | `node --test tests/n8n/linkedinLaneFlow.test.mjs tests/n8n/matchProposal.test.mjs tests/n8n/bareEventChainFlow.test.mjs tests/n8n/companyNameFallbackFlow.test.mjs` | ✅ | ✅ green |
| 61-02 T2 | 02 | 1 | INPUT-05 — the Python oracle searches the SAME properties (`lv_linkedin_url` + `hs_linkedin_url`), stored-variance covered | unit | `.venv/bin/python -m pytest tests/test_identity.py tests/test_e2e_ingest.py -q` | ✅ | ✅ green |
| 61-02 T3 | 02 | 1 | INPUT-05 — `MATCH_LOOKUP_KEYS` widened by exactly one key; a `linkedin_url` row projects into the envelope | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_rows_envelope_contract.py operator-claude-plugin/tests/test_enrichment_envelope.py -q` | ✅ | ✅ green |
| 61-03 T1 | 03 | 2 | INPUT-05 — `required_identity.any_of` has ONE source (`config/column_mapping.yaml`), driven into JS via a PyYAML oracle; both config copies byte-identical | unit + diff | `node --test tests/n8n/columnMapIdentityParity.test.mjs tests/n8n/columnMapAliasParity.test.mjs && diff config/column_mapping.yaml operator-claude-plugin/config/column_mapping.yaml && .venv/bin/python -m pytest tests/test_e2e_ingest.py operator-claude-plugin/tests/test_column_mapping_shipped.py -q` | ✅ | ✅ green (`diff` clean) |
| 61-03 T2 | 03 | 2 | INPUT-05 — a linkedin-only row is ACCEPTED; a name-only row is still REJECTED; the no-invention sentence is byte-identical | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_identity_preflight.py operator-claude-plugin/tests/test_extraction_contract.py operator-claude-plugin/tests/test_extraction_resolvable.py -q` | ✅ | ✅ green |
| 61-03 T3 | 03 | 2 | INPUT-05 — skill sequence covers the linkedin row composition | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_linkedin_row_composition.py operator-claude-plugin/tests/test_skill_sequence_coverage.py operator-claude-plugin/tests/test_enrich_before_ingest_skill_contract.py -q` | ✅ | ✅ green |
| 61-04 T1 | 04 | 3 | RUN-02 — the per-row outcome contract reaches the client: `Build Response` stamps `outcome_contract_version` plus five named signals; the parser fails toward HOLD on a missing or unknown one | unit (n8n + py) | `node --test tests/n8n/outcomeContractFlow.test.mjs && .venv/bin/python -m pytest operator-claude-plugin/tests/test_outcome_contract.py -q` | ✅ | ✅ green |
| 61-04 T2 | 04 | 3 | RUN-02 — `confidence.assess()` is a total, first-match-wins table with a terminal `else → HELD`; an unresolved material conflict holds regardless of tier | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_confidence.py -q` | ✅ | ✅ green |
| 61-04 T3 | 04 | 3 | AFTER-02 — held rows persist `0600` via `durable_paths._atomic_write_0600`; the read path degrades WHOLE, never partially; `confidence_held` is a distinct sixth verdict word with its own resume fingerprint | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_held_queue.py operator-claude-plugin/tests/test_run_manifest.py -q` | ✅ | ✅ green |
| 61-04 T4 | 04 | 3 | RUN-02 — a batch with a failed chunk AND a held row still reaches and dispatches its last row | integration (composition) | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_batch_finishes_composition.py operator-claude-plugin/tests/test_skill_sequence_coverage.py operator-claude-plugin/tests/test_enrich_before_ingest_skill_contract.py -q` | ✅ | ✅ green |
| 61-05 T1 | 05 | 4 | RUN-03 — 61-01's `## Premises` are read and the plan HALTS on contradiction | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_run_state.py -q -k premises` | ✅ | ✅ green |
| 61-05 T2 | 05 | 4 | RUN-01/RUN-04 — `async_ack` responds immediately with the CALLER's own run handle; `run_state` reports `total = pending+running+done+held+failed`, and reports unreadable state as `None`, never `0` | unit (n8n + py) | `node --test tests/n8n/asyncAck.test.mjs` and `.venv/bin/python -m pytest operator-claude-plugin/tests/test_run_state.py -q` | ✅ | ✅ green |
| 61-05 T3 | 05 | 4 | RUN-03 — an interrupted run resumes or fails LOUDLY; per-chunk manifest persistence is load-merge-save; the poll loop is bounded by a backoff array, not an unbounded `while` | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_resume_or_fail_loudly.py operator-claude-plugin/tests/test_report_sufficiency.py operator-claude-plugin/tests/test_run_manifest.py -q` | ✅ | ✅ green |
| 61-05 T4 | 05 | 4 | RUN-01 — one bounded async run observed live | manual (disarmed live) | — | n/a | ✅ green (exec `12040`, see Manual-Only) |
| 61-06 T1 | 06 | 5 | RUN-02 / §13.0.1 — a contact that resolves no company is HELD, never landed unassociated; the association rule has exactly ONE implementation | unit (n8n) | `node --test tests/n8n/pairPipelineAssociationFlow.test.mjs tests/n8n/companyAssociationFlow.test.mjs tests/n8n/contactCreateGateFlow.test.mjs tests/n8n/enrichmentLaneContactCreateRefusal.test.mjs` | ✅ | ✅ **green — gap G1 resolved, the enrichment lane's refusal is now guarded** |
| 61-06 T2 | 06 | 5 | RUN-02/AFTER-02 — an n8n-returned no-company hold is written into the SAME local held queue (one review surface, not two) | integration | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_unattended_pair_composition.py operator-claude-plugin/tests/test_report_sufficiency.py -q` | ✅ | ✅ green |
| 61-06 T3 | 06 | 5 | RUN-01 — ONE grant carries the batch, including a same-run create, with **no widening of `covers()`** (T-61-24: the planned runtime-admission mechanism was never built) | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_unattended_pair_composition.py operator-claude-plugin/tests/test_write_grant.py operator-claude-plugin/tests/test_skill_sequence_coverage.py operator-claude-plugin/tests/test_enrich_before_ingest_skill_contract.py -q` | ✅ | ✅ **green — gap G2 resolved, the DROP branch is now guarded** |
| 61-06 T4 | 06 | 5 | RUN-01 — blocking checkpoint: hold the first live unattended run for Phase 57 (D-61-08) | checkpoint (human) | — | n/a | ✅ resolved (see Manual-Only) |
| 61-06 T5 | 06 | 5 | RUN-03 — `scale_up` is OFF by default and its off-path envelope is dict-equal to today's; two INDEPENDENT depth guards; a dispatched child can never fan again | unit (n8n + py) | `node --test tests/n8n/scaleUpFanOutFlow.test.mjs tests/n8n/asyncAck.test.mjs tests/n8n/pairPipelineAssociationFlow.test.mjs` and `.venv/bin/python -m pytest operator-claude-plugin/tests/test_scale_up_runtime.py operator-claude-plugin/tests/test_run_state.py operator-claude-plugin/tests/test_report_sufficiency.py -q` | ✅ | ✅ green |
| — | all | — | Cross-cutting: every write node in every committed workflow sits behind `_writeSafetyAllows` | unit (graph walk) | `.venv/bin/python -m pytest tests/test_write_gate_coverage.py -q` | ✅ | ✅ green (21 passed / 1 skipped) |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

**Case-(b) check performed explicitly.** Every test filename named anywhere in Phase 61's
artifacts — 51 distinct `test_*.py` / `*.test.mjs` names across the 6 PLANs, 6 SUMMARYs, CONTEXT,
SECURITY, VERIFICATION and the three verdict JSONs — **exists on disk**. There are **zero**
"named-in-a-`<verify>`-block-but-missing" files in Phase 61, so 63's
`test_judge_model_routing.py` situation has no analogue here.

**The DROP-shape instance in Phase 61 is different, and it did exist: `T-61-24`.** Its register
entry describes a mitigation for `covers()`'s *runtime admission of a newly created record id* — a
surface that was **never built** (61-06 Task 3 was a verified-no-defect finding, no code change).
`61-SECURITY.md` closes it `closed (substituted evidence)` on the pre-existing, unchanged
AND-across-both-lists check. That substitution is sound, but nothing in the suite pinned the drop.
That was gap **G2**, the direct analogue of 63's G1 — **now filled**.

---

## Wave 0 Requirements

Existing infrastructure covered all phase requirements. No framework install, runner config or
fixture scaffolding was needed: both suites (`pytest`, `node --test`) and both harness idioms
(`new Function` over the repo's OWN committed jsCode; module-transport stubs for the plugin)
predate the phase and were extended, not created.

---

## Manual-Only Verifications

**Every row here is DISARMED. Nothing in Phase 61 was ever armed, and the first live,
credit-spending, unattended batch has NOT run** — it was deferred to Phase 57 by D-61-08. Phase 57
has since completed (2026-09-01), but the batch itself still has not run. Read no row below as
live proof of a production write.

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `async_ack` responds while the lane is still running, against the REAL deployed workflow | RUN-01/RUN-04 (61-05 T4) | Needs a deployed n8n Cloud instance and a real webhook round-trip; an offline test can only prove the node's shape, never that n8n responded before the execution ended. | POST the D-18 envelope with `async_ack: true` to the enrichment webhook against a **disarmed** deploy; inspect `runData` on the resulting execution (never a stored read-back). Recorded: execution `12040`, 2026-08-30 — 20 nodes ran, **no write / provider / Anthropic node ran**. Honest limit disclosed in `61-05-SUMMARY.md`: `12040`'s round-trip (2.28s) exceeded its execution span (1.911s), so respond-before-finish is proven by a *different* live execution, `12035` (P-07: 0.47s round-trip against a 5s wait), not by `12040`. |
| The self-referencing `Execute Workflow` fan-out publishes, runs, dispatches children, and TERMINATES — no grandchildren | RUN-03 (61-06 T5) | Recursion termination at runtime is a platform behaviour; the two in-JSON depth guards are unit-tested offline, but "it actually stopped" needs real executions and real child correlation via the executions API. | Publish children before parents (a parent cannot activate while a referenced child is unpublished), then POST a 2-synthetic-row batch with `scale_up: true`, **disarmed**. Recorded: parent `12045` → children `12046`/`12047`, `61-SCALE-UP-VERDICT.json`, `depth_guard_stopped_recursion: true`, no write or provider node in the parent or either child, **no grandchildren**. The same batch listed **1** execution inline (`12044`) and **3** fanned — the fan-out is NOT cheaper at this scale, and the verdict refuses that claim. |
| The 61-01 premise probes (the executions API lists child executions; `subExecution.executionId` correlates a detached child; a parent cannot activate against an unpublished child) | RUN-03 (61-01 T1–T3) | Platform behaviour, observable only against the live instance. The suite instead pins that each recorded claim carries exactly one basis token, so a `[documented]` claim can never be silently read as `[observed live]`. | Probes `12036`→`12037`, `12038`→`12039`, recorded in `61-PREMISE-PROBE-VERDICT.json`; the token discipline is enforced by `test_spike_verdict_61.py`. |
| Operator decides where async run state lives (61-01 T4); operator accepts holding the first live unattended run for Phase 57 (61-06 T4) | RUN-01/RUN-03 | `checkpoint:decision` / `gate="blocking"` by design — a human ruling, not a testable behaviour. | Both resolved in-session and recorded in the respective SUMMARY § Decisions Made. 61-06 T4's resolution also pre-authorized T5's second disarmed run. |
| Deployment parity of the committed JSON against the running instance | all n8n rows above | Only observable against the live instance, and it currently DIVERGES. | **Caveat carried forward (CLAUDE.md §13.0.2):** Phase 62 regenerated and committed `wf_enrichment_cloud.json` and five siblings **without deploying**. Every live execution cited above exercised the 2026-08-30 build, not HEAD's JSON. Node count is unchanged at 123 (Phase 62 edited `jsCode`/`jsonBody` strings only), but do not read the live evidence as evidence about HEAD. |
| n8n billing arithmetic (`T-61-16`) | RUN-03 | Unverifiable by any API key this repo holds. `watch.py`'s backoff bound is `[observed in source]`; the surrounding cost model rests on `[documented]` claims (sub-workflow executions "neither billed nor concurrency-capped") this repo has never confirmed against billing. | Not testable. Carried as a standing residual, per §13.0.3's own rule that documentation is not evidence of as-built behaviour. |

---

## Why `nyquist_compliant` is false

**By nature, and now only by nature.** The live-runtime behaviours above (respond-before-finish,
fan-out termination, the platform probes) and two human checkpoints cannot be suite-verified. That
is a deliberate, recorded classification, as in Phase 63 — not an outstanding gap.

Both genuine suite gaps (G1, G2) found by this pass are **filled and perturbation-proved**, so
they are no longer a reason for this flag. Setting `nyquist_compliant: true` would still claim
every requirement has *suite* verification, which is not true and should not be made true: an
offline fake of a live n8n round-trip would prove the wrong thing.

---

## Validation Audit 2026-09-03

| Metric | Count |
|--------|-------|
| Gaps found | 2 |
| Resolved | **2** |
| Reclassified manual-only | 6 |
| Escalated | 0 |

The audit pass itself ran read-only (two sibling auditors were working the same tree) and escalated
both gaps with proven-falsifiable specs. The orchestrator filled both immediately afterward,
sequentially, and perturbation-proved each. No implementation file was modified by either fill —
only test files.

### G1 — the enrichment lane's contact-create refusal had NO regression guard — **RESOLVED**

**The requirement.** 61-06 Task 1 closed CLAUDE.md §13.0.1's gap **by refusal**:
`ENRICH_DECIDE_CLOUD` downgrades **every** `create` on `wf_enrichment_cloud`'s contacts branch to
`action: "review"` — *including an armed one* — rather than duplicating the ingest lane's
resolve+associate subgraph. The load-bearing property is that the association rule keeps exactly
**one** operational implementation.

**Why it was a gap.** `61-VERIFICATION.md` truth 7 cites
`tests/n8n/pairPipelineAssociationFlow.test.mjs`, which loads `n8n/wf_contact_ingest_cloud.json` —
the **other** lane. So does `tests/n8n/contactCreateGateFlow.test.mjs`. A tree-wide grep for the
refusal's own reason string (`"not associated on this lane"`) and its flag
(`contactCreateHeldForAssociation`) returned **zero hits** under `tests/` — independently
re-confirmed by this record's author. The refusal was verified once by a code read and had no
test; deleting the entire downgrade block broke nothing.

**The fix.** `tests/n8n/enrichmentLaneContactCreateRefusal.test.mjs`, three tests:

1. `an ARMED contact create is downgraded to review, never landed unassociated` — arms the
   committed `Decide Action` jsCode by the **exact literal swap**
   `deploy_n8n_workflows.py::enable_baked_flags()` performs (asserting each disabled declaration
   is present verbatim first, so a spelling drift out of the overlay's reach fails here), then
   asserts `action === "review"`, `needs_review === true`, both `lv_enrichment_*` properties, and
   that the review reason **names the ingest lane** — a hold with no route is an operator dead end.
2. `non-vacuity — the SAME row disarmed is write_blocked, not review` — the explicit control.
3. `the association rule keeps exactly ONE implementation` — asserts the five ingest-lane
   association node names are **absent** from this workflow, so the rule cannot grow a second,
   driftable copy.

**The tautology trap this avoids, stated because it is the whole point.** A disarmed variant
passes vacuously: disarmed, the create becomes `write_blocked` at `_writeSafetyAllows` and never
reaches the downgrade branch at all. A test asserting only "not create" while disarmed proves
nothing. Confirmed empirically before the test was written — disarmed yields `write_blocked`,
armed yields `review`.

**Independently confirmed to be a real guard.** The downgrade block was deleted from a temporary
perturbation of `n8n/wf_enrichment_cloud.json`; the suite went **2 pass / 1 fail** with the
intended message. The file was restored via `git checkout` (`git status --porcelain n8n/` clean)
and the suite returned **3/3**.

### G2 — the T-61-24 DROP branch was unguarded — **RESOLVED**

**The requirement.** `covers()` requires **every** id AND **every** domain in a send to be inside
the grant — an AND across the two lists, never an OR. A same-run create is covered via its
**domain**, confirmed before the grant opened, never via its not-yet-existent id. No runtime
admission of created ids exists, and none may quietly appear later.

**Why it was a gap.** `test_covers_admits_a_same_run_create_via_the_domain_named_at_grant_time`
asserts that an id alone refuses and a domain alone admits — but its own docstring makes a **third
claim it never asserts**: *"A send that passes BOTH the unknown-at-grant-time id AND the known
domain still refuses."* Independently confirmed by reading the test body: only two assertions are
present. That combination is precisely what starts passing if the never-built admission mechanism
ships later, or if the AND is ever widened to an OR.

**The fix.**
`operator-claude-plugin/tests/test_write_grant.py::test_covers_never_admits_an_id_absent_from_the_grant_even_alongside_a_covered_domain`
— opens a grant with `record_ids=()` and `record_domains=("newco.example",)`, then asserts that a
send carrying **both** an uncovered id and the covered domain still refuses, that the refusal
**names the offending id** (`outside_record_ids == ["999999"]`), and — the "nothing may quietly
ship later" half — that the grant dict is **byte-unmutated** by the call, so no
admission-by-side-effect can be introduced without failing. It asserts the refusal's *shape*, never
its prose, so a wording change does not trip it while an OR-widening does.

**Independently confirmed to be a real guard.** The AND across the two lists was widened
(`if outside_ids or outside_domains` → `and`) in a temporary perturbation of
`operator-claude-plugin/scripts/write_grant.py`; the test failed on `assert None is not None`. The
file was restored via `git checkout` (`git status --porcelain operator-claude-plugin/scripts/`
clean) and the test returned green.

---

## Validation Sign-Off

- [x] All tasks have an `<automated>` verify or a recorded manual-only justification
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (none needed — existing infrastructure sufficed)
- [x] No watch-mode flags
- [x] Feedback latency < 5s for the quick set
- [x] Every command in this file was executed at HEAD, not inferred
- [x] **G1 filled** (`tests/n8n/enrichmentLaneContactCreateRefusal.test.mjs`) — perturbation-proved
- [x] **G2 filled** (`test_covers_never_admits_an_id_absent_from_the_grant_even_alongside_a_covered_domain`) — perturbation-proved
- [ ] `nyquist_compliant: true` — deliberately NOT set; see "Why `nyquist_compliant` is false"

**Approval:** approved 2026-09-03 (partial — 6 manual-only by nature)
