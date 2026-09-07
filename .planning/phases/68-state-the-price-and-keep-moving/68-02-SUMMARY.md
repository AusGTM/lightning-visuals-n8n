---
phase: 68-state-the-price-and-keep-moving
plan: 02
subsystem: operator-claude-plugin
tags: [consent-posture, skill-md, write-grant, tdd, prose-contract]

# Dependency graph
requires:
  - phase: 68
    provides: "Plan 01's watch.pre_spend_pause and its single call site in suggest-contacts step 4, reused unchanged; the recorded D-68-04 headless-boundary posture in backend-control/SKILL.md"
provides:
  - "The default (no-grant) path of all four batch skills — enrich-before-ingest, enrich-records, contact-upload, suggest-contacts — now states, pauses, opens a grant, and proceeds, instead of stopping to ask (D-68-01/03/05/06/07/08/10)"
  - "operator-claude-plugin/tests/test_implicit_approval_contract.py — the shared prose contract pinning call order, refusal-stops behavior, unsampled-ceiling disclosure, suggestion_companies pricing, once-only pause and inline-grant-offer across all four skills"
affects: ["68-03", "phase-67 (autonomy-tier gate opening, inherits an implicit-open baseline instead of the old two-phase ask)"]

# Actuals (#2632)
actuals:
  tokens: 7979
  tasks: 3
  commits: 4
  plan_head_before: 70142e60bafb666e97d25d7d7032fd131363a077

tech-stack:
  added: []
  patterns:
    - "Implicit-open shape, copied verbatim per skill: plan_grant (priced over exactly this batch, carrying suggestion_companies where object_type can be companies) -> stated proposal[envelope][block]/[consequence] + unsampled-ceiling sentence -> refusal-stops rule -> pre_spend_pause() -> open_grant(proposal, \"yes\", config) -> continue on the pre-existing granted branch"
    - "Two-step split for skills whose disclosure and its arming are documented in separate numbered steps (enrich-records, contact-upload, suggest-contacts): plan_grant (+ agreed_cap for suggest-contacts) lands in the earlier step; pause + open_grant land at the END of the later step, immediately before the dispatch fence — never a second pause"
    - "Single-call-per-fence discipline: every new fenced python block carries exactly one scripts-module call, so test_skill_sequence_coverage.py's >=2-call ratchet needs no new COVERED/NOT_A_PIPELINE registration"

key-files:
  created:
    - operator-claude-plugin/tests/test_implicit_approval_contract.py
  modified:
    - operator-claude-plugin/skills/enrich-before-ingest/SKILL.md
    - operator-claude-plugin/skills/enrich-records/SKILL.md
    - operator-claude-plugin/skills/contact-upload/SKILL.md
    - operator-claude-plugin/skills/suggest-contacts/SKILL.md

key-decisions:
  - "Task 1 (checkpoint:decision) resolved by the operator before this execution began: price-state-pause-open. The default path prices the grant over this batch, states it, pauses, opens it, continues; the ungranted two-phase ask survives verbatim as the interrupted path. Recorded here per the executor's checkpoint_resolution contract, not re-asked."
  - "suggest-contacts step 3 REORDERS rather than merely inserting a block, because agreed_cap raises CapRefused when no grant has priced a suggestion allowance: role ask (unchanged, genuine) -> cap default of 2 stated, not asked (D-68-02) -> reuse an already-open grant's envelope, or plan+state+refusal-check a fresh one -> agreed_cap. Step 4 keeps the pre-existing pause fence from Plan 01 and adds open_grant immediately after it — never a second pause."
  - "contact-upload never prices a suggestion allowance (has_suggestion=False) — it is contacts-only end to end, and envelope()'s documented None-skip is the correct behavior, not an oversight requiring suggestion_companies=0."
  - "enrich-records' implicit-open fence conditions suggestion_companies on object_type == \"companies\" in one line (a ternary), reusing rather than duplicating the suggestion_companies wiring step 5's own Para C already documents in prose — confirmed live: that pre-existing paragraph alone satisfied the suggestion_companies/suggestion_cap contract test for enrich-records before I added any new prose for it."
  - "suggest-contacts never had its own independent ungranted-ask literal (only a cross-reference to enrich-before-ingest's, 'follow ... step 5's two-phase ask verbatim'); Task 3's action explicitly replaces that pointer with the price statement, so this skill has no 'survives' literal in the test's TARGETS entry — consistent with every other skill converting the SAME shape, not a gap."

