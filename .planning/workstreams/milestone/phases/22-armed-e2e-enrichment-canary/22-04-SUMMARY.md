---
phase: 22-armed-e2e-enrichment-canary
plan: 04
subsystem: infra
tags: [hubspot, n8n, operator-runbook, canary, org-type-enum, lusha]

requires:
  - phase: 22-armed-e2e-enrichment-canary
    plan: 01
    provides: "scripts/canary_record_snapshot.py (snapshot/compare + research-gate prediction)"
  - phase: 22-armed-e2e-enrichment-canary
    plan: 02
    provides: "scripts/verify_live_write_safety.py (armed/disarmed read-back verifier)"
  - phase: 22-armed-e2e-enrichment-canary
    plan: 03
    provides: "scripts/enrichment_cost_ledger.py (credits/tokens/report) and 22-LEDGER.md"
  - phase: 20-lusha-v3-migration
    plan: 04
    provides: "lusha_contact_id/lusha_company_id declared properties + sync script, pending live create"
  - phase: 21-transport-schema-hygiene
    plan: 03
    provides: "scripts/probe_org_type_migration.py + scripts/inventory_org_type_values.py, pending live run"
provides:
  - "22-OPERATOR-RUNBOOK.md — one consolidated document sequencing every outstanding armed operator action across Phases 20-22 (Lusha id properties, org-type probe ladder, org-type enum migration, the armed e2e canary), with a dry run before every arm and an independent read-back after every arm/disarm"
  - "The migrate-first decision (Task 2) recorded in the runbook's Sitting 2 preamble and in this SUMMARY — the org-type enum migration (Section C) runs to completion before the canary (Section D) fires, so criterion 2 is fully claimable rather than deferred"
  - "The explicit two-sitting structure (A+B, then the agent interlude that builds Phase 21 Plan 04, then C+D) that a human operator can execute end to end without re-deriving sequencing from four separate SUMMARYs"
affects: []

tech-stack:
  added: []
  patterns:
    - "One runbook, multiple prior-phase pending-operator-action sections stitched together in dependency order, rather than four separate handoffs — same in-process python-dotenv wrapper form and portal/two-key gate conventions every script in this repo already uses, never reinvented"

key-files:
  created:
    - .planning/phases/22-armed-e2e-enrichment-canary/22-OPERATOR-RUNBOOK.md
  modified: []

key-decisions:
  - "Task 2 (checkpoint:decision, gate=blocking) resolved by the orchestrator before this plan executed: migrate-first. The org-type enum migration (Section C) runs to completion in Sitting 2, BEFORE the canary (Section D) fires — not deferred, not run inside the same undifferentiated window as the canary's Step 0-7b. Rationale recorded verbatim in the runbook's Sitting 2 preamble: the canary's second success criterion requires proving writes succeed against the migrated enum, and by the time this plan executes, Sections A/B and the agent interlude will already have produced everything the migration needs (verdict, rollback runbook, gated script) — deferring at that point would trade a settled, evidence-backed conversion for an open gap with no remaining reason to leave it open."
  - "Two sittings, not one, not three: Sitting 1 (Section A: Lusha id properties; Section B: org-type probe ladder) is operator-run today. An agent interlude between sittings builds Phase 21 Plan 04's Task 1 (rollback runbook) and Task 2 (gated migration script) FROM Section B's pasted-back verdict block — this cannot happen before the verdict exists, so it cannot be folded into Sitting 1. Sitting 2 (Section C: the migration itself; Section D: the armed canary) runs back to back once the interlude is done, per the orchestrator's explicit structural instruction."
  - "The create flag (ALLOW_HUBSPOT_CREATE) is named as deliberately excluded from every arm command in the runbook, with the reason stated once in the Scope section rather than repeated per-section: nothing in this milestone's remaining success criteria needs a create path, and arming it widens risk (a wrong record could be created, not just updated) for zero verification value."
  - "Section D's pre-canary branch (Step 1) is written as two independently runnable alternatives (blank the governing fields on the allowlisted company and re-snapshot; or pick a different allowlisted company still blank) with an explicit statement that proceeding unbranched when research_gate_will_fire reads false is not a third option — it forfeits the first success criterion, not just weakens it."

patterns-established:
  - "A consolidated runbook that stitches together read_first material from three prior phases' plans/summaries (20-04-SUMMARY.md's pending action, 21-03-PLAN.md's Task 3, 21-04-PLAN.md's Task 4) into one document, each section self-contained enough to run without opening the source phase, but explicitly citing where its commands came from so a discrepancy is traceable."

