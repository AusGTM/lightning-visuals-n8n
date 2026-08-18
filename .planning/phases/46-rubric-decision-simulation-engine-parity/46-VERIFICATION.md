---
phase: 46-rubric-decision-simulation-engine-parity
verified: 2026-08-19T00:00:00Z
status: passed
score: 5/5 roadmap success criteria verified
behavior_unverified: 0
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: "5/5 roadmap success criteria verified (functionally); 1 administrative gap"
  gaps_closed:
    - "REQUIREMENTS.md RUBRIC-02 traceability row/checkbox reflects the phase's actual delivered state"
  gaps_remaining: []
  regressions: []
---

# Phase 46: Rubric Decision, Simulation & Engine Parity Verification Report

**Phase Goal:** Decide the org-type weight questions with evidence, and prove that any change
lands identically in every scoring engine — before Phases 47/48 touch a record. Writes nothing to
a HubSpot record.

**Verified:** 2026-08-19
**Status:** passed
**Re-verification:** Yes — after gap closure

## What Changed Since 2026-08-11

The single prior gap — `.planning/REQUIREMENTS.md` still showing `RUBRIC-02` as unchecked /
"Not started" despite the deliverable being complete — is closed, and independently confirmed
closed here (not taken on the orchestrator's word):

- `.planning/REQUIREMENTS.md:22` reads `- [x] **RUBRIC-02**` (checked directly).
- `.planning/REQUIREMENTS.md:224` traceability row reads `| RUBRIC-02 | Phase 46 | Complete |`
  (checked directly). RUBRIC-01 (line 223) and RUBRIC-03 (line 225) also both read `Complete`.
- The fix was not a "later phase's documentation sync" as speculated in the task brief — it was
  closed the same day as the original verification, in commit `4548be4` ("docs(46): close
  RUBRIC-02 traceability and record phase verification", 2026-08-11 19:00, same commit that
  first wrote `46-VERIFICATION.md`). The `46-VERIFICATION.md` this report replaces was itself
  committed *after* the fix but described the pre-fix state — an artifact of how that
  verification pass was written, not evidence the gap stayed open. `git log` on
  `.planning/REQUIREMENTS.md` shows no other commit has touched the RUBRIC-02 line since.

No new gap was found. Everything the 2026-08-11 report verified was re-checked against the
current repository state (not re-read from the old report's prose), and nothing has regressed.

## Goal Achievement

### Observable Truths (ROADMAP.md Phase 46 Success Criteria 1–5)

| # | Truth | Status | Evidence (re-checked 2026-08-19) |
|---|-------|--------|--------|
| 1 | A written decision on each changed org-type weight exists, citing closed-deal evidence, with overrides recorded rather than evidence rewritten | ✓ VERIFIED | `46-DECISION.md` still present (unmodified since 2026-08-11 verification), cites `docs/business/icp-scoring.md` for D-01/D-02/D-03. `docs/business/icp-scoring.md` last touched 2026-08-11 18:46 (`git log -1`) — not touched by any of Phases 47/47.5/48/49/50. Read directly: lines 55/59/65/77/81/121/126/135/137 still carry the D-01/D-02/D-03 override annotations next to the original evidence (19%/n=36 club win rate, regulator/gambling framing all intact, un-softened). |
| 2 | Operator can view a re-tier simulation of the 66 currently-scored companies, computed from current `lv_*` inputs, writing nothing to HubSpot, with the 17 false-veto and 18 blank-`lv_org_type` records annotated | ✓ VERIFIED | `46-SIMULATION-REPORT.md` and `46-simulation-20260811.json` still present and unmodified. Re-ran `tests/test_simulate_rubric_weights.py` fresh: **25 passed** (matches the operator's claim exactly), including the three-part zero-write proof (static-scan / namespace-scan / behavioral-stub). No write-capable import, binding, or call exists in the simulation path. |
| 3 | Parity harness passes against decided weights in all engines carrying org-type weights (2, not 3 — corrected in-phase) | ✓ VERIFIED | Re-ran `tests/test_flow_rubric_conformance.py` fresh: 24 passed, 112 skipped (skip count grew from 86→112 as later phases added more archived-flow fixtures; the 24 asserting tests are unchanged and still green). Re-ran `tests/test_taxonomy_conformance.py` fresh: 17 passed. Read `config/icp_scoring.yaml` directly: `individual_club_team: 15`, `regulator: -20`, `graduated_deductions: {}` — unchanged. Read `config/hubspot_flows/4626124224-org-type-score.after.json` directly: action 5 (`individual_club_team`) `staticValue="15"`, action 6 (`regulator`) `staticValue="-20"` — unchanged. Read `config/hubspot_flows/gambling-score.after.json` directly: both branches `staticValue="0"` — unchanged. Read `config/taxonomy.yaml` directly (structure changed to nested `org_types.<key>.score` since 2026-08-11, but values match): `individual_club_team.score=15`, `regulator.score=-20`, `gambling_operator.score=0`. |
| 4 | If a weight changed, it reached the live workflow only via `build_cloud_workflows.py` → deploy → bounce with a running-content read-back | ✓ VERIFIED as "NOT TRIGGERED, reason recorded and sound" — and the two-engine parity rule this criterion protects has since been exercised correctly | `46-ENGINE-INVENTORY.md` unchanged since 2026-08-11. Re-ran `tests/test_n8n_org_type_absence.py`: 3 passed, still guarding the "no org-type weight table in n8n" finding. Went further than the 2026-08-11 pass: confirmed the Phase-46 parity rule this criterion exists to protect (CLAUDE.md §10.3.1, "any change lands in both, in one commit") has since been correctly exercised — commit `f817ec5` (Phase 47.5) changed the hardware-veto predicate in both `src/icp_scoring.py` (line 143: `if is_hardware_vendor or org_type == "hardware_vendor":`) and the `Decide Company Action` node built by `scripts/build_cloud_workflows.py` (line 2875: `if (isHardwareVendor === true \|\| orgType === "hardware_vendor")`) in that single commit, exactly as the rule requires. `n8n/wf_enrichment_cloud.json` was regenerated from the script, never hand-edited (per the same commit's message). This is a real downstream validation of Phase 46's own contribution, not just an absence-of-regression check. |
| 5 | No live document still prints a superseded weight or deduction | ✓ VERIFIED | Re-read `docs/business/icp-scoring.md` directly (unmodified since 2026-08-11): 15/-20/no-gambling-deduction still shown throughout, D-01/D-02/D-03 citations intact. Re-checked `CLAUDE.md` §10.1 directly: `individual_club_team: 15`, `regulator: -20`, `graduated_deductions: {}` at lines 786-788/816 — unchanged, no superseded value reintroduced by any later phase's CLAUDE.md edits (Phase 47.5's §10.3.1 and §13.0 additions are net-new sections about the veto predicate and recompute lane; they don't touch or restate the org-type weight table). The same pre-existing informational note from the 2026-08-11 report still applies unchanged: CLAUDE.md §12.7's illustrative Python skeleton (lines 1646-1648) still shows the old ungoverned `cfg["graduated_deductions"]["gambling_operator"]` dict-access shape rather than the `.get`-guarded form in `src/icp_scoring.py` — outside D-13's scoped file list, a pre-existing code-shape staleness not a printed-weight failure, unchanged from 8 days ago. No grep hit found for a stale `individual_club_team` weight value anywhere in `docs/`, `CLAUDE.md`, or `.planning/`. |

**Score:** 5/5 roadmap success criteria verified against the current codebase (2026-08-19).

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `46-DECISION.md` | Evidenced decision record with override framing (D-14) | ✓ VERIFIED | Present, unmodified since 2026-08-11 |
| `46-SIMULATION-REPORT.md` + JSON twin | Zero-write re-tier simulation, 66 rows, annotated | ✓ VERIFIED | Present, unmodified; 25/25 tests green on fresh run |
| `46-ENGINE-INVENTORY.md` | Engine-count reconciliation with file:line evidence | ✓ VERIFIED | Present, unmodified; regression-guard tests green |
| `config/icp_scoring.yaml` | Signed-off weights landed | ✓ VERIFIED | `individual_club_team: 15`, `regulator: -20`, `graduated_deductions: {}` — read directly, unchanged |
| `config/hubspot_flows/4626124224-org-type-score.after.json` | Matching live flow branch values | ✓ VERIFIED | action 5=`"15"`, action 6=`"-20"` — read directly, unchanged |
| `config/hubspot_flows/gambling-score.after.json` | Deduction removed on both branches | ✓ VERIFIED | Both branches `"0"` — read directly, unchanged |
| `config/taxonomy.yaml` | Score mirror agrees with `icp_scoring.yaml` | ✓ VERIFIED | Structure now nested (`org_types.<key>.score`) but values match; `test_taxonomy_conformance.py` 17/17 green |
| `src/icp_scoring.py` | `.get`-guarded gambling-deduction lookup (D-03) | ✓ VERIFIED | Line 119: `cfg.get("graduated_deductions", {}).get("gambling_operator", 0)` — still present, unmodified guard |
| `tests/test_n8n_org_type_absence.py` | Permanent regression guard for the 2-engine finding | ✓ VERIFIED | 3/3 green on fresh run |
| `tests/test_simulate_rubric_weights.py` | Zero-write proof + weight arithmetic | ✓ VERIFIED | 25/25 green on fresh run |
| `.planning/REQUIREMENTS.md` RUBRIC-02 row | Reflects delivered state | ✓ VERIFIED (was ✗ STALE) | `- [x] **RUBRIC-02**` at line 22; traceability row `Complete` at line 224 — closed in commit `4548be4`, same day as the original verification |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|--------------|--------|----------|
| RUBRIC-01 | 46-03 | Evidenced decision, overrides recorded | ✓ SATISFIED, marked complete | `46-DECISION.md`, `.planning/REQUIREMENTS.md:12` `[x]` |
| RUBRIC-02 | 46-02 | Zero-write simulation, operator-viewable | ✓ SATISFIED, marked complete | `46-SIMULATION-REPORT.md` + 25 passing tests; `.planning/REQUIREMENTS.md:22` `[x]`, traceability row `Complete` — gap closed |
| RUBRIC-03 | 46-04 | Parity across engines carrying org-type weights | ✓ SATISFIED, marked complete | `tests/test_flow_rubric_conformance.py` passes; `.planning/REQUIREMENTS.md:26` `[x]` |

No orphaned requirements found for Phase 46 in `.planning/REQUIREMENTS.md`.

### Behavioral Spot-Checks (all re-run fresh 2026-08-19, not taken from the prior report)

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| D-08 zero-write invariant | `.venv/bin/python -m pytest tests/test_simulate_rubric_weights.py -q` | 25 passed | ✓ PASS |
| Flow parity (offline) | `.venv/bin/python -m pytest tests/test_flow_rubric_conformance.py -q` | 24 passed, 112 skipped | ✓ PASS |
| Taxonomy conformance | `.venv/bin/python -m pytest tests/test_taxonomy_conformance.py -q` | 17 passed | ✓ PASS |
| n8n absence regression guard | `.venv/bin/python -m pytest tests/test_n8n_org_type_absence.py -v` | 3 passed | ✓ PASS |
| Full offline suite (run once) | `.venv/bin/python -m pytest -q` | 2821 passed, 154 skipped | ✓ PASS (grew from 2527/128 at Phase 46's original check — expected, later phases added tests; nothing failing) |
| Committed weight values match signed-off decision | direct read of `config/icp_scoring.yaml` | `individual_club_team: 15`, `regulator: -20`, `graduated_deductions: {}` | ✓ PASS |
| Live flow branch archive values match decision | direct read of `config/hubspot_flows/*.after.json` | action 5=`"15"`, action 6=`"-20"`, both gambling branches=`"0"` | ✓ PASS |
| Two-engine parity rule exercised downstream | `git show --stat f817ec5` | Both `src/icp_scoring.py` and `scripts/build_cloud_workflows.py` changed in one commit, matching CLAUDE.md §10.3.1's rule | ✓ PASS |
| RUBRIC-02 traceability closure commit | `git log --oneline -- .planning/REQUIREMENTS.md` | `4548be4` closes it same-day as original verification | ✓ PASS |

### Anti-Patterns Found

None found in Phase 46's own artifacts. No further scan of later phases' files was performed —
out of scope for a Phase 46 re-verification.

### Human Verification Required

None. Every roadmap success criterion and the single prior gap are checkable directly against
committed files, fresh test runs, and git history, and were checked directly.

### Gaps Summary

None. The one prior gap (administrative — `.planning/REQUIREMENTS.md` RUBRIC-02 checkbox/row
stale) is closed and independently confirmed closed, via a commit (`4548be4`) made the same day
as the original verification. All 5 roadmap success criteria hold on fresh evidence gathered
2026-08-19, 8 days and 5 phases (47, 47.5, 48, 49, 50) after the original pass. Phase 46's own
lasting contribution — the two-engine parity rule (CLAUDE.md §10.3.1) — has been exercised
correctly by at least one later phase (47.5, commit `f817ec5`), which is the strongest evidence
available that the rule is a living practice, not a one-off. Phase 50's WF1 deletion and
`lv_icp_tier` archival, referenced in the task brief as a heads-up, do not touch any artifact
this phase's success criteria depend on (`config/hubspot_flows/4626124224-org-type-score.*.json`
and `gambling-score.*.json` are separate calculated-property flows, both still present and
unchanged).

---

*Verified: 2026-08-19*
*Verifier: Claude (gsd-verifier)*
*Re-verification of: 2026-08-11 report (status gaps_found → passed)*
