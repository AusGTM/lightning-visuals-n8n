---
phase: 46-rubric-decision-simulation-engine-parity
verified: 2026-08-11T00:00:00Z
status: gaps_found
score: 5/5 roadmap success criteria verified (functionally); 1 administrative gap
behavior_unverified: 0
overrides_applied: 0
gaps:
  - truth: "REQUIREMENTS.md RUBRIC-02 traceability row/checkbox reflects the phase's actual delivered state"
    status: partial
    reason: >
      RUBRIC-02 ("Operator can see how the scored population would re-tier under proposed
      weights BEFORE committing them — a simulation over current lv_* inputs that writes
      nothing to HubSpot") is functionally satisfied — 46-SIMULATION-REPORT.md exists, is
      committed, was cited by the operator during sign-off in 46-DECISION.md, and the
      zero-write invariant is proven by three passing tests in
      tests/test_simulate_rubric_weights.py (static scan, namespace scan, behavioral stub).
      Despite this, .planning/REQUIREMENTS.md still shows "- [ ] RUBRIC-02" and its
      traceability row reads "Not started". Every plan in the phase explicitly deferred
      marking it (46-02-SUMMARY.md: "deliberately left unmarked... matching Plan 01's
      precedent"; 46-03-SUMMARY.md: "left unmarked here... Plan 05 should close it
      explicitly when it does the documentation sync") but 46-05's own frontmatter
      `requirements: [RUBRIC-01]` never included RUBRIC-02, so no plan ultimately closed the
      loop. RUBRIC-01 and RUBRIC-03 were correctly flipped to [x]/Complete by Plans 03 and 04
      respectively, so this is an isolated oversight, not a pattern across the phase.
    artifacts:
      - path: ".planning/REQUIREMENTS.md"
        issue: "RUBRIC-02 checkbox unchecked and traceability row reads 'Not started' despite the underlying deliverable being complete and evidenced"
    missing:
      - "Flip '- [ ] **RUBRIC-02**' to '- [x] **RUBRIC-02**' in .planning/REQUIREMENTS.md"
      - "Flip the RUBRIC-02 traceability table row from 'Not started' to 'Complete'"
---

# Phase 46: Rubric Decision, Simulation & Engine Parity Verification Report

**Phase Goal:** Decide the org-type weight questions with evidence, and prove that any change
lands identically in every scoring engine — before Phase 47/48 touch a record. Writes nothing to
a HubSpot record.

**Verified:** 2026-08-11
**Status:** gaps_found (one administrative/tracking gap; all 5 roadmap success criteria are
functionally verified against the codebase)
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (ROADMAP.md Phase 46 Success Criteria 1–5)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | A written decision on each changed org-type weight exists, citing closed-deal evidence, with overrides recorded rather than evidence rewritten | ✓ VERIFIED | `46-DECISION.md` cites `docs/business/icp-scoring.md` §3/§4 verbatim for all three levers (D-01/D-02/D-03), states each as an explicit GTM override, and preserves the 19%/n=36 club finding and the gambling/regulator framing intact. `docs/business/icp-scoring.md` itself was edited (Wave 5) to carry the override annotations inline (`46-DECISION.md D-01/D-02/D-03`) next to the original, un-softened evidence — confirmed by direct read of §4/§5 lines 55, 59, 65, 81, 121, 135, 137. |
| 2 | Operator can view a re-tier simulation of the 66 currently-scored companies, computed from current `lv_*` inputs, writing nothing to HubSpot, with the 17 false-veto and 18 blank-`lv_org_type` records annotated | ✓ VERIFIED | `46-SIMULATION-REPORT.md` (66 rows, committed) + `46-simulation-20260811.json` twin. Row-set cross-check vs `41-final-population.json`: symmetric difference 0. Grepped annotation counts: exactly 17 rows flagged `false_veto`, 18 rows flagged `blank_org_type` — matches ROADMAP.md's own "17 false vetoes"/"18 blank `lv_org_type`" figures exactly. Zero-write invariant proven by 3 passing tests (`test_zero_write_static_scan_finds_no_write_import`, `test_zero_write_namespace_scan_finds_no_write_binding`, `test_zero_write_behavioural_stub_records_read_only_calls`) — ran directly, all pass. `46-DECISION.md`'s Operator Sign-off block confirms the operator was shown this report before deciding. |
| 3 | Parity harness passes against decided weights in all engines carrying org-type weights (corrected: 2, not 3 — see criterion-3 note below) | ✓ VERIFIED (offline/engine level); live-population sweep is expected-red by design, honestly recorded | Ran `tests/test_flow_rubric_conformance.py` (24 passed, 86 skipped) and the full offline suite (2527 passed, 128 skipped) directly — matches the SUMMARY's claimed baseline exactly. `config/hubspot_flows/4626124224-org-type-score.after.json` action 5 (`individual_club_team`)=`"15"`, action 6 (`regulator`)=`"-20"` — read directly from the file, matches the decided values exactly. `config/hubspot_flows/gambling-score.after.json` both branches write `"0"`. `config/taxonomy.yaml`'s `score:` mirror (checked directly) also matches: `individual_club_team: 15`, `regulator: -20`. The live-record-level sweep (`scripts/run_scoring_parity.py`) is documented in `46-DECISION.md`/ROADMAP.md as expected-red until Phase 49's re-score — this is recorded plainly as a self-inflicted, bounded window, not silently reconciled or hidden. |
| 4 | If a weight changed, it reached the live workflow only via `build_cloud_workflows.py` → deploy → bounce with a running-content read-back | ✓ VERIFIED as "NOT TRIGGERED, reason recorded and sound" | `46-ENGINE-INVENTORY.md` documents an exhaustive word-boundary-adjacent-to-number grep across `n8n/wf_enrichment_cloud.json`, `n8n/code/mergeCompanies.js`, and `scripts/build_cloud_workflows.py` finding zero org-type-keyed numeric tables — the 78/62/44 raw substring hits are all traced to enum/synonym/fixture data, not weight tables. Two new permanent-guard tests (`tests/test_n8n_org_type_absence.py`, 3 tests) exist and pass, protecting this finding against regression. ROADMAP.md's own amendment section states the criterion-4 status plainly as "NOT TRIGGERED, not satisfied" with the reactivation triggers named. This is honest, sound, and evidenced — not a silent tick. |
| 5 | No live document still prints a superseded weight or deduction | ✓ VERIFIED | Directly read and grepped: `docs/business/icp-scoring.md` (§4/§5 tables and prose all show 15/-20/no-gambling-deduction, with D-14's evidentiary voice preserved), `CLAUDE.md` §10.1 (`individual_club_team: 15`, `regulator: -20`, `graduated_deductions: {}`) and §10.3 ("Graduated deductions include: revenue above 500M" — gambling line removed), `.planning/intel/constraints.md` (updated with dated amendment note), `.planning/intel/requirements.md` (updated with dated amendment note), `docs/WEB-RESEARCH-SPEC.md` (golden-set table cites `46-DECISION.md` D-01/D-03 explicitly). `.planning/milestones/` and `.planning/PROJECT.md` confirmed untouched (`git status --porcelain` empty for both paths; `git log 5e9d432..HEAD` for those paths empty). Minor informational note: `CLAUDE.md` §12.7's "Local MVP Python Skeleton" code listing (a pre-existing historical/illustrative code sample, not named in D-13's explicit update list) still shows the old ungoverned `cfg["graduated_deductions"]["gambling_operator"]` dict-access shape rather than the `.get`-guarded form landed in `src/icp_scoring.py`. No numeric weight value is wrong there (it's a code-shape staleness, not a printed weight/deduction), and it is outside D-13's scoped file list — not counted as a criterion-5 failure, flagged for awareness only. |

**Score:** 5/5 roadmap success criteria functionally verified against the codebase.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `46-DECISION.md` | Evidenced decision record with override framing (D-14) | ✓ VERIFIED | 444 lines; cites `icp-scoring.md`, records overrides, rejected-alternatives section, re-check procedure, signed-off block filled |
| `46-SIMULATION-REPORT.md` + JSON twin | Zero-write re-tier simulation, 66 rows, annotated | ✓ VERIFIED | Row-set cross-check symmetric difference 0; 17 false_veto + 18 blank_org_type flags match ROADMAP figures exactly |
| `46-ENGINE-INVENTORY.md` | Engine-count reconciliation with file:line evidence | ✓ VERIFIED | Grep evidence, classification of every raw hit, permanent-guard tests created and passing |
| `config/icp_scoring.yaml` | Signed-off weights landed | ✓ VERIFIED | `individual_club_team: 15`, `regulator: -20`, `graduated_deductions: {}` — read directly |
| `config/hubspot_flows/4626124224-org-type-score.after.json` | Matching live flow branch values | ✓ VERIFIED | action 5=`"15"`, action 6=`"-20"`, revisionId=26 in archived file, matching SUMMARY's live-GET claim |
| `config/hubspot_flows/gambling-score.after.json` | Deduction removed on both branches | ✓ VERIFIED | Both branches write `"0"`, revisionId=4 |
| `config/taxonomy.yaml` | `score:` mirror agrees with `icp_scoring.yaml` | ✓ VERIFIED | `individual_club_team: 15`, `regulator: -20` |
| `src/icp_scoring.py` | `.get`-guarded gambling-deduction lookup (no KeyError on empty dict) | ✓ VERIFIED | Line 101: `cfg.get("graduated_deductions", {}).get("gambling_operator", 0)` |
| `tests/test_n8n_org_type_absence.py` | Permanent regression guard for the 2-engine finding | ✓ VERIFIED | 3 tests, all pass |
| `tests/test_simulate_rubric_weights.py` | Zero-write proof + weight arithmetic | ✓ VERIFIED | 25 tests, all pass |
| `.planning/REQUIREMENTS.md` RUBRIC-02 row | Reflects delivered state | ✗ STALE | Checkbox unchecked, row reads "Not started" despite functional completion — see Gaps |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `46-DECISION.md` | `docs/business/icp-scoring.md` | Evidence citations (§3/§4 quotes) | ✓ WIRED | Verified verbatim quotes match source document |
| `46-DECISION.md` Operator Sign-off | `46-SIMULATION-REPORT.md` | "shown the live simulation numbers" | ✓ WIRED | Sign-off block explicitly references the simulation's numbers |
| `config/icp_scoring.yaml` | `config/hubspot_flows/*.after.json` | RUBRIC-03 parity | ✓ WIRED | Values match exactly; `tests/test_flow_rubric_conformance.py` passes |
| `config/icp_scoring.yaml` | `config/taxonomy.yaml` | `score:` mirror | ✓ WIRED | `tests/test_taxonomy_conformance.py` passes |
| `46-DECISION.md` D-01/D-02/D-03 | `docs/business/icp-scoring.md` inline override notes | Documentation sync (D-13/D-14) | ✓ WIRED | Cross-referenced by exact commit-message anchor `46-DECISION.md` in the doc text |
| `docs/hubspot_flows/*.after.json` (pre-PUT archive) | live portal 22617666 | disable→edit→PUT→enable→read-back | ✓ WIRED | Pre-PUT archive commit (`5643dda`) + post-PUT diff commit (`4f7c395`) show only `revisionId` changing between them (content was already landed in `caae5d6`); SUMMARY claims a live GET confirms `isEnabled=true` and the new values — consistent with the archived file content |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|--------------|--------|----------|
| RUBRIC-01 | 46-03 | Evidenced decision, overrides recorded | ✓ SATISFIED, marked complete | `46-DECISION.md`, REQUIREMENTS.md `[x]` |
| RUBRIC-02 | 46-02 | Zero-write simulation, operator-viewable | ✓ SATISFIED functionally, ✗ NOT marked complete | `46-SIMULATION-REPORT.md` + passing zero-write tests exist; REQUIREMENTS.md checkbox/row still shows unchecked/"Not started" — administrative gap, see Gaps section |
| RUBRIC-03 | 46-04 | Parity across engines carrying org-type weights | ✓ SATISFIED, marked complete | `tests/test_flow_rubric_conformance.py` passes; REQUIREMENTS.md `[x]`, with an honest amendment note about the 2-vs-3-engine correction |

### Anti-Patterns Found

None found in the files this phase modified. Reviewed the full diff of every test file changed in commit `caae5d6` (`tests/test_icp_scoring.py`, `tests/test_scoring_parity.py`, `tests/test_flow_rubric_conformance.py`, `tests/test_backfill_seed_company_scores.py`, `tests/test_simulate_rubric_weights.py`) — every changed assertion is legitimate arithmetic fallout from the weight change (e.g., `35/C → 45/B`, `-20 deduction → 0`), several are *stricter* than before (e.g., an added explicit `assert "gambling_operator" not in load_rubric().get(...)`), tests were renamed (not deleted) so names don't lie about the new expected values, and no test was deleted or had its assertion loosened to force a pass.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| D-08 zero-write invariant | `.venv/bin/python -m pytest tests/test_simulate_rubric_weights.py -q` | 25 passed | ✓ PASS |
| Flow parity (offline) | `.venv/bin/python -m pytest tests/test_flow_rubric_conformance.py -q` | 24 passed, 86 skipped | ✓ PASS |
| n8n absence regression guard | `.venv/bin/python -m pytest tests/test_n8n_org_type_absence.py -v` | 3 passed | ✓ PASS |
| Full offline suite (run once) | `.venv/bin/python -m pytest -q` | 2527 passed, 128 skipped | ✓ PASS — matches `caae5d6`'s claimed baseline exactly |
| Committed weight values match signed-off decision | direct read of `config/icp_scoring.yaml` | `individual_club_team: 15`, `regulator: -20`, `graduated_deductions: {}` | ✓ PASS |
| Live flow branch values match decision | direct read of `config/hubspot_flows/*.after.json` | action 5=`15`, action 6=`-20`, both gambling branches=`0` | ✓ PASS |
| D-13 do-not-edit invariant | `git status --porcelain .planning/milestones/ .planning/PROJECT.md` + `git log 5e9d432..HEAD -- <paths>` | both empty | ✓ PASS |

### Human Verification Required

None. All roadmap success criteria and the "verify with particular care" items are checkable directly against committed files, test results, and git history, and were checked directly rather than deferred.

### Gaps Summary

One real but low-severity, purely administrative gap: `.planning/REQUIREMENTS.md`'s `RUBRIC-02` line remains unchecked and its traceability row still reads "Not started," even though the underlying deliverable (the zero-write re-tier simulation) is fully built, committed, tested (25 passing tests including the three-part zero-write proof), and was the artifact the operator reviewed before signing off in `46-DECISION.md`. This happened because Plan 02 deliberately deferred marking it to Plan 03 (pending the blocking sign-off), Plan 03 deliberately deferred it again to Plan 05 ("Plan 05 should close it explicitly when it does the documentation sync" — `46-03-SUMMARY.md` line 176), and Plan 05's own frontmatter `requirements:` list only declared `[RUBRIC-01]`, never picking up `RUBRIC-02`. RUBRIC-01 and RUBRIC-03 were correctly closed by their respective plans, so this is an isolated bookkeeping miss rather than a systemic pattern. Nothing in the actual codebase, tests, or live HubSpot state is broken by this gap — it is purely a stale tracking artifact, fixable with a two-line edit to `.planning/REQUIREMENTS.md` (flip the checkbox and the traceability-table cell). No plan needs to be re-executed and no code needs to change.

Everything else checked — including the items flagged for particular care (D-08 zero-write, D-14 evidentiary voice, D-13 do-not-edit, exact committed weight values, no-weakened-assertions, `config/taxonomy.yaml` mirror, the live flow PUT evidence, and honest reporting of both divergences from the June-snapshot estimates) — was independently verified against the actual repository state (not SUMMARY claims) and holds up.

---

*Verified: 2026-08-11*
*Verifier: Claude (gsd-verifier)*
