---
phase: 61-autonomous-batch-runs
plan: "03"
subsystem: identity-resolution
tags: [n8n, extraction, identity, linkedin, column-mapping, resolutions, plugin]

requires:
  - phase: 61
    provides: "61-02's linkedin match lane (the backend half of D-61-05 CORRECTED) — this plan is the front-end half that lets a linkedin-only row reach it"
provides:
  - "A third `required_identity.any_of` group, `[linkedin_url]`, in both `config/column_mapping.yaml` copies and `n8n/code/columnMap.js`'s hand-written `requiredIdentity()`, pinned equal by a new parity test (D-61-06)"
  - "`extraction.py`'s identity-rejection message COMPOSED from `identity_groups()` rather than a hard-coded sentence, removing one of D-61-06's five drift-prone sites entirely"
  - "`enrich-before-ingest/SKILL.md` documents a linkedin-only row proceeding without a company (D-61-01) and a waterfall-found value being proposed through the existing `resolutions`/`provider_result` loop (D-59-08), never a second proposal surface"
affects: [61-04, 61-05, 61-06]

actuals:
  tokens: 10500
  tasks: 3
  commits: 3

tech-stack:
  added: []
  patterns:
    - "Derive-don't-restate: a rejection message composed at read time from the same config the gate itself reads, so a future config change cannot leave stale prose behind"
    - "Reuse over a second surface: a waterfall-sourced value for a linkedin-only row rides the SAME resolutions/provider_result rewrite-and-revalidate loop extraction.md's non-tabular adapters already use, rather than a parallel proposal mechanism"

key-files:
  created:
    - tests/n8n/columnMapIdentityParity.test.mjs
    - operator-claude-plugin/tests/test_linkedin_row_composition.py
  modified:
    - config/column_mapping.yaml
    - operator-claude-plugin/config/column_mapping.yaml
    - n8n/code/columnMap.js
    - operator-claude-plugin/scripts/extraction.py
    - operator-claude-plugin/skills/contact-upload/extraction.md
    - operator-claude-plugin/skills/enrich-before-ingest/SKILL.md
    - operator-claude-plugin/tests/test_identity_preflight.py
    - operator-claude-plugin/tests/test_extraction_contract.py
    - operator-claude-plugin/tests/test_company_extraction.py
    - operator-claude-plugin/tests/test_skill_sequence_coverage.py
    - operator-claude-plugin/.claude-plugin/plugin.json
    - operator-claude-plugin/CHANGELOG.md
    - n8n/wf_contact_ingest_cloud.json
    - n8n/wf_contact_ingest_local.json

key-decisions:
  - "The company identity message is now 'no identity present: needs a non-blank ''name''' (derived) rather than the old bespoke 'give the company's name — that alone is enough' — no test pinned the friendlier phrasing, and deriving both messages from one function is what closes the drift class rather than keeping a hand-written exception for one record type"
  - "test_company_extraction.py's identical verbatim pin was updated alongside test_extraction_contract.py's (Rule 1) even though only the latter was in the plan's declared files_modified — both pinned the exact same pre-plan contact message and would have broken identically"
  - "test_skill_sequence_coverage.py's COVERED map was edited even though not in the plan's declared files_modified — Task 3's own action text explicitly requires 'registered in the census's COVERED map', and the sequence-inventory ratchet fails the suite otherwise the moment a qualifying new SKILL.md code block is added"
  - "The composition test's new 8-call identity (config_gate.load_config -> preingest.build_rows_spec/rows_from_table -> chunking.plan_chunks/chunk_ceiling -> preingest.match_batch/classify_matches -> extraction.validate) documents the reuse claim as a real, parseable code block rather than only prose — proving the plan's design claim is checked, not merely asserted"

requirements-completed: [INPUT-05]

