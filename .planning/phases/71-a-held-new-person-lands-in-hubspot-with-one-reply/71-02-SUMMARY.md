---
phase: 71-a-held-new-person-lands-in-hubspot-with-one-reply
plan: 02
subsystem: operator-claude-plugin (skill wiring, resume decision)
tags: [held-queue, company-known-stamp, stable-identity, resume, tdd]

requires:
  - phase: 71-a-held-new-person-lands-in-hubspot-with-one-reply
    provides: "plan 01's held_queue.identity_keys/stable_key/stamped_domains/legacy_reason, the company_known stamp schema, and the forbidden-marker exemption"
provides:
  - "preingest.confirmed_company_domains(classified, company_spec=None) -- the zero-new-lookup fold over step 2's own match results and company-row confirm table"
  - "run_manifest.rows_to_resume's CONFIDENCE_HELD lookup keyed by held_queue.stable_key(row), so a held entry survives a row_id change across runs"
  - "enrich-before-ingest step 5's persist site stamps company_known onto each held entry; step 6 and review-triage step 2b both derive known_company_domains from held_queue.stamped_domains(held_entries) instead of a hardcoded empty set"
  - "review-triage step 4d: skip/drop record immediately via held_queue.record_verb, closing RESEARCH Assumption A3"
affects: [71-03-a-held-new-person-lands-in-hubspot-with-one-reply]

actuals:
  tokens: 15397
  tasks: 3
  commits: 8
plan_head_before: b1aa65fe10cd441e1ffd518d268faffed8bbd95f

tech-stack:
  added: []
  patterns:
    - "known_company_domains is always seeded from held_queue.stamped_domains(held_entries) first, then grown by in-conversation sources on top (D-71-03) -- never a caller-supplied set from scratch"
    - "A markdown SKILL.md fence that would otherwise churn an already-registered test_skill_sequence_coverage.py tuple can be kept to a single scripts-module call (below the >=2 registration threshold) when the added line has no natural reason to merge into an existing multi-call fence -- used for step 8's held_entries=held_queue.load() and 4d's skip/drop wiring, where the plan didn't ask for a fixed position"
    - "Where the plan explicitly asks for a line to land inside an already-registered fence (step 2/3/5's confirmed_domains and company_known additions), the resulting registry/pin churn is handled as a same-commit deviation, never deferred"

key-files:
  created: []
  modified:
    - operator-claude-plugin/scripts/run_manifest.py
    - operator-claude-plugin/scripts/preingest.py
    - operator-claude-plugin/skills/enrich-before-ingest/SKILL.md
    - operator-claude-plugin/skills/review-triage/SKILL.md
    - operator-claude-plugin/tests/test_run_manifest.py
    - operator-claude-plugin/tests/test_preingest_match.py
    - operator-claude-plugin/tests/test_held_facet_render_composition.py
    - operator-claude-plugin/tests/test_review_triage_facets.py
    - operator-claude-plugin/tests/test_skill_sequence_coverage.py
    - operator-claude-plugin/tests/test_enrich_before_ingest_skill_contract.py
    - operator-claude-plugin/tests/test_batch_finishes_composition.py
    - operator-claude-plugin/tests/test_match_state.py
    - operator-claude-plugin/tests/test_held_queue.py
    - operator-claude-plugin/tests/test_held_queue_facets.py

key-decisions:
  - "Task 1's Open Question 1 (RESEARCH): wired held_entries=held_queue.load() into step 8's watch.resume_or_disclose call; left current_outcomes unwired, filed below as a triaged todo for plan 03 rather than silently deferred a second time."
  - "Task 2's company_spec binding: bound from company_domain.to_envelope_spec's own result (prose reference, since the company-row confirm table's own dispatch is conversational, not literal code in this SKILL.md) -- documented with one sentence rather than inventing a second code path."
  - "confirmed_company_domains is added to the SAME python fence as match_state.save (per the plan's explicit 'add one line to the same fence' instruction), accepting the consequent test_skill_sequence_coverage.py registry churn on three already-registered tuples (step 2, step 3, step 5) rather than dodging it with a separate single-call fence."
  - "Task 3's skip/drop wiring (4d) is placed as its own bolded sub-step, not merged into 4c's create-confirm fence -- skip/drop write nothing to HubSpot and need no grant or re-read, so gating them behind 4c's confirm-and-mark idiom would have been a false dependency."

requirements-completed: []