requirements-completed: [FLOW-01, FLOW-02, FLOW-03]

coverage:
  - id: D1
    description: "enrich-before-ingest step 5's default (no-grant) path prices a grant over exactly this batch, states proposal[envelope][block]/[consequence] plus the unsampled-ceiling sentence, pauses once, opens the grant with the literal \"yes\", and continues on the granted branch; a plan_grant refusal stops the round and never falls through to authorize_ungranted_send; the pre-existing two-phase ask survives byte-identical as the interrupted path"
    requirement: FLOW-01
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_implicit_approval_contract.py (7 tests, enrich-before-ingest)"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_enrich_before_ingest_skill_contract.py"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_skill_sequence_coverage.py"
        status: pass
    human_judgment: false
  - id: D2
    description: "enrich-records (step 5/6), contact-upload (step 4/5) and suggest-contacts (step 3/4) carry the identical implicit-open shape, each pausing exactly once immediately before its own dispatch fence, each naming backend-control's 'Opening a write grant' action inline as the direct route to a larger grant (D-68-07), each preserving its own pre-existing arming-scope literal or refusal relay unchanged"
    requirement: FLOW-02
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_implicit_approval_contract.py (25 tests, the remaining three skills)"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_enrich_skill_contract.py"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_write_grant.py"
        status: pass
    human_judgment: false
  - id: D3
    description: "suggestion_companies is priced only where a batch's object_type can be companies (enrich-before-ingest, enrich-records, suggest-contacts), left unset for suggestion_cap so PRICED_CAP prices any later suggest-contacts round in the same sitting; contact-upload never prices one, matching envelope()'s documented None-skip for a contacts-only lane"
    requirement: FLOW-03
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_implicit_approval_contract.py::test_suggestion_companies_is_priced_and_suggestion_cap_is_left_unset"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_implicit_approval_contract.py::test_contact_upload_never_prices_a_suggestion_allowance"
        status: pass
    human_judgment: false
  - id: D4
    description: "No Python script changed by this plan (git diff --name-only f0ab716 -- scripts/ still lists watch.py only, unchanged since Plan 01); the two pre-existing pinned prose-contract test files are byte-identical to f0ab716"
    verification:
      - kind: other
        ref: "git diff --name-only f0ab716 -- operator-claude-plugin/scripts/"
        status: pass
      - kind: other
        ref: "git diff --quiet f0ab716 -- operator-claude-plugin/tests/test_enrich_skill_contract.py operator-claude-plugin/tests/test_enrich_before_ingest_skill_contract.py"
        status: pass
    human_judgment: false
  - id: D5
    description: "The prose wording quality — whether an operator reading these four skills experiences the default path as a genuine statement-and-proceed rather than a disguised question — is a judgment call a test cannot make"
    verification: []
    human_judgment: true
    rationale: "The structural facts (call order, literal survival, single-pause, refusal wording) are all mechanically verified above; whether the resulting prose actually READS as a statement rather than an ask, in the operator's own experience mid-conversation, is not something a grep/pytest check can confirm — reserved for the phase's own end-of-phase human review."

duration: ~50min (investigation + 3 tasks; commits span 2026-09-07T14:18:19+10:00 to 14:25:32+10:00 AEST)
completed: 2026-09-07
status: complete
---

# Phase 68 Plan 02: State the price and keep moving — the four batch skills Summary

**All four batch-write skills (enrich-before-ingest, enrich-records, contact-upload, suggest-contacts) now price, state, pause once, and open a grant by default instead of stopping to ask — the ungranted two-phase ask survives verbatim as the path taken only when the operator interrupts.**

## Performance

