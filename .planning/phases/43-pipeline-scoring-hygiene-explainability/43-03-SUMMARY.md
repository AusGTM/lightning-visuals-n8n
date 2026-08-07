---
phase: 43-pipeline-scoring-hygiene-explainability
plan: 03
subsystem: scoring-explainability
tags: [python, hubspot, deals, icp-tier, operator-plugin, subprocess]

requires:
  - phase: 40-scoring-engine-remediation-notes
    provides: "config/icp_scoring.yaml's version key (lv-icp-v0.1), which this plan stamps into the report"
provides:
  - "scripts/build_loss_reason_report.py -- the first consumer of lv_closed_lost_reason, offline-testable, empty-dataset-correct"
  - "operator-claude-plugin/skills/loss-reason-report/SKILL.md -- the first plugin skill that shells out to a backend-repo script instead of the n8n webhook surface"
affects: [43-04-plan-scoring-consolidation]

actuals:
  tokens: 8400
  tasks: 2
  commits: 2

tech-stack:
  added: []
  patterns:
    - "Deals property schema probe (GET crm/v3/properties/deals/{name}, 404 vs 200) to distinguish 'property absent' from 'property present and empty' -- never inferred from a read returning nothing."
    - "Deal-to-company join with a documented primary-then-fallback order (hs_primary_associated_company, then Associations v4), counted per path, with an explicit Unknown-tier bucket for unjoinable rows instead of silent drop."
    - "Plugin skill shells out to a backend-repo script via subprocess (never import), invisible to test_no_backend_imports.py's ast scan, keeping the plugin's credential surface unchanged."

key-files:
  created:
    - scripts/build_loss_reason_report.py
    - tests/test_loss_reason_report.py
    - operator-claude-plugin/skills/loss-reason-report/SKILL.md
  modified:
    - operator-claude-plugin/.claude-plugin/plugin.json
    - operator-claude-plugin/CHANGELOG.md
    - operator-claude-plugin/tests/test_plugin_manifest.py
    - operator-claude-plugin/tests/test_report_enrichment.py

key-decisions:
  - "Tri-state property wording, exact strings used: absent -> '<label> does not exist in this portal.'; present-and-empty -> '<label> exists and is 0% filled (0 of N examined deals).'; present-and-filled -> '<label> exists and F of N examined deals have it filled.' Applied identically to lv_closed_lost_reason and HubSpot's native closed_lost_reason."
  - "Join fallback order as implemented: hs_primary_associated_company first (counted as joined_primary); if empty, Associations v4 (crm/v4/objects/deals/{id}/associations/companies, first result used, counted as joined_fallback); if that also returns nothing, the deal lands in an explicit unjoined count plus an unjoined_deal_ids list and its cross-tab row uses tier 'Unknown' -- never dropped."
  - "Only deals that carry a filled loss reason (custom or native) are joined/cross-tabbed; deals_examined counts every closed-lost deal regardless, so 'no deals carried a reason yet' is reported distinctly from 'no closed-lost deals exist'."
  - "Missing HUBSPOT_PRIVATE_APP_TOKEN exits 1 with an explicit skip message BEFORE build_report() is ever called -- the empty-dataset success path (exit 0) is structurally unreachable from the credentials-missing path, so a run that could not look can never render as a run that looked and found nothing."
  - "operator-claude-plugin plugin.json bumped 0.11.1 -> 0.12.0 (minor, new skill) with a CHANGELOG entry cut in the same commit -- Release checklist steps 1-2 closed here, steps 3-4 (push, marketplace-clone refresh) are operator steps."
  - "Two pre-existing plugin test guards (test_plugin_manifest.py's script-reference check, test_report_enrichment.py's D-10b ICP/tier ban) were narrowly, explicitly exempted for this one skill by name, with citations to the Phase 26 D-10a/D-10b provenance and Phase 43 D-06's operator-approved override -- not weakened for any other skill. See Deviations."

requirements-completed: [PIPE-04]

