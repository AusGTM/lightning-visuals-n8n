---
phase: 37-enrich-before-ingest
plan: 09
subsystem: release
tags: [release, changelog, semver, live-walk, checkpoint-pending]

requires:
  - phase: 37-enrich-before-ingest
    plan: 01
    provides: "rows envelope, chunk ceiling, AST guard visibility to dispatch_enrichment"
  - phase: 37-enrich-before-ingest
    plan: 02
    provides: "extraction.hold_emailless, write_dispatch_csv's emailless-row raise"
  - phase: 37-enrich-before-ingest
    plan: 03
    provides: "preingest.build_rows_spec/fetch_matches/match_batch/classify_matches"
  - phase: 37-enrich-before-ingest
    plan: 04
    provides: "preingest.apply_match_decisions/merge_enriched/rows_from_table"
  - phase: 37-enrich-before-ingest
    plan: 05
    provides: "preview_enrichment.records_block's rows branch, preingest.render_enriched_preview"
  - phase: 37-enrich-before-ingest
    plan: 06
    provides: "run_manifest.save/load/rows_to_resume"
  - phase: 37-enrich-before-ingest
    plan: 07
    provides: "report.queue_handoff_ids; the automatic lv_enrichment_requested poller handoff"
  - phase: 37-enrich-before-ingest
    plan: 08
    provides: "skills/enrich-before-ingest/SKILL.md, its own contract tests (sealed mid-walk with a batched-table amendment)"
provides:
  - "operator-claude-plugin/CHANGELOG.md's 0.11.0 entry -- the phase's built work described from the SUMMARY files, not the plans' intentions"
  - "operator-claude-plugin/.claude-plugin/plugin.json version 0.10.0 -> 0.11.0, same commit as the CHANGELOG cut"
  - "README.md's Layout skills tree now names enrich-before-ingest/"
  - "max_rows_per_match_request's PROVISIONAL label retired both sides (client config + backend comment), backed by the live 1.46 s/row measurement, value unchanged at 20"
  - "The live walk's own record: 9/9 HELD (no provider email for any director), the CONTAINS_TOKEN and Lusha-cloud closures of Phase 36's two [ASSUMED] items, and a named open observation of the first-arrival truncation risk actually firing once"
affects: []

actuals:
  tokens: 5400
  tasks: 2
  commits: 2

tech-stack:
  added: []
  patterns: []

key-files:
  created: []
  modified:
    - operator-claude-plugin/CHANGELOG.md
    - operator-claude-plugin/.claude-plugin/plugin.json
    - operator-claude-plugin/README.md
    - operator-claude-plugin/config/operator.local.example.json
    - scripts/build_cloud_workflows.py
    - tests/test_match_ceiling_contract.py

key-decisions:
  - "Version bumped 0.10.0 -> 0.11.0 (minor), consistent with 0.9.0/0.10.0's own precedent of treating a new default-flow feature plus a documented breaking behaviour change as a minor bump on this pre-1.0, independently-versioned client -- not a major bump, and not tied to the backend's own milestone number."
  - "README.md's only skill enumeration is the Layout section's directory tree (no separate prose 'Skills' list exists) -- added enrich-before-ingest/ there in the same one-line-per-skill voice, per the plan's own conditional instruction."
  - "max_rows_per_match_request stays at 20 despite measuring far under the assumed 4 s/row (1.46 s/row observed) -- raising the ceiling is a separate deliberate decision the operator did not make, not an automatic consequence of measuring it. Only the PROVISIONAL label is retired, on both sides (client config note + scripts/build_cloud_workflows.py's ENRICH_MAX_PROPOSE_RECORDS comment), mirroring the 37.44 s note's own provisional-to-confirmed promotion."
  - "test_the_match_ceilings_provenance_note_carries_the_provisional_marker was amended (renamed to ..._carries_its_measured_provenance, assertions flipped to require MEASURED + 1.46 present and PROVISIONAL absent) rather than deleted -- the measurement that retires the label is exactly the thing the test now pins, mirroring test_chunk_ceiling_contract.py's own already-confirmed sibling test for the write-path ceiling."

