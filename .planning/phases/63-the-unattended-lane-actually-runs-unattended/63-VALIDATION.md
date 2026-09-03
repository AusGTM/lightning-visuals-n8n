---
phase: "63"
slug: "the-unattended-lane-actually-runs-unattended"
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
status: validated
nyquist_compliant: false
wave_0_complete: true
created: "2026-09-03"
---

# Phase 63 — Validation Strategy

> Reconstructed from artifacts (State B) on 2026-09-03, **after** the phase closed. Phase 63 ran
> without a VALIDATION.md — `workflow.nyquist_validation` is absent from `.planning/config.json`
> and therefore defaults to **enabled**, so the `verify:post` nyquist hook was active and was
> skipped. Phase 61 shipped the same way. This file closes that gap for 63; whether to set the
> key explicitly (either way) is a standing project decision, not one this file makes.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (Python) + `node --test` (n8n code nodes) |
| **Config file** | none — tests are discovered by convention |
| **Quick run command** | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_sweep_shim.py tests/test_replay_judge_models.py tests/test_judge_spec.py -q` |
| **Full suite command** | `.venv/bin/python -m pytest -q` and `node --test tests/n8n/*.test.mjs` |
| **Estimated runtime** | quick ~2s · full python ~4 min · node ~30s |

**Two invocation traps, both load-bearing:** use `.venv/bin/python`, never bare `python3` — the
system interpreter lacks this project's dependencies. And use the **glob** form
`node --test tests/n8n/*.test.mjs`; the directory form is broken on node 24.

---

## Sampling Rate

- **After every task commit:** the quick run command above
- **After every plan wave:** full suite
- **Before `/gsd-verify-work`:** full suite must be green
- **Max feedback latency:** ~2s for the quick set

At phase close the suites read **3964 passed / 154 skipped** (pytest) and **862 pass / 0 fail**
(node). The one test added by this validation pass brings `test_judge_spec.py` to 10.

---

## Per-Task Verification Map

Phase 63's requirements are two todo files rather than `REQ-` identifiers — the phase was
numbered specifically to close them, and `init.execute-phase` reports its `phase_req_ids` as
*"closes the two todos carrying `resolves_phase: 63`"*.

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 63-01 | 01 | 1 | sweep-crontab-pins-a-versioned-plugin-path — durable shim resolves newest install and execs its wrapper (D-63-01); version ordering reused from `durable_paths.py`, not reimplemented (D-63-04) | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_sweep_shim.py -q` | ✅ | ✅ green (12 tests) |
| 63-01 | 01 | 1 | same — wrapper staleness self-check is loud, never refusing (D-63-02) | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_sweep_shim.py -q` | ✅ | ✅ green |
| 63-01 | 01 | 1 | same — `SWEEP-CRON-TEMPLATE.md` names the shim and documents the one-time re-point | grep | `grep -n "lv-sweep-launcher.sh" operator-claude-plugin/skills/backend-sweep/SWEEP-CRON-TEMPLATE.md` | ✅ | ✅ green |
| 63-02 | 02 | 2 | same — a GENUINE scheduled fire resolves through the shim, and follows a simulated update with no schedule or shim edit | manual harness | `scripts/verify_sweep_shim_scheduler.sh` | ✅ | ✅ green (3 live runs, see Manual-Only) |
| 63-01/02 | 01, 02 | — | same — **backstop**: an interrupted fire leaves no partial state; two overlapping fires resolve independently and stamp complete, uninterleaved lines | manual harness | `scripts/verify_sweep_shim_concurrency.sh` | ✅ | ✅ green (see Manual-Only) |
| 63-03 | 03 | 1 | enrichment-throughput-ceiling — offline two-model replay over stored judge inputs, with the `confidence_band`-only class isolated (D-63-06) | unit | `.venv/bin/python -m pytest tests/test_replay_judge_models.py -q` | ✅ | ✅ green |
| 63-04 | 04 | 2 | same — the DROP branch was genuinely taken: nothing shipped, and **nothing may quietly ship later** | unit (added by this pass) | `.venv/bin/python -m pytest tests/test_judge_spec.py::test_jg_drop_63_04_judge_model_is_unconditional_single_constant -q` | ✅ | ✅ green |
| 63-04 | 04 | 2 | same — builder flag surface unchanged | unit | `.venv/bin/python -m pytest tests/test_judge_spec.py tests/test_builder_flag_parity.py -q` | ✅ | ✅ green |
| 63-05 | 05 | 3 | same — deploy carried no arming overlay | unit + inline | `.venv/bin/python -m pytest tests/test_deploy_flag_overlay.py tests/test_deploy_write_safety_overlay.py -q` | ✅ | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

**`tests/test_judge_model_routing.py` is named in 63-04's PLAN frontmatter and `<verify>` block
and does not exist. That is correct, not a gap:** it belongs to 63-04's SHIP branch, and 63-04
took DROP. The gap that *was* real — nothing guarding the drop — is the row above it.

---

## Wave 0 Requirements

Existing infrastructure covered all phase requirements. No framework install or fixture work was
needed; both halves of the phase extended suites that already existed.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| A genuine scheduled fire resolves through the shim to the newest install, and follows a plugin update with no schedule or shim edit | sweep-crontab-pins-a-versioned-plugin-path (63-02) | Needs a **real** scheduler. Memory `sweep-trigger-llm-free` records this project's earlier trigger passing its own interactive probe and still failing silently under a real cron tick — an interactive invocation inherits an environment the scheduler never has, so an in-suite test would prove the wrong thing. Also needs ~3 min of wall time waiting on two 60s `StartInterval` ticks. | `./scripts/verify_sweep_shim_scheduler.sh; echo "rc=$?"` — registers a uniquely-labelled temporary launchd agent against an isolated `mktemp -d` world, tears it down on every exit path, confirms absence with an independent `launchctl list`. Record: `63-SWEEP-SHIM-SCHEDULER-PROOF.md` |
| An interrupted fire leaves no lockfile/pidfile/partial line; two genuinely overlapping fires each resolve `--newest` independently and each stamp a complete, uninterleaved line | sweep-crontab-pins-a-versioned-plugin-path (63-01 + 63-02, both tagged `verification: backstop`) | Same real-scheduler requirement, plus overlap is only reachable with **two** launchd labels — launchd never runs two instances of a single label concurrently, so no same-label schedule can overlap itself at any payload length. ~10 min wall time (60s interval, 90s payload). | `./scripts/verify_sweep_shim_concurrency.sh; echo "rc=$?"` — run it in the background; a foreground `sleep` that long is blocked in this environment. Record: `63-SWEEP-SHIM-CONCURRENCY-PROOF.md`. Evidence is read by line CONTENT only (per-fire embedded pid/start/end), never count or position. |

Both harnesses are self-contained, re-runnable, and cost nothing: zero network calls, zero
provider credits, zero n8n executions, zero HubSpot writes, zero crontab invocations (D-63-03).
They are not missing automation — they **are** the automation, simply not suite-runnable.

---

## Why `nyquist_compliant` is false

Two of the phase's behaviours are verified by manual harnesses rather than by the suites, for the
reasons in the table above. That is a deliberate, recorded classification, not an outstanding gap:
the behaviours ARE verified, and the harnesses are committed and re-runnable. Setting
`nyquist_compliant: true` would claim every requirement has *suite* verification, which is not
true and should not be made true — an in-suite fake of a launchd tick would prove the wrong thing,
which is precisely the failure mode `sweep-trigger-llm-free` records.

---

## Validation Audit 2026-09-03

| Metric | Count |
|--------|-------|
| Gaps found | 3 |
| Resolved | 1 |
| Reclassified manual-only | 2 |
| Escalated | 0 |

**The one resolved gap (G1).** Phase 63 Plan 04 evaluated routing `confidence_band`-only judge
inputs to a cheaper model and took its DROP branch on two independent reasons
(`insufficient_corpus`: 3 such inputs against a fixed minimum of 10; `material_disagreement`:
input `11975:0` disagreed on `decision`). Nothing shipped — but nothing guarded the drop either,
so per-reason model routing could have been introduced later with no test failing.

`tests/test_judge_spec.py::test_jg_drop_63_04_judge_model_is_unconditional_single_constant` now
asserts, for both the company and contact judge-request nodes, that model selection is a single
unconditional reference to `ANTHROPIC_JUDGE_MODEL` — one `const model` assignment, RHS a bare
identifier, no second judge-model flag in the builder source. It asserts the **property** (one
model, no branch) rather than a model id string, so a legitimate future model upgrade does not
trip it while a per-reason split does.

Independently confirmed to be a real guard, not a tautology: injecting a
`confidence_band`-conditional ternary to `claude-haiku-4-5` into a temporary perturbation of
`n8n/wf_enrichment_local_live.json` made the test fail with the intended message; the file was
restored (`git status` clean on it) and the suite returned 10/10. No implementation file was
modified — `scripts/build_cloud_workflows.py` and every `n8n/*.json` staying untouched is
load-bearing evidence in `63-JUDGE-LEVER-DROP-RECORD.md` and had to remain so.

---

## Validation Sign-Off

- [x] All tasks have an `<automated>` verify or a recorded manual-only justification
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (none needed — existing infrastructure sufficed)
- [x] No watch-mode flags
- [x] Feedback latency < 5s for the quick set
- [ ] `nyquist_compliant: true` — deliberately NOT set; see "Why `nyquist_compliant` is false"

**Approval:** approved 2026-09-03 (partial — 2 manual-only by nature)
