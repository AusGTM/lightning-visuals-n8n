---
phase: 72-enrichment-extras-land-in-hubspot
plan: 09
subsystem: n8n-ingest
tags: [n8n, ingest, mergeContacts, linkedin, gap-closure, tdd]

requires:
  - phase: 72-enrichment-extras-land-in-hubspot
    provides: plan 08's live gate (F72-1) and 72-VERIFICATION.md's gap 1 / 72-REVIEW.md's WR-01, which both diagnosed this exact defect
provides:
  - "MERGE_CONTACTS's CANDIDATE_ALIASES: the one place preingest.py's PROVIDER_KEY_ALIASES rename is undone on the write side, read by both the confidenceByField/sourceByField derivation and the candidate builder"
  - "a regression fixture that seeds source_by_field with the pre-alias key production actually sends, so a recurrence of F72-1 is caught offline"
affects: [72-12]

actuals:
  tokens: 1200
  tasks: 2
  commits: 2
plan_head_before: 448ac7bd138a7b38de2ae54d0fdefd612f632e41

tech-stack:
  added: []
  patterns:
    - "a single alias map read by both halves of a merge wrapper that previously computed a rename independently in two places and silently disagreed"

key-files:
  created: []
  modified:
    - tests/n8n/ingestWidenedFieldsFlow.test.mjs
    - scripts/build_cloud_workflows.py
    - n8n/wf_contact_ingest_cloud.json
    - n8n/wf_contact_ingest_local.json

key-decisions:
  - "One CANDIDATE_ALIASES map declared once inside MERGE_CONTACTS, read by both the confidenceByField/sourceByField loop and the candidate-builder block, so the rename can never again be spelled out twice and drift."
  - "sourceByField is aliased (not just confidenceByField): mergeContacts()'s _isProviderSource(resolvedSource) observation-time gate (D-72-07) reads sourceByField by the same candidate key and has the same vocabulary mismatch — aliasing only confidence would have left provenance/staleness reasoning broken for this field."
  - "Alias writes are guarded on the target key already being present in the (copied) source_by_field, so a caller-supplied entry (e.g. hs_linkedin_url answered independently by a provider, or an explicit csv source) is never overwritten by the alias — closes T-72-09-01's tampering concern."
  - "sourceByField is built as a local spread-copy of row.source_by_field, never a mutation of the original — this node echoes { ...row, merge: merged } downstream and the request-level object must not grow keys."
  - "Plan-time discrepancy discovered and NOT escalated to a checkpoint: the plan's Task 1 narrative expected the UPDATE fixture to stay green through RED, but mergeContacts.js's _gate() checks confidence < minConfidence BEFORE reaching the fill_blank_only class branch, so a flat 80 vs hs_linkedin_url's min_confidence 85 returns needs_review unconditionally, regardless of currentValue. Both RED failures share the same root cause and Task 2's planned fix (aliasing both write targets from the one pre-alias key) already resolves both — verified by forward trace and confirmed by the GREEN run, so no architectural fork existed and no ruling was needed."

requirements-completed: [D-72-04, D-72-17, D-72-19, D-72-22]

coverage:
  - id: D1
    description: "A linkedin_url value on an ingest CREATE row lands as BOTH lv_linkedin_url (canonical) and native hs_linkedin_url on the created contact — proven offline against the regenerated committed workflow."
    requirement: "D-72-04"
    verification:
      - kind: integration
        ref: "tests/n8n/ingestWidenedFieldsFlow.test.mjs#D-72-04: a linkedin_url header value produces a Create body carrying BOTH lv_linkedin_url and hs_linkedin_url"
        status: pass
      - kind: integration
        ref: "tests/n8n/ingestWidenedFieldsFlow.test.mjs#D-72-04: hs_linkedin_url is withheld from an update whose contact already holds a different non-blank value"
        status: pass
    human_judgment: false
  - id: D2
    description: "The regression test reproduces F72-1 offline using production's real source_by_field key vocabulary (the pre-alias linkedin_url key), so a recurrence is caught by the suite rather than only by a live gate."
    requirement: "D-72-19"
    verification:
      - kind: unit
        ref: "/usr/bin/grep -c 'source_by_field: { linkedin_url: apollo }' tests/n8n/ingestWidenedFieldsFlow.test.mjs returns 2"
        status: pass
    human_judgment: false
  - id: D3
    description: "F72-1 is closed on the live, deployed HubSpot portal — a real created contact carries both lv_linkedin_url and hs_linkedin_url from a waterfall-found value."
    human_judgment: true
    rationale: "This plan is offline-only (per its objective and CLAUDE.md's never-deploy instruction for gap-closure plans in this phase). Nothing was deployed, bounced, or armed. The live redeploy and a D-72-17-shape read-back are 72-VERIFICATION.md's second 'missing' item for this gap and are deferred to 72-12 (per this plan's 'affects' field) — verify-work must not auto-pass this against a live claim this plan never made."

