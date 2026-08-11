---
phase: 44-sj-3-dispatch-gate-drain-cap
plan: 03
subsystem: crm-automation
tags: [n8n, hubspot, sj3, deploy, bounce, live-evidence, drain, dispatch-gate]
status: complete

requires:
  - phase: 44-sj-3-dispatch-gate-drain-cap
    plan: 01
    provides: the SJ-3 gate/drain cluster and ALLOW_SJ3_DRAIN_WRITES this plan deployed
  - phase: 44-sj-3-dispatch-gate-drain-cap
    plan: 02
    provides: the budget-derived cap and SJ-3 Tick Outcome node this plan deployed
provides:
  - the gate/drain/cap RUNNING live (deploy of all 5 wf_*_cloud.json + bounce of the
    4 active workflows, each step read-back verified)
  - 44-LIVE-EVIDENCE.md — execution 11820's raw evidence: 1 execution, 0 enrichment
    sub-executions (GATE-01/research A1 discharged), verbatim gate_closed outcome
    (GATE-02), HubSpot read-back of the drained disposable with full 272-property
    diff attribution (DRAIN-01)
  - live verify_live_write_safety.py now reads disarmed PASS + drain authority PASS
    (13 declaring nodes) — the 44-01 interim FAIL window is closed
  - REQUIREMENTS.md traceability rows for all nine Phase 44 requirements carrying
    evidence/test pointers
affects: [45 (burn-rate alarm builds on a backend whose queue now drains at rest)]

tech-stack:
  added: []
  patterns:
    - "live-proof plan: operator runs the deploy (permission classifier boundary),
      agent does bounce + read-backs + seeding + measurement, drain judged from a
      HubSpot read-back diffed against a full-property baseline, never from a 200"

key-files:
  created:
    - .planning/phases/44-sj-3-dispatch-gate-drain-cap/44-LIVE-EVIDENCE.md
  modified:
    - .planning/REQUIREMENTS.md

decisions:
  - "Opening checkpoint (pre-deploy safety) resolved 'approved' by operator in the
    orchestrating session 2026-08-10 before this executor started: no arm window,
    drain-at-rest accepted, fresh disposable mandated (280155690475 deleted/404),
    tree clean + suites green"
  - "Bounce restricted to the 4 ACTIVE workflows; LV Review Decision (Cloud) received
    the PUT but was not activated (inactive operator state, no running instance to
    reload) — matches n8n_control doctrine and the 2026-08-07 deploy precedent"
  - "Tick observed via a manual execution fired by the operator from the SJ-3 Trigger
    node (the plan's stated preference; the API run-now 405 and the ~21h-out natural
    tick made it the only same-session mechanism). mode='manual' recorded honestly in
    the evidence with the schedule's own firing already proven by prior tick history"

metrics:
  duration: ~50 min (including two operator round-trips)
  completed: 2026-08-10

estimate:
  tokens: 70000
  tasks: 3
actuals:
  tokens: 7500   # chars/4 over the realized diff (~30,000 chars: evidence file 14.5k, SUMMARY ~9k, REQUIREMENTS/STATE/ROADMAP deltas)
  tasks: 3
  commits: 2
---

# Phase 44 Plan 03: Deploy + Bounce + Live Proof Summary

The SJ-3 gate, drain and cap are now live and empirically proven: a gate-closed manual
tick (execution 11820) cost exactly one execution with zero enrichment sub-executions,
emitted the named `gate_closed` outcome with consistent counts and `cap: 40`, and
drained a seeded disposable to `lv_enrichment_requested="false"` /
`lv_enrichment_status="skipped"` — confirmed by a full-property HubSpot read-back, with
the live write-safety verifier reading disarmed PASS + drain PASS.

## Tasks

| Task | Name | Commit | Result |
| ---- | ---- | ------ | ------ |
| — | Checkpoint: pre-deploy safety confirmation | (no commit) | Resolved **approved** by operator in orchestrating session, 2026-08-10 |
| 1 | Deploy the changed workflows and bounce them | (no commit — live n8n state only) | Deploy run by operator (five 200s, disarmed); agent bounced 4 active workflows (8/8 `verified`); verifier: disarmed PASS + drain PASS |
| 2 | Observe one live gate-closed tick | (no commit — live observation) | Execution 11820 (`manual`): 0 sub-executions, dispatch node never ran, verbatim `gate_closed` item, drain read-back confirmed, disposable deleted, 0 leaked |
| 3 | Record evidence + close traceability | `c3c2955` | 44-LIVE-EVIDENCE.md complete; REQUIREMENTS.md rows carry evidence/test pointers; suites green |

## Live evidence (headline numbers — full detail in 44-LIVE-EVIDENCE.md)

- **Deploy:** all 5 `wf_*_cloud.json` updated (200 each), zero creates, no
  `ENABLE_BAKED_FLAGS`.
