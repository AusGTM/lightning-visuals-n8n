---
phase: 72-enrichment-extras-land-in-hubspot
plan: 07
subsystem: docs-and-release
tags: [todo-triage, plugin-release, changelog, claude-md, uat-gate-spec, documentation-only]

requires:
  - phase: 72-enrichment-extras-land-in-hubspot
    provides: "plans 01-06's shipped behaviour (recency arm, overflow slots, widened ingest
      candidate set, company geo/phone producers) — this plan documents and releases it,
      touching no code"
provides:
  - "The D-71-06 charter todo retired to completed/ with a Resolution section naming the
    three places the shipped answer differs from its original mapping table"
  - "A new triaged design todo for the enrichment-lane/companies-branch property-history gap
    (WINDOWS.md ledger id 29), satisfying CLAUDE.md §31's zero-inbox rule"
  - "operator-claude-plugin 0.49.0 with a CHANGELOG section covering the mobile-header
    behaviour change, LinkedIn dual-write, recency-based refresh, and overflow slots"
  - "CLAUDE.md §17.2.2 as-built delta describing the real recency/TTL promotion arm,
    the overflow slots, and the widened ingest lane's operator-visible consequences"
  - "docs/OPERATOR-AUTONOMOUS-BATCH-UAT.md §6, the D-72-17 seven-step live gate spec plan 08
    will execute"
affects: ["72-08 (runs the D-72-17 gate this plan specifies)"]

actuals:
  tokens: 6037
  tasks: 3
  commits: 3
plan_head_before: 42aa99ff68f49f9987d179f2b553ee4b4b85f935

tech-stack:
  added: []
  patterns:
    - "Documentation-only plan enforced by its own verify step: a git diff --stat over
      src/, n8n/, scripts/, config/, operator-claude-plugin/scripts/ against the base commit
      must be empty — the plan's own prohibition made mechanically checkable, not just stated."

key-files:
  created:
    - .planning/todos/pending/2026-09-12-enrichment-lane-and-companies-branch-have-no-property-history-hop.md
  modified:
    - .planning/todos/completed/2026-09-12-ingest-lane-drops-paid-for-enrichment-extras-map-them-instead.md
    - operator-claude-plugin/.claude-plugin/plugin.json
    - operator-claude-plugin/CHANGELOG.md
    - CLAUDE.md
    - docs/OPERATOR-AUTONOMOUS-BATCH-UAT.md

key-decisions:
  - "The new history-gap todo cites WINDOWS.md ledger id 29 rather than duplicating its
    finding, per the plan's own instruction — CLAUDE.md §31's design-kind triage (owner,
    decision_needed, files) is what makes it a decidable question instead of an open ledger
    row with nowhere to land a ruling."
  - "The D-72-17 gate spec's Step 1 is written as a verify-exists step, not a creation step,
    reflecting the D-72-23 execution-time amendment plan 05 already applied — the sync tool's
    armed form is documented only as a fallback if the live portal has drifted from the undo
    manifest."
  - "CLAUDE.md's new delta is one subsection (§17.2.2), placed immediately after the existing
    §17.2.1 system-correctable clause it extends, rather than split across §17.2 and §29 — the
    plan's own acceptance criteria name a single new subsection, and the promotion-rules tie
    is the closer fit for all three sub-findings (recency arm, overflow slots, widened ingest)."

requirements-completed: [D-72-01, D-72-11, D-72-17, D-72-21]