coverage:
  - id: D1
    description: "A LinkedIn-URL-only row satisfies the identity rule in both the YAML config and columnMap.js's hand-written reimplementation, with a parity test that fails if either side is edited alone"
    requirement: INPUT-05
    verification:
      - kind: unit
        ref: "tests/n8n/columnMapIdentityParity.test.mjs#a row satisfying each configured identity group in full passes requiredIdentity()"
        status: pass
      - kind: unit
        ref: "tests/n8n/columnMapIdentityParity.test.mjs#requiredIdentity() has no group beyond what the YAML configures (linkedin_url alone passes, nothing wilder)"
        status: pass
    human_judgment: false
  - id: D2
    description: "extraction.py's identity-rejection reason is composed from the configured groups, enumerating all three, rather than a hard-coded two-group sentence"
    requirement: INPUT-05
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_extraction_contract.py::test_a_record_with_no_record_type_key_still_routes_to_the_contact_rules"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_identity_preflight.py::test_linkedin_url_alone_satisfies_the_identity_rule_and_the_row_is_accepted"
        status: pass
    human_judgment: false
  - id: D3
    description: "A name-only row (no email, no linkedin_url) still routes to the weak-key rejected path — the new group is additive"
    requirement: INPUT-05
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_identity_preflight.py::test_a_bare_name_with_no_email_and_no_linkedin_is_still_rejected"
        status: pass
    human_judgment: false
  - id: D4
    description: "The no-invention sentence in extraction.md is byte-identical to its pre-plan text, pinned by a durable test rather than a one-time summary check"
    requirement: INPUT-05
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_extraction_contract.py::test_no_invention_sentence_is_byte_identical_to_its_pre_plan_61_03_text"
        status: pass
    human_judgment: false
  - id: D5
    description: "A linkedin-only row is driven end to end through the real match lane to unmatched, then a waterfall-found value is proposed and recorded through the resolutions/provider_result loop and re-validated, with an illegitimate source still rejected"
    requirement: INPUT-05
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_linkedin_row_composition.py::test_a_lusha_hit_for_the_unmatched_row_is_proposed_through_resolutions_and_revalidated"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_linkedin_row_composition.py::test_a_resolutions_entry_naming_an_illegitimate_source_is_rejected_not_laundered"
        status: pass
    human_judgment: false

duration: ~55min
completed: 2026-08-30
status: complete
---

# Phase 61 Plan 03: LinkedIn-Only Row Acceptance, End to End Summary

**A LinkedIn-URL-only row — the exact walk-failure row from 53-WALK-RECORD-3.md FINDING D — now passes every identity gate in the plugin (YAML, columnMap.js, extraction.py), with its rejection message derived from config instead of hard-coded, and its waterfall findings routed through the existing D-59-08 resolutions loop instead of a second proposal surface.**

## Performance

- **Duration:** ~55 min
- **Tasks:** 3
- **Files modified:** 16 (2 new test files, 12 modified, 2 regenerated workflow JSONs)

## Accomplishments

- **Task 1 — the third identity group, with parity.** `required_identity.any_of` in
  both `config/column_mapping.yaml` copies and `n8n/code/columnMap.js`'s
  `requiredIdentity()` gained `[linkedin_url]` as a third, additive group. A new
  `tests/n8n/columnMapIdentityParity.test.mjs`, driven from the YAML rather than
  hand-written cases, fails if either side is edited alone. Regenerated all eight
  workflow JSONs; only the two ingest-lane files (which inline `columnMap.js`)
  changed, confirming the fix's blast radius matched the plan's prediction exactly.
- **Task 2 — a derived rejection message.** `extraction.py`'s two hard-coded
  per-type rejection sentences are replaced by `_identity_rejection_reason()`,
  composed from `identity_groups()` — removing one of D-61-06's five drift-prone
  sites entirely rather than adding a fourth thing to keep in step. The derived
  contact message enumerates all three groups; the derived company message is
  `"no identity present: needs a non-blank 'name'"`. `extraction.md`'s group-list
  sentence now names all three, gained a third worked example (linkedin-only,
  accepted), and the no-invention sentence (D-61-02, untouched) is now pinned by a
  durable byte-identical test per REVIEW-A10, not only a one-time summary check.