- **Bounce:** deactivate → activate on `1fXPuIabz3RsAHgn`, `950HPb7a1GgSAIyZ`,
  `AwbBeShdPgV48eiY`, `Cj83mOgrIm59oxcX` — all 8 operations `verified` via
  `n8n_control.set_active`'s independent read-backs.
- **Write-safety:** `verify_live_write_safety.py` → `VERDICT: disarmed PASS`,
  `drain authority: ALLOW_SJ3_DRAIN_WRITES expected "true", declared by 13 node(s) — PASS`.
- **GATE-01:** execution **11820** (2026-08-10T02:39:30–33Z, mode `manual`, fired by
  the operator from `SJ-3 Trigger`); enrichment watermark **11817 unmoved** → zero
  sub-executions; `SJ-3 Dispatch To Enrichment` absent from runData;
  `SJ-3 Build Dispatch Event` emitted `[[]]`. Research assumption A1 is now an
  observation.
- **GATE-02:** `SJ-3 Tick Outcome` verbatim:
  `{"sj3_tick_outcome":"gate_closed","found":1,"permitted":0,"dispatched":0,"declined":1,"deferred":0,"cap":40}`.
- **DRAIN-01:** seeded disposable `280176525780`
  (`ZZ-SCORING-TEST-DELETE-ME-23b8a66814c1`, the only record matching SJ-3's predicate
  — pre-seed queue total was 0) read back `lv_enrichment_requested="false"`,
  `lv_enrichment_status="skipped"`. Full 272-property diff: the two drain keys +
  `hs_lastmodifieddate`, plus four creation-time portal-flow fields
  (`AUTOMATION_PLATFORM`/`CALCULATED`, timestamped 20 min pre-tick, history-verified) —
  nothing else changed.
- **Cleanup:** DELETE → 204; portal-wide `ZZ-SCORING-TEST-DELETE-ME` sweep → **0
  survivors**.

## Deviations from Plan

**1. [Permission boundary] Deploy executed by the operator, not the agent**
- **Found during:** Task 1
- **Issue:** the permission classifier denies agent-side live deploys in all invocation
  forms (standing rule, 2026-08-05, re-confirmed this session).
- **Fix:** returned a `checkpoint:human-action`; the operator ran the exact mandated
  command in the orchestrating session and supplied the verbatim output, recorded in
  the evidence file. No workaround variants attempted.

**2. [Scope narrowing] Bounce covered the 4 active workflows only**
- **Found during:** Task 1
- **Issue:** the plan says "bounce each deployed workflow"; `LV Review Decision (Cloud)`
  was inactive before the deploy.
- **Fix:** left inactive — no running instance to reload, and activating it would be an
  unrequested mutation (n8n_control doctrine; 2026-08-07 precedent). Recorded in the
  evidence file.

**3. [Mechanism] Tick fired manually by the operator from `SJ-3 Trigger`**
- **Found during:** Task 2
- **Issue:** no API run-now for schedule triggers (documented 405); next natural daily
  tick ~21h out (23:00–23:15Z cluster).
- **Fix:** the plan's own preferred mechanism — a second `checkpoint:human-action` for
  the UI-fired manual execution from that trigger node only. `mode: manual` recorded
  honestly; the schedule's own firing is separately proven by prior tick history.

No code deviations — no repo source files were touched by this plan.

## Known Stubs

None.

## Threat register outcomes

| Threat | Disposition |
|--------|-------------|
| T-44-11 (DoS, deploy mid-arm-window) | Mitigated — precondition verified live: no `scheduled_arm.py` process, all five overlay constants disarmed, empty allowlists, before the operator deployed |
| T-44-12 (Tampering, un-bounced content) | Mitigated — 8/8 bounce operations independently read-back verified; every observation from an actual post-bounce execution |
| T-44-13 (Spoofing, HubSpot node false success) | Mitigated — DRAIN-01 judged from the HubSpot read-back diffed against a 272-property baseline, with property-history attribution of every changed field |
| T-44-14 (EoP, deploying armed) | Mitigated — no `ENABLE_BAKED_FLAGS` in the operator's command (verbatim output on file); post-bounce verifier reads disarmed PASS |
| T-44-15 (Repudiation, evidence pruned) | Mitigated — outcome item, runData and read-backs captured during the observation and committed in 44-LIVE-EVIDENCE.md (`c3c2955`) |

## Verification

- `verify_live_write_safety.py` (live): disarmed PASS, drain authority PASS (13 nodes).
- Execution 11820: 1 execution, 0 enrichment sub-executions, `gate_closed` outcome.
- HubSpot read-back: both drained values, full-diff attribution, nothing else changed.
- `.venv/bin/python -m pytest -q` — **2438 passed**, 121 skipped.
- `node --test tests/n8n/*.test.mjs` — **656 pass**, 0 fail.
- Leaked disposables: **0**.

## Commits

- `c3c2955` docs(44-03): live evidence — gate-closed tick costs 1 execution, drain lands, cap echoed

## Self-Check: PASSED

44-LIVE-EVIDENCE.md and 44-03-SUMMARY.md present; commit `c3c2955` in git log; both
suites green at the required counts.