requirements-completed: []
# REQ-armed-e2e-canary and REQ-canary-cost-ledger are NOT marked complete by this plan.
# REQ-canary-cost-ledger is already Complete in REQUIREMENTS.md (from Plan 03's shipped
# ledger tooling and live credit-balance read). REQ-armed-e2e-canary stays Pending: the
# runbook that sequences the armed run is committed, but the armed run itself (Task 3,
# a blocking checkpoint:human-verify) has not happened yet. Marking it complete before
# the operator actually fires the canary and reads back the evidence would be exactly
# the "script's exit code taken as proof" failure mode this milestone's own runbooks
# warn against (22-RESEARCH.md Pitfall 4). This plan deliberately does not touch
# STATE.md or ROADMAP.md either, per its own project constraints.

coverage:
  - id: D1
    description: "22-OPERATOR-RUNBOOK.md sequences sections A through C and canary steps 0 through 7b in order, each with at least one copy-pasteable command in the established dotenv-wrapper form, chaining Plan 01/02/03's tooling and Phase 20/21's pending operator actions into one document"
    requirement: "REQ-armed-e2e-canary"
    verification:
      - kind: manual_procedural
        ref: "Direct read of 22-OPERATOR-RUNBOOK.md: Scope, Command form, Section A (A1-A3), Section B (B1-B6), Agent interlude, Sitting 2 preamble, Section C (C1-C7), Section D Steps 0/1/2/3/3b/4/5/6/7/7b, Pass/fail, Abort path, Where the outcome is written — all present in order"
        status: pass
      - kind: other
        ref: "grep -c 'load_dotenv' .planning/phases/22-armed-e2e-enrichment-canary/22-OPERATOR-RUNBOOK.md -> 27 occurrences across the document's live commands"
        status: pass
    human_judgment: false
  - id: D2
    description: "Every arming action is followed by a separately numbered read-back step; both the canary's arm (Step 3b) and disarm (Step 7b) invoke scripts/verify_live_write_safety.py with an explicit --expectation"
    requirement: "REQ-armed-e2e-canary"
    verification:
      - kind: manual_procedural
        ref: "Direct read: Step 3b runs verify_live_write_safety.py --expectation armed --allowlist 9604614548 immediately after Step 3's arm; Step 7b runs the same script --expectation disarmed immediately after Step 7's disarm; Section A's A3, Section B's B5, Section C's C5 each carry their own independent schema/inventory read-back"
        status: pass
    human_judgment: false
  - id: D3
    description: "The pre-canary branch (Section D Step 1) is written as two named alternatives with commands, plus an explicit statement that proceeding when research would not fire does not satisfy the first success criterion"
    requirement: "REQ-armed-e2e-canary"
    verification:
      - kind: manual_procedural
        ref: "Direct read of Section D Step 1: Branch 1 (blank + re-snapshot) and Branch 2 (different allowlisted company + re-snapshot) both given with commands; 'not a third option' / 'first success criterion cannot be claimed' stated explicitly"
        status: pass
    human_judgment: false
  - id: D4
    description: "The Task 2 decision (migrate-first) is recorded in both the runbook (Section C's disposition, stated in the Sitting 2 preamble) and this SUMMARY, without re-opening the decision"
    requirement: "REQ-armed-e2e-canary"
    verification:
      - kind: manual_procedural
        ref: "Direct read: runbook's 'SITTING 2' preamble states 'Decision recorded (Task 2 ... resolved by the orchestrator -- not re-opened here): migrate-first' with rationale; this SUMMARY's key-decisions repeats it"
        status: pass
    human_judgment: false
  - id: D5
    description: "Both test suites remain green after this documentation-only plan"
    verification:
      - kind: unit
        ref: ".venv/bin/python -m pytest -q -> 682 passed"
        status: pass
      - kind: unit
        ref: "node --test tests/n8n/*.test.mjs -> 354 pass / 0 fail"
        status: pass
    human_judgment: false
  - id: D6
    description: "Task 3 — the operator runs the consolidated runbook end to end (Sections A-D), the armed e2e canary window itself"
    verification: []
    human_judgment: true
    rationale: "The entire window is classifier-blocked for agents in this environment (confirmed twice: Phase 20 Plan 04's own attempt, and again in Phase 21). Firing a live HubSpot write, converting a one-way-door schema property, and burning real provider/Anthropic spend are exactly the class of action this project's own policy reserves for a human operator, never an executor. The checkpoint below is the handoff."

duration: 35min
completed: 2026-07-30
status: complete
---

# Phase 22 Plan 4: Consolidated Operator Runbook Summary

