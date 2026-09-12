---
phase: 72-enrichment-extras-land-in-hubspot
plan: 08
subsystem: n8n-workflows
tags: [live-gate, hubspot, n8n-cloud, linkedin-dual-write, non-clobber, documentation]

requires:
  - phase: 72-enrichment-extras-land-in-hubspot
    provides: "plans 01-07's shipped code, deployed workflow bodies and gate spec — this plan
      runs the phase's one armed send against them and records what actually happened"
provides:
  - "Task 1's live level-and-verify recorded PASS in 72-UAT.md (properties exist, five
    workflows deployed/bounced disarmed, node counts and executionOrder v1 confirmed)"
  - "Task 2's one armed window recorded PASS-with-findings: one CREATE (contact
    352455353810) and one UPDATE (contact 1251) read back against every D-72-17 must-have
    truth, surfacing F72-1 — a real code defect, not fixed in-gate per the plan's own
    prohibition"
  - "CLAUDE.md SS13.0.2/SS17.2.2 upgraded from documented to observed with execution ids and
    record ids, honestly stating the one claim (D-72-04's create-path dual write) that is
    NOT met"
  - "docs/OPERATOR-AUTONOMOUS-BATCH-UAT.md SS6 corrected (F72-2, wrong property name) and
    given a run-outcome note for the next operator"
  - "WINDOWS.md ledger id 30 (kind: unmet-truth) and a STATE.md blocker tracking F72-1 for
    gap-closure"
affects: ["a future gap-closure plan closing F72-1 (lv_linkedin_url on the ingest CREATE
  path) before D-72-04's dual write can be called complete"]

actuals:
  tokens: 6910
  tasks: 3
  commits: 4
plan_head_before: 3a013d59

tech-stack:
  added: []
  patterns:
    - "The [documented]/[observed live] tagging discipline (CLAUDE.md SS13.0.3) applied to a
      finding that FAILS rather than confirms a claim: the delta states plainly which path
      the observation covers and which it does not, instead of upgrading the whole claim on
      a partial pass."

key-files:
  created: []
  modified:
    - .planning/phases/72-enrichment-extras-land-in-hubspot/72-UAT.md
    - CLAUDE.md
    - docs/OPERATOR-AUTONOMOUS-BATCH-UAT.md
    - .planning/WINDOWS.md

key-decisions:
  - "F72-1 (lv_linkedin_url missing on ingest CREATE) is recorded as a finding with its full
    root cause, and NOT patched inside this gate — the plan's own prohibition ('a defect
    found at the gate is a finding for a gap-closure plan, never a patch made inside it') is
    followed literally, even though the root cause was fully traced during this plan
    (build_cloud_workflows.py's confidenceByField keyed pre-PN-1-rename)."
  - "requirements-completed copies D-72-17 verbatim per the SUMMARY contract, but its
    coverage entry is marked verification status: fail, human_judgment: true — the
    frontmatter lists what the plan targeted, the coverage block is what actually happened.
    REQUIREMENTS.md has no D-72-* entries to tick (those IDs are 72-CONTEXT.md decision
    tags, confirmed by a harmless no-op test call against requirements.mark-complete before
    relying on it), so no roadmap requirement was falsely marked done by this plan."
  - "D-72-10 (hs_additional_emails serialisation) is recorded as NOT OBSERVED rather than
    pass or fail — the waterfall returned no second email for either row in the gate, so the
    provenance-only path was never exercised. This is the one item CONTEXT.md's 'Claude's
    Discretion' section left for live verification, and it remains open."

requirements-completed: [D-72-11, D-72-17, D-72-18, D-72-21, D-72-10]

coverage:
  - id: D1
    description: "Task 1: the three overflow-slot properties are verified live and all five changed cloud workflow bodies are deployed and bounced disarmed, node counts and settings.executionOrder: v1 read back matching committed JSON"
    requirement: D-72-21
    verification:
      - kind: manual_procedural
        ref: "72-UAT.md Task 1 — sync tool 0-pending on both objects; deploy tool verdict 'OK — all active, node counts match, write flags false, execution order v1'"
        status: pass
    human_judgment: false
  - id: D2
    description: "The three overflow-slot properties (lv_phone_2 contacts/companies, lv_mobilephone_2 contacts) exist live, confirmed by sync tool 0-pending diff on both objects"
    requirement: D-72-11
    verification:
      - kind: manual_procedural
        ref: "72-UAT.md Task 1 Step 1 (0-pending on both objects); type/readOnlyValue confirmed in plan 05, not re-GET'd fresh this task"
        status: pass
    human_judgment: false
  - id: D3
    description: "D-72-17: an absent person at a company HubSpot already holds is created via enrich-before-ingest and the created contact carries mobilephone, BOTH hs_linkedin_url and lv_linkedin_url, and the returned geo fields"
    requirement: D-72-17
    verification:
      - kind: manual_procedural
        ref: "72-UAT.md Task 2, contact 352455353810 (exec 12402): mobilephone/hs_linkedin_url/geo land; lv_linkedin_url does NOT land"
        status: fail
    human_judgment: true
    rationale: "The create-path dual write partially fails (F72-1): mobilephone, hs_linkedin_url and every returned geo field land correctly, but lv_linkedin_url is withheld even into a blank field due to a confidence-lookup key mismatch. This is a genuine gap between what the truth requires and what was observed, not a judgment call automation could resolve — a human/gap-closure plan must fix the code before this can pass."
  - id: D4
    description: "D-72-17/SAFE-01: an UPDATE row against a contact holding a non-blank fill_blank_only field (phone) proves that field was NOT overwritten, and lv_linkedin_url promotes correctly on this (non-create) path"
    requirement: D-72-17
    verification:
      - kind: manual_procedural
        ref: "72-UAT.md Task 2, contact 1251 (exec 12406): phone unchanged before/after; lv_linkedin_url landed via waterfall/85"
        status: pass
    human_judgment: false
  - id: D5
    description: "D-72-10: how hs_additional_emails actually serialises on write (or that it was not written at all) is observed and recorded"
    requirement: D-72-10
    verification: []
    human_judgment: true
    rationale: "The waterfall returned no second email for either the CREATE or UPDATE row in this gate, so D-72-10's provenance-only path was never exercised live. Recorded as NOT OBSERVED, not as pass or fail — this remains an open item for a future gate with a person who has two revealed emails."
  - id: D6
    description: "CLAUDE.md's as-built delta is upgraded from documented to observed with execution/record ids, honestly split by path where the observation is a partial pass, and docs/OPERATOR-AUTONOMOUS-BATCH-UAT.md's property-name defect is fixed"
    verification:
      - kind: unit
        ref: "grep -c 'observed live' CLAUDE.md (25 before this plan's Task 3 edits -> 31 after)"
        status: pass
      - kind: unit
        ref: "grep -c '^## Verdict\\|^## Clean-up' 72-UAT.md (2)"
        status: pass
      - kind: other
        ref: ".venv/bin/python -m pytest -q tests/ operator-claude-plugin/tests/ (4947 passed, 154 skipped); node --test tests/n8n/*.test.mjs (1167/1167); git diff --stat 3a013d59..HEAD -- src/ n8n/ scripts/ config/ operator-claude-plugin/scripts/ (empty)"
        status: pass
    human_judgment: false

duration: ~50min (Task 1 recorded 2026-09-12 by a prior executor; this session covers checkpoint resolution and Task 3, 2026-09-13)
completed: 2026-09-13
status: complete
---

# Phase 72 Plan 08: Enrichment Extras Land in HubSpot — Live Gate Summary

**The phase's one armed send lands `mobilephone` and `hs_linkedin_url` on a newly created HubSpot contact and proves an existing contact's phone survives an update untouched, but `lv_linkedin_url` does not land on the ingest CREATE path — a real, root-caused code defect (F72-1) recorded for gap closure rather than patched inside the gate.**

## Performance

- **Duration:** ~50 min for this session (Task 1 was recorded by a prior executor on 2026-09-12; this session resolved the Task 2 checkpoint and ran Task 3)
- **Tasks:** 3 (2 checkpoints + 1 auto)
- **Files modified:** 4 (72-UAT.md, CLAUDE.md, docs/OPERATOR-AUTONOMOUS-BATCH-UAT.md, WINDOWS.md)

## Accomplishments

- Recorded Task 2's live armed window in `72-UAT.md`: one CREATE (contact `352455353810` via `enrich-before-ingest`, n8n execution `12402`) and one UPDATE (contact `1251`, execution `12406`), with the full per-field waterfall-vs-landed comparison table for both.
- Found and root-caused F72-1: `lv_linkedin_url` does not land on the ingest CREATE path. `build_cloud_workflows.py`'s `MERGE_CONTACTS` builds `confidenceByField` keyed on `row.source_by_field`'s pre-PN-1-rename CSV key (`linkedin_url`), but the candidate carries the value under the renamed keys `lv_linkedin_url`/`hs_linkedin_url` — `mergeContacts.js`'s promotion gate looks up `confidenceByField["lv_linkedin_url"]`, misses, and falls back to the flat `csv`/80 confidence, below the field's `fill_blank_only`@85 threshold. `hs_linkedin_url` is unaffected because its key is never renamed. Confirmed the same field lands correctly on the UPDATE/enrich-records path (contact `1251`, waterfall/85) — the defect is create-path-specific.
- Confirmed SAFE-01 live for the first time on this lane: contact `1251`'s pre-existing non-blank `phone` survived a row supplying a different phone value, unchanged.
- Confirmed `hs_additional_emails`'s D-72-10 provenance-only path was NOT exercised live (no second email returned by the waterfall for either row) — recorded honestly as not-observed rather than claimed as pass.
- Fixed F72-2 (a doc defect): `docs/OPERATOR-AUTONOMOUS-BATCH-UAT.md` named the wrong property (`lv_enrichment_provenance`, the company property) for a contact; corrected to `lv_contact_enrichment_provenance`.
- Upgraded CLAUDE.md's Phase 72 as-built delta (SS13.0.2, SS17.2.2) from documented to observed, following SS13.0.3's tagging discipline honestly: D-72-04's dual write is stated as observed-and-partially-failing, split by path, not upgraded wholesale on the strength of the passing half.
- Appended WINDOWS.md ledger id 30 (`kind: unmet-truth`) and a STATE.md blocker for F72-1, so the gap survives past this SUMMARY into ship-gate visibility.

## Task Commits

Each task was committed atomically (`type="checkpoint:human-verify"` x2, `type="auto"` x1):

1. **Task 1: Create the three slot properties, then level live with committed — all disarmed** — `19d7dbfa` (docs, prior executor, 2026-09-12)
2. **Task 2: One armed window, one record — the read-back F71-5 asked for** — `99cac016` (docs, this session, records the operator's live gate run)
3. **Task 3: Record the verdict, and upgrade the as-built claims from documented to observed** — `8448302b` (docs)

**Plan metadata:** this commit (SUMMARY + STATE + ROADMAP + REQUIREMENTS).

## Files Created/Modified

- `.planning/phases/72-enrichment-extras-land-in-hubspot/72-UAT.md` — Task 2 recorded in full: pre-check, CREATE row table, UPDATE row table, flags/burst-watch, Findings (F72-1..F72-4), Clean-up, Verdict.
- `CLAUDE.md` — SS13.0.2 dated extension (live node counts/executionOrder/gate outcome); SS17.2.2 items 2 and 3 given `[observed live]` paragraphs, item 3's split honestly stating D-72-04 is NOT complete on create.
- `docs/OPERATOR-AUTONOMOUS-BATCH-UAT.md` — F72-2 property-name fix; new "Run outcome, 2026-09-13" note (wrong-portal MCP trap, bidi phone comparison, F72-1's known failure, hs_additional_emails no-op case).
- `.planning/WINDOWS.md` — ledger id 30 (`unmet-truth`, F72-1).

## Decisions Made

- **F72-1 is recorded, root-caused, and NOT patched inside this gate** — the plan's own prohibition against patching a gate-found defect is followed literally, even though the fix location was fully identified during the investigation.
- **`requirements-completed` copies D-72-17 verbatim (contract requirement), but its coverage entries split pass/fail by path** — the frontmatter states what the plan targeted, the coverage block states what actually happened, and REQUIREMENTS.md has no D-72-* entries to falsely tick (verified with a harmless no-op probe call before relying on this).
- **D-72-10 is recorded as NOT OBSERVED, not pass or fail** — the waterfall found no second email for either row, so the question CONTEXT.md flagged as needing live verification remains genuinely open.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking, doc-only] Fixed the wrong property name in the gate's own run instructions (F72-2)**
- **Found during:** Task 3, cross-referencing the operator's Task 2 report against `config/hubspot_properties.yaml`
- **Issue:** `docs/OPERATOR-AUTONOMOUS-BATCH-UAT.md` line 513 named `lv_enrichment_provenance` (the COMPANY property, line 192 of `config/hubspot_properties.yaml`) as where a contact's second email would be provenanced; the correct contact property is `lv_contact_enrichment_provenance` (line 506).
- **Fix:** Corrected the property name in the doc.
- **Files modified:** `docs/OPERATOR-AUTONOMOUS-BATCH-UAT.md`
- **Verification:** `grep` confirms the corrected name; the plan explicitly names this as allowed Task 3 work ("F72-2 ... doc defect, fix allowed — it is paperwork, not gate code").
- **Committed in:** `8448302b`

---

**Total deviations:** 1 auto-fixed (1 doc-only blocking fix, explicitly pre-authorized by the plan). **Impact:** none — a documentation correction with no code, config, or workflow change. F72-1, the substantive finding, was deliberately NOT auto-fixed per the plan's own prohibition and is tracked instead (see Known Stubs / Next Phase Readiness below).

## Issues Encountered

- The gate session's HubSpot MCP connector was initially pointed at the wrong portal (`443043042` instead of the plugin's target `22617666`); its pre-check output was discarded and every read/write in the gate went through the plugin's own portal instead. No data crossed portals. Recorded as F72-4 in `72-UAT.md` and as a caution in the doc's new run-outcome note.
- Plan 01's flagged consequence (a CSV correcting `firstname`/`lastname`/`company` on an existing contact no longer applies through the ingest lane) was observed live exactly as predicted on contact `1251`. The operator did not give an explicit ruling this sitting on whether that behaviour is acceptable — plan 01's two "Operator confirm:" items remain open (F72-3).

## Known Stubs

- **F72-1 (open, tracked):** `lv_linkedin_url` does not land on the ingest CREATE path. Root cause fully identified (`scripts/build_cloud_workflows.py:479-483,487-494`, `n8n/code/mergeContacts.js:400`) but not fixed — the plan's own prohibition forbids patching a gate-found defect inside the gate. Tracked in `.planning/WINDOWS.md` (ledger id 30) and as a `STATE.md` blocker. A gap-closure plan is required before D-72-04's dual write can be called complete on both paths.
- **D-72-10 not exercised (open by nature, not a stub):** `hs_additional_emails`'s provenance-only serialisation was never observed live in this gate (no second email revealed for either row). Not a code gap — the next gate with a two-email person will exercise it.

## User Setup Required

None — this plan is documentation-only (recording the operator's already-performed live gate and upgrading claims to observed). No new external service configuration required. The armed HubSpot/n8n operations this plan documents were already performed by the operator per the checkpoint resolution before this plan resumed; this plan itself made no live API calls.

## Next Phase Readiness

- Phase 72 is otherwise complete: plans 01-08 are all summarized, the live gate ran, and the repo's own contract documents (CLAUDE.md, the operator UAT doc) now state what was actually observed rather than what was expected.
- **F72-1 is the one open item blocking a clean close of D-72-17/D-72-04**: a gap-closure plan should fix `MERGE_CONTACTS`'s `confidenceByField` lookup so it is keyed on the same (renamed) field name the candidate object uses, add a regression test asserting `lv_linkedin_url` promotes on a CREATE row exactly as it does on an UPDATE row, then regenerate/deploy/bounce and re-run a disarmed proof before the next armed send.
- Plan 01's two "Operator confirm:" items (firstname/lastname/company non-application on the ingest lane; jobtitle routing to needs_review pre-plan-04) remain open product questions for the operator, now confirmed observed live rather than merely predicted.
- No other blockers.

## Self-Check: PASSED

- `[ -f .planning/phases/72-enrichment-extras-land-in-hubspot/72-UAT.md ]` → FOUND
- `git log --oneline --all | grep -q 19d7dbfa` → FOUND
- `git log --oneline --all | grep -q 99cac016` → FOUND
- `git log --oneline --all | grep -q 8448302b` → FOUND
- All plan-level `<verification>` commands re-run and passing: `.venv/bin/python -m pytest -q --tb=short -p no:cacheprovider tests/ operator-claude-plugin/tests/` (4947 passed, 154 skipped); `node --test tests/n8n/*.test.mjs` (1167/1167); `git diff --stat 3a013d59..HEAD -- src/ n8n/ scripts/ config/ operator-claude-plugin/scripts/` (empty); `grep -c "observed live" CLAUDE.md` (31, up from 25); `grep -c "^## Verdict\|^## Clean-up" 72-UAT.md` (2).

---
*Phase: 72-enrichment-extras-land-in-hubspot*
*Completed: 2026-09-13*
