---
phase: 72-enrichment-extras-land-in-hubspot
plan: 03
subsystem: operator-plugin
tags: [preingest, held_queue, merge-policy, linkedin, tdd, create-time-merge, source-by-field]

requires:
  - phase: 72-enrichment-extras-land-in-hubspot
    plan: 02
    provides: the 12-key promotable_contact_props()/canonical_props() convergence
      (mobilephone split, seven remaining widened contact keys, hs_linkedin_url as
      a second native write target) this plan's alias and held-queue widening build on
provides:
  - "preingest.PROVIDER_KEY_ALIASES: a one-entry alias table resolving the waterfall's lv_linkedin_url onto the row's own canonical linkedin_url key, applied before merge_enriched's allowlist test"
  - "preingest.merge_enriched(rows, responses, *, create_row_ids=frozenset()) and IDENTITY_FIELDS: on a named CREATE row, the provider wins over the CSV for every non-identity field"
  - "preingest.provider_sourced_fields(merge_result): the round-level, truthful source_by_field map D-72-22's ingest-lane confidence override reads"
  - "held_queue.ROW_FIELD_ALLOWLIST widened by seven keys (seniority, lv_persona_group, city, state, country, hs_state_code, hs_country_region_code) so a held-then-created row keeps what the waterfall found"
affects: [72-04, 72-08]

actuals:
  tokens: 12256
  tasks: 3
  commits: 6
plan_head_before: a9202145

tech-stack:
  added: []
  patterns:
    - "config-derived-inertness: a boundary strip (strip_enrichment_extras) is left in place unmodified when its drop-set becomes structurally unreachable, rather than removed, because it still guards the STRUCT-01 contract"
    - "a per-field alias table checked BEFORE an allowlist test, so an admitted key can never be an arbitrary attacker-chosen name (T-72-11)"
    - "a new dataclass field (MergeResult.answered_fields) added specifically because the pinned single-argument helper signature (provider_sourced_fields(merge_result)) forced the information onto the result -- conflicts alone cannot recover a blank-fill or byte-equal answer"

key-files:
  created: []
  modified:
    - operator-claude-plugin/scripts/preingest.py
    - operator-claude-plugin/scripts/held_queue.py
    - operator-claude-plugin/skills/enrich-before-ingest/SKILL.md
    - operator-claude-plugin/skills/review-triage/SKILL.md
    - operator-claude-plugin/tests/test_preingest_merge.py
    - operator-claude-plugin/tests/test_held_queue.py
    - operator-claude-plugin/tests/test_enrich_before_ingest_skill_contract.py
    - operator-claude-plugin/tests/test_skill_sequence_coverage.py

key-decisions:
  - "review-triage/SKILL.md's create route (4a) is documented, not wired, for create_row_ids: held_entries[rid]['row'] is already the FINAL merged row (held_queue stores the merged row, never the provider response it came from), so this route calls no merge at all and there is nothing to pass create_row_ids TO. A row held via enrich-before-ingest already had provider-wins applied at ITS OWN merge time, since that skill now passes every classified['unmatched'] row_id as create_row_ids (an unmatched row is a create either now, sendable, or later, held-then-created via this very route)."
  - "MergeResult gained a new field (answered_fields) despite the plan's 'no new MergeResult field... needed anywhere' sentence -- that sentence is scoped to the D-72-20 conflict-recording half (conflicts already carries everything D-72-20 asks for); provider_sourced_fields(merge_result)'s pinned single-argument signature has no other way to recover 'the provider answered this field' for a blank-fill or byte-equal value, since neither produces a conflict entry."
  - "source_by_field wires into enrich-before-ingest/SKILL.md only, not review-triage -- the plan's must_haves name only enrich-before-ingest for D-72-07, and review-triage 4b delegates its dispatch to contact-upload/SKILL.md 'by heading, never a second copy' with no code block of its own to add the kwarg to."
  - "held_queue.ROW_FIELD_ALLOWLIST stays an explicitly enumerated tuple, not derived from promotable_contact_props()/canonical_props() -- unchanged reasoning from before this plan (import cycle with preingest; extraction._load_mapping raises on an unresolvable mapping)."

requirements-completed: [D-72-19, D-72-05, D-72-20, D-72-01]

