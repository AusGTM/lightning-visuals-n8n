---
phase: "60"
slug: "review-lane-authority"
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: "2026-09-01"
---

# Phase 60 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Seeded from `60-RESEARCH.md` § Validation Architecture. Task IDs fill in once plans exist.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (Python plugin + root) and Node's built-in `node:test` (n8n JS logic) |
| **Config file** | none dedicated — `operator-claude-plugin/tests/conftest.py` (plugin fixtures + autouse credential guard) and `tests/conftest.py` (root) |
| **Quick run command** | `.venv/bin/python -m pytest operator-claude-plugin/tests -q` |
| **Full suite command** | `.venv/bin/python -m pytest -q && .venv/bin/python -m pytest operator-claude-plugin/tests -q && node --test tests/n8n/*.test.mjs` |
| **Estimated runtime** | ~90–150 seconds for the full three-suite sweep |

**Repo gotcha (do not re-derive):** the n8n tests MUST use the glob form
`node --test tests/n8n/*.test.mjs`. The directory form is broken on node 24.

---

## Sampling Rate

- **After every task commit:** Run `.venv/bin/python -m pytest operator-claude-plugin/tests -q`
- **After every plan wave:** Run the full suite command above (all three suites)
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** ~150 seconds

---

## Per-Task Verification Map

Task IDs filled in 2026-09-01 when the four plans were written. Every row derives from a locked
decision in `60-CONTEXT.md` — no REQ-IDs are mapped to this phase
(`milestones/v1.1-REQUIREMENTS.md` carries no review-lane id), so the D-60-NN ids are the
coverage contract and each plan's `must_haves.truths` cites the ones it carries.

**Spec-less probe fallback: SKIP, recorded.** No `SPEC.md` and no requirement ids for this
phase, so no probe predicates were generated this run.

| Behavior (from decision) | Decision | Plan · Task | Test Type | Automated Command | File Exists |
|---|---|---|---|---|---|
| `"review"` is a valid, grantable lane | D-60-01, D-60-02 | 60-01 · T1 | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_write_grant.py -k lane -x` | ❌ needs rewrite — `test_the_review_lane_is_not_grantable` currently asserts the opposite |
| A review decision cannot exceed the grant's record scope | D-60-03 | 60-01 · T1 (behavior 5), 60-01 · T2 | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_write_grant.py -k covers -x` | ✅ generic scope check exists; add a review-specific case |
| `submit_decision` no longer reads a shell kill switch; grant-authorization gates it | D-60-04 | 60-01 · T1 (source), 60-01 · T2 (suite) | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_review_decision.py -x` | ✅ exists; ~15 tests pin the env gate and need rewriting |
| A `reject` still works with no grant open (the `is_undoing` carve-out survives, re-pointed) | D-60-07 | 60-01 · T1 (behavior 4), 60-01 · T2 | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_review_decision.py -k undoing -x` | ✅ exists; must be re-pointed at the grant check, not deleted |
| Arming review sets `ALLOW_HUBSPOT_REVIEW_WRITES` only — never `ALLOW_HUBSPOT_RECORD_WRITES` / `ALLOW_HUBSPOT_CREATE` | D-60-05 | 60-01 · T1 (behavior 2) | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_control_flag_parity.py -x` | ✅ parity test unaffected; add a Python test proving the review arm's flag set |
| The JSON-side flag separation invariant stays intact | D-60-05 | 60-01 · T1 and T3 (assert no diff) | n8n JS | `node --test tests/n8n/reviewWriteFlagSeparation.test.mjs` | ✅ exists — must stay green **unmodified** (it pins what this phase must not violate) |
| Guardrail A detects a dirty `ALLOW_HUBSPOT_REVIEW_WRITES` before opening a grant | D-60-01 consequence (research finding) | 60-02 · T1 | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_write_grant_guardrails.py -x` | ❌ new case needed; `_gate()` fixture needs its 4-constant list widened in the same commit |
| One arm window covers a whole batch of review decisions (normal, out-of-scope, crashed, revoked exits) | D-60-06 | 60-02 · T2 | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_write_grant_guardrails.py -x` | ❌ new coverage needed |
| Review writes land in the per-run `written_records-<run_id>.json` artifact | D-60-08 | 60-03 · T1 (mapping), 60-03 · T2 (wiring) | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_written_records.py -x` | ❌ new coverage needed — review writes go through `submit_decision`, not `dispatch_plan` |
| A written-records failure never stops a review write (both raise shapes) | D-60-08 (carried from D-59-10) | 60-03 · T2 (behaviors 4 and 5) | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_review_decision.py -k written -x` | ❌ new coverage needed |
| `reviewDecision.js`'s stale `not_allowlisted` message is corrected via the builder | research Pitfall 5 | 60-04 · T1 | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_review_outcome_parity.py -x` | ✅ exists (pins outcome literals, not message text) |
| The operator surfaces and the shipped version describe the authority that now exists | D-60-01/02/04/05/06/08 | 60-04 · T2 and T3 | unit + source | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_skill_sequence_coverage.py operator-claude-plugin/tests/test_enrich_skill_contract.py operator-claude-plugin/tests/test_enrich_before_ingest_skill_contract.py -x` | ✅ exist; skill edits must keep both pinned symbols and the compilable Python block |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase behaviors — every command above runs against a test
file that already exists. No framework install, no new conftest, no new fixtures directory.
What is missing is **cases inside existing files**, not infrastructure, so there is no Wave 0
scaffolding task.

---

## Manual-Only Verifications

| Behavior | Why Manual | Test Instructions |
|----------|------------|-------------------|
| An end-to-end review approve under a real grant actually writes to HubSpot | Requires a live, armed n8n workflow, a real flagged record, and real HubSpot writes — outside an automated suite's authority, and this phase's own arming gates are what would be under test | Open a grant scoped to one flagged record, approve it, then confirm via an independent re-read (`verify_decision`'s post-PATCH refetch) that the approved fields hold, and confirm `verify_live_write_safety.py --expectation disarmed` returns `disarmed PASS` afterwards |
| No stuck-open review authorization survives the run | Same — requires reading live deployed workflow state | `verify_live_write_safety.py --expectation disarmed` after any armed review batch |

**These are the phase's own subject matter, so they cannot be self-certified by the code under
test.** They belong to a supervised operator walk, not to CI.

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (none — see above)
- [ ] No watch-mode flags
- [ ] Feedback latency < 150s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