coverage:
  - id: D1
    description: "run_manifest.rows_to_resume's CONFIDENCE_HELD branch looks up held_entries by held_queue.stable_key(row), computed fresh from the resuming row -- a held entry saved under a prior run's row_id is found by this run's differently-positioned row"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_run_manifest.py#test_a_prior_runs_held_entry_is_found_by_this_runs_differently_positioned_row"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_run_manifest.py#test_a_prior_runs_retry_verb_re_includes_this_runs_differently_positioned_row"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_run_manifest.py#test_the_reported_row_id_stays_the_resuming_rows_own_source_position_never_the_stable_key"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_run_manifest.py#test_a_row_with_no_identity_group_resolves_through_the_total_fallback_without_raising"
        status: pass
    human_judgment: false
  - id: D2
    description: "watch.resume_or_disclose(rows, held_entries=held_queue.load()) is now the live call at enrich-before-ingest step 8, making a confidence_held row's recorded verb actually short-circuit the resume in production"
    verification:
      - kind: integration
        ref: "operator-claude-plugin/tests/test_run_manifest.py#test_resume_or_disclose_with_held_entries_wired_skips_a_settled_row_end_to_end"
        status: pass
    human_judgment: false
  - id: D3
    description: "preingest.confirmed_company_domains folds step-2 auto-matched rows (including a step-3-confirmed row moved into that bucket) and an optional company_spec into a domain->source map, both words members of held_queue.COMPANY_KNOWN_SOURCES, freemail and name-only entries excluded, company-row wins on conflict"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_preingest_match.py#test_an_auto_matched_rows_own_email_domain_is_confirmed_under_step2_match"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_preingest_match.py#test_a_step_3_confirmed_row_moved_into_auto_matched_contributes_identically"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_preingest_match.py#test_every_confirmed_company_domains_value_is_a_member_of_company_known_sources"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_preingest_match.py#test_when_both_sources_name_the_same_domain_the_company_row_word_wins"
        status: pass
    human_judgment: false
  - id: D4
    description: "enrich-before-ingest step 5 stamps company_known onto each held entry (derived from the merged row's own cleaned email domain and step 2/3's confirmed_domains); step 6 derives known_company_domains from held_queue.stamped_domains(held_entries) -- a Jimmy-shaped entry reads new_person from the stamp alone, driven over a real saved-and-reloaded queue"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_held_facet_render_composition.py#test_step_6_fence_loads_the_queue_and_facets_what_it_loaded_not_a_dict_literal"
        status: pass
      - kind: integration
        ref: "operator-claude-plugin/tests/test_batch_finishes_composition.py#test_a_batch_with_a_failed_chunk_and_a_held_row_still_reaches_and_dispatches_its_last_row"
        status: pass
    human_judgment: false
  - id: D5
    description: "review-triage step 2b derives known_company_domains from held_queue.stamped_domains(held_entries) too -- a COLD START (no prior conversation) reads a stamped no_match entry as new_person from the entry alone, and the create is settled under the entry's own stable key after the mark"
    verification:
      - kind: integration
        ref: "operator-claude-plugin/tests/test_review_triage_facets.py#test_one_held_new_person_end_to_end_read_render_create_confirm_mark"
        status: pass
    human_judgment: false
  - id: D6
    description: "review-triage 4d records skip/drop immediately via held_queue.record_verb, in the same idiom 4c already uses -- closing RESEARCH Assumption A3 (no such call site existed before this task)"
    verification: []
    human_judgment: true
    rationale: "The wiring is a direct, mechanical port of 4c's own record_verb idiom (same function, same call shape, already covered by test_held_queue.py's record_verb unit tests) and no operator-facing behavior changed beyond it -- but no new automated test drives the 4d fence itself end to end (it is prose + a two-line snippet with a single scripts-module call, below the sequence-coverage registration threshold), so a human should confirm the prose reads correctly against 4c's own style before the phase's end-of-phase UAT."

duration: 55min
completed: 2026-09-12
status: complete
---

# Phase 71 Plan 2: Wire the tracer's stamp into both surfaces and the resume decision Summary

**A held row's `company_known` stamp (written once, at persist time) now drives `new_person` on both `enrich-before-ingest` step 6 and a cold-start `review-triage` sitting, and `run_manifest.rows_to_resume` looks a held entry up by its stable identity instead of a per-run positional `row_id` — closing both gaps quick batch `260911-w6n` left and plan 01 built the machinery for.**

