---
phase: 37-enrich-before-ingest
plan: 09
subsystem: release
tags: [release, changelog, semver, checkpoint-pending]

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
    provides: "skills/enrich-before-ingest/SKILL.md, its own contract tests"
provides:
  - "operator-claude-plugin/CHANGELOG.md's 0.11.0 entry -- the phase's built work described from the SUMMARY files, not the plans' intentions"
  - "operator-claude-plugin/.claude-plugin/plugin.json version 0.10.0 -> 0.11.0, same commit as the CHANGELOG cut"
  - "README.md's Layout skills tree now names enrich-before-ingest/"
affects: []

actuals:
  tokens: 4200
  tasks: 1
  commits: 1

tech-stack:
  added: []
  patterns: []

key-files:
  created: []
  modified:
    - operator-claude-plugin/CHANGELOG.md
    - operator-claude-plugin/.claude-plugin/plugin.json
    - operator-claude-plugin/README.md

key-decisions:
  - "Version bumped 0.10.0 -> 0.11.0 (minor), consistent with 0.9.0/0.10.0's own precedent of treating a new default-flow feature plus a documented breaking behaviour change as a minor bump on this pre-1.0, independently-versioned client -- not a major bump, and not tied to the backend's own milestone number."
  - "README.md's only skill enumeration is the Layout section's directory tree (no separate prose 'Skills' list exists) -- added enrich-before-ingest/ there in the same one-line-per-skill voice, per the plan's own conditional instruction."

requirements-completed: [INGEST-02, STRUCT-02, PREVIEW-01, DISPATCH-03]

coverage:
  - id: D1
    description: "All four offline gates green at or above their corrected baselines before any release commit: repo pytest 2151/6, plugin pytest 1232/5, node 621 (FILE glob), arming grep 0 for every n8n/*.json file."
    requirement: INGEST-02
    verification:
      - kind: unit
        ref: ".venv/bin/python -m pytest -q -- 2151 passed, 6 skipped"
        status: pass
      - kind: unit
        ref: ".venv/bin/python -m pytest operator-claude-plugin/tests/ -q -- 1232 passed, 5 skipped"
        status: pass
      - kind: unit
        ref: "node --test tests/n8n/*.test.mjs -- 621 pass"
        status: pass
      - kind: other
        ref: "grep -c 'ALLOW_HUBSPOT_[A-Z_]* = \"true\"' n8n/*.json -- 0 for every file"
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
    description: "The nine Gold Coast Turf Club directors walk end to end with the released plugin, and every record that reaches HubSpot carries an email. This is Task 2's own checkpoint:human-verify (gate=blocking) and is not machine-verifiable -- it requires a live HubSpot tenant, a live Cloudflare-backed match/enrich round trip, and a human judging whether the skill's prose reads as intended in a real conversation."
    verification: []
    human_judgment: true
    rationale: "Task 2 is explicitly checkpoint:human-verify with gate=\"blocking\" because it performs real writes to a live HubSpot tenant and measures live match latency -- neither is something an offline suite can prove, and this plan's own autonomous: false setting means the executor stops here rather than self-approving, per explicit instruction."
  - id: D4
    description: "Push, merge to master, and marketplace clone refresh -- Task 3's own checkpoint:human-action, operator-run release steps that scripts/deploy_n8n_workflows.py-adjacent tooling and this executor are both denied from performing."
    verification: []
    human_judgment: true
    rationale: "Task 3 is checkpoint:human-action -- git push/merge and the marketplace clone refresh are operator-run steps per the phase's own hard rules; the executor must present exact instructions and never attempt them."

duration: ~15min (Task 1 only)
completed: 2026-08-05
status: checkpoint-pending
---

# Phase 37 Plan 09: Release Prove-Out -- Gates Green, CHANGELOG Cut, Two Operator Checkpoints Open Summary

**All four offline gates confirmed green at or above baseline (repo pytest 2151/6, plugin 1232/5, node 621, arming grep 0); the 0.11.0 release commit (`857e20c`) bumps `plugin.json` and cuts the CHANGELOG in the same commit, describing the emailless-row refusal as the breaking change it is. Task 2 (the live nine-directors walk) and Task 3 (push/merge/marketplace refresh) are both open operator checkpoints -- per this plan's own `autonomous: false`, the executor stops here rather than attempting either.**