coverage:
  - id: D1
    description: "The D-71-06 charter todo is retired to completed/ with a Resolution section naming the three places the shipped answer differs from its original mapping table (capped _2 overflow slot per kind, provenance-only verification stamps, companies in scope)"
    requirement: D-72-01
    verification:
      - kind: manual_procedural
        ref: "ls .planning/todos/pending/ | grep -c ingest-lane-drops-paid-for-enrichment-extras (0) + grep -c '^## Resolution' on the completed file (1)"
        status: pass
    human_judgment: false
  - id: D2
    description: "Every pending todo this phase leaves behind is triaged per CLAUDE.md §31 -- scripts/todo_triage.py --check exits clean and the new design todo declares kind + decision_needed + owner + files"
    verification:
      - kind: unit
        ref: "scripts/todo_triage.py --check (exit 0)"
        status: pass
      - kind: unit
        ref: "tests/test_todo_triage.py (2 passed)"
        status: pass
    human_judgment: false
  - id: D3
    description: "The plugin ships as a visible new version -- plugin.json bumped from 0.48.0 to 0.49.0 with a matching CHANGELOG [0.49.0] section"
    verification:
      - kind: unit
        ref: "grep -c '\"version\": \"0.49.0\"' plugin.json (1); grep -c '^## \\[0.49.0\\]' CHANGELOG.md (1)"
        status: pass
      - kind: unit
        ref: ".venv/bin/python -m pytest operator-claude-plugin/tests/ (3068 passed, 5 skipped)"
        status: pass
    human_judgment: false
  - id: D4
    description: "The CHANGELOG's [0.49.0] section states, in the operator's own words, that a 'Mobile' spreadsheet column now lands in mobilephone instead of phone -- a behaviour change for every existing operator template"
    requirement: D-72-03
    verification:
      - kind: unit
        ref: "grep -A 40 '^## \\[0.49.0\\]' CHANGELOG.md | grep -c -i mobile (6)"
        status: pass
    human_judgment: false
  - id: D5
    description: "D-72-17/D-72-21: the live gate this phase's one armed send will run is written down as an executable, ordered spec before plan 08 runs it, including the D-72-23 verify-exists correction to property creation and the widened deploy scope"
    requirement: D-72-17
    verification:
      - kind: unit
        ref: "grep -c 'D-72-17\\|ALLOW_HUBSPOT_PROPERTY_WRITES\\|lv_mobilephone_2' docs/OPERATOR-AUTONOMOUS-BATCH-UAT.md (5); grep -c 'hand-delete' (4)"
        status: pass
    human_judgment: false
  - id: D6
    description: "CLAUDE.md carries an as-built delta for this phase in the established style, so §29's never-write list and §17.2's promotion rules read true against the shipped code, naming which lane carries the property-history fetch and which does not"
    verification:
      - kind: unit
        ref: "grep -c 'As-built delta' CLAUDE.md (10, up from 9); grep -c 'D-72-06\\|D-72-11\\|D-72-03' CLAUDE.md (3)"
        status: pass
      - kind: other
        ref: "git diff --stat 42aa99ff..HEAD -- src/ n8n/ scripts/ config/ operator-claude-plugin/scripts/ (empty -- no code touched by this doc-only plan)"
        status: pass
    human_judgment: false

duration: 45min
completed: 2026-09-12
status: complete
---

# Phase 72 Plan 07: Enrichment Extras Land in HubSpot — Paperwork, Release, and the Live Gate Spec Summary

**The D-71-06 charter todo is retired with its resolution, the one gap this phase leaves is a triaged design decision, the plugin ships as `0.49.0` with the "Mobile" header behaviour change called out, CLAUDE.md gets an as-built delta describing what plans 01-06 actually shipped, and the operator now has a seven-step ordered gate spec instead of eight plan files to reconstruct one from.**

## Performance

- **Duration:** ~45 min
- **Tasks:** 3
- **Files modified:** 6 (1 created, 5 modified)

## Accomplishments

