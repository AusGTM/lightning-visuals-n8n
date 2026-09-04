---
phase: 59-frictionless-write-path
plan: 07
subsystem: enrichment
tags: [resolve-and-propose, d-59-08, chunking, dispatch, gate-inventory, plugin-release]

requires:
  - phase: 59-frictionless-write-path (59-06)
    provides: "enrichment.RecordSpecError.resolvable — the resolve-and-propose payload for GATE-02..GATE-05, built but not yet wired to any operator-visible surface"
provides:
  - "chunking.ChunkResult.resolvable — the gate's resolvable tuple carried through dispatch_plan"
  - "dispatch_plan's RecordSpecError handler relays the gate's own message instead of a generic placeholder"
  - "enrich-records/SKILL.md and enrich-before-ingest/SKILL.md both instruct relaying a resolvable proposal to the operator"
  - "59-GATE-INVENTORY.md's GATE-02..GATE-05 delivery claim corrected to match what actually ships"
affects: [59-frictionless-write-path, enrichment-lane]

actuals:
  tokens: 5437
  tasks: 3
  commits: 2

tech-stack:
  added: []
  patterns:
    - "Exception handler binds `as e` and threads `str(e)` + `getattr(e, 'resolvable', ())` onto a result object, instead of substituting a placeholder — spec-sourced refusal text is safe to relay because it predates any request, unlike transport-sourced text (T-25-17)."

key-files:
  created: []
  modified:
    - operator-claude-plugin/scripts/chunking.py
    - operator-claude-plugin/tests/test_chunking.py
    - operator-claude-plugin/skills/enrich-records/SKILL.md
    - operator-claude-plugin/skills/enrich-before-ingest/SKILL.md
    - operator-claude-plugin/.claude-plugin/plugin.json
    - operator-claude-plugin/CHANGELOG.md
    - .planning/phases/59-frictionless-write-path/59-GATE-INVENTORY.md

key-decisions:
  - "ChunkResult.resolvable defaults to an empty tuple, never None, mirroring RecordSpecError.resolvable exactly so a caller iterates it unconditionally on every result including successes and transport failures."
  - "The generic placeholder string is deleted outright, not kept as a fallback for an empty resolvable — a RecordSpecError always carries a message the gate wrote, which is strictly better than one this module would invent."
  - "ChunkResult's T-25-17 docstring is amended in place (never silently overridden) to record why carrying RecordSpecError.resolvable is not a breach: the exception is raised before any request exists, and its text is composed from the operator's own record spec, never transport/response/config values."
  - "Task 1 and Task 2 land in one commit per the plan's release rule (a plugin-touching commit must carry its version bump and CHANGELOG entry in the same commit); Task 3's planning-document correction stays a separate commit with no bump."

requirements-completed: []

coverage:
  - id: D1
    description: "A GATE-02 people spec driven through plan_chunks -> dispatch_plan yields outcome.results[0] carrying the gate's own message (not a generic placeholder) and its non-empty resolvable tuple, with the refusal happening before any transport call."
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_chunking.py#test_a_gate_02_person_spec_carries_the_gates_own_message_through_dispatch"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_chunking.py#test_a_gate_02_refusal_never_reaches_the_transport"
        status: pass
    human_judgment: false
  - id: D2
    description: "Every ChunkResult carries a resolvable tuple unconditionally — () for a transport-reason failure, never None — and D-13's failed_batch re-send contract is unchanged for a spec-refused chunk."
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_chunking.py#test_a_transport_failure_still_carries_an_empty_resolvable_tuple"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_chunking.py#test_a_refused_gate_02_chunk_still_lands_in_failed_batch"
        status: pass
    human_judgment: false
  - id: D3
    description: "Both enrich-records/SKILL.md (step 9) and enrich-before-ingest/SKILL.md (dispatch section) instruct relaying a non-empty resolvable entry as a proposal naming its resolution_sources value, with explicit operator-confirms-first language, rather than reporting a dead end."
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_enrich_skill_contract.py (full file, 0 pins broken)"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_enrich_before_ingest_skill_contract.py (full file, 0 pins broken)"
        status: pass
    human_judgment: false
  - id: D4
    description: "Plugin released at 0.26.0 with a matching CHANGELOG entry in the same commit as the fix."
    verification:
      - kind: other
        ref: "grep -c '\"version\": \"0.26.0\"' operator-claude-plugin/.claude-plugin/plugin.json (returns 1); git show --stat d13a2fd lists plugin.json and CHANGELOG.md alongside the skill/script files"
        status: pass
    human_judgment: false
  - id: D5
    description: "59-GATE-INVENTORY.md's GATE-02..GATE-05 Owner cells and closing paragraph name 59-07 as completing delivery, and GATE-01/GATE-06 rows are byte-identical to before."
    verification:
      - kind: other
        ref: "grep -c '59-07' .planning/phases/59-frictionless-write-path/59-GATE-INVENTORY.md (7); git diff on the file shows no GATE-01 or GATE-06 table row edited"
        status: pass
    human_judgment: false

duration: 25min
completed: 2026-08-29
status: complete
---

# Phase 59 Plan 07: Carry GATE-02..GATE-05's resolvable payload through dispatch_plan Summary

**`chunking.dispatch_plan`'s `RecordSpecError` handler now relays the gate's own message and its `resolvable` tuple instead of a generic placeholder — closing the one severed integration link that kept GATE-02 through GATE-05's D-59-08 resolve-and-propose payload from ever reaching the operator.**

## Performance

- **Duration:** 25 min
- **Started:** 2026-08-29T00:00:00Z (approx, gap-closure spawn)
- **Completed:** 2026-08-29
- **Tasks:** 3
- **Files modified:** 7

