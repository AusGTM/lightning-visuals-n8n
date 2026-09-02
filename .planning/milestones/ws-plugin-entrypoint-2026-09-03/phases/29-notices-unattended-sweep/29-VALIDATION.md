---
phase: 29
slug: notices-unattended-sweep
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-31
---

# Phase 29 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Seeded by plan-phase from `29-RESEARCH.md` §"Validation Architecture". The planner fills the
> per-task map; `/gsd-validate-phase` sets `status: validated`.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (repo standard; plugin tests live under `operator-claude-plugin/tests/` and carry the plugin's own `requirements.txt`) |
| **Config file** | repo-root pytest config |
| **Quick run command** | `.venv/bin/python -m pytest operator-claude-plugin/tests -q` |
| **Full suite command** | `.venv/bin/python -m pytest -q && node --test tests/n8n/*.test.mjs` |
| **Estimated runtime** | ~30–60 seconds quick; full suite longer |

**Note:** the repo's established invocation is `.venv/bin/python -m pytest` (system python lacks
deps) and `node --test tests/n8n/<file>.test.mjs` in **file** form — the directory form is broken on
the installed node version. Do not substitute a bare `pytest`.

**Standing constraint inherited from Phase 23:** `operator-claude-plugin/tests/conftest.py` carries
an **autouse** network guard. Every test in this phase runs with `requests` stubbed, so no sweep or
watch test can reach n8n. This is what makes it safe to test a component whose entire safety property
is that it cannot write.

---

## Sampling Rate

- **After every task commit:** run the quick command
- **After every plan wave:** run the full suite
- **Before `/gsd-verify-work`:** full suite green, plus the three manual-only platform checks below
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 29-01-01 | 29-01 | 1 | NOTICE-03 | T-29-01 | probe routine reads only, and is deleted after observation | manual | n/a — platform capability (see Manual-Only Verifications) | n/a | ⬜ pending |
| 29-01-02 | 29-01 | 1 | NOTICE-01 | T-29-01 | bonus capability probed, never depended on | manual | n/a — platform capability | n/a | ⬜ pending |
| 29-01-03 | 29-01 | 1 | NOTICE-01, NOTICE-03 | T-29-02 | findings dated and version-stamped so a stale platform result is detectable | doc (existence + shape) | `test -f .planning/workstreams/plugin-entrypoint/phases/29-notices-unattended-sweep/29-HOST-PROBE.md && grep -qiE 'A1\|scheduled routine' .planning/workstreams/plugin-entrypoint/phases/29-notices-unattended-sweep/29-HOST-PROBE.md` | ❌ W0 | ⬜ pending |
| 29-02-01 | 29-02 | 1 | NOTICE-03 | — | fixtures reproduce the two deceptively-healthy shapes, so the blind spots are testable | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_sweep_fixtures.py -q` | ❌ W0 | ⬜ pending |
| 29-02-02 | 29-02 | 1 | NOTICE-02 | T-29-04, T-29-05 | duration computed with no new HTTP path; unknown never folded in as zero | unit | `.venv/bin/python -m pytest tests/test_enrichment_cost_ledger.py -q` | ✅ exists | ⬜ pending |
| 29-02-03 | 29-02 | 1 | NOTICE-02 | T-29-06 | bound is measured, or labelled provisional with a re-measure trigger | doc (existence + shape) | `test -f .planning/workstreams/plugin-entrypoint/phases/29-notices-unattended-sweep/29-TIMING.md && grep -qiE 'sample size\|provisional' .planning/workstreams/plugin-entrypoint/phases/29-notices-unattended-sweep/29-TIMING.md` | ❌ W0 | ⬜ pending |
| 29-03-01 | 29-03 | 2 | NOTICE-03, NOTICE-04 | T-29-08, T-29-09, T-29-10 | one condition end to end; healthy input yields silence; unrecognized cause attributes to admin | unit (end-to-end over fixtures) | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_sweep_tracer.py -q` | ❌ W0 | ⬜ pending |
| 29-03-02 | 29-03 | 2 | NOTICE-05 | T-29-07 | sweep import closure ⊆ allowlist; the ONLY reachable non-GET verb is the named bodyless `backend_status.fetch_backend_status` POST (D-13), kept honest by no-`files=`/no-`data=`/empty-`json=` AST assertions; guard proven to bite | unit (AST import-graph) | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_sweep_read_only.py -q` | ❌ W0 | ⬜ pending |
| 29-03-03 | 29-03 | 2 | NOTICE-03, NOTICE-04 | T-29-24 | a sweep that cannot run says so: `ConfigError` and an all-reads-unavailable gather each yield an admin-attributed notice, never silence (D-15) | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_sweep_tracer.py -q` | ❌ W0 | ⬜ pending |
| 29-04-01 | 29-04 | 2 | NOTICE-02 | T-29-11, T-29-12, T-29-14 | two terminal reports and no third; run-handle correlation basis stated | unit (fake clock) | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_watch_bound_fallback.py -q` | ❌ W0 | ⬜ pending |
| 29-04-02 | 29-04 | 2 | NOTICE-01 | T-29-13, T-29-14 | per-record outcomes via Phase 26's renderer; unknown cost never reported as zero; no ICP field | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_watch_settle_reporting.py -q` | ❌ W0 | ⬜ pending |
| 29-05-01 | 29-05 | 3 | NOTICE-03, NOTICE-04 | T-29-15 | unreadable balance never reported as exhausted; both conditions attribute to admin | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_sweep_conditions.py -q` | ❌ W0 | ⬜ pending |
| 29-05-02 | 29-05 | 3 | NOTICE-03 | T-29-16 | a successful maintenance run carrying a swallowed read failure is not read as healthy — detected via `get_execution` + `harvest_errors`, since the collection read has no `runData` (D-17); stuck-armed fires on EITHER write-safety flag and on a truthy `disagreement` (D-16) | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_sweep_conditions.py -q` | ❌ W0 | ⬜ pending |
| 29-05-03 | 29-05 | 3 | NOTICE-04 | T-29-17, T-29-18 | structural silence when healthy; grouped delivery; admin default on unrecognized cause | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_sweep_attribution.py -q` | ❌ W0 | ⬜ pending |
| 29-06-01 | 29-06 | 4 | NOTICE-05 | T-29-20 | shipped skill's named capabilities ⊆ the same read-only allowlist | unit (static, over the skill body) | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_sweep_read_only.py -q` | ❌ W0 | ⬜ pending |
| 29-06-02 | 29-06 | 4 | NOTICE-03 | T-29-23 | two-part install documented; admin instructions labelled as admin | doc | `grep -qi 'sweep' operator-claude-plugin/README.md && grep -qi 'watch_bound_seconds' operator-claude-plugin/README.md && grep -qi 'sweep' operator-claude-plugin/CHANGELOG.md` | ❌ W0 | ⬜ pending |
| 29-06-03 | 29-06 | 4 | NOTICE-03, NOTICE-04, NOTICE-05 | T-29-21, T-29-22 | live notice arrives with no session open; healthy fire is silent; no write and no credit consumed | manual (human-executed) | n/a — platform mechanism (see Manual-Only Verifications) | n/a | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Wave 0 is **plan 29-02** (wave 1, autonomous), which creates everything the later plans' `<automated>`
commands run against:

- [ ] `operator-claude-plugin/tests/conftest.py` — sweep fixtures: `executions_healthy`,
      `executions_with_failure`, `executions_with_stuck` (both sides of the threshold),
      `execution_missing_stopped_at`, `execution_maintenance_falsely_successful`,
      `backend_status_healthy`, `backend_status_unknown_balance`,
      `backend_status_unconfigured_provider`, `backend_status_exhausted`,
      `backend_status_review_backlog`
- [ ] `operator-claude-plugin/tests/test_sweep_fixtures.py` — asserts the fixture distinctions hold,
      in particular that the three provider states stay three
- [ ] `scripts/enrichment_cost_ledger.py` — duration and record-count helpers plus a `durations`
      subcommand, so the watch bound can be measured rather than guessed
- [ ] `29-TIMING.md` — the measured (or explicitly provisional) bound

The remaining test files are created by the plan that first needs them, each in the same task as the
code it verifies: `test_sweep_tracer.py` and `test_sweep_read_only.py` (29-03),
`test_watch_bound_fallback.py` and `test_watch_settle_reporting.py` (29-04),
`test_sweep_conditions.py` and `test_sweep_attribution.py` (29-05).

**Critical Wave 0 constraint:** the fixtures must include the two payloads that look healthy and are
not — a successful maintenance execution whose read node silently failed (29-RESEARCH.md Pitfall 1 /
D-08b), and a configured provider whose balance is unknown rather than zero (Pitfall 5). Omit either
and the sweep's blind spots become untestable, which means untested, which means shipped.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| A scheduled routine can invoke this plugin's own skill and get real data back | NOTICE-03 (D-04, A1) | No pytest harness can drive Claude Desktop's Scheduled-tasks platform; same treatment as Phase 27's Artifact-publish check | 29-01 Task 1 — author a throwaway routine at `~/Documents/Claude/Scheduled/lv-sweep-probe/SKILL.md` invoking the plugin's read-only status skill, let it fire once, record whether it reached the skill and whether real data came back, then delete it. A NO here blocks the phase on D-01b's fallback rather than being worked around |
| Where a scheduled routine's output surfaces, and its text ceiling | NOTICE-03 (A5) | Rendering surface is a platform property, not a repo one | Observed during 29-01 Task 1's single fire; recorded in `29-HOST-PROBE.md` Section 2 and consumed by 29-05 Task 3's grouping |
| Claude Desktop chat reports back unprompted mid-conversation | NOTICE-01 (A2) | Directly observed only in the CLI runtime; Desktop is the actual target and could not be fired in research | 29-01 Task 2 — start something spanning more than one turn and observe whether its completion arrives on its own. **INCONCLUSIVE is treated as NO.** A negative changes nothing: 29-04 builds D-07's bounded path regardless |
| A notice reaches the operator from a sweep running with no session open, and a healthy sweep is silent | NOTICE-03, NOTICE-04, NOTICE-05 | No fixture can demonstrate a notification arriving with nobody watching | 29-06 Task 3 — install the routine, confirm silence on a healthy fire, then lower the review-backlog threshold below the real count so one condition fires on real data (never by breaking a credential or arming the backend), confirm the notice and its attribution, restore the threshold, then verify from n8n execution history and provider balances that no write and no credit consumption occurred |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or a justified manual-only entry
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
