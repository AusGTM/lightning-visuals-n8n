---
phase: 48
slug: enrichment-coverage
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-08-12
---

# Phase 48 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from `48-RESEARCH.md` § "Validation Architecture" (lines 858–937).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework (Python)** | pytest, via `.venv/bin/python -m pytest` (system python lacks deps — the venv path is mandatory) |
| **Framework (n8n/JS)** | node built-in `node:test`, via `node --test tests/n8n/*.test.mjs` — **GLOB form only**; the directory form `tests/n8n/` is broken on node 24 |
| **Config file** | none dedicated — both suites already wired; no new framework install this phase |
| **Quick run command** | `.venv/bin/python -m pytest tests/test_<phase48_driver>.py -x` · `node --test tests/n8n/researchErrorGateFlow.test.mjs` |
| **Full suite command** | `.venv/bin/python -m pytest` **and** `node --test tests/n8n/*.test.mjs` |
| **Estimated runtime** | ~60–120 seconds for both offline suites |

---

## Sampling Rate

- **After every task commit:** the single relevant test file (`-k <marker>`, or the one new `.test.mjs`). This phase's changes are narrow and additive; the full suite per task is waste.
- **After every plan wave:** both full offline suites (`.venv/bin/python -m pytest`, `node --test tests/n8n/*.test.mjs`).
- **Before `/gsd-verify-work`:** full suite green **plus** the live-only checks below, which no automated test can cover.
- **Max feedback latency:** ~15 seconds (single-file quick run).

**Known-red, do NOT "fix":** `run_scoring_parity.py`'s population sweep is RED BY DESIGN until Phase 49.

---

## Per-Task Verification Map

Task IDs are placeholders until PLAN.md files exist; the planner binds them. Requirement/behavior rows are fixed.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 48-01-xx | 01 | 1 | COVER-01 | — | Each of the 4 already-researched records maps to the exact CONTEXT.md enum value (Jam TV→`broadcaster`, Waikato→`individual_club_team`, The Rumble→`content_producer`, Editix→`unknown`) | unit | `.venv/bin/python -m pytest tests/test_<phase48_driver>.py -k mapping -x` | ❌ W0 | ⬜ pending |
| 48-01-xx | 01 | 1 | COVER-01 | — | A record written `unknown` also carries a non-empty `lv_enrichment_review_reason`; state is provably distinct from blank `lv_org_type` | unit | `... -k marker -x` | ❌ W0 | ⬜ pending |
| 48-01-xx | 01 | 1 | COVER-01 | T-48-01 (out-of-vocabulary enum write) | Racing NSW research output is constrained to the 9 live `VALID_ORG_TYPES`; an out-of-vocab value is rejected before it reaches a PATCH | unit, offline, synthetic response | `... -k racing_nsw -x` | ❌ W0 | ⬜ pending |
| 48-02-xx | 02 | 1 | COVER-02 | T-48-02 (silent mid-run truncation) | `estimate_cost()`-derived estimate is correct for the Phase 48 id set, and `refuse_if_over_budget()` **raises** on a synthetic over-budget estimate rather than truncating | unit, offline | `... -k budget -x` | ❌ W0 | ⬜ pending |
| 48-03-xx | 03 | 1 | COVER-01 (D-04) | T-48-03 (error payload consumed as data) | `IF Research Errored` routes a genuine `{error:...}` item to the failure branch and a healthy `{content:[...]}` item down the normal lane, driven through the node's REAL emitted expression | node:test, offline, against committed `n8n/wf_enrichment_cloud.json` | `node --test tests/n8n/researchErrorGateFlow.test.mjs` | ❌ W0 | ⬜ pending |
| 48-03-xx | 03 | 1 | COVER-01 (D-09 no-regression) | — | The recompute lane still routes correctly after D-04's node insertion — no node rename/renumber collision | node:test, offline | `node --test tests/n8n/companyRecomputeLaneFlow.test.mjs` | ✅ exists | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_<phase48_driver>.py` — new Phase 48 driver unit tests (mapping correctness, `unknown`+reason marker semantics, budget refusal). Follow `tests/test_veto_remediation_report.py`'s pattern of asserting a classifier function's output against named fixture ids.
- [ ] `tests/n8n/researchErrorGateFlow.test.mjs` — D-04 gate structural test. Model directly on `tests/n8n/companyRecomputeLaneFlow.test.mjs`: load `n8n/wf_enrichment_cloud.json`, fake the `$()` node lookups, evaluate the IF node's real `leftValue` expression via `new Function`. Do **not** assert against a hand-written copy of the expression.
- [ ] No framework install needed — pytest and `node:test` are both already wired.