## Performance

- **Duration:** ~55 min
- **Tasks:** 3
- **Files modified:** 14 (9 declared, 5 undeclared deviations — see below)
- **Commits:** 8

## Accomplishments

- `run_manifest.rows_to_resume`'s `CONFIDENCE_HELD` branch now computes `held_queue.stable_key(row)` fresh from the resuming row and looks the held entry up by that key — the same derivation the write side (plan 01's step-5 edit) already uses. A held entry saved under a prior run's `row_id` is found by a later run's differently-positioned row; the reported `row_id` inside `skipped`/`still_held` stays the source position (D-69-04), unchanged.
- `enrich-before-ingest` step 8 now wires `held_entries=held_queue.load()` into `watch.resume_or_disclose`, making the settled-verb short-circuit (`create`/`skip`/`drop` → excluded regardless of fingerprint) live in production for the first time — it was dead code before this plan (Open Question 1, decided here).
- `preingest.confirmed_company_domains(classified, company_spec=None)`: the zero-new-lookup fold over step 2's own match results (`auto_matched`, including a step-3-confirmed row moved into that bucket) and an optional company-row confirm-table spec, producing a domain→source map whose two words (`step2_match`, `step2_company_row`) are both members of `held_queue.COMPANY_KNOWN_SOURCES`.
- `enrich-before-ingest` step 5's persist fence now stamps `company_known` onto every held entry, derived from the merged row's own cleaned email domain (`enrichment._clean_domain`, the same cleaning `classify_facet` itself applies) looked up in `confirmed_domains`.
- Both operator surfaces — `enrich-before-ingest` step 6 and `review-triage` step 2b — derive `known_company_domains = held_queue.stamped_domains(held_entries)` instead of a hardcoded empty set. `review-triage`'s own cold-start composition test now proves a Jimmy-shaped stamped entry reads `new_person` with zero conversation knowledge and zero domain supplied by the caller.
- `review-triage` step 2b's anomalous branch now says `held_queue.legacy_reason()`'s own sentence (naming the D-71-05 wipe) instead of a generic unreadable line, when one is available.
- New `review-triage` step 4d: `skip`/`drop` now record immediately via `held_queue.record_verb`, in the same idiom 4c already uses — closing RESEARCH Assumption A3, which this plan confirmed by reading (no such call site existed anywhere in the skill before this task).

## Task Commits

1. **Task 1 (RED)** — `cda4f378` (test): cross-run stable-key lookup test, rekeys 6 pre-existing confidence_held fixtures
2. **Task 1 (GREEN)** — `ff213f77` (feat): `rows_to_resume`'s lookup change
3. **Task 2 (RED)** — `95af5e09` (test): `confirmed_company_domains` tests
4. **Task 2 (GREEN)** — `0a4a9401` (feat): `confirmed_company_domains` implementation
5. **Task 2 (wiring, deviation)** — `a9e60345` (test): registry/pin updates across 5 undeclared test files
6. **Task 2 (SKILL.md)** — `15e2602a` (feat): the four SKILL.md wiring edits (steps 2/3/5/6/8)
7. **Task 3 (test)** — `3b79701f` (test): cold-start composition test + registry update
8. **Task 3 (SKILL.md)** — `1f75dc6c` (feat): step 2b stamp read, legacy_reason, 4d skip/drop wiring

**Plan metadata:** (this commit)

## Files Created/Modified

- `operator-claude-plugin/scripts/run_manifest.py` — `rows_to_resume`'s lookup key
- `operator-claude-plugin/scripts/preingest.py` — new `confirmed_company_domains`
- `operator-claude-plugin/skills/enrich-before-ingest/SKILL.md` — steps 2, 3, 5, 6, 8
- `operator-claude-plugin/skills/review-triage/SKILL.md` — steps 2b, 4a, 4c, new 4d
- `operator-claude-plugin/tests/test_run_manifest.py` — new cross-run/resume tests
- `operator-claude-plugin/tests/test_preingest_match.py` — `confirmed_company_domains` tests
- `operator-claude-plugin/tests/test_held_facet_render_composition.py` — stamped-queue cold-start assertion
- `operator-claude-plugin/tests/test_review_triage_facets.py` — cold-start composition test
- `operator-claude-plugin/tests/test_skill_sequence_coverage.py` — 5 registry tuple updates, 1 new entry
- `operator-claude-plugin/tests/test_enrich_before_ingest_skill_contract.py` — re-pinned persist-fence literal/tuple (deviation)
- `operator-claude-plugin/tests/test_batch_finishes_composition.py` — extended to drive the domain/stamp derivation (deviation)
- `operator-claude-plugin/tests/test_match_state.py` — extended round-trip test (deviation)
- `operator-claude-plugin/tests/test_held_queue.py`, `test_held_queue_facets.py` — rekeyed 5 pre-existing fixtures broken by Task 1 (deviation)