- **Duration:** ~50 min (investigation of ~15 files before the first edit, then 3 tasks; commit timestamps span 2026-09-07T14:18:19+10:00 to 14:25:32+10:00 AEST)
- **Tasks:** 3 (Task 1 pre-resolved by operator per checkpoint_resolution; Task 2 and Task 3 executed this session, each RED-then-GREEN)
- **Files modified:** 5 (1 test file created/extended, 4 SKILL.md files modified)

## Accomplishments
- `enrich-before-ingest/SKILL.md` step 5's default path prices a grant, states its arithmetic and any unsampled-ceiling blind spot, pauses once, opens the grant with the literal `"yes"`, and continues — the source-of-truth site every other skill's ask either quoted or independently mirrored.
- The same shape landed at `enrich-records` (step 5/6), `contact-upload` (step 4/5) and `suggest-contacts` (step 3/4, which REORDERS its role/cap ask so `agreed_cap` always has a priced allowance to check against).
- `operator-claude-plugin/tests/test_implicit_approval_contract.py` pins the shared contract (call order, `"yes"` literal, refusal-stops rule, unsampled-ceiling disclosure, `suggestion_companies` pricing, once-only pause, inline grant offer, literal survival) across all four skills — 32 tests, parameterised over a `TARGETS` table generalised to a tuple of numbered steps per skill.

## Task Commits

Each task was committed atomically (TDD: RED then GREEN):

1. **Task 1: Confirm the rendering of the implicit consent posture** (checkpoint:decision) — resolved by the operator before this execution began (`price-state-pause-open`); no code artifact of its own, recorded in Decisions Made below.
2. **Task 2: enrich-before-ingest step 5 — the source of truth states, pauses, opens, proceeds** (tracer, tdd)
   - `2eac67d` — `test(68-02): add failing tests for the implicit-approval contract` (RED)
   - `cae5cc9` — `feat(68-02): enrich-before-ingest step 5 states, pauses, opens, and proceeds by default` (GREEN)
3. **Task 3: The same conversion at the three remaining sites** (auto, tdd)
   - `080f209` — `test(68-02): extend the implicit-approval contract to the remaining three skills` (RED)
   - `65ce73b` — `feat(68-02): enrich-records, contact-upload and suggest-contacts state and proceed` (GREEN)

**Plan metadata:** this commit (SUMMARY + STATE + ROADMAP)

## Files Created/Modified
- `operator-claude-plugin/tests/test_implicit_approval_contract.py` — new prose-contract test, parameterised over all four batch skills (32 tests)
- `operator-claude-plugin/skills/enrich-before-ingest/SKILL.md` — step 5's default block, its three single-call fences, the refusal rule, the unsampled-ceiling sentence, the inline grant offer
- `operator-claude-plugin/skills/enrich-records/SKILL.md` — the same at step 5, with the pause+open_grant fences at the end of step 6, immediately before step 8's dispatch
- `operator-claude-plugin/skills/contact-upload/SKILL.md` — the same at step 4, with the pause+open_grant fences at the end of step 5, immediately before step 6's dispatch
- `operator-claude-plugin/skills/suggest-contacts/SKILL.md` — step 3 reordered (role ask stays; cap default stated; grant reuse-or-plan; `agreed_cap`); step 4's old pointer replaced by the price statement, `open_grant` added after Plan 01's existing pause fence

## Decisions Made