duration: 35min
completed: 2026-09-12
status: complete
---

# Phase 72 Plan 09: LinkedIn dual-write gap closure (G1) Summary

**One CANDIDATE_ALIASES map inside MERGE_CONTACTS closes the LinkedIn dual-write gap (D-72-04/D-72-17) by undoing preingest.py's key rename at the single place both the confidence derivation and the candidate builder read it, proven offline with a regression fixture that finally uses production's real key vocabulary.**

## Performance

- **Duration:** 35 min
- **Started:** 2026-09-12T14:47:00Z
- **Completed:** 2026-09-12T15:22:00Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Reseeded both D-72-04 regression fixtures in `tests/n8n/ingestWidenedFieldsFlow.test.mjs` with `source_by_field: { linkedin_url: "apollo" }` — the single pre-alias key `preingest.provider_sourced_fields()` actually emits — replacing the already-renamed `{ lv_linkedin_url, hs_linkedin_url }` pair the old (buggy) fixture used, which let the suite stay green through the live F72-1 defect.
- Added `CANDIDATE_ALIASES = { linkedin_url: ["lv_linkedin_url", "hs_linkedin_url"] }` inside `MERGE_CONTACTS` (`scripts/build_cloud_workflows.py`), read by both the `confidenceByField`/`sourceByField` derivation loop and the candidate-builder block, so the rename is spelled exactly once.
- Regenerated `n8n/wf_contact_ingest_cloud.json` and `n8n/wf_contact_ingest_local.json` via `scripts/build_cloud_workflows.py` — no hand-edits, node count unchanged at 78, diff confined to the `MERGE_CONTACTS` node's `jsCode` string in both files.
- Full regression coverage confirmed: `node --test tests/n8n/*.test.mjs` (1167/1167 passed) and `.venv/bin/python -m pytest -q tests/ operator-claude-plugin/tests/` (4947 passed, 154 skipped).

## Task Commits

1. **Task 1: RED — reseed both D-72-04 fixtures with the pre-alias key that production really sends** - `52705d00` (test)
2. **Task 2: one candidate-alias map in MERGE_CONTACTS, read by both the confidence/source derivation and the candidate builder** - `0f7c8c08` (fix)

_No plan-metadata commit was created separately for the RED task per the tracer pattern — the tracer feedback gate (see Deviations) ran between the two task commits and required no separate commit._

## Files Created/Modified
- `tests/n8n/ingestWidenedFieldsFlow.test.mjs` — both D-72-04 fixtures reseeded with the pre-alias `source_by_field` key
- `scripts/build_cloud_workflows.py` — `MERGE_CONTACTS`'s `CANDIDATE_ALIASES` constant, alias-aware `confidenceByField`/`sourceByField` derivation loop, alias-driven candidate builder for `linkedin_url`
- `n8n/wf_contact_ingest_cloud.json` — regenerated (MERGE_CONTACTS node jsCode only)
- `n8n/wf_contact_ingest_local.json` — regenerated (MERGE_CONTACTS node jsCode only)