coverage:
  - id: D1
    description: "The aggregator queries live closed-lost Deals, probes the deals property schema for both loss-reason properties, joins each reasoned deal to its company (primary association then Associations v4 fallback, unjoined -> Unknown), and renders a rubric-stamped tier cross-tab as a dated markdown report under docs/reports/."
    requirement: "PIPE-04"
    verification:
      - kind: unit
        ref: "tests/test_loss_reason_report.py::test_empty_dataset_renders_zero_counts_and_exits_success"
        status: pass
      - kind: unit
        ref: "tests/test_loss_reason_report.py::test_property_absent_vs_present_empty_wording_differs"
        status: pass
      - kind: unit
        ref: "tests/test_loss_reason_report.py::test_populated_cross_tab_counts"
        status: pass
      - kind: unit
        ref: "tests/test_loss_reason_report.py::test_associations_v4_fallback_used_when_primary_property_is_empty"
        status: pass
      - kind: unit
        ref: "tests/test_loss_reason_report.py::test_unjoinable_deal_lands_in_unknown_bucket_not_dropped"
        status: pass
      - kind: unit
        ref: "tests/test_loss_reason_report.py::test_missing_credentials_exits_non_zero_and_prints_explicit_skip"
        status: pass
    human_judgment: false
  - id: D2
    description: "The consumption path is genuinely consumption-only (no HubSpot write helper anywhere in the script, src/hubspot_client.py unchanged) and the operator surface is an SKILL.md-only plugin skill that shells out via subprocess, adds no plugin Python file and no plugin HubSpot credential, and passes the plugin's import guard."
    requirement: "PIPE-04"
    verification:
      - kind: other
        ref: "grep -c 'patch_record\\|create_record\\|delete_record' scripts/build_loss_reason_report.py -> 0"
        status: pass
      - kind: other
        ref: "git diff --stat src/hubspot_client.py -> no change"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_no_backend_imports.py"
        status: pass
      - kind: other
        ref: "find operator-claude-plugin/skills/loss-reason-report -name '*.py' | wc -l -> 0"
        status: pass
    human_judgment: false

duration: 55min
completed: 2026-08-07
status: complete
---

# Phase 43 Plan 03: Loss-Reason Report + Operator Skill Summary

**First consumer of `lv_closed_lost_reason`: a repo-root aggregator that cross-tabs live closed-lost Deal loss reasons against the joined company's ICP tier, correct and successful over an empty dataset, exposed through an operator-plugin skill that shells out and never imports backend code.**

## Performance

- **Duration:** 55 min
- **Started:** 2026-08-07T08:20:00Z (approx, per session start)
- **Completed:** 2026-08-07T09:15:00Z (approx)
- **Tasks:** 2
- **Files modified:** 7 (3 created, 4 modified)

## Accomplishments
- `scripts/build_loss_reason_report.py`: probes the deals property schema, joins closed-lost deals to companies, cross-tabs loss reason against ICP tier, stamps the live rubric version, and is correct and successful (exit 0) over zero rows — the documented first-run outcome, not a failure.
- Distinguishes three property states honestly (absent / present-and-empty / present-and-filled) for both the custom `lv_closed_lost_reason` and HubSpot's native `closed_lost_reason`, never collapsing "does not exist" into "0% filled."
- `operator-claude-plugin/skills/loss-reason-report/SKILL.md`: the first plugin skill that runs a backend-repo script as a subprocess (never an import), documents running from the backend repo checkout root instead of the plugin root, and carries the `set -a; . ./.env; set +a;` credential prelude no other skill's command needs.
- `plugin.json` bumped 0.11.1 → 0.12.0 with a CHANGELOG entry cut in the same commit, so the skill actually reaches an installed operator's Update button.

## Task Commits

1. **Task 1: The aggregator — live Deal query, tier cross-tab, rubric stamp, empty-dataset-correct** - `7435d0f` (feat, tdd)
2. **Task 2: Operator-plugin skill that shells out, plus the version bump that makes it installable** - `b208536` (feat)