## Decisions Made

See `key-decisions` in frontmatter. The two load-bearing ones beyond what's already there:

**Open Question 1 (RESEARCH) — decided in Task 1, recorded here per the plan's own instruction:** `held_entries=held_queue.load()` is wired into step 8; `current_outcomes` stays unwired. Passing `held_entries` is what makes the settled-verb short-circuit live — this phase's own cross-run promise. `current_outcomes` would require a fresh zero-credit match pass whose scope belongs to a separate gap. **This is filed as a triaged `defect` todo for plan 03**, per the plan's own instruction, with `evidence: operator-claude-plugin/scripts/run_manifest.py:449` (the `entry is None or current is None` re-include line).

**RESEARCH Assumption A3 — settled by reading, confirmed true:** before this task, `skip`/`drop`/`retry` were named in `review-triage`'s step-3 answer vocabulary but had NO `held_queue.record_verb` call site anywhere in the skill — only `create` (4c) was wired. This task adds the missing `skip`/`drop` wiring (new step 4d), in the same idiom 4c already uses. `retry` is NOT an operator-facing answer word in `review-triage` at all (confirmed by re-reading steps 1-8 in full and grepping `VERB_RETRY` across `skills/`) — it is read-only there (2b's `entry_verb(e) is None` filter drops it from `undecided`, and 2c's own prose says it "belongs to the next enrichment run's own resume"), so it needed no new wiring.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Adding `preingest.confirmed_company_domains`/`enrichment._clean_domain`/`held_queue.stamped_domains` calls to already-registered SKILL.md fences broke `test_skill_sequence_coverage.py`'s exhaustive registry**
- **Found during:** Task 2, first full-suite run after wiring the SKILL.md steps
- **Issue:** The plan's own action B ("add one line to the SAME fence") and action D ("step 6 replace `known_company_domains = set()`") both insert a new scripts-module call into a python fence `test_skill_sequence_coverage.py` already registers by its exact AST-extracted call tuple. Five tuples changed (step 2, step 3, step 5, and both skills' read/bucket fences), and step 8's `held_entries=held_queue.load()` addition turned a previously-unregistered single-call fence into a newly-registrable two-call one.
- **Fix:** Updated all six registry entries (five changed tuples + one new one) with the actual extracted tuples, read from the test's own failure output as the plan instructs — never guessed. Extended the covering tests (`test_match_state.py`, `test_batch_finishes_composition.py`) to actually drive the new calls, added a new test in `test_run_manifest.py` for the step-8 entry, and re-pinned `test_enrich_before_ingest_skill_contract.py`'s literal `build_entry` call string and byte-for-byte tuple assertion.
- **Files modified:** `test_skill_sequence_coverage.py`, `test_enrich_before_ingest_skill_contract.py`, `test_batch_finishes_composition.py`, `test_match_state.py`, `test_run_manifest.py` (the last already declared for Task 1).
- **Verification:** `test_skill_sequence_coverage.py` and the full plugin suite both green.
- **Committed in:** `a9e60345`

