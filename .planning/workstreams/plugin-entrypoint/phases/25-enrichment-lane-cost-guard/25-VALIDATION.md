---
phase: 25
slug: enrichment-lane-cost-guard
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-31
---

# Phase 25 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Seeded by plan-phase from `25-RESEARCH.md` §"Validation Architecture". `/gsd-validate-phase` sets
> `status: validated`.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest for Python (repo + plugin); `node --test` for n8n Code-node JS |
| **Config file** | repo-root pytest config; plugin tests live under `operator-claude-plugin/tests/` |
| **Quick run command** | `.venv/bin/python -m pytest operator-claude-plugin/tests -q` |
| **Full suite command** | `.venv/bin/python -m pytest -q && node --test tests/n8n/*.test.mjs` |
| **Estimated runtime** | ~30–60 seconds quick; full suite longer |

**Note:** the repo's established invocation is `.venv/bin/python -m pytest` (system python lacks
deps) and `node --test tests/n8n/<file>.test.mjs` in FILE form — the directory form is broken on the
installed node version. Do not substitute a bare `pytest`.

**Safety note binding every row below:** no automated verification in this phase performs a live
armed dispatch, a live deploy, or a workflow activation. The two live probes (25-01 Task 2) are
human-executed checkpoints against the committed disarmed build; every other network interaction runs
against `conftest.py`'s recording stub behind the autouse network guard.

---

## Sampling Rate