## Performance

- **Duration:** ~15 min (Task 1 only)
- **Completed:** 2026-08-05
- **Tasks:** 1/3 (Task 2 is an open `checkpoint:human-verify`, Task 3 an open `checkpoint:human-action` -- neither executed by this agent)
- **Files modified:** 3

## Accomplishments

- Ran all four gates before writing anything, per the plan's own instruction, and recorded the
  exact observed numbers:
  - `.venv/bin/python -m pytest -q` -> **2151 passed, 6 skipped** (baseline: >= 2151/6)
  - `.venv/bin/python -m pytest operator-claude-plugin/tests/ -q` -> **1232 passed, 5 skipped**
    (baseline: >= 1232/5)
  - `node --test tests/n8n/*.test.mjs` -> **621 pass** (FILE glob only; baseline: >= 621)
  - `grep -c 'ALLOW_HUBSPOT_[A-Z_]* = "true"' n8n/*.json` -> **0** for every one of the 8 files
    under `n8n/`
  All four at or above baseline; none was skipped or adjusted to match a lower observed number.
- Wrote `operator-claude-plugin/CHANGELOG.md`'s `[0.11.0]` entry from the eight 37-01 through
  37-08 SUMMARY files, not from the plans' stated intentions. It names, at minimum: the email
  gate at `write_dispatch_csv` and that it now RAISES on an emailless row (called out explicitly
  as a **breaking change**, not a bug fix, since a blank-email row was never reaching a real
  HubSpot record in the first place); the two arming phrases and why a combined phrase is
  structurally impossible (the enriched preview must sit between them); the match lane's four
  outcome groups by name, including `unchecked` as distinct from `unmatched`; the run manifest's
  idempotent resume (never re-spends credit on an already-finished row); and the automatic
  `lv_enrichment_requested` poller handoff 37-07's checkpoint resolved to (option-b, no client
  action, no third arming phrase).
- Recorded the deliberate test flip explicitly in the CHANGELOG's own `### Test coverage`
  section, in the same words as the SUMMARY: the extraction round-trip case that used to assert
  an emailless row was written now asserts the refusal instead.
- Bumped `operator-claude-plugin/.claude-plugin/plugin.json`'s `version` from `0.10.0` to
  `0.11.0` in the **same commit** as the CHANGELOG entry (`857e20c`), confirmed by
  `git show --stat` naming both files.
- `operator-claude-plugin/README.md`'s "Layout" section is the file's only skill enumeration (a
  directory tree under `skills/`, one line per skill, no separate prose skills list exists) --
  added `enrich-before-ingest/` there in the same one-line voice as its neighbours.
- Re-ran all four gates after making the CHANGELOG/version/README edits, confirming no
  regression (identical numbers to the pre-edit run) before committing.
- `git status --short operator-claude-plugin/scratch` -- empty.

## Task Commits

1. **Task 1: all gates green, and the CHANGELOG cut in the same commit as the bump** -
   `857e20c` (release) -- carries `operator-claude-plugin/CHANGELOG.md`,
   `operator-claude-plugin/.claude-plugin/plugin.json`, `operator-claude-plugin/README.md`.

_No plan-metadata commit yet -- Task 2's checkpoint is open; the orchestrator resolves
STATE.md/ROADMAP.md/REQUIREMENTS.md and the final metadata commit once it is answered._

## Files Created/Modified

- `operator-claude-plugin/CHANGELOG.md` -- new `[0.11.0]` entry: the enrich-before-ingest skill,
  the two-arm design and why it cannot collapse, the four match outcome groups, the idempotent
  resume manifest, the automatic poller handoff, and the emailless-row breaking change with its
  own test-flip note.
- `operator-claude-plugin/.claude-plugin/plugin.json` -- `version`: `0.10.0` -> `0.11.0`.
- `operator-claude-plugin/README.md` -- Layout section's skills tree gains one line for
  `enrich-before-ingest/`.

## Decisions Made