---

## Manual-Only Verifications

Every row below is provable **only** by live evidence (a run-report artifact, an independent read-back), not by a test. Rows marked **OPERATOR-ONLY** require an action Claude must not perform this phase — both Phase 47.5 waivers EXPIRED with that phase.

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Population re-derived live and date-stamped | COVER-01 | A committed snapshot is evidence, not a guarantee; the count moved 18→5 across Phase 47 | Live `search_records` (`lv_icp_fit_score HAS_PROPERTY AND lv_org_type NOT_HAS_PROPERTY`); capture the count **and** the id list into the run report. Claude MAY perform this read. Use the dotenv-absolute-path form — `.env` is Read/Bash permission-blocked |
| D-04 deploy + bounce | COVER-01 (D-04) | **OPERATOR-ONLY.** Needs `DRY_RUN=false` AND `ALLOW_N8N_DEPLOY=true` in one invocation, plus deactivate→reactivate | Claude prepares the exact invocation string and hands off, then waits for operator confirmation. Never arm this flag under any framing |
| Both arming ceremonies | COVER-02 | **OPERATOR-ONLY.** Two independent surfaces: the driver's own env-flag gate (direct PATCH leg) **and** `scripts/june_run_arm.py`'s n8n-side allowlist (`HubSpot Company Update` leg). Both must be armed or the writes silently do not land | Claude prepares dry-run payloads + the operator invocation string. Assert the allowlist is **non-empty and exactly the intended id set** at arm time — an EMPTY allowlist denies every write and still reports `armed` (Trap #4) |
| Independent disarm read-back, both surfaces | COVER-02 | Stored ≠ running. A bare PUT does not reload a running workflow (Trap #3) | Independent GET or a live execution's own node list — never a re-read of the stored PUT body |
| D-09 before/after tier numbers | COVER-01 | Live-observed values from the real scoring pipeline at execution time | Record in the run report. Phase 48 **records**; Phase 49 / RESCORE-03 narrates |
| `IF Research Errored` fires on a real erroring Anthropic call | COVER-01 (D-04) | The offline node test proves routing logic against a synthetic item; it cannot prove the *deployed* workflow behaves identically | Requires the operator-only deploy+bounce to exist first. Judge by node-level `runData`, never by `executionStatus` — n8n `status: "success"` lies (Trap #1) |
| **Jam TV `17317850381` stays vetoed** after the `broadcaster` write | COVER-01 | Its veto is **geographic** (`lv_anti_icp_reason = "Non-ANZ geography"`, region `Other`); the write is org-type. +20 base cannot clear it | Read-back must explicitly confirm the veto is **still present** after the D-09 recompute settles — not merely that the org-type write landed |
| **Waikato `20538284384`'s `lv_is_gambling_operator: true` changes nothing** | COVER-01 | Gambling is a graduated deduction and `graduated_deductions` is `{}` since Phase 46 D-03 | Note explicitly in the run report so a future reader does not misread the boolean as a veto trigger |
| Actual cost reported against the pre-run estimate | COVER-02 | Actuals only exist after the run | Run report compares actual n8n executions + provider credits + Anthropic spend to the ex-ante `estimate_cost()` figure |
| Window-count declaration honoured (D-06) | COVER-02 | 1 deploy+bounce, 1 armed write window, record cap 5 | Exceeding the declaration is a **disclosure obligation** in the run report, not a silent event |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (2 new test files)
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] Live-only rows above are each assigned to a run-report artifact, not silently dropped
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