- **Task 3 — the resolutions reuse, proven as code.** `enrich-before-ingest/SKILL.md`
  documents that a strong-key-only row proceeds without a company (D-61-01) and
  that a Lusha-only waterfall miss HOLDS the row (D-61-04: Apollo's match body and
  ZoomInfo's `hasZoomKey` never read `linkedin_url` at all) rather than falling
  through to company-oriented `claude_web` research. A hit is proposed through the
  existing `resolutions`/`provider_result` loop — documented as a real, parseable
  8-call code sequence, registered in the sequence-inventory census, and proven end
  to end by a new composition test.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add the third identity group to the two code gates, and pin their parity** - `e7a0e3d` (feat)
2. **Task 2: Derive the refusal message from the configured groups, and update the prose contract** - `76cc9b5` (feat)
3. **Task 3: Route the waterfall's findings through D-59-08's resolutions loop, with a composition test** - `5b5a5fc` (feat)

**Plan metadata:** pending (this commit)

## Files Created/Modified

- `config/column_mapping.yaml`, `operator-claude-plugin/config/column_mapping.yaml` — third identity group `[linkedin_url]`, byte-identical
- `n8n/code/columnMap.js` — `requiredIdentity()` gained the linkedin_url branch
- `n8n/wf_contact_ingest_cloud.json`, `n8n/wf_contact_ingest_local.json` — regenerated (only these two changed of the eight)
- `tests/n8n/columnMapIdentityParity.test.mjs` (new) — YAML-driven parity guard
- `operator-claude-plugin/scripts/extraction.py` — `_identity_rejection_reason()`/`_describe_identity_group()` compose the message from `identity_groups()`
- `operator-claude-plugin/skills/contact-upload/extraction.md` — group-list sentence names all three groups; third worked example added; no-invention sentence untouched
- `operator-claude-plugin/tests/test_extraction_contract.py` — accepted-count assertion 2→3, verbatim refusal pin rewritten to derived text (REVIEW-A1), new no-invention durable pin (REVIEW-A10)
- `operator-claude-plugin/tests/test_company_extraction.py` — identical verbatim pin updated (Rule 1 deviation, see below)
- `operator-claude-plugin/tests/test_identity_preflight.py` — linkedin-only acceptance case + bare-name-still-rejected companion (D-61-03's fence)
- `operator-claude-plugin/skills/enrich-before-ingest/SKILL.md` — step 2 (strong key proceeds, D-61-01; search-widening note), step 5 (Lusha-only hold, D-61-04; resolutions-reuse code block)
- `operator-claude-plugin/tests/test_linkedin_row_composition.py` (new) — end-to-end composition test for the new SKILL.md sequence
- `operator-claude-plugin/tests/test_skill_sequence_coverage.py` — new identity registered in `COVERED`
- `operator-claude-plugin/.claude-plugin/plugin.json`, `operator-claude-plugin/CHANGELOG.md` — 0.29.0 → 0.30.0

## Decisions Made

- The company identity message is now the derived `"no identity present: needs a
  non-blank 'name'"` rather than the old bespoke "give the company's name — that
  alone is enough" — no test pinned the friendlier phrasing, and one derivation
  function for both record types is what actually closes the drift class.
- `test_company_extraction.py`'s identical verbatim pin was updated alongside
  `test_extraction_contract.py`'s, even though only the latter was in the plan's
  declared `files_modified` — both pinned the exact same pre-plan contact message
  and would have broken identically the moment the message changed.
- `test_skill_sequence_coverage.py`'s `COVERED` map was edited even though not in
  the plan's declared `files_modified` — Task 3's own action text explicitly
  requires "registered in the census's COVERED map", and the ratchet fails the
  suite the moment a new qualifying SKILL.md code block appears unregistered.
- The new composition test's identity sequence (`config_gate.load_config ->
  preingest.build_rows_spec/rows_from_table -> chunking.plan_chunks/chunk_ceiling
  -> preingest.match_batch/classify_matches -> extraction.validate`) documents the
  resolutions-reuse claim as real, parseable code — the census scanner is what
  proves the claim is checked, not merely asserted in prose.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated `test_company_extraction.py`'s identical verbatim rejection-message pin**
- **Found during:** Task 2's own full-suite verification run
- **Issue:** `test_extraction_contract_backwards_compat_pin_absent_record_type_routes_to_contacts`
  in `test_company_extraction.py` pinned the exact same pre-plan two-group contact
  rejection sentence as `test_extraction_contract.py`'s pin (REVIEW-A1 named only
  the latter). Deriving the message from three groups broke both identically.
- **Fix:** Updated the assertion to the same derived three-group text, mirroring
  the REVIEW-A1 rewrite.
- **Files modified:** `operator-claude-plugin/tests/test_company_extraction.py`
- **Verification:** `.venv/bin/python -m pytest -q` — full suite green (3385/154 at Task 2, 3389/154 by end of plan).
- **Committed in:** `76cc9b5` (Task 2 commit)

**2. [Rule 3 - Blocking] Registered the new SKILL.md sequence in `test_skill_sequence_coverage.py`'s `COVERED` map**
- **Found during:** Task 3
- **Issue:** Adding the new resolutions-reuse code block to `enrich-before-ingest/SKILL.md`
  created a new, real 8-call sequence identity the sequence-inventory ratchet
  (`test_no_new_or_orphaned_sequence_exists_in_the_live_corpus`) would fail on as
  "UNREGISTERED" without a registered `COVERED` entry pointing at a real covering
  test.
- **Fix:** Registered the identity in `COVERED`, pointing at the new
  `test_linkedin_row_composition.py::test_a_lusha_hit_for_the_unmatched_row_is_proposed_through_resolutions_and_revalidated`.
- **Files modified:** `operator-claude-plugin/tests/test_skill_sequence_coverage.py`
- **Verification:** `.venv/bin/python -m pytest operator-claude-plugin/tests/test_skill_sequence_coverage.py -q` — all green, including the staleness guard confirming the covering test mentions the sink function (`validate`).
- **Committed in:** `5b5a5fc` (Task 3 commit)

---

**Total deviations:** 2 auto-fixed (1 bug/Rule 1, 1 blocking/Rule 3) — both direct,
disclosed consequences of the plan's own stated changes (deriving the message; adding
a new documented code sequence). Neither introduces scope beyond what the plan
already required; neither is in the plan's declared `files_modified`, but both are
named by the plan's own action text or an unavoidable structural consequence of it.
**Impact on plan:** No scope creep. No assertion was weakened, deleted, or reworded —
`git diff -- <touched test files> | grep -cE '^[-+][[:space:]]*assert '` reads 0
across the three identity-preflight test files (the changed assertions are
multi-line string literals, not new/removed `assert` statement lines); the one named
exception (REVIEW-A1's rewrite of the verbatim refusal string) is exactly the
planned edit.

## Issues Encountered

- `chunking.chunk_ceiling` has no fallback for a missing `max_rows_per_match_request`
  key by design — `fake_config` (conftest.py) does not carry it, so the new
  composition test needed the same real-config-example pattern
  `test_chunking.py`'s own match-lane test already uses (`_match_ceiling_config`
  helper). Not a defect; matched an existing, documented convention.

## User Setup Required

None — no external service configuration required. This plan is entirely offline:
YAML/JS edits, a Python message derivation, prose documentation, and tests. Zero
live n8n, HubSpot, Anthropic, or provider calls; zero arming.

## Next Phase Readiness

- **D-61-05 CORRECTED is now fully landed, both halves.** 61-02 made a LinkedIn URL
  searchable on the backend; this plan (61-03) makes every front-end gate accept a
  linkedin-only row so it can reach that lane. The exact walk-failure row
  (53-WALK-RECORD-3.md FINDING D) is no longer refused anywhere in the plugin.
- **Not yet done:** a live proof that a linkedin-only row, sent through the real
  `enrich-before-ingest` flow against the live n8n instance, actually reaches
  HubSpot's new linkedin search lane and gets scored/matched. This plan's own
  `<verification>` was offline-only; a future plan or walk should prove this live.
- Requirement `INPUT-05` is now fully addressed by 61-02 (backend lane) + 61-03
  (front-end acceptance + resolutions reuse) together.

## Self-Check: PASSED

All 16 claimed files verified present on disk; all 3 task commit hashes (`e7a0e3d`,
`76cc9b5`, `5b5a5fc`) verified present in `git log --oneline --all`.

---
*Phase: 61-autonomous-batch-runs*
*Completed: 2026-08-30*
