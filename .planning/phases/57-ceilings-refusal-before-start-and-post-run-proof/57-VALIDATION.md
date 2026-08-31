---
phase: 57
slug: ceilings-refusal-before-start-and-post-run-proof
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-08-31
---

# Phase 57 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from `57-RESEARCH.md` § Validation Architecture (lines 686-726).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (`operator-claude-plugin/tests/` and root `tests/`) + Node built-in `node --test` (`tests/n8n/*.test.mjs`) |
| **Config file** | none committed — `tests/conftest.py` documents there is no `pytest.ini` / `pyproject.toml` / `setup.cfg` `[pytest]` block |
| **Quick run command** | `.venv/bin/python -m pytest operator-claude-plugin/tests -q` |
| **Full suite command** | `.venv/bin/python -m pytest -q` **and** `node --test tests/n8n/*.test.mjs` (glob form only — directory form is broken on node 24) |
| **Estimated runtime** | ~30s quick / ~4–6 min full |

**Baseline at phase start:** root 3539 passed / 154 skipped (STATE.md, Phase 61 close).

---

## Sampling Rate

- **After every task commit:** `.venv/bin/python -m pytest operator-claude-plugin/tests -q`
- **After every plan wave:** `.venv/bin/python -m pytest -q` AND `node --test tests/n8n/*.test.mjs`
- **Before `/gsd-verify-work`:** full suite green
- **Max feedback latency:** ~30 seconds (quick command)
- **Phase gate:** the ZoomInfo live-probe result (pass / fail / inconclusive) is reported in the phase summary **regardless of outcome** — it may not be resolvable from this repo alone (RESEARCH Assumption A3).

---

## Per-Task Verification Map

> Populated per task by the planner. The **Caller Path** column is not optional — Phase 59's
> defining lesson (ROADMAP.md:168-180) is that four gaps shipped past three green suites
> because every test drove a unit boundary rather than the integration path.