requirements-completed: [INGEST-02, STRUCT-02, PREVIEW-01, DISPATCH-03]

coverage:
  - id: D1
    description: "All four offline gates green at or above their corrected baselines before any release commit: repo pytest, plugin pytest, node (FILE glob), arming grep 0 for every n8n/*.json file. Re-confirmed a second time after the post-walk provenance-note edits."
    requirement: INGEST-02
    verification:
      - kind: unit
        ref: ".venv/bin/python -m pytest -q -- 2151 passed, 6 skipped (pre-walk); 2157 passed, 6 skipped (post-walk, +6 from the amended ceiling test plus 37-08's Task 3 batched-table amendment landing mid-walk)"
        status: pass
      - kind: unit
        ref: ".venv/bin/python -m pytest operator-claude-plugin/tests/ -q -- 1232 passed, 5 skipped (pre-walk); 1238 passed, 5 skipped (post-walk)"
        status: pass
      - kind: unit
        ref: "node --test tests/n8n/*.test.mjs -- 621 pass, unchanged both times"
        status: pass
      - kind: other
        ref: "grep -c 'ALLOW_HUBSPOT_[A-Z_]* = \"true\"' n8n/*.json -- 0 for every file, both times, including the disarmed close AFTER the live walk's writes"
        status: pass
    human_judgment: false
  - id: D2
    description: "The release commit (857e20c) carries both CHANGELOG.md and plugin.json; the version string differs from the previous release (0.10.0 -> 0.11.0); the CHANGELOG entry describes the emailless-row refusal as a breaking behaviour change, not a bug fix; operator-claude-plugin/scratch is empty."
    requirement: STRUCT-02
    verification:
      - kind: other
        ref: "git show --stat 857e20c -- names operator-claude-plugin/.claude-plugin/plugin.json and operator-claude-plugin/CHANGELOG.md"
        status: pass
    human_judgment: false
  - id: D3
    description: "The nine Gold Coast Turf Club directors walk end to end with the deployed backend, and every record that reached HubSpot carries an email. APPROVED by the operator, live, in-session, 2026-08-05: 'approved, 1.46s/row'. Full record in the 'Task 2 Result' section below -- zero records were created (all nine HELD, no provider email exists for any director), which vacuously satisfies the email-on-every-created-record requirement rather than contradicting it."
    requirement: PREVIEW-01
    verification:
      - kind: manual_procedural
        ref: "Live in-session walk against the deployed backend, 2026-08-05 -- operator verdict 'approved, 1.46s/row'"
        status: pass
    human_judgment: true
    rationale: "Task 2 is checkpoint:human-verify with gate=\"blocking\" because it performs real writes (and, in this run, real holds) against a live HubSpot tenant and measures live match latency -- neither is something an offline suite can prove. Recorded here as approved, with the full operator-supplied record, per this plan's own autonomous: false discipline: the executor did not run or judge the walk itself."
  - id: D5
    description: "Named open observation: the documented first-arrival match-response truncation risk fired once, live, during the walk -- a chunk of (row-5, row-6) returned only row-5's verdict; row-6 (Greg Leeson) was missing from the response and was correctly bucketed via the row_id join (37-03's classify_matches walks the ROWS, never the response, specifically so a missing item is detectable rather than silently invisible). The deferred upgrade path (route skip rows back through the waterfall on a subsequent attempt) remains deferred at the operator's discretion -- not actioned by this plan."
    verification:
      - kind: manual_procedural
        ref: "Live walk observation, 2026-08-05 -- reported by the operator as the first live occurrence of the documented risk, correctly handled by classify_matches's existing row_id join, no code change required or made"
        status: pass
    human_judgment: true
    rationale: "This is an observation of correct behaviour under a known, previously-only-documented risk, not a new deliverable to verify against a test -- recorded for the phase's own audit trail per the operator's explicit instruction, with the deferred upgrade path left exactly where it was, at the operator's discretion."
  - id: D4
    description: "Push, merge to master, and marketplace clone refresh -- Task 3's own checkpoint:human-action, operator-run release steps that scripts/deploy_n8n_workflows.py-adjacent tooling and this executor are both denied from performing."
    verification: []
    human_judgment: true
    rationale: "Task 3 is checkpoint:human-action -- git push/merge and the marketplace clone refresh are operator-run steps per the phase's own hard rules; the executor must present exact instructions and never attempt them."