**One document — `22-OPERATOR-RUNBOOK.md` — sequences every outstanding armed operator action across Phases 20-22 (Lusha id properties, the org-type probe ladder, the org-type enum migration, and this phase's armed e2e canary) into two operator sittings, with a dry run before every arm and an independent read-back after every arm and disarm; the migrate-first disposition is recorded and the armed window itself is handed to the operator as a blocking checkpoint.**

## Performance

- **Duration:** ~35 min
- **Completed:** 2026-07-30
- **Tasks:** 2/3 (Task 1 written and committed; Task 2's decision recorded per the orchestrator's resolution; Task 3 is the blocking operator checkpoint this plan hands off)
- **Files modified:** 1 created (`22-OPERATOR-RUNBOOK.md`)

## Accomplishments

- Wrote `22-OPERATOR-RUNBOOK.md`, reading forward from `19-OPERATOR-RUNBOOK.md`'s established ceremony (scope statement, dotenv wrapper command form, which-n8n-key warning, arm/read-back/disarm/read-back as four distinct steps) and stitching in the three prior-phase pending-operator-actions it needed to chain: Phase 20 Plan 04's Lusha id property creates (Section A), Phase 21 Plan 03's org-type probe ladder (Section B), and Phase 21 Plan 04's org-type enum migration (Section C, gated on an agent interlude between the two sittings) before the canary itself (Section D).
- Structured the document as two operator sittings rather than one undifferentiated window: **Sitting 1** (Section A + Section B) is runnable today and ends with the operator pasting the probe ladder's `=== VERDICT ===` block back; an **agent interlude** (not operator work) then builds Phase 21 Plan 04's rollback runbook and gated migration script from that verdict; **Sitting 2** (Section C, then Section D) runs the migration to completion before the canary fires.
- Recorded the Task 2 decision — **migrate-first** — verbatim in the runbook's Sitting 2 preamble with its rationale, and repeated it here without re-opening it, per the orchestrator's explicit resolution.
- Wrote Section D (the canary itself) as the numbered Step 0 through Step 7b sequence the plan's action text specified: a disarmed redeploy plus three independent read-backs (write-safety, Lusha URLs, native search) before anything is armed; a pre-canary snapshot with an explicit two-branch fork when `research_gate_will_fire` reads false; the credit baseline; arm plus a distinct armed read-back (Step 3b) required before firing; exactly one webhook POST; a read-back comparing against the pre-canary snapshot with an immediate abort-to-disarm on any non-zero neighbour count; the cost ledger capture; and disarm plus a distinct disarmed read-back (Step 7b) as the closing gate.
- Verified both test suites remain green (this plan ships documentation only, no production-path code changed).

## Task Commits

1. **Task 1: Write the consolidated operator runbook** - `1911f61` (docs)
2. **Task 2: Record the migration disposition (migrate-first)** - no separate commit; the decision is recorded inline in Task 1's committed runbook (Sitting 2 preamble) and in this SUMMARY's frontmatter/prose, matching the orchestrator's resolution rather than a live re-decision. Same convention 22-02's Task 2 used for a live-evidence-only step with no independent diff.

## Files Created/Modified

- `.planning/phases/22-armed-e2e-enrichment-canary/22-OPERATOR-RUNBOOK.md` - the consolidated arm/fire/read-back/disarm ceremony plus the three prerequisite operator sections (A, B, C) and the canary itself (D)

## Decisions Made

See `key-decisions` in the frontmatter. The consequential one: **migrate-first**, resolved by the orchestrator before this plan executed (not a live Task 2 checkpoint pause) — the org-type enum migration runs to completion in Sitting 2 before the canary fires, so ROADMAP criterion 2's schema-migration half is fully testable rather than deferred.

## Deviations from Plan

None — plan executed exactly as written. Task 2's checkpoint:decision was pre-resolved by the orchestrator (per this plan's `<orchestrator_decision>` context) rather than paused on live; this SUMMARY records that resolution rather than treating it as reopened, per the explicit instruction not to re-litigate it.

## Known Stubs

None. This plan ships documentation only — no code stubs, no placeholder data paths.

## Issues Encountered

None.

## User Setup Required

The entire armed window described in `22-OPERATOR-RUNBOOK.md` is the pending user action — see the checkpoint below. No additional environment variables or dashboard configuration beyond what the runbook itself names (`N8N_URL`, `N8N_API_KEY`, `N8N_ENRICHMENT_WEBHOOK_SECRET`, `TEST_COMPANY_IDS`, `HUBSPOT_PRIVATE_APP_TOKEN`, `ANTHROPIC_API_KEY` — all already provisioned per prior phases' live runs).

## Next Phase Readiness

This is the last plan of Phase 22 and, pending the operator's run of `22-OPERATOR-RUNBOOK.md`, the last outstanding armed action in the v0.5 milestone. No blockers for the agent side — everything downstream of this point is the operator's Sitting 1, then Sitting 2 (with an agent interlude in between to build Phase 21 Plan 04 from Sitting 1's verdict). `22-LEDGER.md` and `REQUIREMENTS.md`'s `REQ-armed-e2e-canary` row stay as the visible markers of what remains once the operator has run the window.

---
*Phase: 22-armed-e2e-enrichment-canary*
*Completed: 2026-07-30*

## Self-Check: PASSED

- `.planning/phases/22-armed-e2e-enrichment-canary/22-OPERATOR-RUNBOOK.md` — FOUND on disk.
- Commit `1911f61` — FOUND in `git log --oneline`.
- `682 passed` (pytest, full suite), `354 pass / 0 fail` (node --test) — both suites green.