coverage:
  - id: D1
    description: "D-72-19: a provider response carrying lv_linkedin_url lands on the merged row's own linkedin_url key (never a surviving lv_linkedin_url key), and PROVIDER_KEY_ALIASES is a closed one-entry dict checked before the allowed_keys test"
    requirement: D-72-19
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_preingest_merge.py::test_provider_key_aliases_maps_lv_linkedin_url_onto_the_rows_own_linkedin_url_key"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_preingest_merge.py::test_a_response_carrying_both_linkedin_names_resolves_to_one_key_with_a_conflict_recorded"
        status: pass
    human_judgment: false
  - id: D2
    description: "D-72-01: strip_enrichment_extras is inert for a real merged row carrying every promotable key, proven behaviourally (not by asserting an empty drop-set) by driving a response through merge_enriched with every promotable key except the one lane-side-only write target no real response ever carries"
    requirement: D-72-01
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_preingest_merge.py::test_strip_enrichment_extras_is_inert_for_a_real_merged_row_carrying_every_promotable_key"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_preingest_merge.py::test_write_dispatch_csv_accepts_a_merged_row_with_every_promotable_key"
        status: pass
    human_judgment: false
  - id: D3
    description: "D-72-05: on a CREATE row, a differing provider value replaces the CSV value for jobtitle/phone/mobilephone/seniority/city/state/country/hs_state_code/hs_country_region_code/lv_persona_group/linkedin_url, recorded replaced:True; email/firstname/lastname/company never replace, recorded replaced:False; a non-create row keeps the pre-72 rule; the default call is byte-identical to the empty create_row_ids set"
    requirement: D-72-05
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_preingest_merge.py::test_a_create_row_conflict_promotes_the_provider_value_for_non_identity_fields (11 parametrized fields)"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_preingest_merge.py::test_a_create_row_conflict_never_replaces_an_identity_field (4 parametrized fields)"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_preingest_merge.py::test_a_create_row_id_does_not_affect_a_different_row_not_named"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_preingest_merge.py::test_merge_enriched_without_create_row_ids_is_byte_identical_to_the_empty_set"
        status: pass
    human_judgment: false
  - id: D4
    description: "D-72-20: the CSV loser on a CREATE conflict lives in MergeResult.conflicts only; held_queue.build_entry's persisted top-level key set is unchanged; neither preingest.py's nor held_queue.py's NEW code contains a source_values key"
    requirement: D-72-20
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_preingest_merge.py::test_held_queue_build_entry_key_set_is_unchanged_by_this_plan"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_held_queue.py::test_the_entrys_top_level_key_set_is_unchanged_by_the_widening"
        status: pass
    human_judgment: false
  - id: D5
    description: "D-72-07/D-72-22 enabling fact: provider_sourced_fields(merge_result) names a field only when the waterfall answered it for every answered row, omits a partially-answered field, never names a dropped key, and is wired into enrich-before-ingest/SKILL.md's dispatch as source_by_field={f: 'waterfall' for f in ...}"
    requirement: D-72-07
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_preingest_merge.py::test_provider_sourced_fields_names_a_field_answered_for_every_row_and_omits_a_partial_one"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_preingest_merge.py::test_provider_sourced_fields_never_names_a_dropped_key"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_preingest_merge.py::test_provider_sourced_fields_is_empty_when_nothing_was_answered"
        status: pass
      - kind: manual_procedural
        ref: "grep -c provider_sourced_fields|source_by_field operator-claude-plugin/scripts/preingest.py operator-claude-plugin/skills/enrich-before-ingest/SKILL.md"
        status: pass
    human_judgment: false
  - id: D6
    description: "D-72-01/D-72-15 (held_queue): a held entry carrying seniority, lv_persona_group, and the five location keys persists all seven and survives a save/load round-trip; the closed tuple still drops an arbitrary spreadsheet column and a forbidden-shaped non-allowlisted key; suggestion_declines.ROW_FIELD_ALLOWLIST is untouched"
    requirement: D-72-01
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_held_queue.py::test_the_seven_widened_keys_all_persist_and_survive_a_save_load_round_trip"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_held_queue.py::test_a_forbidden_shaped_row_key_outside_the_allowlist_is_dropped_not_refused"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_held_queue.py::test_suggestion_declines_row_field_allowlist_is_unchanged_by_this_plan"
        status: pass
    human_judgment: false
  - id: D7
    description: "Review-triage's create route knowingly does not call merge_enriched (documented, not a gap) -- a product-adjacent architectural observation, not something a test can adjudicate"
    human_judgment: true
    rationale: "Whether the operator wants review-triage's create route to re-derive create_row_ids semantics some other way, or accepts that the decision is fully baked in upstream at enrich-before-ingest's own merge time, is a design judgment this plan documents rather than resolves further -- see Deviations."