- Moved `.planning/todos/pending/2026-09-12-ingest-lane-drops-paid-for-enrichment-extras-map-them-instead.md` to `completed/` with a `## Resolution` section naming Phase 72 (plans 01-06 by name) and the three places the shipped answer differs from the todo's own original mapping table: overflow capped at one `_2` slot per kind (not open-ended), verification stamps live in provenance JSON only (not new per-field properties, and `hs_additional_emails` turned out to be an enumeration so the second-email write was never built), and companies are in scope alongside contacts.
- Filed `.planning/todos/pending/2026-09-12-enrichment-lane-and-companies-branch-have-no-property-history-hop.md` (`kind: design`, `decision_needed`, `owner: operator`) for the gap plan 04 recorded (WINDOWS.md ledger id 29): the enrichment lane's contacts branch and the companies branch have no `propertiesWithHistory` hop, so `industry`/enrichment-lane `jobtitle` recency stay unobservable. Confirmed all five pre-existing "Reviewed Todos (not folded)" from `72-CONTEXT.md` are untouched.
- Bumped `operator-claude-plugin/.claude-plugin/plugin.json` from `0.48.0` to `0.49.0` and added a matching `## [0.49.0]` CHANGELOG section, written for the operator: enrichment extras now reach a created contact, the "Mobile" header now lands in `mobilephone` not `phone` (with the previous behaviour stated explicitly), LinkedIn's dual write, create-time provider-wins with the CSV value recorded rather than discarded, the phone/mobile overflow slot, a held row keeping its geo/seniority/persona, the `jobtitle` refresh window, and a note that the release pairs with a backend workflow deploy.
- Appended CLAUDE.md §17.2.2, an as-built delta covering three things §17.2/§29 no longer described correctly: the real recency/TTL promotion arm now implemented in all three merge engines (D-72-06/07/08/09), naming which lane carries the property-history fetch (contact ingest, via the new `HubSpot Contact History` node) and which does not (the enrichment lane's contacts branch and the companies branch — the gap the new todo tracks); the three overflow-slot properties (D-72-11), capped at one `_2` slot per kind with no `_3` ever; and the widened ingest lane (D-72-01..04), including the `firstname`/`lastname`/`company` update-path consequence plan 01 recorded.
- Added a D-72-17 gate section (`docs/OPERATOR-AUTONOMOUS-BATCH-UAT.md` §6) as seven ordered steps the operator runs: verify (not create) the three overflow-slot properties per D-72-23's amendment; regenerate/deploy/bounce every changed workflow disarmed per D-72-21's widened scope; one armed single-record send (referencing the Busteed/ATC record this phase's charter names); re-read the created contact for `mobilephone`/`hs_linkedin_url`/`lv_linkedin_url`/geo; one UPDATE-row non-clobber check including the firstname/lastname/company consequence; recording how `hs_additional_emails` behaved; and hand-deleting the created contact. Named both env flags (`ALLOW_HUBSPOT_PROPERTY_WRITES`, `ALLOW_N8N_ARM`) and the arm/disarm rule (the bounce script exits 1 while armed).

## Task Commits

Each task was committed atomically (`type="auto"`, no TDD):

1. **Task 1: Retire the charter todo, file the history gap, leave the queue triaged** - `f941b0ac` (docs)
2. **Task 2: Ship the plugin as a visible new version, with the alias flip called out** - `7f7b1f4d` (docs)
3. **Task 3: CLAUDE.md as-built delta and the D-72-17 gate spec** - `dc3ac3cf` (docs)

**Plan metadata:** this commit (SUMMARY + STATE + ROADMAP + REQUIREMENTS).

## Files Created/Modified

- `.planning/todos/pending/2026-09-12-enrichment-lane-and-companies-branch-have-no-property-history-hop.md` — new. `kind: design`, cites WINDOWS.md id 29, names the decision (add a history hop to those two lanes, or accept `lv_<field>_verified_at` as a narrower substitute).
- `.planning/todos/completed/2026-09-12-ingest-lane-drops-paid-for-enrichment-extras-map-them-instead.md` — moved from `pending/`, `## Resolution` section appended.
- `operator-claude-plugin/.claude-plugin/plugin.json` — `"version": "0.49.0"`.
- `operator-claude-plugin/CHANGELOG.md` — `## [0.49.0]` section.
- `CLAUDE.md` — `### 17.2.2 As-built delta` subsection appended after §17.2.1.
- `docs/OPERATOR-AUTONOMOUS-BATCH-UAT.md` — `## 6. Phase 72 gate (D-72-17)` section appended.

## Decisions Made

- **The history-gap todo cites WINDOWS.md id 29 rather than restating its finding** — the todo's own body adds the triage fields (`kind`, `decision_needed`, `owner`, `files`) the ledger row itself has no room for, per the plan's explicit instruction to reference, not duplicate.
- **The D-72-17 gate spec's Step 1 is a verify-exists step, not a creation step** — this reflects D-72-23's execution-time amendment (plan 05 already created the three overflow-slot properties live), which plan 07's own read_first context flagged explicitly; the armed sync-tool form is documented as a fallback for portal drift only.
- **CLAUDE.md's delta landed as one subsection (§17.2.2), not split across §17.2/§29** — the plan's acceptance criteria name a single new subsection, and all three sub-findings (recency arm, overflow slots, widened ingest) tie most directly to the promotion-rules section they extend.

## Deviations from Plan

None - plan executed exactly as written. All three tasks' `<verify>` commands passed on the first attempt; no auto-fixes, no architectural questions, no blocking-human checkpoints were raised during this plan's own execution.

## Issues Encountered

None.

## Known Stubs

None — every artifact this plan produces (the retired todo, the new todo, the plugin release, the CLAUDE.md delta, the gate spec) is a complete, checked-in document; nothing here defers work to a later plan except the history-hop gap, which is itself the artifact this plan's Task 1 exists to file.

## User Setup Required

None — no external service configuration required. This plan touches no `src/`, `n8n/`, `scripts/`, `config/` or `operator-claude-plugin/scripts/` file (confirmed empty by `git diff --stat` against the plan's own base commit); nothing was armed, deployed, or bounced; no live HubSpot or n8n call was made.

## Next Phase Readiness

- Plan 08 has an executable, ordered D-72-17 gate spec to run rather than reconstructing one from eight plan files — including the widened D-72-21 deploy scope and the D-72-23 verify-exists correction.
- The plugin's `0.49.0` release is committed; per the release checklist in `operator-claude-plugin/CHANGELOG.md`, pushing to `master` and refreshing the marketplace clone remain the operator's own steps, outside this plan's scope.
- The enrichment-lane/companies-branch history-hop gap is now a triaged, decidable question (`.planning/todos/pending/2026-09-12-enrichment-lane-and-companies-branch-have-no-property-history-hop.md`) rather than an untracked residual — ready for a future phase's planning to pick up if the operator rules on it.
- No blockers.

## Self-Check: PASSED

- `[ -f .planning/todos/pending/2026-09-12-enrichment-lane-and-companies-branch-have-no-property-history-hop.md ]` → FOUND
- `[ -f .planning/todos/completed/2026-09-12-ingest-lane-drops-paid-for-enrichment-extras-map-them-instead.md ]` → FOUND
- `[ ! -f .planning/todos/pending/2026-09-12-ingest-lane-drops-paid-for-enrichment-extras-map-them-instead.md ]` → CONFIRMED (moved)
- `git log --oneline --all | grep -q f941b0ac` → FOUND
- `git log --oneline --all | grep -q 7f7b1f4d` → FOUND
- `git log --oneline --all | grep -q dc3ac3cf` → FOUND
- All plan-level `<verification>` commands re-run and passing: `scripts/todo_triage.py --check` (exit 0); `.venv/bin/python -m pytest -q tests/ operator-claude-plugin/tests/` (4947 passed, 154 skipped); `node --test tests/n8n/*.test.mjs` (1167/1167); `git diff --stat 42aa99ff..HEAD -- src/ n8n/ scripts/ config/ operator-claude-plugin/scripts/` (empty).

---
*Phase: 72-enrichment-extras-land-in-hubspot*
*Completed: 2026-09-12*