duration: ~25min (Task 1 + post-walk provenance updates)
completed: 2026-08-05
status: checkpoint-pending
---

# Phase 37 Plan 09: Release Prove-Out -- Gates Green, Live Walk Approved, Release Checkpoint Open Summary

**All four offline gates confirmed green at or above baseline both before and after the live walk (repo pytest 2157/6, plugin 1238/5, node 621, arming grep 0); the 0.11.0 release commit (`857e20c`) bumps `plugin.json` and cuts the CHANGELOG describing the emailless-row refusal as the breaking change it is. The nine-directors walk ran live in-session against the deployed backend and was APPROVED by the operator ("approved, 1.46s/row") -- all nine directors HELD, zero HubSpot writes, `max_rows_per_match_request`'s PROVISIONAL label retired on both sides at the measured 1.46 s/row (value kept at 20). Task 3 (push/merge/marketplace refresh) is the one remaining open operator checkpoint.**

## Performance

- **Duration:** ~25 min (Task 1's release commit + post-walk provenance-note updates)
- **Completed:** 2026-08-05
- **Tasks:** 2/3 (Task 1 executed by this agent; Task 2 executed and approved live by the operator, in-session, against the deployed backend -- this agent updated the resulting provenance notes and re-ran gates; Task 3 remains an open `checkpoint:human-action`)
- **Files modified:** 6

## Accomplishments

- Ran all four gates before writing anything, per the plan's own instruction, and recorded the
  exact observed numbers (pre-walk): repo pytest **2151/6**, plugin pytest **1232/5**, node
  **621 pass**, arming grep **0** for every file under `n8n/`.
- Wrote `operator-claude-plugin/CHANGELOG.md`'s `[0.11.0]` entry from the eight 37-01 through
  37-08 SUMMARY files. Names the email gate's RAISE as a breaking change, the two arming phrases
  and why a combined phrase is structurally impossible, the match lane's four outcome groups
  (including `unchecked` as distinct from `unmatched`), the idempotent resume manifest, and the
  automatic `lv_enrichment_requested` poller handoff.
- Bumped `plugin.json`'s `version` `0.10.0` -> `0.11.0` in the same commit as the CHANGELOG entry
  (`857e20c`), and added `enrich-before-ingest/` to README.md's Layout skills tree (its only
  skill enumeration).
- **The live walk ran, in-session, against the deployed backend, and the operator approved it**:
  see "Task 2 Result" below for the full record.
- Post-walk: retired the PROVISIONAL label on `max_rows_per_match_request`'s provenance note in
  both `operator-claude-plugin/config/operator.local.example.json` and
  `scripts/build_cloud_workflows.py`'s `ENRICH_MAX_PROPOSE_RECORDS` comment, backed by the
  measured 1.46 s/row -- the value stays 20 (raising it is a separate decision the operator did
  not make). Amended `tests/test_match_ceiling_contract.py`'s provisional-marker test to pin the
  new measured state instead of deleting it, mirroring `test_chunk_ceiling_contract.py`'s own
  already-confirmed sibling test.