- **After every task commit:** run the quick command plus the task's own `<automated>` verify
- **After every plan wave:** run the full suite
- **Before `/gsd-verify-work`:** full suite must be green
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 25-01-01 | 25-01 | 1 | INGEST-04 | T-25-06, T-25-11 | scope probe never prints the token; a 404 and a 403 classify differently | unit (mocked) | `.venv/bin/python -m pytest tests/test_check_hubspot_list_scope.py -q` | ❌ W0 | ⬜ pending |
| 25-01-02 | 25-01 | 1 | INGEST-04, PREVIEW-03 | T-25-12 | live probes run against the committed disarmed build; credit cost disclosed in advance | manual | n/a — human-executed live probes (see Manual-Only Verifications) | n/a | ⬜ pending |
| 25-01-03 | 25-01 | 1 | INGEST-04 | T-25-15 | view handling is a recorded decision, not a silent omission | manual | n/a — decision checkpoint (see Manual-Only Verifications) | n/a | ⬜ pending |
| 25-02-01 | 25-02 | 1 | PREVIEW-02 | T-25-04, T-25-03, T-25-14 | header-auth-bound endpoint; sequential probe chain; committed artifact stays disarmed | structural (built JSON) | `.venv/bin/python scripts/build_cloud_workflows.py && .venv/bin/python -m pytest tests/test_remaining_credits_response.py tests/test_cloud_write_path.py -q` | ✅ exists | ⬜ pending |
| 25-02-02 | 25-02 | 1 | PREVIEW-02 | T-25-05, T-25-03 | unreadable balance survives assembly as unreadable; genuine zero distinguishable | unit + structural | `node --test tests/n8n/backendStatusResponse.test.mjs && .venv/bin/python -m pytest tests/test_backend_status_workflow.py -q` | ❌ W0 | ⬜ pending |
| 25-02-03 | 25-02 | 1 | PREVIEW-02 | T-25-14 | new workflow deploys credential-bound, not silently unbound | unit | `.venv/bin/python -m pytest tests/test_deploy_credential_binding.py tests/test_deploy_n8n_workflows.py tests/test_enabled_build_invariants.py -q` | ✅ exists | ⬜ pending |
| 25-03-01 | 25-03 | 2 | INGEST-04 | T-25-07, T-25-16 | list branch is additive; record-ID path unchanged; no `$env`/`$vars` | structural (built JSON) | `.venv/bin/python scripts/build_cloud_workflows.py && .venv/bin/python -m pytest tests/test_remaining_credits_response.py tests/test_cloud_write_path.py tests/test_provider_gate_topology.py tests/test_fetch_by_id_topology.py -q` | ✅ exists | ⬜ pending |
| 25-03-02 | 25-03 | 2 | INGEST-04 | T-25-07, T-25-15, T-25-02 | oversize list refused not truncated; view never resolved as a list; selection survives expansion | unit + structural | `node --test tests/n8n/listExpansion.test.mjs && .venv/bin/python -m pytest tests/test_enrichment_list_branch.py -q` | ❌ W0 | ⬜ pending |
| 25-03-03 | 25-03 | 2 | INGEST-04 | T-25-07 | the shipped ceiling and view handling are discoverable outside the planning directory | unit (suite regression) | `.venv/bin/python -m pytest tests/test_enrichment_list_branch.py tests/test_deploy_credential_binding.py -q` | ❌ W0 | ⬜ pending |
| 25-04-01 | 25-04 | 2 | INGEST-04, DISPATCH-02 | T-25-01, T-25-02, T-25-17, T-25-18 | `armed` has no default; selection always explicit; unarmed path leaves the stub's call log empty | unit (stub transport) | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_enrichment_envelope.py -q` | ❌ W0 | ⬜ pending |
| 25-04-02 | 25-04 | 2 | DISPATCH-02 | T-25-02 | shipped default's credit-burn consequence is stated in the file that ships it; no provider key placeholder | unit (static) | `.venv/bin/python -m pytest operator-claude-plugin/tests -q` | ❌ W0 | ⬜ pending |
| 25-05-01 | 25-05 | 2 | PREVIEW-02 | T-25-20, T-25-23 | every rate carries value, unit, citation, date; unknown and measured-zero are distinct; no runtime doc-path read | unit (static) | `.venv/bin/python -m pytest operator-claude-plugin/tests -q` | ❌ W0 | ⬜ pending |
| 25-05-02 | 25-05 | 2 | PREVIEW-02 | T-25-05, T-25-21, T-25-22 | comparison branches on unreadable before magnitude; no numeric fallback; unreachable endpoint yields unknowns not zeros | unit (stub transport) | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_cost_guard.py -q` | ❌ W0 | ⬜ pending |
| 25-06-01 | 25-06 | 3 | PREVIEW-03 | T-25-24 | chunk concatenation equals the input exactly; no empty trailing chunk; list count honestly unknown | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_chunking.py -q` | ❌ W0 | ⬜ pending |
| 25-06-02 | 25-06 | 3 | PREVIEW-03, DISPATCH-02 | T-25-01, T-25-25, T-25-08, T-25-17 | failing middle chunk does not stop the run; timeout counts as failed; failed batch excludes succeeded ids | unit (stub transport) | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_chunking.py -q` | ❌ W0 | ⬜ pending |
| 25-07-01 | 25-07 | 4 | PREVIEW-02, PREVIEW-03 | T-25-05, T-25-27, T-25-22 | unreadable renders as unknown not zero; list preview shows no numeric count; preview survives an unreachable endpoint | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_preview_enrichment.py operator-claude-plugin/tests/test_preview_rendering.py -q` | ❌ W0 | ⬜ pending |
| 25-07-02 | 25-07 | 4 | INGEST-04, DISPATCH-02 | T-25-01, T-25-17, T-25-26 | skill states endpoint and armed state up front; no secret in the conversation; no second entry point | unit (static) | `.venv/bin/python -m pytest operator-claude-plugin/tests -q` | ❌ W0 | ⬜ pending |
| 25-07-03 | 25-07 | 4 | INGEST-04, DISPATCH-02, PREVIEW-02, PREVIEW-03 | — | ROADMAP describes what shipped; no requirement reduced without a recorded amendment; no phase section lost | unit (suite regression) | `.venv/bin/python -m pytest -q` | ✅ exists | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Wave 0 for this phase is the set of test files that do not yet exist. Each is created by the task
that first needs it — there is no separate scaffolding plan, because
`operator-claude-plugin/tests/conftest.py` (fixtures + autouse network guard) and the repo's
`tests/n8n/` idioms already landed in Phase 23 plan 23-03 and Phase 16 respectively.