duration: 60min
completed: 2026-09-12
status: complete
---

# Phase 72 Plan 03: Enrichment Extras Land in HubSpot — LinkedIn Naming, Create-Time Merge, Held Widening Summary

**A one-entry alias table resolves the LinkedIn naming fork so `strip_enrichment_extras` is now structurally inert, a new `create_row_ids` kwarg makes the waterfall beat a stale spreadsheet cell on a brand-new contact while never touching identity fields, and `held_queue.ROW_FIELD_ALLOWLIST` widens by seven keys so a person held on one sitting and created on the next still carries the geo, seniority and persona the waterfall paid for.**

## Performance

- **Duration:** ~60 min
- **Tasks:** 3
- **Files modified:** 8 (0 created)
- **Commits:** 6 (3 TDD RED/GREEN pairs)

## Accomplishments

- `preingest.PROVIDER_KEY_ALIASES = {"lv_linkedin_url": "linkedin_url"}` (D-72-19): the waterfall's promotable name and the CSV's canonical name are now one logical field. Applied in `merge_enriched`'s per-field loop BEFORE the `allowed_keys` test, so the aliased name is what is checked, compared, recorded in `conflicts`, and written — `dropped_property_keys` still reports the ORIGINAL key a caller sent. `config/column_mapping.yaml`'s aliases and `required_identity.any_of` are untouched, confirmed by re-running `tests/n8n/columnMapIdentityParity.test.mjs` unmodified (4/4 pass).
- `strip_enrichment_extras` needed no code edit — once `lv_linkedin_url` is aliased away and `hs_linkedin_url` (D-72-04's second, native, lane-side-only write target) never rides a row as a response key, the function's drop-set (`promotable_contact_props() - canonical_props()`, still exactly `{lv_linkedin_url, hs_linkedin_url}`) can never match anything on a real merged row. Proved behaviourally: a row built by driving every `promotable_contact_props()` key (minus the one lane-only exception) through a real `merge_enriched` call survives `strip_enrichment_extras` byte-for-byte, and `write_dispatch_csv` accepts it without raising.
- `merge_enriched(rows, responses, *, create_row_ids=frozenset())` and `IDENTITY_FIELDS = ("email", "firstname", "lastname", "company")` (D-72-05): on a row named in `create_row_ids`, a differing provider value now replaces the CSV value for every field except the four identity fields — proven across all eleven non-identity promotable/aliased fields and all four identity fields via parametrized tests, plus a per-row scoping test (`create_row_ids` on one row never leaks to a sibling row in the same batch) and a byte-identical-to-empty-set additive proof. Every replacement is recorded in the pre-existing `conflicts` tuple; no new key reaches the persisted held-entry schema (D-72-20).
- `preingest.provider_sourced_fields(merge_result)` (D-72-07/D-72-22): the round-level, truthful `source_by_field` map — names a field only when the waterfall answered it for EVERY answered row in the batch, never a field answered for only some rows (the conservative, under-claiming direction). This required a new `MergeResult.answered_fields` field (one entry per answered row, the keys that row's response supplied AND passed the allowlist) — `conflicts` alone cannot recover "the provider answered this field" for a blank-fill or byte-equal value, since neither produces a conflict entry, and the helper's pinned single-argument signature forces the information onto the result.
- `enrich-before-ingest/SKILL.md` wired both new mechanisms into production: step 5's `merge_enriched` call now passes `create_row_ids={row["row_id"] for row in unmatched_rows}` — every unmatched row is a create either now (sendable) or later (held, then created via review-triage 4a), so provider-wins applies uniformly regardless of route; step 7's `dispatch.dispatch(...)` call now passes `source_by_field={f: "waterfall" for f in preingest.provider_sourced_fields(merge_report)}`, making D-72-22's confidence override reachable on the enrich-before-ingest production path for the first time (previously only reachable in plan 01's own test fixtures).
- `held_queue.ROW_FIELD_ALLOWLIST` widened by seven keys — `seniority`, `lv_persona_group`, `city`, `state`, `country`, `hs_state_code`, `hs_country_region_code` (D-72-01/D-72-15) — kept as an explicitly enumerated tuple (still cannot import `preingest`/`extraction` directly, for the same reasons as before this plan). The tuple's own comment and the module docstring record that Phase 72 FLIPPED the "not needed by a create" rationale rather than overriding it: a create resumed from this queue via review-triage's own step 4a is exactly the D-72-17 read-back route. `hs_linkedin_url` stays excluded (a lane-side-only write target with no reachable producer). `suggestion_declines.ROW_FIELD_ALLOWLIST` and `_looks_forbidden` are untouched, confirmed by dedicated tests and `git diff` showing zero changes to `suggestion_declines.py` in this plan.

## Task Commits

TDD plan — every task followed RED/GREEN discipline (`tdd="true"`):

1. **Task 1 RED: failing tests for the lv_linkedin_url/linkedin_url naming alias** — `f2d3e8db` (test)
2. **Task 1 GREEN: lv_linkedin_url aliases onto the row's own linkedin_url key** — `fb0e9f0c` (feat)
3. **Task 2 RED: failing tests for create-time provider-wins and source_by_field** — `d43a961a` (test)
4. **Task 2 GREEN: on CREATE the provider wins, and provider_sourced_fields feeds source_by_field** — `c8943823` (feat)
5. **Task 3 RED: failing tests for the held_queue.ROW_FIELD_ALLOWLIST widening** — `d0c25b0b` (test)
6. **Task 3 GREEN: a held row keeps the geo, seniority and persona a later create needs** — `dbb1cee1` (feat)

**Plan metadata:** this commit (SUMMARY + STATE + ROADMAP + REQUIREMENTS).

### RED evidence, all three tasks

`gsd_run check tdd-red-evidence` parses TAP output only (`# tests N` / `not ok N - <name>` lines) and this project's Python tests run under pytest's default reporter, not TAP — confirmed directly: feeding it a real pre-fix pytest run classified it `INVALID_RED` / `zero_tests_discovered` regardless of the actual pass/fail content, because it never recognizes pytest's own summary format. This is the same disclosed limitation `68-01-SUMMARY.md` and `70-05-SUMMARY.md` already recorded for this install. RED evidence is instead the real pytest run, quoted in each RED commit's own message:

- **Task 1:** pre-fix `test_preingest_merge.py` run exited 1 with 4 failures, including the target test `test_provider_key_aliases_maps_lv_linkedin_url_onto_the_rows_own_linkedin_url_key` failing on `assert merged["linkedin_url"] == "https://li/amy"` → `KeyError: 'linkedin_url'`.
- **Task 2:** filtered pre-fix run produced 19 failures / 1 pass, every failure a real `TypeError` (`unexpected keyword argument 'create_row_ids'`) or `AttributeError` (`no attribute 'provider_sourced_fields'`) — never a load/fixture crash.
- **Task 3:** filtered pre-fix run produced 3 failures / 9 passes, every failure a real `AssertionError`/`KeyError` for the planned widening; the 9 passes are the additive controls (top-level key set, forbidden-key drop, `suggestion_declines` unchanged) that correctly need no code change.

## Files Created/Modified

- `operator-claude-plugin/scripts/preingest.py` — `PROVIDER_KEY_ALIASES`, `IDENTITY_FIELDS`, `merge_enriched`'s `create_row_ids` kwarg and per-field loop changes, `MergeResult.answered_fields`, `provider_sourced_fields()`.
- `operator-claude-plugin/scripts/held_queue.py` — `ROW_FIELD_ALLOWLIST` widened by seven keys; comment and module docstring updated to record the rationale flip.
- `operator-claude-plugin/skills/enrich-before-ingest/SKILL.md` — step 5 passes `create_row_ids`; step 7 computes and passes `source_by_field`; `preingest` added to step 7's import line.
- `operator-claude-plugin/skills/review-triage/SKILL.md` — documentation-only comment at 4a explaining why `create_row_ids` does not apply on this route.
- `operator-claude-plugin/tests/test_preingest_merge.py` — new tests for all three tasks; four pre-existing tests updated (two swapped `lv_linkedin_url` for `hs_linkedin_url` as their "still promotable, not canonical" demonstration key; one swapped `lv_linkedin_url` for `hs_linkedin_url` in the policy-unreadable fallback test since the alias now fires regardless of policy readability; one updated to expect `seniority` surviving into a held-queue entry).
- `operator-claude-plugin/tests/test_held_queue.py` — new tests for Task 3; two pre-existing tests updated to use `hs_linkedin_url` as their "still excluded" demonstration key instead of `seniority`/`city`.
- `operator-claude-plugin/tests/test_enrich_before_ingest_skill_contract.py` — `RECOVERED_MERGE_CALL` updated to pin the `merge_enriched(...)` call's now-multi-line opening, since `create_row_ids=` widened it past one line.
- `operator-claude-plugin/tests/test_skill_sequence_coverage.py` — the enrich-before-ingest ingest-send sequence registry widened in place to include the new `preingest.provider_sourced_fields` call, same covering nodeid (a pure, local, no-I/O computation that does not change the composition that nodeid actually drives).

## Decisions Made

- **Review-triage's create route (4a) documents `create_row_ids` rather than calling `merge_enriched` with it** — see Deviations below; this was the single most consequential interpretive question in this plan, resolved by tracing the actual data flow rather than guessing.
- **`MergeResult.answered_fields` is a new field** — the plan's "no new `MergeResult` field... needed anywhere" sentence is read as scoped to the D-72-20 conflict-recording half specifically (which is true — `conflicts` needed no new field), not a blanket prohibition; `provider_sourced_fields`'s pinned signature (`merge_result` alone) has no other source for "the provider answered this field" that survives a blank-fill or byte-equal value.
- **`source_by_field` wires into `enrich-before-ingest/SKILL.md` only** — the plan's `must_haves` explicitly name only that skill for D-72-07; `review-triage`'s create dispatch delegates to `contact-upload/SKILL.md` "by heading, never a second copy" and has no code block of its own to add the kwarg to.
- **`suggestion_declines.py` was not touched, and was never going to satisfy the plan's own verify script** — see Issues Encountered.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug fallout] Four pre-existing tests broken by the D-72-19 alias landing**
- **Found during:** Task 1, running the full targeted test file after the alias landed.
- **Issue:** `test_a_policy_promotable_key_fills_a_blank_row_field_instead_of_being_dropped` asserted `merged["lv_linkedin_url"]`; `test_without_the_new_strip_the_step_7_chain_raises_non_canonical_key_in_row` and `test_the_suggest_contacts_path_tolerates_a_widened_key_through_validate` used `lv_linkedin_url` as their "promotable but not canonical" demonstration key, which the alias now resolves to canonical `linkedin_url`; `test_merge_allowlist_falls_back_to_canonical_props_when_the_policy_is_unreadable` used the same key to demonstrate a fallback-drop that the alias now bypasses regardless of policy readability.
- **Fix:** updated the first test's assertions to the aliased key; swapped the remaining three to `hs_linkedin_url` — the one remaining promotable-but-not-canonical key the alias does not touch.
- **Files modified:** `operator-claude-plugin/tests/test_preingest_merge.py`.
- **Verification:** full `test_preingest_merge.py` suite green (87 passed after Task 2's additions).
- **Committed in:** `fb0e9f0c` (Task 1 GREEN commit).

**2. [Rule 1 - Bug fallout] Three tests/registries broken by the `create_row_ids` kwarg and `source_by_field` wiring**
- **Found during:** Task 2, running the targeted verify commands and the full plugin suite after the GREEN implementation.
- **Issue:** `test_held_queue.py::test_an_enriched_held_row_survives_the_write_to_disk_end_to_end` asserted `jimmy["lv_linkedin_url"]` (now aliased to `jimmy["linkedin_url"]`, already admitted via `enrichment.MATCH_LOOKUP_KEYS`); `test_enrich_before_ingest_skill_contract.py`'s `RECOVERED_MERGE_CALL` pinned the exact single-line `merge_enriched(unmatched_rows, recovery["responses"])` call, which the `create_row_ids=` kwarg addition made multi-line; `test_skill_sequence_coverage.py`'s registered call sequence for the enrich-before-ingest ingest-send fence did not include the new `preingest.provider_sourced_fields` call.
- **Fix:** updated the first assertion to the aliased key; narrowed `RECOVERED_MERGE_CALL` to the call's stable opening two lines; widened the registered sequence tuple in place, keeping the same covering nodeid since the actual composition that test drives (`record_dispatch_outcome`/`run_report.record_audit`) is unaffected by the new pure, local, no-I/O call.
- **Files modified:** `operator-claude-plugin/tests/test_held_queue.py`, `operator-claude-plugin/tests/test_enrich_before_ingest_skill_contract.py`, `operator-claude-plugin/tests/test_skill_sequence_coverage.py`.
- **Verification:** the four targeted files' full suites green (207 passed); full plugin suite green (3064 passed, 5 skipped).
- **Committed in:** `c8943823` (Task 2 GREEN commit).

**3. [Rule 1 - Bug fallout] Two pre-existing tests broken by the held_queue widening**
- **Found during:** Task 3, running the targeted verify commands after the GREEN implementation.
- **Issue:** `test_held_queue.py::test_build_entry_only_persists_allowlisted_row_fields` and `test_an_enriched_held_row_survives_the_write_to_disk_end_to_end` used `seniority`/`city` as their "still excluded from the closed allowlist" demonstration keys — both are now legitimately admitted.
- **Fix:** swapped both to `hs_linkedin_url` (the one remaining lane-side-only key with no reachable producer); the second test's assertion was inverted to expect `city` present and `hs_linkedin_url` absent.
- **Files modified:** `operator-claude-plugin/tests/test_held_queue.py`.
- **Verification:** targeted verify suite green (201 passed); full plugin suite green (3068 passed, 5 skipped); full repo suite green (4929 passed, 154 skipped); `node --test tests/n8n/*.test.mjs` 1113/1113, zero diff.
- **Committed in:** `dbb1cee1` (Task 3 GREEN commit).

---

**Total deviations:** 3 Rule 1 fallout groups (pre-existing tests broken by this plan's own correct behavior changes), covering 8 files beyond the plan's own `<files>` lists across all three tasks combined (`test_enrich_before_ingest_skill_contract.py`, `test_skill_sequence_coverage.py` beyond Task 2's own list; no new production files beyond the plan's own five).
**Impact on plan:** every fix is test/registry fallout mechanically caused by this plan's own intended widenings; no production behavior beyond what each task's `<behavior>`/`<action>` section specifies was touched by any fix.

## Issues Encountered

- **The plan's Task 2 read_first premise for `review-triage/SKILL.md` was wrong: there is no `merge_enriched` call site on the create route (4a) at all.** `held_entries[rid]["row"]` is already the FINAL merged row, projected through `held_queue.ROW_FIELD_ALLOWLIST` — no raw provider `properties` response survives on disk to re-merge against. Consulted `advisor()` before committing to an interpretation. Resolution: documented the fact at the 4a code block (satisfying the plan's grep-based verify, which only checks the string `create_row_ids` appears, honestly) rather than inserting a no-op `merge_enriched(..., [], create_row_ids=...)` call whose only purpose would have been passing that grep. **Standing gap, not fixed here and out of this plan's file scope:** `suggest_contacts.py` also calls `merge_enriched` (its own docstring names it as the other caller) and is NOT in this plan's `<files>` list — a row held via `suggest-contacts` and later approved as a create through review-triage will NOT have had D-72-05's provider-wins rule applied at ITS merge time, since that call site passes no `create_row_ids`. No test exists for this gap and no live run has hit it; per CLAUDE.md §31 this is a sentence in this SUMMARY, not a todo.
- **`preingest.rerequest_unanswered` constructs its own `MergeResult` manually and does not propagate the new `answered_fields` field from either the original `merge_report` or its own `retry_result`.** `rerequest_unanswered` is not in this plan's `<files>` list. Practical consequence: if a caller runs `provider_sourced_fields` on the result of a re-request pass, any field the RETRY answered will read as never-answered (empty `answered_fields` for those rows), understating — never overstating — the truthful `source_by_field` map. This is the same safe, under-claiming direction D-72-07 already requires, so it is not a correctness regression, only a completeness gap. No test exists for this and no todo is filed (CLAUDE.md §31) — named here for the record.
- **The plan's own Task 3 `<verify>` grep asserts `suggestion_declines.ROW_FIELD_ALLOWLIST` must NOT contain `"city"`, but it already does** — added correctly by Plan 02 (Rule 1 fallout, restoring that module's own documented invariant `== extraction.canonical_props()`), before this plan touched anything. Confirmed via `git diff` that no commit in this plan modifies `suggestion_declines.py` at all. This is a stale plan-text assumption (the verify script predates Plan 02's landed widening), not a defect introduced here; the actual acceptance criterion — "`suggestion_declines.ROW_FIELD_ALLOWLIST` is unchanged [by this plan]" — is met and independently pinned by `test_suggestion_declines_row_field_allowlist_is_unchanged_by_this_plan`.
- **The pre-existing, unrelated `source_values` string in `preingest.py`'s `_row_view` (a dry-run preview-rendering helper, pre-dating this plan by 5+ commits) makes the Task 2 `<verify>` grep for `source_values` in `preingest.py` fail on its face** (it counts 4, not 0) — this is a local variable name and a preview-only dict key, unrelated to the persisted held-entry schema D-72-20 protects. The real acceptance criterion (no `source_values` key added to `held_queue.build_entry`'s output) is met and independently pinned by tests.

## Known Stubs

None — every mechanism this plan adds (`PROVIDER_KEY_ALIASES`, `create_row_ids`/`IDENTITY_FIELDS`, `provider_sourced_fields`, the `held_queue` widening) is exercised end-to-end by real tests and wired into the actual production SKILL.md call sites (except review-triage's documented non-wiring, explained above).

## User Setup Required

None — no external service configuration required. Nothing in this plan deploys, bounces, or arms anything, and nothing here calls HubSpot or n8n Cloud.

## Next Phase Readiness

- Plan 04's recency/TTL gate can now read a genuinely truthful `source_by_field` on the enrich-before-ingest path (this plan's own must-have), and plan 04's `merge_enriched`-adjacent recency work should be aware that `MergeResult` now carries an `answered_fields` field alongside `conflicts`.
- The two named gaps above (suggest-contacts' own `merge_enriched` call not passing `create_row_ids`; `rerequest_unanswered` not propagating `answered_fields`) are not blockers for this phase's own D-72-17 live gate, since that gate's own scenario (re-run one absent person through `enrich-before-ingest`, `create all 1`) exercises the wired path, not either gap.
- `docs/OPERATOR-AUTONOMOUS-BATCH-UAT.md`'s D-72-17 gate spec (a later plan's job) should confirm the created contact's `linkedin_url`/`lv_linkedin_url`/`hs_linkedin_url` trio and geo fields land as this plan's tests predict.

## Self-Check: PASSED

- `[ -f operator-claude-plugin/scripts/preingest.py ]` → FOUND
- `[ -f operator-claude-plugin/scripts/held_queue.py ]` → FOUND
- `[ -f operator-claude-plugin/tests/test_preingest_merge.py ]` → FOUND
- `git log --oneline --all | grep -q f2d3e8db` → FOUND
- `git log --oneline --all | grep -q fb0e9f0c` → FOUND
- `git log --oneline --all | grep -q d43a961a` → FOUND
- `git log --oneline --all | grep -q c8943823` → FOUND
- `git log --oneline --all | grep -q d0c25b0b` → FOUND
- `git log --oneline --all | grep -q dbb1cee1` → FOUND
- All plan-level `<verification>` commands re-run and passing: `.venv/bin/python -m pytest -q operator-claude-plugin/tests/ tests/` → 4929 passed, 154 skipped; `node --test tests/n8n/*.test.mjs` → 1113/1113; `config/column_mapping.yaml` byte-unchanged since Plan 02's close, alias values contain no `lv_linkedin_url`, identity groups unchanged, `columnMapIdentityParity.test.mjs` passes unmodified.

---
*Phase: 72-enrichment-extras-land-in-hubspot*
*Completed: 2026-09-12*