| Req ID | Behavior | Test Type | Automated Command | Caller path the test MUST drive |
|--------|----------|-----------|-------------------|----------------------------------|
| RUN-05 | A batch that would exhaust the allowance refuses BEFORE starting, with arithmetic, offering a smaller batch | unit + integration | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_write_grant.py -k ceiling -x` | `write_grant.plan_grant()` / `envelope()` themselves — the real path an operator's request reaches. NOT a bare arithmetic-comparison helper in isolation. |
| D-57-01 | Spending stops mid-batch **before the breaching chunk is sent**; remainder held; run completes; grant closes `ceiling_breach` | integration | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_write_grant.py -k breach -x` | A REAL multi-chunk `chunking.dispatch_plan()` call with `stub_module_transport_factory` (mirroring `test_a_revocation_midway_does_not_stop_a_running_dispatch`'s 3-chunk idiom). Must assert (a) the transport was NEVER called for the breaching chunk — the tally is pre-send, revised after review; and (b) `write_grant.record_send_outcome(...)` is **actually called as a consequence of that dispatch**, not merely that it accepts the right shape when called directly (Pitfall 1). |
| D-57-03 | Every backend `action` maps to the correct widened outcome, **including `enrich`** | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_written_records.py -x` | `classify_item` direct unit test is appropriate (pure function). ALSO cover `report_enrichment.py`'s `_ACTION_TO_OUTCOME` for the 4 currently-unmapped actions (`update`, `review`, `research_failed`, `recompute_refused`) — verified drift between two vocabulary surfaces (Pitfall 3). |
| AFTER-01 | One report joining per-record outcome, held rows named individually, spend vs ceiling, disarm verdict | integration | new test driving the join against fixture `written_records` / `run_state` / `held_queue` artifacts on disk (`tmp_path` + `_patch_durable_dir` idiom) | Must assert the join **finds held rows by name** — a fixture entry with `hs_object_id: None` must still appear keyed by `row_id`, proving the `row_id` gap is closed, not merely that the function runs. |
| AFTER-03 | A gated (`write_blocked`) record must never read as completed | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_written_records.py -k gated` | Assert `classify_item({"action": "write_blocked", ...})` yields the NEW `gated` word (not the old `not_written` collapse) **and** that the operator-facing render uses distinct text for `gated` vs `written`. |
| G-4 | Report names which balances were readable / unreadable, and improves what is fixable | unit (Apollo/Lusha) + disarmed live probe (ZoomInfo) | `.venv/bin/python -m pytest operator-claude-plugin/tests -k backend_status_unknown_balance`; `.venv/bin/python -m pytest operator-claude-plugin/tests/test_prove_zoominfo_balance.py -q`; then the gated live probe | Disclosure half already covered by `conftest.py:532-547` (Apollo's label there is **`http_403`**). The gate half must be proved by ZERO calls reaching an injected transport double under `no_network` — not by an AST/string check. The live-probe half must hit the REAL `Status Credit Request` → `ZoomInfo Usage` chain on the deployed instance; it writes no CRM record, but it is a POST that triggers provider probes and a possible ZoomInfo token mint, so "read-only" refers to EFFECT and not to HTTP verbs. **Closure is defined in `57-04-PLAN.md` § "What closes G-4" — an `inconclusive` probe does NOT close it.** |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

### Populated by the planner, 2026-08-31 — per task

> **REVISED 2026-08-31 after cross-AI review (`57-REVIEWS.md`).** Two changes run through the
> whole table. (1) Task numbers shifted: 57-02 gained a LEADING `checkpoint:decision`, and 57-01 gained one as its
> Task 2 (the cycle-2 revision swapped 57-01's tracer and checkpoint, so 57-01's is NOT leading), and 57-05 gained one at the end. (2) **Markdown identifier greps are no
> longer accepted as the primary proof of runbook wiring.** The first pass verified
> `record_dispatch_outcome` / `execution_ceiling` / `build_run_report` with `grep -c … SKILL.md`,
> which passes on prose — a direct violation of this table's own "Caller path the test MUST drive"
> column and the Phase 59 lesson it exists for. Those rows now drive an AST test that COMPILES the
> runbook's fenced python and asserts on the parsed tree.
>
> **Wave structure changed:** 57-04 moved to wave 1 (it consumes nothing from 57-01), and 57-05
> now depends on 57-04 as well as 57-02 and 57-03, because it claims G-4's disclosure half.
> Waves are: 1 = 57-01, 57-04 · 2 = 57-02, 57-03 · 3 = 57-05.

| Plan · Task | Automated command | Caller path the test MUST drive | Status |
|---|---|---|---|
| 57-01 · T1 (tracer) | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_write_grant.py operator-claude-plugin/tests/test_chunking.py operator-claude-plugin/tests/test_n8n_read.py operator-claude-plugin/tests/test_write_grant_surface.py operator-claude-plugin/tests/test_write_grant_guardrails.py operator-claude-plugin/tests/test_unattended_pair_composition.py -q` (SIX files, matching the plan's own `<verify>` — the last three carry scripted transports the frozen-call-order change breaks) | **Task 1 is now the tracer and Task 2 the checkpoint — the two were swapped in the cycle-2 revision (REVIEW-57-H1), because the sampling fixes must land before the measurement that judges them.** `write_grant.plan_grant()` for the refusal; a REAL 3-chunk `chunking.dispatch_plan()` with `stub_module_transport_factory` for the PRE-SEND stop (assert the transport is NOT called for the breaching chunk, and `len(results) == 2`); the resulting `DispatchOutcome` passed to `write_grant.record_dispatch_outcome` for the close — never a hand-built outcome. Plus `n8n_read.executions_in_window` itself for `listing_exhausted` / `max_pages`. Plus `chunking.single_dispatch_outcome` — `inspect.signature` for `record_count`, and a value assertion that a one-chunk wrap of a 7-record `dispatch.dispatch` dict projects `1 + 7` through `EXECUTIONS_BASIS` | ⬜ |
| 57-01 · T2 (checkpoint) | none — blocking operator decision | **Runs AFTER T1's fixes, not before.** Its measurement drives `write_grant.allowance_headroom(cfg)` — not the raw walker — and prints `sampled` alongside `covers_full_window` / `listing_exhausted` / `truncated_by_page_cap`, because `sampled` is the predicate the refusal turns on. Carries a precondition refusing presentation if T1 did not land. This is the evidence for whether RUN-05's refusal can fire on this account at all, and 57-05 T4's option-b is unselectable if it reads `CEILING_UNKNOWN` | ⬜ |
| 57-01 · T3 | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_write_grant.py -q` | `envelope()` itself, with a stubbed executions transport; the block asserted from the real render, not a helper. Plus `grep`-checked decision-record edits in STATE.md / 57-DISCUSSION-LOG.md / 61-CONTEXT.md | ⬜ |
| 57-01 · T4 | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_write_grant.py operator-claude-plugin/tests/test_preingest_merge.py operator-claude-plugin/tests/test_retry_reuses_dispatch.py -q` | `preingest.rerequest_unanswered` itself with a stubbed dispatch (the second-pass-under-one-grant path); and an AST test that COMPILES each SKILL.md dispatch block and asserts `dispatch_plan(..., execution_ceiling=…)` plus `record_dispatch_outcome` inside a `try`/`finally`. **A `grep` on SKILL.md is a secondary assertion only** | ⬜ |
| 57-01 · T4 (single-shot leg) | same command | **The FOURTH dispatch path (REVIEW-57-H7): `dispatch.dispatch(out_path, True, cfg, run_id=…)` at `enrich-before-ingest/SKILL.md:610`, which has no chunk boundary inside it and returns a plain dict, not a `DispatchOutcome`.** An AST test compiling that block and asserting BOTH: a ceiling check BEFORE the call, and a `chunking.single_dispatch_outcome(...)` wrap after it whose result reaches `record_dispatch_outcome`. All three skills are compiled and asserted, with `contact-upload` differentiated — a `grep` for the function name satisfies none of this | ⬜ |
| 57-02 · T1 (checkpoint) | none — blocking operator decision | Whether `written` may be claimed from a pre-write action plus a pre-known id. Evidence assembled from `build_cloud_workflows.py:465-520` and the two decision nodes | ⬜ |
| 57-02 · T2 | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_written_records.py -q` | `classify_item` and the new pure `outcome_for_action` direct, parametrised over the ten real action values — where the ten are EXTRACTED from `scripts/build_cloud_workflows.py`, not hard-coded in the test. The executor proves the test can fail by temporarily adding an eleventh literal to the builder | ⬜ |
| 57-02 · T3 | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_report_enrichment.py -q` | `build_enrichment_report`/`build_sync_report`, plus a cross-module agreement test over all ten actions, plus a never-raise test over a malformed and a forbidden-named row | ⬜ |
| 57-02 · T4 | `node --test tests/n8n/ingestResponseRowId.test.mjs` | the GENERATED `n8n/wf_contact_ingest_cloud.json`. **No live read-back — this plan no longer deploys**; deployment moved to 57-05 T4 behind the phase gate | ⬜ |
| 57-03 · T2 | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_remainder_queue.py -q` | `build_entry`/`save`/`load` against `tmp_path` via the `_patch_durable_dir` idiom, with a RECURSIVE forbidden-value scan exercised through dict-in-list (the real `people`/`companies` shape) | ⬜ |
| 57-03 · T3 | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_write_grant.py operator-claude-plugin/tests/test_chunking.py -q` | `chunking.failed_batch` round-tripped through `plan_chunks` for ALL FIVE shapes (the `people`/`companies` cases currently lose data); `plan_grant()` for the offer AND for the state-transition test that a refusal writes no file; a REAL `dispatch_plan()` ceiling stop for the remainder write, read back off disk, for a `people` plan as well as a `record_ids` plan | ⬜ |
| 57-04 · T1 | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_prove_zoominfo_balance.py -q` + the gated live run | The probe's injectable entry function driven with a transport double under the `no_network` fixture — gate absent, gate truthy-but-not-`"true"`, wrong instance all assert ZERO calls; valid case asserts exactly one. **An AST/string check on the gate is not sufficient.** Then the deployed `Status Credit Request` → `ZoomInfo Usage` chain for the live verdict | ⬜ |
| 57-04 · T2 | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_cost_guard.py -q` | `cost_guard.compare` and `write_grant._headroom` over the new fixture; the Apollo assertion pins `http_403` (`conftest.py:542`), NOT `unrecognized_response_shape` | ⬜ |
| 57-05 · T1 | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_written_records.py operator-claude-plugin/tests/test_run_manifest.py operator-claude-plugin/tests/test_run_report.py -q` | `written_records.classify_read` and `run_manifest.classify_read` over absent / good / unparseable / wrong-run files on `tmp_path`; `run_report.record_audit` / `load_audit` including the authority test that a grant-shaped argument is refused | ⬜ |
| 57-05 · T2 | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_run_report.py -q` | `build_run_report` against fixture artifacts on disk; the join asserted by finding an `hs_object_id: None` row under its `(row_id, lane)` key in both the dict and the rendered block; five seeded contradiction pairs; the crash-reconstructed path where the caller passes no ceiling or disarm and the persisted audit record supplies them | ⬜ |
| 57-05 · T3 | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_run_report.py operator-claude-plugin/tests/test_write_grant.py -q` | the EXTENDED AST test that compiles both SKILL.md code blocks and asserts `build_run_report(..., outcomes=…)` and both `record_audit` calls, one before the dispatch and one in the `finally` | ⬜ |
| 57-05 · T4 (checkpoint) | full suite green as a precondition | Blocking operator decision: deploy the regenerated disarmed ingest workflow, and separately authorise (or not) the first live credit-spending batch. Landing the phase authorises nothing | ⬜ |

---

## Wave 0 Requirements

- [ ] Integration-shaped test driving `write_grant.record_send_outcome` **from a real dispatch path**. Corrected against the tree (REVIEW-57-M8): the function is invoked **ten times across two test files** — four in `test_write_grant.py` and six in `test_write_grant_guardrails.py` — **none of them at line 1507**, which the first pass cited. Outside its own definition in `write_grant.py` there are **zero production callers**, which is the actual gap: every existing invocation is a direct call from a test. Land the dispatch-path test red before any implementation task.
- [ ] Characterization test confirming `chunking.dispatch_plan`'s current `for` loop always completes all chunks — makes the later "stops early on breach" diff legible against a known baseline.
- [ ] ZoomInfo-specific `provider_error` response fixture — `conftest.py`'s existing `_balance()` / `backend_status_*` fixtures cover Apollo's **`http_403`** (`conftest.py:542`, NOT `unrecognized_response_shape` — the research and the first plan set were both wrong on this) but no ZoomInfo shape. Add only if G-4's fix needs a regression test.
- [ ] Characterization test for `chunking.failed_batch` over ALL FIVE shapes `plan_chunks` accepts. Land it red: `people` and `companies` currently return only the first chunk (`chunking.py:494-517`), which is a live silent-drop defect, not a new requirement.
- [ ] The live READ-ONLY month-to-date sampling measurement (57-01 T2's precondition — the checkpoint, now Task 2 after the cycle-2 swap). It is not a test, but it is the evidence that decides whether RUN-05's preflight refusal is reachable at all on this account. **It is taken AFTER the tracer, not before it** — the cycle-2 revision swapped the two (REVIEW-57-H1), because measuring the sampling before fixing its predicate would judge the wrong code. It drives `write_grant.allowance_headroom(cfg)` rather than the raw walker, and prints `sampled` alongside `covers_full_window` / `listing_exhausted` / `truncated_by_page_cap`.

*Framework and most fixtures already exist; these gaps are additive test cases, not new infrastructure.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| ZoomInfo live balance behaviour | G-4 | Requires a live credentialled call to the deployed n8n instance; the 2026-08-25 `provider_error` observation predates the current (correct) `Accept` header code, so only a re-probe can say whether it persists | Run the new disarmed probe script against the deployed instance; record pass / fail / inconclusive in the phase summary either way. Read-only — never arms a write. |
| Apollo balance read | G-4 | Structurally unfixable in code — non-master API key, 403 by design | No test. Disclosed as a permanent blind spot per D-57-02; assert only that the disclosure text names it. |

---

## Prohibitions (validation-side)

- **No task in this phase may arm a write or spend a provider credit.** Every proof must be performable disarmed (`prove_scale_up_runtime.py` / `prove_async_recovery.py` are the templates). The single live action in the phase is 57-05 T4's disarmed workflow deploy, behind a blocking checkpoint.
- **No test may assert a ceiling behaviour by calling a helper the production path never calls.** That is the exact Phase 59 failure mode this map exists to prevent.
- **No `grep -c <identifier> SKILL.md` may be the ONLY proof that a runbook is wired to a function.** It passes on prose. Where a runbook must call something, the test compiles that runbook's fenced python block and asserts on the parsed tree; the grep stays as a cheap secondary check. Added 2026-08-31 after cross-AI review found three such criteria in the first plan set.
- **No gate may be proved by the presence of its own text.** A gate that stops a network call is proved by driving the entry point with a transport double and asserting zero calls, under the `no_network` fixture.

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] Every ceiling/report behaviour's test drives the real caller path (Phase 59 lesson)
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