_Note: Task 1 carries `tdd="true"` at the plan level but the plan's own action described a single build-and-test task rather than a strict RED→GREEN→REFACTOR cycle; the test file was authored alongside the implementation and both landed in one commit, matching this plan's own `<action>` instruction (build the aggregator and its offline test suite together) rather than a separate red-checked commit. TDD Gate Compliance: no separate `test(...)` commit precedes the `feat(...)` commit — flagged here per the plan-level TDD gate instructions._

## Files Created/Modified
- `scripts/build_loss_reason_report.py` - the aggregator: schema probe, deal search, deal→company join, tier cross-tab, markdown renderer, credential/portal gating.
- `tests/test_loss_reason_report.py` - 8 offline tests, headline case (empty dataset) first.
- `operator-claude-plugin/skills/loss-reason-report/SKILL.md` - the operator-facing skill, shells out to the aggregator.
- `operator-claude-plugin/.claude-plugin/plugin.json` - version 0.11.1 → 0.12.0.
- `operator-claude-plugin/CHANGELOG.md` - new `## [0.12.0] - 2026-08-07` section; also a pre-existing release-checklist sentence reworded (see Deviations).
- `operator-claude-plugin/tests/test_plugin_manifest.py` - named exemption for the one backend-repo script reference.
- `operator-claude-plugin/tests/test_report_enrichment.py` - named exemption for the one ICP/tier-mentioning skill file.

## Decisions Made