**Task 1 (checkpoint:decision), pre-resolved by the operator: `price-state-pause-open`.** The default path prices the grant over this batch, states it, pauses, opens it, continues; the ungranted two-phase ask survives verbatim as the interrupted path; every pinned literal stays byte-identical. This decision was resolved before this execution began (per the spawning prompt's `checkpoint_resolution`) and is recorded here, not re-asked.

**suggest-contacts step 3 reorders rather than inserts.** `agreed_cap` raises `CapRefused` when no grant has priced a suggestion allowance — leaving the implicit open at step 4 (mirroring the other three skills) would make every default-path round refuse at step 3 before reaching it. The role ask stays a genuine ask; the cap default of 2 is stated per D-68-02; a grant already open (the common case, immediately after a company batch) is reused per D-60-02 rather than re-planned.

**contact-upload never prices a suggestion allowance.** It is contacts-only end to end; passing `suggestion_companies=0` would be a fabricated figure for a suggestion round this lane never runs. Confirmed by a dedicated negative test (`test_contact_upload_never_prices_a_suggestion_allowance`) checking for the absence of the keyword-argument form specifically — an earlier draft of that test failed on a false positive because the PROSE explaining the omission itself contains the substring "suggestion_companies"; the test now checks `"suggestion_companies="` (the keyword-arg form) rather than the bare word.

**enrich-records reuses its own pre-existing Para C rather than duplicating it.** Step 5 already documented (in prose only, pre-Phase-68) that the explicit `plan_grant` call for a companies batch carries `suggestion_companies`/leaves `suggestion_cap` unset. Confirmed live during RED: `test_suggestion_companies_is_priced_and_suggestion_cap_is_left_unset[enrich-records]` passed BEFORE any GREEN edit for that check specifically, because the existing paragraph alone satisfied it — my new fence only needed to actually MAKE the call the paragraph already described.

## Deviations from Plan

None — plan executed exactly as written. One acceptance-criterion technicality is worth recording (not a Rule 1-4 deviation, since nothing was fixed or changed to work around it):

**Plan's literal `grep -c "arms this send and nothing else"` under-reports for enrich-records and contact-upload due to a pre-existing markdown line-wrap.** Both files wrap that exact phrase across two lines in the SOURCE MARKDOWN ("... — arms this\n   send and nothing else.**"), confirmed present in `f0ab716` (before this phase started) via `git show f0ab716:.../enrich-records/SKILL.md | grep -c ...` returning `0` on the unedited original too. A single-line `grep -c` therefore reports `0` on both files regardless of what this plan does. The property itself is intact and is verified accurately by the whitespace-normalizing pytest check (`test_every_pre_existing_arming_scope_literal_survives`, using the same `_normalized()` collapse-whitespace idiom `test_enrich_before_ingest_skill_contract.py` already established), which passes for both files. A Python-side confirmation (`re.sub(r'\s+', ' ', text).count(...)` == 1 for both) is quoted in this session's tool output for the record.

## Issues Encountered

None beyond the grep-wrap technicality documented above, which required no fix — only a more accurate verification method (already the one the test file uses).

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- All four batch skills now share one implicit-open shape; Plan 68-03 (not yet started) can build on `test_implicit_approval_contract.py`'s `TARGETS` table for any further sharpening of the D-59-06 revoke sentence it names as its own grep target (explicitly left untouched by this plan, per its own instruction, in all four files).
- Phase 67's autonomy-tier gate opening now inherits an implicit-open baseline at every batch skill instead of the old two-phase ask — one switch site per skill, as CONTEXT.md's Approval section anticipated.
- No blockers. `git diff --name-only f0ab716 -- operator-claude-plugin/scripts/` still lists `watch.py` only; nothing armed, no live HubSpot writes, no provider credits spent by this plan's own execution.

---
*Phase: 68-state-the-price-and-keep-moving*
*Completed: 2026-09-07*

## Self-Check: PASSED

- All 5 key files confirmed present on disk (`[ -f ]`): `test_implicit_approval_contract.py`, `enrich-before-ingest/SKILL.md`, `enrich-records/SKILL.md`, `contact-upload/SKILL.md`, `suggest-contacts/SKILL.md`.
- All 4 task commits (`2eac67d`, `cae5cc9`, `080f209`, `65ce73b`) confirmed in `git log --oneline --all`.
- All plan-level `<verify>` commands re-run and green: `.venv/bin/python -m pytest operator-claude-plugin/tests/ -q` (2605 passed, 5 skipped), `node --test tests/n8n/*.test.mjs` (940 pass, 0 fail), `git status --porcelain -- n8n/ scripts/build_cloud_workflows.py` (empty), `git diff --quiet f0ab716 -- operator-claude-plugin/scripts/suggest_contacts.py operator-claude-plugin/scripts/write_grant.py` (exits 0).
- Every task-level acceptance criterion re-verified via grep/git diff, matching expected output, except the grep-wrap technicality documented above under Deviations.