- **Version bump: 0.10.0 -> 0.11.0 (minor).** Consistent with this client's own prior practice
  (0.8.0 -> 0.9.0 for the name-split feature, 0.9.0 -> 0.10.0 for the URL structured-fallback
  feature) of treating a new default-flow feature plus a documented breaking behaviour change as
  a minor bump on a pre-1.0, independently-versioned client -- not tied to the backend's own
  milestone number, per the CHANGELOG's own stated versioning model.
- **README.md's Layout section is the only place that enumerates skills** -- there is no
  separate prose "Skills" section; the directory-tree listing under `skills/` is it. Added the
  new lane there rather than inventing a new enumeration section, per the plan's own conditional
  ("update only if it enumerates the plugin's skills").

## Deviations from Plan

None -- Task 1 executed exactly as written. Gates were run before any file was edited, per the
plan's own instruction, and re-run after editing to confirm no regression; both runs produced
identical numbers.

## Issues Encountered

One git-commit heredoc attempt failed with a shell quoting error (`unexpected EOF while looking
for matching`) on the first try; the retry (same message, one word change: `"backend's own"` ->
`"backend existing"`, removing an apostrophe inside the single-quoted heredoc) succeeded. Not
logged as a Rule 1/2/3 deviation -- no production code or plan-scoped file was affected, and the
commit that landed carries the intended content and file set.

## User Setup Required

None -- Task 2 and Task 3 are both operator-run checkpoints, described in full below, not
executed by this agent.

## Next Phase Readiness

**Blocked on Task 2's checkpoint** -- `checkpoint:human-verify`, `gate="blocking"`. This plan is
`autonomous: false`; per explicit instruction this executor stops here and returns the structured
checkpoint state rather than self-approving or attempting the live walk.

### Task 2: walk the nine directors end to end (open)

A human needs to walk the nine Gold Coast Turf Club directors end to end with the **released**
plugin (version `0.11.0`, once Task 3's release steps have landed it where the operator can
install it):

1. Extract the nine directors from their board page -- nine rows, names/roles/company, no
   emails.
2. Ask for the enrich-first flow. Confirm step 1 states the two-arm warning up front, without
   yet naming either phrase.
3. Confirm the match step reports four groups by name, and anything it could not look up is
   `unchecked`, never `unmatched`.
4. Confirm each proposal is one per turn, showing the candidate's own fields beside the question;
   confirm a batched "yes" to two at once is not accepted.
5. Read the cost preview -- confirm it prices the unmatched set only, not all nine.
6. Say "arm the enrichment". Let it run.
7. **Read the enriched preview carefully.** For each row: what came in, what enrichment added,
   SEND or HELD. Confirm every held row is named with a reason and that nothing has reached
   HubSpot yet.
8. Say "arm the upload". Confirm a **second**, distinct arming prompt is required even though the
   first arm happened earlier in the same conversation.
9. Read the backend report, then confirm held rows are restated **after** it.
10. **In HubSpot, check every record this run created -- every one must carry an email.** If any
    does not, the phase has not met its definition of done.
11. Record the wall-clock time the match step took per row -- this replaces
    `max_rows_per_match_request`'s PROVISIONAL value (currently `20`, derived by regex from the
    backend's `ENRICH_MAX_PROPOSE_RECORDS` constant, never independently measured). If the walk
    does not produce a usable measurement, say so and the PROVISIONAL label stays as-is in
    `operator.local.example.json`.
12. Run the disarmed close: `grep -c 'ALLOW_HUBSPOT_[A-Z_]* = "true"' n8n/*.json` must report 0
    across every file.

**Resume by typing** `"approved"` **plus the measured per-row match latency**, or describing
which step behaved differently from the above.

### Task 3: push, merge to master, refresh the marketplace clone (not yet reached)

Once Task 2 is approved, this operator-run release checklist follows -- **not automatable, and
`scripts/deploy_n8n_workflows.py` and any equivalent are denied to agents in every form**:

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
*Completed: 2026-08-05 (Task 1 only; Tasks 2-3 open checkpoints)*

## Self-Check: PASSED

`operator-claude-plugin/CHANGELOG.md`, `operator-claude-plugin/.claude-plugin/plugin.json`, and
`operator-claude-plugin/README.md` verified present on disk with the stated edits; commit hash
`857e20c` verified present in `git log --oneline --all`; `plugin.json`'s `version` field verified
reading `0.11.0`.