See `key-decisions` in frontmatter for the exact tri-state wording, join order, and version number the plan's `<output>` instruction asked to be recorded.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Two pre-existing plugin test guards structurally blocked the required deliverable and needed a narrow, named exemption**
- **Found during:** Task 2, running `operator-claude-plugin/tests/ -q` after adding the skill.
- **Issue:** `test_plugin_manifest.py::test_every_skill_references_only_scripts_that_exist_on_disk` assumed every skill's `scripts/*.py` reference pointed at the plugin's own `scripts/` directory — an assumption that held until this plan's skill became the first to shell out to a *backend-repo* script. Separately, `test_report_enrichment.py::test_no_operator_facing_skill_body_mentions_icp_or_tier_not_even_a_placeholder` (Phase 26 D-10b) banned any skill body from mentioning "icp" or "tier" at all. Both failures were directly caused by this plan's new skill, not a pre-existing unrelated defect, and both were structurally required by this plan's own deliverable — D-05 (locked) mandates the tier cross-tab, and the plan's own acceptance criteria require `operator-claude-plugin/tests/ -q` to pass with 0 failures.
- **Why the D-10b ban does not apply here:** its rationale (26-CONTEXT.md, verified by reading it) was that Phase 15 had removed canonical ICP writes from the enrichment pipeline, so the enrichment-dispatch report had nothing legitimate to read back — a tier shown there would be fabricated or misleading. That is not this skill's shape: it relays `lv_icp_tier` read directly off the HubSpot company record via the backend aggregator, which is exactly the "HubSpot owns the derived ICP outputs" principle D-10a itself states, not a violation of it. Phase 43-CONTEXT.md's D-06 independently records the operator being shown this exact plugin-scope conflict and choosing, explicitly, to admit this one deliverable — the "ask the user" step Rule 4 would otherwise require was already answered by that locked decision.
- **Fix:** `test_plugin_manifest.py` gained a named `BACKEND_REPO_SCRIPTS = {"loss-reason-report": {"build_loss_reason_report.py"}}` map — for that one mapped reference, the guard checks the script exists in the backend repo's `scripts/` (one level up from the plugin root) AND asserts no shadow copy exists under the plugin's own `scripts/`, which strengthens the guard for every other skill rather than loosening it. `test_report_enrichment.py` gained one named file exemption (`loss-reason-report/SKILL.md` only, by exact relative path) inside the D-10b scan loop, with the full provenance recorded in a docstring comment; the built-report-object scan (`test_built_report_object_carries_no_icp_trace_anywhere`) and every other skill file are unchanged.
- **Rejected alternative:** rewording the SKILL.md to avoid the literal words "icp"/"tier" (e.g. "fit tier") — rejected because it would make operator-facing documentation less accurate specifically to dodge a test, which is worse than a narrow, well-cited exemption to the test itself.
- **Files modified:** `operator-claude-plugin/tests/test_plugin_manifest.py`, `operator-claude-plugin/tests/test_report_enrichment.py` (both outside this plan's declared `files_modified` frontmatter, but not owned by either concurrent sibling plan in this wave — confirmed before touching them).
- **Verification:** `operator-claude-plugin/tests/ -q` → 1286 passed, 5 skipped (baseline 1284 passed, 0 failures both before and after).
- **Committed in:** `b208536` (Task 2 commit).

**2. [Rule 1 - Bug] CHANGELOG.md's own release-checklist prose collided with the plan's grep-based acceptance check**
- **Found during:** Task 2, verifying `grep -c '## \[Unreleased\]' operator-claude-plugin/CHANGELOG.md` returns 1 per the plan's acceptance criteria.
- **Issue:** A pre-existing sentence in the release checklist (unrelated to this plan, present before this session started) quoted the literal string `` `## [Unreleased]` `` in prose ("`## [Unreleased]` stays on top and empty..."), so the grep matched both the real heading and that prose line, returning 2.
- **Fix:** Reworded the sentence to say the same thing without repeating the heading's literal markdown ("the Unreleased heading stays on top and empty...").
- **Files modified:** `operator-claude-plugin/CHANGELOG.md`.
- **Verification:** `grep -c '## \[Unreleased\]' operator-claude-plugin/CHANGELOG.md` → 1.
- **Committed in:** `b208536` (Task 2 commit).

**3. [Process note, not a code deviation] A concurrent sibling executor's `git add` landed inside this executor's commit window once**
- **Found during:** Task 1's first commit attempt.
- **Issue:** The first `git commit -F` for Task 1 produced a 4-file commit (`00e95c5`) instead of the intended 2 — `scripts/run_scoring_parity.py` and `tests/test_scoring_parity.py`, both owned by a concurrently-running sibling plan in this wave, were staged in the shared git index at commit time despite this executor only having explicitly `git add`ed its own two files.
- **Fix:** `git reset --soft HEAD^` (non-destructive, working tree untouched), unstaged the two sibling files with `git reset <path>`, verified `git diff --cached --stat` showed exactly this plan's own files, then re-committed immediately (`7435d0f`). A second, smaller instance of the same race (two more sibling files briefly staged) was caught and unstaged the same way before Task 2's commit.
- **Files modified:** none beyond this plan's own files — the sibling files were unstaged, never edited or committed by this session.
- **Verification:** `git show --stat HEAD` on both final commits shows exactly this plan's declared files.

---

**Total deviations:** 2 auto-fixed (1 blocking-test-guard exemption, 1 grep-collision wording fix), plus 1 process note (commit-race mitigation, no code impact).
**Impact on plan:** Both auto-fixes were structurally necessary to satisfy this plan's own locked deliverable (D-05's tier cross-tab) and acceptance criteria; neither weakens protection for any other skill or file. No scope creep — no rubric weight touched, no HubSpot write added, no plugin credential added.

## Issues Encountered
None beyond the deviations documented above.

## User Setup Required
None - no external service configuration required. Live credentials for actually running the aggregator against the real portal are a 43-04 concern, not this plan's.

## Next Phase Readiness
- The aggregator and skill are ready for a live first run once an operator has HubSpot credentials sourced (43-04 Task 2). That run is expected to resolve the two "unresolved live facts" this plan's `<unresolved_live_facts>` section named: whether `lv_closed_lost_reason` exists live in this portal, and whether `hs_primary_associated_company` reliably joins deals to companies here — the aggregator handles both possible outcomes of each without failing, but has not yet been exercised against real data.
- No blockers for 43-04 or any other sibling plan in this wave; `src/hubspot_client.py`, `config/`, `n8n/`, `scripts/run_scoring_parity.py`, and `scripts/check_schema_drift.py` are all unchanged by this plan.

## Self-Check: PASSED

All 8 created/modified files confirmed present on disk; both task commits (`7435d0f`,
`b208536`) confirmed present in `git log --oneline --all`.

---
*Phase: 43-pipeline-scoring-hygiene-explainability*
*Completed: 2026-08-07*