- [ ] `tests/test_check_hubspot_list_scope.py` — INGEST-04 scope-probe classification (25-01)
- [ ] `tests/test_backend_status_workflow.py` — PREVIEW-02 status endpoint structure (25-02)
- [ ] `tests/n8n/backendStatusResponse.test.mjs` — PREVIEW-02 unreadable-vs-zero assembly (25-02)
- [ ] `tests/n8n/listExpansion.test.mjs` — INGEST-04 expansion and its three refusals (25-03)
- [ ] `tests/test_enrichment_list_branch.py` — INGEST-04 additive wiring (25-03)
- [ ] `operator-claude-plugin/tests/test_enrichment_envelope.py` — INGEST-04 / DISPATCH-02 (25-04)
- [ ] `operator-claude-plugin/tests/test_cost_guard.py` — PREVIEW-02 (25-05)
- [ ] `operator-claude-plugin/tests/test_chunking.py` — PREVIEW-03 (25-06)
- [ ] `operator-claude-plugin/tests/test_preview_enrichment.py` — PREVIEW-02 / PREVIEW-03 rendering (25-07)

No new test framework install is needed: pytest and `node --test` are both already present and
already used for structurally identical logic in this repo.

**Critical Wave 0 constraints:**
1. No dispatch test may perform a real POST. The arming guard is the thing under test; a test that
   accidentally arms and sends is worse than no test. The autouse `no_network` fixture from 23-03 is
   what makes this structural rather than a convention.
2. No test may assert only that an unreadable balance is falsy. Zero is falsy too, and that assertion
   passes against the exact defect D-10 exists to prevent. Every unreadable-versus-zero test must
   assert the two produce *different* output.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Whether the HubSpot credential carries `crm.lists.read` | INGEST-04 (D-02a) | Requires a live authenticated call; the token is env-held and permission-blocked to tooling | **Sequence first, before any list/view implementation.** Run `python scripts/check_hubspot_list_scope.py "<real company list name>"` with the token exported. A 403 means the scope is missing and the private app needs it granted plus the credential re-provisioned; a 404 proves the scope is present. Record the verdict in `25-BLOCKERS.md` |
| Per-record wall-clock time through the enrichment chain | PREVIEW-03 (D-11a) | No batch-timing data exists in this repo; the number cannot be derived offline | **Sequence before fixing the chunk-size default.** Time POSTs of 1, 3 and 5 records with an empty provider selection (free of provider credits), plus one single-record fire with the full waterfall (costs roughly 2 Lusha + 1 ZoomInfo credit and a few cents of Anthropic spend) for the worst case. The committed disarmed build means zero HubSpot writes. Derive `max_records_per_chunk` as `floor(60 / worst-case seconds-per-record)`, floor 1, and record every input in `25-BLOCKERS.md` |
| How a saved-view input is handled | INGEST-04 (D-02a) | A scope decision with a requirement-amendment consequence; not a machine call | Decision checkpoint in 25-01 Task 3. Choose refuse-and-redirect, a discovery spike, or (rejected on its face) resolving a view against the list endpoint. Record the choice, the date, the operator-facing sentence, and the implementing plan in `25-BLOCKERS.md` |
| Live `hubspot/backend-status` returns a real 200 and a real 403 with the tri-state intact | PREVIEW-02 (D-10) | Unit tests prove the *probe* contract and the *assembly* logic; only a live call proves the new endpoint's own wiring preserves them end to end | After the status workflow is deployed (an admin deploy-time action outside every plan in this phase), POST once with the shared secret and confirm Lusha and ZoomInfo return numbers while Apollo returns the unreadable marker and not a zero |
| An armed enrichment batch lands enrichment on real records | DISPATCH-02 | Requires live n8n, a deploy-time arming window, and burns real credits | Out of scope for every automated verification in this phase. Arming stays a deploy-time admin operation coupled to the `TEST_RECORD_*` allowlist; run it, if at all, as a separately scheduled canary after `/gsd-verify-work` |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or are declared manual-only above
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] No automated verification performs a live armed dispatch
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
