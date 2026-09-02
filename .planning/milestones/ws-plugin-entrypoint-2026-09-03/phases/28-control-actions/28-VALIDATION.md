---
phase: 28
slug: control-actions
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-31
---

# Phase 28 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Seeded by plan-phase from `28-RESEARCH.md` §"Validation Architecture". The planner filled the
> per-task map; `/gsd-validate-phase` sets `status: validated`.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (repo convention; the plugin carries its own `requirements.txt`) |
| **Config file** | repo-root pytest config — plugin tests live under `operator-claude-plugin/tests/` |
| **Quick run command** | `.venv/bin/python -m pytest operator-claude-plugin/tests -q` |
| **Full suite command** | `.venv/bin/python -m pytest -q && node --test tests/n8n/*.test.mjs` |
| **Estimated runtime** | ~30–60 seconds quick; full suite longer |

**Note:** the repo's established invocation is `.venv/bin/python -m pytest` (system python lacks
deps) and `node --test tests/n8n/*.test.mjs` in FILE form — the directory form is broken on the
installed node version. Do not substitute a bare `pytest`.

**Wave 0 is already in place.** `operator-claude-plugin/tests/conftest.py` shipped in 23-03 and
supplies `stub_transport` plus the **autouse** `no_network` guard. Every test in this phase inherits
it, which is why no automated verification in Phase 28 can reach the network — let alone arm
anything. 28-01 Task 3 asserts the guard covers `requests.put` and `requests.get`, the two verbs
this phase introduces.

---

## Sampling Rate

- **After every task commit:** run the quick command
- **After every plan wave:** run the full suite
- **Before `/gsd-verify-work`:** full suite green **plus** both live checkpoints in 28-02 and the
  armed canary in 28-06 actually performed and recorded
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 28-01-01 | 28-01 | 1 | CONTROL-02, CONTROL-06, CONTROL-07 | T-28-02 | verdict comes from an independent re-read; a stale read-back is `failed`; reversal quotes the captured prior value | unit (stub transport) | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_control_pipeline.py -q` | ❌ W0 | ⬜ pending |
| 28-01-02 | 28-01 | 1 | CONTROL-05 | T-28-01, T-28-03, T-28-06 | out-of-allowlist diff refuses with an empty call log; the bracket restores the PRIOR active state | unit (stub transport) | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_control_allowlist_diff.py -q` | ❌ W0 | ⬜ pending |
| 28-01-03 | 28-01 | 1 | CONTROL-06 | T-28-02, T-28-04 | no path returns `verified` on a status code; four-key filter pinned to the deploy script; PUT/GET blocked in tests | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_control_verify_reporting.py operator-claude-plugin/tests/test_transport_guard.py -q` | ❌ W0 | ⬜ pending |
| 28-02-01 | 28-02 | 2 | CONTROL-06 | T-28-07, T-28-09 | the probe cannot write a write-safety constant and refuses without its enabling variable and instance guard | unit (stub transport) | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_control_probe.py -q` | ❌ W0 | ⬜ pending |
| 28-02-02 | 28-02 | 2 | CONTROL-06 | T-28-09 | D-20 no-op round-trip: `settings`/`connections` survive; execute endpoint confirmed absent | **manual (human-executed, live)** | n/a — see Manual-Only Verifications | n/a | ⬜ pending |
| 28-02-03 | 28-02 | 2 | CONTROL-03, CONTROL-06 | T-28-08 | D-18/A1: the deactivate→PUT→activate bracket observed effective on a running instance; cadence restored and verified | **manual (human-executed, live)** | n/a — see Manual-Only Verifications | n/a | ⬜ pending |
| 28-03-01 | 28-03 | 3 | CONTROL-04 | T-28-14, T-28-16 | bidirectional setter with fail-closed re-scan; literal/charset parity with the deploy script and Phase 27's reader | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_control_flag_parity.py -q` | ❌ W0 | ⬜ pending |
| 28-03-02 | 28-03 | 3 | CONTROL-04, CONTROL-07 | T-28-11, T-28-12, T-28-13 | empty record allowlist refused; disarm runs on the exception path; `disarm_failed` is a distinct loud outcome; permitted diff is the declaration lines only | unit (stub transport) | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_control_arming.py -q` | ❌ W0 | ⬜ pending |
| 28-03-03 | 28-03 | 3 | CONTROL-04 | T-28-15 | every committed `n8n/wf_*_cloud.json` declaration reads its disabled literal | unit (artifact scan) | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_control_disarmed_artifacts.py -q` | ❌ W0 | ⬜ pending |
| 28-04-01 | 28-04 | 3 | CONTROL-03 | T-28-17, T-28-19 | plain-language description for every supported shape; refusal-with-examples for an unmappable phrase; no rendered string carries field-expression syntax | unit (pure) | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_control_cadence.py -q` | ❌ W0 | ⬜ pending |
| 28-04-02 | 28-04 | 3 | CONTROL-03, CONTROL-05 | T-28-18, T-28-31 | per-job enable/disable per D-25: one `disabled` boolean on one Schedule Trigger; reverting it reproduces the node byte for byte; a non-trigger node refuses | unit (stub transport) | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_control_cadence.py -q` | ❌ W0 | ⬜ pending |
| 28-04-03 | 28-04 | 3 | CONTROL-03, CONTROL-05, CONTROL-07 | T-28-18, T-28-20 | cadence PUT touches one node; a refusal object cannot be written as an interval; prior cadence quoted back | unit (stub transport) | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_control_cadence.py -q` | ❌ W0 | ⬜ pending |
| 28-05-01 | 28-05 | 4 | CONTROL-01, CONTROL-05, CONTROL-06 | T-28-21, T-28-22, T-28-23, T-28-24, T-28-25 | confirmation has no default; out-of-allowlist refused pre-network; lane start bypasses no guard; no schedule-to-fire path exists | unit (stub transport) | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_control_surface.py -q` | ❌ W0 | ⬜ pending |
| 28-05-02 | 28-05 | 4 | CONTROL-05, CONTROL-07 | T-28-24 | every script path a SKILL.md names exists; the manifest test globs every skill | unit (static) | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_plugin_manifest.py -q` | ✅ exists | ⬜ pending |
| 28-05-03 | 28-05 | 4 | CONTROL-01 | — | the source artifacts promise only what exists, and record the probed reason the other capability was dropped | static (grep) | `grep -q "no endpoint to execute a workflow by id" .planning/workstreams/plugin-entrypoint/REQUIREMENTS.md` | ✅ exists | ⬜ pending |
| 28-06-01 | 28-06 | 5 | CONTROL-04, CONTROL-06 | T-28-26, T-28-27, T-28-29 | one armed window, human-executed, bounded to one record, read-back verified both directions, literal shape matches the deploy overlay | **manual (human-executed, live, armed)** | n/a — see Manual-Only Verifications | n/a | ⬜ pending |
| 28-06-02 | 28-06 | 5 | CONTROL-04 | T-28-28 | nothing armed survives the canary into a committed file | unit + full suite | `.venv/bin/python -m pytest operator-claude-plugin/tests -q && .venv/bin/python -m pytest -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