## Decisions Made
See `key-decisions` in frontmatter. The load-bearing one: the alias fix touches BOTH `confidenceByField` and `sourceByField` (not confidence alone), because `mergeContacts()`'s `_isProviderSource(resolvedSource)` gate reads `sourceByField` by the same candidate key and has the identical vocabulary mismatch — aliasing only the confidence half would have left provenance and the D-72-07 staleness/observation-time logic broken for this field.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug in plan narrative, not in code] Task 1's RED expectation was wrong for the UPDATE fixture — both D-72-04 tests failed, not one**
- **Found during:** Task 1 (RED)
- **Issue:** The plan's `<action>` text predicted the UPDATE test (`ROW_I_EMAIL`) would stay GREEN through RED, reasoning that `fill_blank_only` stages a candidate regardless of confidence once a differing non-blank current value exists. Tracing `mergeContacts.js`'s `_gate()` shows the `confidence < minConfidence` check runs unconditionally *before* the `fill_blank_only` class branch — so a flat confidence of 80 against `hs_linkedin_url`'s `min_confidence: 85` returns `needs_review` regardless of `currentValue`, and the UPDATE test failed too (`decisionFor("hs_linkedin_url").decision === "needs_review"`, not `"stage_only"`).
- **Fix:** No code change was needed for this — Task 2's already-planned fix (aliasing both `lv_linkedin_url` and `hs_linkedin_url` confidence/source from the single `linkedin_url` source entry) raises `hs_linkedin_url`'s confidence to 85 on the very same code path, which clears the threshold, reaches the `fill_blank_only` branch, and correctly resolves to `stage_only` against the differing existing value. Verified: both D-72-04 tests pass after Task 2's GREEN commit.
- **Files modified:** None beyond what Task 1/Task 2 already touched.
- **Verification:** `node --test tests/n8n/ingestWidenedFieldsFlow.test.mjs` — both tests green after the fix.
- **Committed in:** `52705d00` (RED, documents the actual 2-test failure and root cause), `0f7c8c08` (GREEN, resolves both).
- **Not escalated to a checkpoint:** confirmed via forward trace before writing code that no architectural fork existed — the one alias map that Task 2 already specified resolves both failures through the identical mechanism, so this was a plan-narrative inaccuracy (an incomplete trace of `_gate()`'s branch order), not a false assumption that changes what to build.
- **Note for 72-VERIFICATION.md readers:** the `missing:` item's claim that "hs_linkedin_url does not itself need the alias, since its own key already survives unaliased when a provider independently answers it" describes the OLD (buggy) fixture's accidental behavior, where `source_by_field` happened to carry a literal `hs_linkedin_url` key. Production's real `source_by_field` never carries that key for this field (only the pre-alias `linkedin_url`), so `hs_linkedin_url` DOES need the alias — it is not a no-op, as this plan's Task 2 action text itself already anticipated ("It is NOT a pure no-op live"). VERIFICATION.md is left unedited per instructions; this SUMMARY is the correction record.

---

**Total deviations:** 1 auto-resolved (Rule 1 — plan-narrative inaccuracy corrected in the SUMMARY, no code impact since Task 2's design already covered it).
**Impact on plan:** None on scope or design. The fix implemented is exactly the one the plan specified (one alias map, two consumers); only the plan's inline RED-outcome prediction was inaccurate.

## Issues Encountered
- Initial commit message for Task 2 used backticks and curly braces inside a heredoc, which the shell partially re-interpreted (backtick command substitution attempted `"< minConfidence"` as a file redirect) — Task 1's commit message was garbled in a few words as a result (meaning preserved, formatting slightly off; not re-committed since amending is disallowed without an explicit request and the content remains accurate). Task 2's commit message was rewritten without backticks/quotes and written via a temp file + `git commit -F` to avoid a repeat.
- A pre-existing architecture guard test (`tests/test_architecture_guard.py::test_pn1_build_script_never_writes_a_bare_linkedin_or_persona_property_key`) flagged the first draft of the new code comment for containing a bare quoted `"linkedin_url"` literal (the regex scans the whole file text, including comments, for that exact string). Reworded the comment to avoid the literal quoted string; no functional code was affected. Full python suite reconfirmed green afterward.

## User Setup Required
None — no external service configuration required.

## Next Phase Readiness
- G1 is closed offline: both regression fixtures pass with production's real key vocabulary, and a recurrence would be caught by `tests/n8n/ingestWidenedFieldsFlow.test.mjs` before it ever reaches a live gate again.
- **Not closed live.** This plan deployed nothing and armed nothing, per its scope. 72-VERIFICATION.md's second `missing:` item for this gap — regenerate + redeploy + bounce disarmed + a D-72-17-shape live read-back — is deferred to plan 72-12 (see `affects:` above). Until 72-12 runs that read-back, the live HubSpot portal still reflects the pre-fix `wf_contact_ingest_cloud.json` behavior for any contact created before this plan's redeploy.
- Record for 72-12's read-back comparison: the D-72-17 live gate's withheld `lv_linkedin_url` candidate value was the bare handle `jimmybusteed`, while `hs_linkedin_url` landed as a full URL on that same contact. Post-fix, both properties will carry whatever shape `row.linkedin_url` actually holds for a given row — if that's a bare handle, both will be the handle, and `fill_blank_only` will then protect it against a later URL-shaped writer. 72-12 should confirm this against the actual re-created/re-read contact rather than assuming a URL shape.

---
*Phase: 72-enrichment-extras-land-in-hubspot*
*Completed: 2026-09-12*

## Self-Check: PASSED