## Accomplishments
- `ChunkResult` gains a `resolvable` field (default `()`, never `None`); `dispatch_plan`'s `except enrichment.RecordSpecError:` now binds the exception and carries `str(e)` + `e.resolvable` onto the result, deleting the fixed placeholder string that was substituted before.
- A new integration test drives `chunking.plan_chunks` → `chunking.dispatch_plan` for GATE-02's own example (a named person with no email, no LinkedIn URL, no lastname+company) — the exact path that was untested before this plan, since every prior `.resolvable` test called `enrichment.build_envelope` directly.
- Both `enrich-records/SKILL.md` (step 9) and `enrich-before-ingest/SKILL.md` (the dispatch section) now instruct relaying a non-empty `resolvable` entry as a proposal — naming its `detail` and which `resolution_sources` value it claims — with explicit "Claude proposes, the operator confirms" language.
- `59-GATE-INVENTORY.md`'s GATE-02..GATE-05 Owner cells and closing paragraph are corrected: 59-06 built the payload, but delivery — the payload actually reaching the operator — was completed by this gap-closure plan.
- Plugin released at 0.26.0 with a CHANGELOG entry describing the severed payload and its repair, in the same commit as the code fix.

## Task Commits

Each task was committed atomically (Tasks 1+2 folded into one commit per the plan's release rule):

1. **Task 1 + Task 2: Carry the resolvable payload through dispatch_plan; relay it from both skills; release 0.26.0** - `d13a2fd` (fix)
2. **Task 3: Correct 59-GATE-INVENTORY.md's GATE-02..GATE-05 delivery claims** - `736cf4e` (docs)

**Plan metadata:** committed alongside STATE.md/ROADMAP.md updates (see final commit).

## Files Created/Modified
- `operator-claude-plugin/scripts/chunking.py` - `ChunkResult.resolvable` field; `RecordSpecError` handler binds `as e` and threads message + resolvable; T-25-17 docstring amended to record the distinction
- `operator-claude-plugin/tests/test_chunking.py` - 4 new integration tests driving `plan_chunks` → `dispatch_plan`
- `operator-claude-plugin/skills/enrich-records/SKILL.md` - step 9 extended to relay a resolvable proposal
- `operator-claude-plugin/skills/enrich-before-ingest/SKILL.md` - dispatch section extended, in this file's own voice
- `operator-claude-plugin/.claude-plugin/plugin.json` - 0.25.0 → 0.26.0
- `operator-claude-plugin/CHANGELOG.md` - 0.26.0 entry describing the severed payload and its repair
- `.planning/phases/59-frictionless-write-path/59-GATE-INVENTORY.md` - GATE-02..GATE-05 Owner cells + closing paragraph corrected; GATE-01/GATE-06 untouched

## Decisions Made
- `resolvable` defaults to an empty tuple, never `None`, on `ChunkResult` — mirrors `RecordSpecError.resolvable` exactly so a caller (or the skills relaying `outcome.results`) can iterate it unconditionally on every result, success or failure, spec-refused or transport-refused.
- The generic placeholder (`"this chunk could not be turned into a request"`) is deleted, not retained as a fallback for an empty `resolvable` — a `RecordSpecError` always carries a message the gate wrote.
- `ChunkResult`'s T-25-17 docstring is amended in place, never silently overridden, to record that admitting a `RecordSpecError` message is not a widening of the "carries nothing from config" rule: the exception is raised by `build_envelope` before any request is built, from the operator's own spec, never from transport/response/config values.
- Task 1 and Task 2 land in one commit (the per-commit release rule: a plugin-touching commit must carry its version bump and CHANGELOG entry in the same commit) — accomplished by leaving Task 1's changes staged-but-uncommitted until Task 2 completed, rather than amending or rebasing.

## Deviations from Plan

None - plan executed exactly as written. No pins in `test_enrich_skill_contract.py` or `test_enrich_before_ingest_skill_contract.py` targeted the paragraphs edited in Task 2, so no test-file edits were needed there (the plan anticipated this as a possibility, not a certainty).

## Issues Encountered
- The first commit attempt for Task 3 (a heredoc-based `git commit -m "$(cat <<'EOF' ...)"`) hit a bash parse error (`unexpected EOF while looking for matching ''`) for unclear reasons given no unmatched quote was visible in the message text. Worked around by writing the message to a scratch file and using `git commit -F`, which succeeded cleanly. No repository state was affected — the failed attempt made no commit.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- GATE-02 through GATE-05 now genuinely reach the operator through the documented `enrich-records`/`enrich-before-ingest` dispatch flow — D-59-08's core promise (resolve-and-propose, not refuse-and-stop) holds for all six converted gates.
- `59-VERIFICATION.md`'s gap 1 (D-59-08, GATE-02..GATE-05) is closed by this plan. Gaps 2-4 (D-59-07's concurrent-writer safety, the `WrittenRecordsError` propagation defect, and the single-lane grant disclosure) remain open, tracked as separate gap-closure plans (59-08, 59-09 per the phase's gap-closure sequence).
- No blockers for those remaining gap-closure plans; this plan touched only `chunking.py`, its test file, both SKILL.md dispatch surfaces, the release artifacts, and the gate inventory — no overlap with `written_records.py` or `write_grant.py`.

---
*Phase: 59-frictionless-write-path*
*Completed: 2026-08-29*

## Self-Check: PASSED

All 7 modified/created files found on disk. Both task commits (`d13a2fd`, `736cf4e`) confirmed present in `git log`.