**Requirement coverage:** CONTROL-01 (28-05), CONTROL-02 (28-01), CONTROL-03 (28-02, 28-04),
CONTROL-04 (28-03, 28-06), CONTROL-05 (28-01, 28-04, 28-05), CONTROL-06 (28-01, 28-02, 28-05,
28-06), CONTROL-07 (28-01, 28-03, 28-04, 28-05). All 7 covered.

---

## Wave 0 Requirements

Wave 0 shipped in **23-03** and needs nothing new: `operator-claude-plugin/tests/conftest.py`
already supplies `stub_transport` and the autouse `no_network` guard, and the plugin's
`requirements.txt` already pins its dependencies. Phase 28 adds no new package.

Each plan creates its own test file as part of the task that needs it; the `❌ W0` marks above mean
"created by that task", not "blocked on a missing harness".

**Critical constraint, stronger than Phase 23's:** no automated verification in this phase may arm
anything or perform a live mutating PUT. Every network-touching function takes an injected
transport, and the autouse guard makes an un-injectable call untestable. 28-01 Task 3 asserts the
guard covers `requests.put` and `requests.get` explicitly, because this is the first phase that can
write to a live workflow.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| A no-op GET→PUT round-trip preserves `settings` and `connections` on this n8n Cloud version (D-20) | CONTROL-06 | Performs a real PUT against a live workflow; agent tooling in this repo is blocked from arming writes and this is the first live PUT the phase makes | 28-02 Task 2. Run the probe's `roundtrip` against `LV Scheduled Maintenance (Cloud)`; expect a `verified` verdict and identical `settings`/`connections`. A schema rejection means 28-01's four-key filter is wrong and everything downstream stops |
| `POST /api/v1/workflows/{id}/execute` does not exist on this instance (research A2) | CONTROL-01 | Requires a live call against this specific Cloud account; the upstream PR's state is not evidence about this tenant | 28-02 Task 2. Expect 404 or 405. A 2xx overturns D-05a and is a scope decision for the user, not a fix |
| A deactivate→PUT→activate bracket makes a content change effective on an already-running instance (D-17/D-18, research A1) | CONTROL-03, CONTROL-06 | No mock can reproduce n8n's own runtime reload timing; this is the phase's single MEDIUM-LOW-confidence load-bearing assumption | 28-02 Task 3. Change one read-only Schedule Trigger's interval through the pipeline, watch the executions API for the observed spacing, restore, and verify the restore separately. If the bracket proves insufficient, 28-03 needs a different mechanism |
| One armed arm→dispatch→disarm cycle, executed for real | CONTROL-04, CONTROL-06 | Requires live n8n + HubSpot and performs a real write. Agent tooling in this repo is blocked from arming writes | 28-06 Task 1. Bounded to one record by the `TEST_RECORD_*` allowlist. Confirm the decline path sends nothing, both read-backs report verified, only the allowlisted record was written, the written literal matches the deploy overlay's shape, and the window closes with a disarming redeploy |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify, or are `checkpoint:*` tasks listed above
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (already shipped in 23-03)
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] No automated verification arms anything or performs a live mutating PUT
- [ ] Both 28-02 checkpoints and the 28-06 canary performed and recorded
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