**2. [Rule 3 - Blocking] Five pre-existing `confidence_held` fixtures (from plan 01, unrelated to this task's own files) keyed `held_entries` by a literal `"row-1"`, broken by Task 1's stable-key lookup change**
- **Found during:** Task 2, full-suite run
- **Issue:** `test_held_queue.py::test_persisting_an_email_into_a_held_row_does_not_make_a_no_match_hold_resumable` and four tests in `test_held_queue_facets.py` (`test_a_settled_row_is_not_resumed_even_when_the_fingerprint_now_differs` ×3 parametrizations, `test_an_entry_with_no_status_keeps_todays_fingerprint_behaviour_exactly`) built `held_entries` keyed by the literal string `"row-1"`, matching the OLD `held_entries.get(row_id)` lookup. Task 1's `held_entries.get(held_queue.stable_key(row))` change made these keys miss, since the resuming rows in these fixtures carry no company field and fall to the `source-position::row-1` fallback, not the bare `"row-1"` string.
- **Fix:** Rekeyed all five fixtures onto `held_queue.stable_key(resume_row)`, computed from the same row passed to `rows_to_resume`.
- **Files modified:** `test_held_queue.py`, `test_held_queue_facets.py`.
- **Verification:** Full plugin suite green — 3032 passed, 5 skipped, 0 failed.
- **Committed in:** `a9e60345`

---

**Total deviations:** 2 auto-fixed (both blocking, both direct mechanical consequences of TDD-verified changes this plan's own tasks made — same shape as plan 01's own two deviations). **Impact:** No architectural change, no scope creep — both were necessary to keep the exhaustive skill-sequence registry and the pre-existing resume tests correct after the plan's own required edits.

## Issues Encountered

None beyond the two deviations documented above, both resolved within this plan.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- Both operator surfaces now render `new_person` from the entry's own persist-time stamp, on a cold start, with no lookup anywhere in the path.
- A held entry's settlement (`create`/`skip`/`drop`) survives a run boundary and a `row_id` change, on both the write side (plan 01) and the read side (this plan).
- `current_outcomes` remains unwired at step 8, filed as a triaged todo for plan 03.
- No HubSpot call, no n8n dispatch, no arming, no deploy occurred in this plan, per its own prohibitions. `git status --porcelain -- n8n/` is empty.
- Full plugin suite green: 3032 passed, 5 skipped, 0 failed (≥3006 required). Full root suite green: 4893 passed, 154 skipped. `node --test tests/n8n/*.test.mjs`: 1101 passed, 0 failed.

## TDD Gate Compliance

Both TDD tasks (1 and 2) carry a `test(71-02): ...` commit immediately preceding their `feat(71-02): ...` commit, each verified RED (test run against pre-implementation code, observed failing for the stated reason) before the implementation commit landed:

- Task 1: RED observed as 10 failing tests (`AssertionError`s showing the row landing in `to_resume`/`rows` instead of `skipped`/`()`) against the pre-change `held_entries.get(row_id)` lookup — `cda4f378` before `ff213f77`.
- Task 2: RED observed as `AttributeError: module 'preingest' has no attribute 'confirmed_company_domains'` (8 failing tests) before the function existed — `95af5e09` before `0a4a9401`.
- Task 3 was not marked `tdd="true"` requiring a fresh RED for genuinely new behavior in the SKILL.md wiring sense (the underlying `held_queue`/`held_entries` functions were already exercised); its test-file changes (`3b79701f`) precede its SKILL.md commit (`1f75dc6c`) in the same test-then-feat ordering regardless.

No `refactor(71-02)` commit was needed — no post-GREEN cleanup changed behavior.

## Self-Check: PASSED

- `operator-claude-plugin/scripts/run_manifest.py` — FOUND, `held_entries.get(held_queue.stable_key(row))` present exactly once.
- `operator-claude-plugin/scripts/preingest.py` — FOUND, `def confirmed_company_domains(` present exactly once.
- `operator-claude-plugin/skills/enrich-before-ingest/SKILL.md` — FOUND, contains `held_queue.stamped_domains(held_entries)`, `company_known=`, `held_entries=held_queue.load()`; contains no `known_company_domains = set()`.
- `operator-claude-plugin/skills/review-triage/SKILL.md` — FOUND, contains `held_queue.stamped_domains(held_entries)` and `held_queue.legacy_reason`; contains no `known_company_domains = set()`; heading count still 3.
- Commits `cda4f378`, `ff213f77`, `95af5e09`, `0a4a9401`, `a9e60345`, `15e2602a`, `3b79701f`, `1f75dc6c` — all present in `git log --oneline --all`.
- `.venv/bin/python -m pytest -q --tb=short -p no:cacheprovider operator-claude-plugin/tests/` — 3032 passed, 5 skipped, 0 failed.
- `.venv/bin/python -m pytest -q --tb=short -p no:cacheprovider` (root) — 4893 passed, 154 skipped, 0 failed.
- `node --test tests/n8n/*.test.mjs` — 1101 passed, 0 failed.
- `git status --porcelain -- n8n/` — empty.
- `git status --porcelain` — no path outside `operator-claude-plugin/` or `.planning/` touched; no edit under `~/.claude/plugins/`.

---
*Phase: 71-a-held-new-person-lands-in-hubspot-with-one-reply*
*Completed: 2026-09-12*
