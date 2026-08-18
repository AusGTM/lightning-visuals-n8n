---
phase: 49-re-score-strategy-reporting
verified: 2026-08-13T08:00:00Z
status: passed_with_gaps
score: 4/4 success criteria substantively met; 1 acceptance-gate honestly red (disclosed, root-caused, scheduled fix)
overrides_applied: 0
gaps:
  - truth: "docs/OPERATOR-RESCORE.md's own AMENDMENT-block convention is not exercised despite the procedure being live-exercised and found incomplete for one failure class"
    status: partial
    reason: >
      The runbook's own §Acceptance says the live parity sweep is "the proof that a re-score
      landed... never edited to make it pass — if it is red, the rubric and the live records
      still disagree, and the fix is to finish the re-score, not to loosen the comparison."
      W1's own live exercise disproved that instruction for exactly the failure class this
      phase discovered: a same-value PATCH on the 4 stuck-tier records can never turn the
      sweep green by "finishing the re-score" (re-running --execute again is a no-op against
      already-correct values, confirmed twice in 49-W1-ARM-RECORD.md). The actual fix is
      Phase 50's derived-tier property, not more re-score cycles. The document's own house
      convention ("if something below turns out to be wrong or incomplete once exercised
      live, add a new AS-BUILT AMENDMENT block") calls for exactly this correction, but the
      file still reads "No amendments have been made to this document yet." A future operator
      who reads only the runbook (its stated purpose) and hits this failure class has no
      guidance in the runbook itself pointing at the real fix — they would have to separately
      discover WINDOWS.md ids 9-12 or TIER-DERIVATION-SPIKE-2026-08-13.md.
    artifacts:
      - path: "docs/OPERATOR-RESCORE.md"
        issue: "Acceptance section's guidance is now known-incomplete for the same-value-PATCH stale-tier failure class; no AS-BUILT AMENDMENT block added despite the doc's own convention calling for one"
    missing:
      - "An AS-BUILT AMENDMENT block in docs/OPERATOR-RESCORE.md, dated 2026-08-13, cross-referencing WINDOWS.md ids 9-12 and TIER-DERIVATION-SPIKE-2026-08-13.md, noting that a same-value component PATCH cannot self-correct a stale tier and pointing at the Phase 50 derived-tier fix"
deferred: []
human_verification: []
---

# Phase 49: Re-score Strategy & Reporting Verification Report

**Phase Goal:** A future rubric-triggered full-population re-score has a defined,
budget-bounded procedure the operator can trust before invoking it, and the milestone's net
effect on the target list is visible in plain language. Phase 46 DID change three weights
(commit `caae5d6`), so the full-population re-score was owed, not merely proven.

**Verified:** 2026-08-13
**Status:** passed_with_gaps
**Re-verification:** No — initial verification

## Overall Judgment

The phase goal is **met**. The operator has a real, evidence-backed, budget-bounded procedure
(`docs/OPERATOR-RESCORE.md` + `scripts/rescore_population.py`), the owed full-population
re-score actually ran under that procedure against the live portal, and a plain-language
before/after report exists, is committed, and was published and operator-approved. The one
place this phase does not close cleanly — the live acceptance sweep is red on 4/66 records —
is not an unexplained failure. It is a genuine, root-caused, disclosed, ledgered (`WINDOWS.md`
ids 9-12) finding with a credible scheduled fix (`TIER-DERIVATION-SPIKE-2026-08-13.md`), and
the phase's own reporting says so in plain language rather than smoothing it over
(`49-RESCORE-REPORT.md` §9, `49-RUN-REPORT.md`). That is exactly the honest-disclosure
behavior this milestone has been built to produce, not a defect in it.

The verdict is `passed_with_gaps`, not `passed`, for two reasons: (1) the phase's own stated
acceptance gate (the live parity sweep) does not exit green, and RESCORE-02/RESCORE-03's
"complete" status in REQUIREMENTS.md rests on that gap being disclosed rather than closed; (2)
`docs/OPERATOR-RESCORE.md`'s own acceptance guidance, now known to be incomplete for this
failure class, has not received the AS-BUILT AMENDMENT its own house convention calls for. It
is not `failed`: every score value is correct, the procedure ran exactly as declared, all
deviations are disclosed with evidence rather than buried, and the residual gap has a named,
credible fix path already spiked.

## Goal Achievement

### Observable Truths (Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Operator can see, before any future rubric change, exactly which records would be re-scored, chunk size, and write window | ✓ VERIFIED | `docs/OPERATOR-RESCORE.md` states population=66, chunk_size=100, chunks=1, window=W1, arm_keys, cost — every figure copied verbatim from `49-PLAN-OUTPUT.json`, which was independently re-verified byte-for-byte against the doc's cited numbers (population_count 66, chunk_size 100, chunks 1, window "W1", cost.records 66). Both weight and veto branches are documented with real measured/estimated costs. |
| 2 | Because no `lv_icp_scoring_version` exists, plan explicitly re-scores the entire 66-company population and states cost up front | ✓ VERIFIED | `docs/OPERATOR-RESCORE.md` "Why the whole population, every time" section states this explicitly; `49-PLAN-OUTPUT.json.cost` gives exact pre-declared 0 n8n / 0 Anthropic / 0 provider-credit / 1 HubSpot-batch-call cost for the weight branch, and a separately-computed veto-branch cost (66 n8n executions, 2.6% of monthly allowance) derived from Phase 47.5's measured per-POST unit cost, not guessed. |
| 3 | If Phase 46 changed a weight, the full-population re-score executed under this defined procedure | ⚠ MET WITH DISCLOSED GAP | Phase 46 did change three weights (`individual_club_team` 5→15, `regulator` 0→−20, gambling deduction removed — confirmed against `docs/OPERATOR-RESCORE.md`'s own restatement). The re-score executed live: 66/66 population, one W1 window, canary-then-remainder, exact-set gate, independent full-population component read-back confirming 66/66 components match the oracle (`49-W1-ARM-RECORD.md` lines 149-158). The declared window shape (1 deploy+bounce, 1 W1, conditional W2) was honored exactly on window count; 2 line items exceeded their own declared *count* within those windows (3 HubSpot batch calls vs. 2 declared in W1; 2 Anthropic calls vs. 1 declared in W2's Entain research) — both disclosed with evidence, not absorbed (`49-RUN-REPORT.md` Cost actuals table; `49-ENTAIN-EVIDENCE.json`'s `pilot_call_discarded`/`verdict_call` keys). **The procedure's own acceptance gate (`run_scoring_parity.py`'s live sweep) is honestly red at 4/66** — diagnosed root cause (same-value PATCH fires no HubSpot workflow re-enrollment event), ledgered as `WINDOWS.md` ids 9-12, with a spiked and credible fix path (`TIER-DERIVATION-SPIKE-2026-08-13.md`) deferred to Phase 50 because it requires a new property, which this milestone's scope explicitly excludes. |
| 4 | Operator receives a plain-language before/after tier-distribution comparison covering the whole milestone's re-scoring activity | ✓ VERIFIED | `49-RESCORE-REPORT.md` — three-point P1/P2/P3 comparison, each point's tier counts cross-checked directly against source JSON (see Data-Flow Trace below) and matching exactly. Published as a private Claude Artifact (`https://claude.ai/code/artifact/2ac2d25f-586c-4123-9c23-2e6cc7634d2b`) and operator-approved 2026-08-13 (`49-RUN-REPORT.md` "Deviation: the published Artifact" section). §9 states the red acceptance sweep plainly, with cause and scheduled fix, rather than omitting it. |

**Score:** 3/4 truths cleanly VERIFIED; 1/4 (#3) met with a disclosed, root-caused, ledgered gap that does not undermine the phase's goal but keeps the overall verdict from a clean pass.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `docs/OPERATOR-RESCORE.md` | Budget-bounded operator runbook, both branches | ✓ VERIFIED, with 1 disclosed gap | Exists, substantive, figures match `49-PLAN-OUTPUT.json` verbatim. Gap: acceptance-section guidance not amended per its own convention after being found incomplete for the stale-tier failure class (see `gaps` above). |
| `scripts/rescore_population.py` | Driver: exact-set gate, `--plan`, canary/execute, `--snapshot` | ✓ VERIFIED | `select_scored_population()` now refuses on truncation (post-review fix, commit `d62180a`); exact-set gate (`enforce_exact_population`) confirmed present and is the described "stronger than a count cap" mechanism. |
| `49-P2-SNAPSHOT.json` / `49-P3-SNAPSHOT.json` | Before/after population census | ✓ VERIFIED, DATA FLOWS | Independently re-computed tier counts from `records[]` match both the file's own `tier_distribution` field and `49-RESCORE-REPORT.md`'s printed table exactly (P2: A9/B27/C21/D7/U2; P3: A9/B41/C7/D7/U2). |
| `49-PARITY-VERDICT.json` | Genuine, unedited acceptance-sweep result | ✓ VERIFIED | 66 comparisons, 4 `real_finding` entries matching `WINDOWS.md` ids 9-12 exactly by company id; verdict string states "FAIL: 4 of 66..." — not silently passed. |
| `49-RESCORE-REPORT.md` | Plain-language milestone report | ✓ VERIFIED | 9 sections, denominator caveat up front (§1), red-sweep disclosure up front and in dedicated §9, every table sourced to a committed JSON file. |
| `49-RUN-REPORT.md` | Cost/window actuals vs. declared | ✓ VERIFIED | Every declared-vs-actual row checked against its cited source file (`49-DEPLOY-PROOF.md` execution `11871`, `49-W1-ARM-RECORD.md`, `49-W2-RECORD.md`, `49-ENTAIN-EVIDENCE.json`); no unexplained variance. |
| `49-REVIEW.md` | Code review, 1 Critical + 4 Warnings | ✓ VERIFIED | CR-01 and WR-02 genuinely fixed in commit `d62180a` (content-identical dangling duplicate `63b6587` exists from a committer-timestamp-only amend — not a discrepancy, both carry the same tree). Spike scripts (`scripts/spike_tier_formula*.py`) deleted, closing WR-03/WR-04 as a side effect. `select_scored_population()` now has the refuse-on-truncation guard WR-02 asked for, plus 3 new tests. WR-01/IN-01/IN-02 deferred as non-blocking — recorded in the fix commit's message, not in `WINDOWS.md` (WR-01 in particular is a real, if narrow, write-surface widening with no ledger entry — an observation, not a blocker). |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `docs/OPERATOR-RESCORE.md` figures | `49-PLAN-OUTPUT.json` | direct citation | WIRED | Verified byte-for-byte: population 66, chunk_size 100, chunks 1, window W1, arm_keys, cost fields all match. |
| `49-RESCORE-REPORT.md` P1/P2/P3 table | `46-simulation-20260811.json` / `49-P2-SNAPSHOT.json` / `49-P3-SNAPSHOT.json` | direct citation, re-derived counts | WIRED | Independently recomputed tier distributions from each source file match the report's printed numbers exactly on all three points. |
| Code-review fixes | Live repo state | `git show`, file existence, offline suites | WIRED | Spike scripts absent from `scripts/`; `select_scored_population()` contains the refuse-on-truncation logic described in the fix commit. |
| `WINDOWS.md` ids 9-12 | `49-PARITY-VERDICT.json` real_findings | company-id match | WIRED | All 4 company ids in `real_findings` exactly match the 4 `WINDOWS.md` entries; root-cause text is consistent across both. |
| D-11 Artifact resolution | Operator approval | `49-RUN-REPORT.md`, `49-07-SUMMARY.md` | WIRED | Published Artifact URL cited, "approved" response recorded, sequence (executor deferred → orchestrator published → operator approved) documented with no gap in the chain. |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Offline pytest suite green | `.venv/bin/python -m pytest -q -m "not live"` | `2719 passed, 128 skipped` | ✓ PASS |
| Offline node suite green (glob form) | `node --test tests/n8n/*.test.mjs` | `tests 676, pass 676, fail 0` | ✓ PASS |
| Spike scripts removed post-review | `ls scripts/spike_tier_formula*.py` | No such file or directory | ✓ PASS |
| CR-01/WR-02 fix on branch | `git rev-parse d62180a`; `git branch --contains d62180a` | On `master`, tree matches | ✓ PASS |

### Requirements Coverage

| Requirement | Description | Status | Evidence |
|-------------|-------------|--------|----------|
| RESCORE-01 | Defined, budget-bounded re-score procedure | ✓ SATISFIED | `docs/OPERATOR-RESCORE.md` + `scripts/rescore_population.py --plan`; figures independently cross-checked against `49-PLAN-OUTPUT.json`. |
| RESCORE-02 | Whole-population re-score (no scoring_version segmentation possible) executed | ✓ SATISFIED, with disclosed gap | 66/66 re-scored, one W1 window, independent component read-back confirms 66/66 match oracle. Tier-side acceptance sweep is red on 4/66 for a diagnosed, disclosed, non-write-mechanism reason — REQUIREMENTS.md's own "Complete" annotation already reflects this nuance correctly (cites the P2/P3 snapshots, not a false claim of a clean sweep). |
| RESCORE-03 | Plain-language before/after tier comparison | ✓ SATISFIED | `49-RESCORE-REPORT.md`, published Artifact, operator-approved. |

### Anti-Patterns Found

None blocking. `scripts/rescore_population.py`, `scripts/build_rescore_report.py`, and
`docs/OPERATOR-RESCORE.md` were scanned for TBD/FIXME/XXX/TODO/HACK/placeholder markers — none
found. The two spike scripts that did carry a live-write gate defect (CR-01) have been deleted
rather than left as debt.

### Human Verification Required

None. All four success criteria and both flagged deviations resolve on documentary and
executable evidence; nothing here requires a human to observe runtime/visual behavior beyond
what the operator has already reviewed and approved (the published Artifact, per
`49-RUN-REPORT.md`).

### Gaps Summary

One gap, non-blocking to the phase's goal but real: `docs/OPERATOR-RESCORE.md` has not been
amended to reflect what this phase's own live exercise discovered — that a same-value
component PATCH can never make the acceptance sweep go green for the stale-tier failure class,
so "finish the re-score" (the doc's current acceptance-section instruction) is not always the
right next action. The finding is well-ledgered elsewhere (`WINDOWS.md` ids 9-12,
`49-RESCORE-REPORT.md` §9, `TIER-DERIVATION-SPIKE-2026-08-13.md`), but the runbook itself —
the document an operator is told to "read before deciding whether to re-score" — still says
"No amendments have been made to this document yet," which is stale against its own house
convention. Recommend a short AS-BUILT AMENDMENT block before/at the start of Phase 50, not a
blocker to sealing Phase 49.

---

*Verified: 2026-08-13*
*Verifier: Claude (gsd-verifier)*