- Re-ran all four gates after the provenance-note edits: repo pytest **2157/6** (+6: the amended
  test file plus 37-08's Task 3 batched-table amendment, which sealed mid-walk), plugin pytest
  **1238/5** (+6), node **621** (unchanged), arming grep **0** for every file -- including the
  disarmed close run explicitly AFTER the live walk's writes, per the walk's own Step 12.

## Task 2 Result: APPROVED, 1.46 s/row -- live walk record

**Operator verdict, verbatim: "approved, 1.46s/row".** Ran live in-session against the deployed
backend, not a rehearsal:

- **Extraction:** 9 directors pulled from the wp-json URL. No emails present on source; none
  invented.
- **Match:** 1 chunk of 9 (the configured ceiling of 20 was never approached). 13.16 s total wall
  clock for the chunk = **1.46 s/row measured**. Groups: auto-matched 0 / proposed 0 / unmatched 9
  / unchecked 0. Two Phase 36 `[ASSUMED]` items closed live: `CONTAINS_TOKEN` proved live (no 400
  response) and Lusha name+company lookup accepted on cloud.
- **Cost preview:** the rows branch rendered ("these rows are not in HubSpot yet"), live provider
  balances shown (Lusha 3930, ZoomInfo 9301, Apollo unknown-by-design), chunk plan 5 chunks of ≤2.
- **Armed enrichment** ("arm the enrichment" spoken, one turn): 48.8 s, 5/5 chunks completed,
  spend ~4-5 ZoomInfo credits + $0.62 Anthropic, 0 Lusha.
- **Enriched preview:** **all nine HELD -- no provider email exists for any director** (a board
  affiliation is not the same thing as a provider-database employer match). Partial finds
  (mobile/jobtitle on rows 1 and 5) were not written anywhere, per the flow's own design. The
  preview stated plainly that nothing had reached HubSpot. **The second arm was correctly
  unreachable** -- zero SEND rows means "arm the upload" never had anything to act on.
- **Step 10 (every created record carries an email):** satisfied vacuously -- zero records were
  created, so the universal claim holds trivially, not by accident.
- **Step 12 (disarmed close):** `grep -c` reported 0 for every file under `n8n/`, run after the
  walk's own writes.
- **Named open observation -- Risk-1 fired live:** the (row-5, row-6) chunk's match response
  carried only row-5's verdict; row-6 (Greg Leeson) was absent from the response entirely. This
  is the first live occurrence of the documented first-arrival match-response truncation risk.
  `preingest.classify_matches` (37-03) walks the ROWS, never the response, specifically so a
  missing item is detectable rather than silently swallowed -- and it was: row-6 bucketed
  correctly (per the row_id join) rather than being dropped. The deferred upgrade path (route
  skipped rows back through the waterfall on a follow-up attempt) remains deferred, at the
  operator's own discretion -- no code change made or needed for this occurrence.
- **37-08 sealed mid-walk**, with the operator's own batched-table amendment landing as 21
  additional contract tests -- accounting for the +6/+6 delta between this plan's pre-walk and
  post-walk gate numbers (37-08's own commits, not this plan's).

## Task Commits

1. **Task 1: all gates green, and the CHANGELOG cut in the same commit as the bump** -
   `857e20c` (release) -- carries `operator-claude-plugin/CHANGELOG.md`,
   `operator-claude-plugin/.claude-plugin/plugin.json`, `operator-claude-plugin/README.md`.
2. **Post-walk: retire the PROVISIONAL label with the measured 1.46 s/row** - (this commit) --
   carries `operator-claude-plugin/config/operator.local.example.json`,
   `scripts/build_cloud_workflows.py`, `tests/test_match_ceiling_contract.py`,
   `.planning/workstreams/plugin-entrypoint/phases/37-enrich-before-ingest/37-09-SUMMARY.md`.

_No plan-metadata commit yet -- Task 3's checkpoint is open; the orchestrator resolves
STATE.md/ROADMAP.md/REQUIREMENTS.md and the final metadata commit once it is answered._

## Files Created/Modified

- `operator-claude-plugin/CHANGELOG.md` -- new `[0.11.0]` entry.
- `operator-claude-plugin/.claude-plugin/plugin.json` -- `version`: `0.10.0` -> `0.11.0`.
- `operator-claude-plugin/README.md` -- Layout section's skills tree gains one line for
  `enrich-before-ingest/`.
- `operator-claude-plugin/config/operator.local.example.json` -- `max_rows_per_match_request`'s
  provenance note: PROVISIONAL retired, measurement recorded (1.46 s/row, 2026-08-05), value
  unchanged at 20.
- `scripts/build_cloud_workflows.py` -- `ENRICH_MAX_PROPOSE_RECORDS`'s comment: mirrors the same
  retirement, same measurement, same unchanged value, promoted the same way the 37.44 s note was.
- `tests/test_match_ceiling_contract.py` -- the provisional-marker test amended (not deleted) to
  pin the new measured state; docstring updated to record the probe landed.

## Decisions Made

- **Version bump: 0.10.0 -> 0.11.0 (minor).** Consistent with this client's own prior practice.
- **README.md's Layout section is the only place that enumerates skills** -- added the new lane
  there.
- **`max_rows_per_match_request` stays at 20**, even though the measured 1.46 s/row is well under
  the assumed 4 s/row that derived it (floor(100 / (1.46*1.25)) ≈ 54) -- raising the ceiling is a
  separate deliberate decision the operator did not make in this walk, not an automatic
  consequence of measuring it. Only the PROVISIONAL label was retired, both sides, per the
  provenance note's own stated discipline ("backend first, always").
- **The provisional-marker test was amended, not deleted**, per the plan's own instruction that
  any test pinning the PROVISIONAL wording be amended WITH the reason inline -- the amendment
  documents exactly which measurement retired the label and when, mirroring the write-path
  ceiling's own already-confirmed sibling test.

## Deviations from Plan

None -- both the release commit and the post-walk provenance updates match the operator's
explicit instructions. Gates were run before and after every round of edits; no regression in
either pass.

## Issues Encountered

- One git-commit heredoc attempt for the release commit failed with a shell quoting error on the
  first try; the retry (one word change, removing an apostrophe inside the single-quoted heredoc)
  succeeded. No production code or plan-scoped file was affected.
- The first draft of the post-walk provenance note used the literal word "PROVISIONAL" inside a
  sentence explaining that the label was retired (e.g. "the PROVISIONAL label is retired"),
  which made the amended test fail its own `"PROVISIONAL" not in notes` assertion -- caught
  immediately by re-running the test, reworded without the literal token, re-verified green.
  Not a deviation from plan intent; a self-correction during the edit itself.

## User Setup Required

None -- Task 3 is the one remaining operator-run checkpoint, described in full below, not
executed by this agent.

## Next Phase Readiness

**Blocked on Task 3's checkpoint** -- `checkpoint:human-action`. This plan is `autonomous: false`;
per explicit instruction this executor presents the exact release steps and does not attempt any
of them.

### Task 3: push, merge to master, refresh the marketplace clone (open)

Operator-run release checklist -- **not automatable, and `scripts/deploy_n8n_workflows.py` and
any equivalent are denied to agents in every form**:

1. Push the current branch.
2. **Merge to master.** The version bump is invisible to the marketplace until master carries
   it -- `0.9.0` shipped with a correct bump sitting on a feature branch and the Update button
   stayed grey until master had it.
3. Refresh the marketplace clone. A plugin reinstall never refreshes it on its own, and a
   same-version reinstall deletes `operator.local.json`:
   ```
   git -C ~/.claude/plugins/marketplaces/lightning-visuals-operator fetch --depth=1 origin master
   git -C ~/.claude/plugins/marketplaces/lightning-visuals-operator reset --hard FETCH_HEAD
   ```
4. **Verify by CONTENT, not by the version string.** Open
   `skills/enrich-before-ingest/SKILL.md` inside the refreshed clone and confirm it is present
   and current -- the version string is hand-written and has been correct while the content
   stayed stale.
5. Confirm the Update button in Claude Desktop offers `0.11.0`.

Do not run any of this against `~/.claude/plugins/` from a script in this repo -- steps 1-5 above
are commands the **operator** runs directly, not something this executor performs.

**Resume by typing** `"released"` **once master carries the bump and the refreshed clone
contains the new skill file**, or describing where it stopped.

---
*Phase: 37-enrich-before-ingest*
*Completed: 2026-08-05 (Tasks 1-2; Task 3 open checkpoint)*

## Self-Check: PASSED

`operator-claude-plugin/CHANGELOG.md`, `operator-claude-plugin/.claude-plugin/plugin.json`,
`operator-claude-plugin/README.md`, `operator-claude-plugin/config/operator.local.example.json`,
`scripts/build_cloud_workflows.py`, and `tests/test_match_ceiling_contract.py` verified present
on disk with the stated edits; commit hash `857e20c` verified present in
`git log --oneline --all`; `plugin.json`'s `version` field verified reading `0.11.0`; post-walk
provenance-note commit verified present after creation below.
