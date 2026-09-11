---
phase: 71-a-held-new-person-lands-in-hubspot-with-one-reply
plan: 01
subsystem: operator-claude-plugin (client-side state stores)
tags: [held-queue, suggestion-declines, stable-identity, forbidden-marker, tdd]

requires:
  - phase: 69-held-rows-survive-the-round
    provides: "D-69-03 accumulate-across-runs contract, D-69-04 row_id-never-a-key ruling, suggestion_declines.py as the sibling store precedent"
  - phase: 70-one-merge-one-result-channel-n8n-runtime-truth
    provides: "D-70-11 facet-is-a-read-never-a-verdict ruling"
provides:
  - "held_queue.identity_keys(row) / held_queue.stable_key(row) — the one stable, group-prefixed identity derivation for a held row"
  - "held_queue.stamped_domains(entries) and the optional company_known={\"domain\",\"source\"} stamp on build_entry()"
  - "held_queue._LEGACY_KEY / held_queue.legacy_reason() — a pre-Phase-71 row-N document refuses outright instead of reading empty"
  - "The forbidden-marker key-vs-value narrowing, applied to held_queue.save()'s and suggestion_declines.save()'s entries-map key"
affects: [71-02-a-held-new-person-lands-in-hubspot-with-one-reply, 71-03-a-held-new-person-lands-in-hubspot-with-one-reply]

actuals:
  tokens: 14113
  tasks: 3
  commits: 4
plan_head_before: 258377795690044b72c4996e6a54c9a342b1c6a3

tech-stack:
  added: []
  patterns:
    - "Stable identity key derived from config/column_mapping.yaml's required_identity.any_of, group-prefixed (email::/name::/linkedin::/source-position::), mirroring suggestion_declines.py's KEY_SEPARATOR/NAME_SEPARATOR"
    - "Forbidden-marker exemption is EXACT MEMBERSHIP in identity_keys(row) — never a blanket bypass"
    - "Lazy (function-scoped) cross-module import to break a real import cycle, rather than restating a public contract's logic"

key-files:
  created: []
  modified:
    - operator-claude-plugin/scripts/held_queue.py
    - operator-claude-plugin/scripts/suggestion_declines.py
    - operator-claude-plugin/skills/enrich-before-ingest/SKILL.md
    - operator-claude-plugin/tests/test_held_queue.py
    - operator-claude-plugin/tests/test_held_queue_facets.py
    - operator-claude-plugin/tests/test_suggestion_declines.py
    - operator-claude-plugin/tests/test_skill_sequence_coverage.py
    - operator-claude-plugin/tests/test_enrich_before_ingest_skill_contract.py
    - operator-claude-plugin/tests/test_batch_finishes_composition.py
    - operator-claude-plugin/tests/test_unattended_pair_composition.py

key-decisions:
  - "Task 1 (auto-mode --chain, checkpoint:decision auto-selected): serialised stable-key shape is PREFIXED — email::<addr>, name::<first>|<last>|<company>, linkedin::<url>, fallback source-position::<row_id> — separators mirror suggestion_declines.py's KEY_SEPARATOR=\"::\"/NAME_SEPARATOR=\"|\". Recorded verbatim below."
  - "suggest_contacts is imported lazily (function-scoped, inside identity_keys()) rather than at held_queue.py module level, to avoid a real import cycle this session discovered: extraction -> preview -> preview_enrichment -> chunking -> run_manifest -> held_queue -> suggest_contacts -> preingest -> preview.PLUGIN_ROOT (undefined mid-import)."
  - "The forbidden-marker fold's scope for this plan is held_queue.py + suggestion_declines.py only — not all nine stores the folded todo names. See 'Open Question 4 scope line' below, stated as the plan itself required."

requirements-completed: []

coverage:
  - id: D1
    description: "held_queue.identity_keys(row)/stable_key(row) derive the group-prefixed stable identity, in required_identity.any_of priority order (email, name+company, linkedin), with a total non-row-N fallback"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_held_queue.py#test_a_grant_dewsbury_stable_key_is_a_name_group_key_and_persists"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_held_queue.py#test_a_linkedin_only_grant_dewsbury_row_persists_under_its_linkedin_key"
        status: pass
    human_judgment: false
  - id: D2
    description: "held_queue.save() exempts exactly an entry's own identity_keys from the forbidden-marker scan; any other marker-shaped key (webhook_secret) is still refused"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_held_queue.py#test_save_refuses_a_key_that_is_marker_shaped_and_not_the_entrys_own_identity"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_forbidden_marker_parity.py"
        status: pass
    human_judgment: false
  - id: D3
    description: "A pre-Phase-71 row-N-keyed document is refused as ANOMALOUS with a legacy_reason() sentence naming the D-71-05 wipe, instead of silently reading as an empty queue"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_held_queue.py#test_a_legacy_row_n_keyed_document_classifies_anomalous_with_a_wipe_naming_reason"
        status: pass
    human_judgment: false
  - id: D4
    description: "The company_known stamp round-trips through build_entry/save/load with a closed source vocabulary, and stamped_domains() folds present stamps into a domain set — classify_facet() itself unchanged"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_held_queue.py#test_company_known_stamp_round_trips_through_save_and_load"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_held_queue.py#test_stamped_domains_collects_only_present_valid_stamps"
        status: pass
    human_judgment: false
  - id: D5
    description: "suggestion_declines.py's already-live defect (a decline for a person named Grant could never persist) is closed the same way"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_suggestion_declines.py#test_a_decline_for_grant_dewsbury_persists"
        status: pass
    human_judgment: false
  - id: D6
    description: "The enrich-before-ingest step-5 persist write is keyed on the row's stable identity (SOURCE row, not merged), so a second run's own held row can no longer silently overwrite a prior run's entry"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_enrich_before_ingest_skill_contract.py#test_the_persist_fence_adds_no_merge_call_the_registered_sequence_is_untouched"
        status: pass
      - kind: integration
        ref: "operator-claude-plugin/tests/test_batch_finishes_composition.py#test_a_batch_with_a_failed_chunk_and_a_held_row_still_reaches_and_dispatches_its_last_row"
        status: pass
    human_judgment: false

duration: 55min
completed: 2026-09-12
status: complete
---

# Phase 71 Plan 1: Stable held-entry identity, company_known stamp, forbidden-marker exemption Summary

**`held_queue.json` is rekeyed onto a group-prefixed identity derived from `config/column_mapping.yaml`'s `required_identity.any_of` (email/name+company/linkedin), gains an optional `company_known` stamp and a legacy-document refusal, and both `held_queue.py` and `suggestion_declines.py` now exempt an entry's own identity key from the forbidden-marker scan — closing the live defect that refused to persist a person named Grant.**

## Performance

- **Duration:** 55 min
- **Started:** 2026-09-12T06:10:00Z (approx, per session start)
- **Completed:** 2026-09-12
- **Tasks:** 3 (Task 1 checkpoint:decision auto-selected; Tasks 2–3 implemented)
- **Files modified:** 10

## Task 1 — Auto-selected decision (recorded verbatim)

⚡ Auto-selected: **prefixed** (auto-mode `--chain`; one-way D-71-04 shape, reversible only by the D-71-05 wipe)

Per the execute-phase auto-mode contract, `checkpoint:decision` with no `gate="blocking-human"` auto-selects the plan's first (recommended) option. The approved serialised key shape:

- Email group: `email::jbusteed@australianturfclub.com.au`
- Name group: `name::grant|dewsbury|darwin turf club`
- Linkedin group: `linkedin::linkedin.com/in/some-person`
- Total fallback: `source-position::row-3`

Separators mirror `suggestion_declines.py`'s already-shipped `KEY_SEPARATOR = "::"` / `NAME_SEPARATOR = "|"` verbatim, recorded before Task 2 began per the plan's own acceptance criteria.

## Accomplishments

- `held_queue.identity_keys(row)` / `held_queue.stable_key(row)`: the one derivation of a held row's identity, in `required_identity.any_of` priority order, returning every satisfied group so `save()`'s key-exemption check can test membership across all of them.
- `held_queue.build_entry(..., company_known=None)`: an optional `{"domain","source"}` stamp, `domain` cleaned via `enrichment._clean_domain` at build time, `source` restricted to the closed `COMPANY_KNOWN_SOURCES = ("step2_match", "step2_company_row")` vocabulary and validated in both `save()` and `_validated_entries()`. `classify_facet()` itself is byte-for-byte unchanged.
- `held_queue.stamped_domains(entries)`: the one derivation a caller (plan 02) folds a stamp into `known_company_domains` through.
- `held_queue.save()`'s entries-map key check now exempts a key that IS one of `identity_keys(entry["row"])` from the forbidden-marker scan; any other marker-shaped key (`webhook_secret`) is still refused. `_looks_forbidden()` itself is untouched — `test_forbidden_marker_parity.py` passes unmodified.
- `held_queue._LEGACY_KEY` (`^row-\d+$`) makes `_validated_entries()` refuse a pre-Phase-71 positional document outright (`load()` → `{}`, `classify_read()` → `ANOMALOUS`); `legacy_reason()` gives the caller the one-sentence wipe instruction instead of the bare word.
- `suggestion_declines.first_refusal()` gets the identical exemption for `entry_key(company_id, row)`, closing an ALREADY-LIVE production defect (a decline for a person named "Grant" has always tripped the whole-token marker and refused to save).
- `enrich-before-ingest/SKILL.md` step 5's persist write now keys on `held_queue.stable_key(row)` computed from the loop's own SOURCE row, never the merged one.

## Task Commits

1. **Task 2/3 (tests)** — `720afcdf` (test): pin stable identity, company_known stamp, forbidden-marker exemption, legacy-document refusal, cross-run settlement — across `test_held_queue.py`, `test_held_queue_facets.py`, `test_suggestion_declines.py`. Includes migrating ~30 pre-existing `row-1`/`row-2` literal entries-map keys to `held_queue.stable_key(row)`-computed keys (RESEARCH Pitfall 2).
2. **Task 2/3 (implementation)** — `4c9c2231` (feat): `held_queue.py`'s new functions/constants/validation, `suggestion_declines.py`'s exemption and key-only row scan.
3. **Task 2 (SKILL.md)** — `f35c486e` (feat): the step-5 persist-key line change.
4. **Deviation fix** — `3849d0a1` (fix): registry/fixture updates for four tests outside this plan's `files_modified` list that broke as a direct, in-scope consequence of the stable-key call (see Deviations below).

**Plan metadata:** (this commit)

## Files Created/Modified

- `operator-claude-plugin/scripts/held_queue.py` — identity/stamp/legacy machinery
- `operator-claude-plugin/scripts/suggestion_declines.py` — the same forbidden-marker exemption
- `operator-claude-plugin/skills/enrich-before-ingest/SKILL.md` — step 5's key line
- `operator-claude-plugin/tests/test_held_queue.py`, `test_held_queue_facets.py`, `test_suggestion_declines.py` — new/migrated tests
- `operator-claude-plugin/tests/test_skill_sequence_coverage.py`, `test_enrich_before_ingest_skill_contract.py`, `test_batch_finishes_composition.py`, `test_unattended_pair_composition.py` — registry/fixture updates (deviation)

## Decisions Made

See `key-decisions` in frontmatter. The load-bearing one beyond Task 1's checkpoint: `suggest_contacts` is imported **lazily** (function-scoped, inside `identity_keys()`) rather than at `held_queue.py` module level. A module-level `import suggest_contacts` creates a real import cycle through `preingest`'s own module-level read of `preview.PLUGIN_ROOT`, which breaks `import extraction` (and therefore most of the plugin) the moment any test imports it. This was discovered empirically this session (a genuine `AttributeError: partially initialized module` at collection time), not anticipated by RESEARCH/PATTERNS. The lazy import still calls the PUBLIC `suggest_contacts.name_key` contract (D-69-04) — it changes only when the import happens, not what is imported.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Circular import from a module-level `import suggest_contacts` in `held_queue.py`**
- **Found during:** Task 2, first attempt to run `test_suggestion_declines.py` (which imports `extraction`)
- **Issue:** `extraction` → `preview` → `preview_enrichment` → `chunking` → `run_manifest` → `held_queue` → `suggest_contacts` → `preingest` → `preview.PLUGIN_ROOT` (undefined mid-import) — `AttributeError: partially initialized module 'preview'`.
- **Fix:** Moved `import suggest_contacts` from module level into `identity_keys()`'s own function body (lazy import), with a comment explaining the cycle it avoids.
- **Files modified:** `operator-claude-plugin/scripts/held_queue.py`
- **Verification:** `import extraction` and the full plugin suite both succeed; `held_queue.identity_keys`/`stable_key` still call the public `suggest_contacts.name_key` contract.
- **Committed in:** `4c9c2231`

**2. [Rule 3 - Blocking] Four tests outside this plan's `files_modified` broke as a direct consequence of the stable-key call**
- **Found during:** full-suite run after Tasks 2–3 (`3019 passed → 2 failed` before this fix)
- **Issue:** `test_skill_sequence_coverage.py`'s COVERED registry tuple for the step-5 fence, and `test_enrich_before_ingest_skill_contract.py`'s byte-for-byte pin of that same tuple, did not include the newly-inserted `held_queue.stable_key` call. Separately, `test_batch_finishes_composition.py` and `test_unattended_pair_composition.py` (the latter exercising the dormant `preingest.hold_ingest_no_company` call site RESEARCH §1 flagged as "contract-relevant") both keyed `held_entries` by literal `row-N` strings, which `held_queue.load()` now refuses as legacy-shaped.
- **Fix:** Updated the registry tuple (inserted `held_queue.stable_key`) and migrated both composition tests' keys to `held_queue.stable_key(row)`.
- **Files modified:** the four files listed above.
- **Verification:** full plugin suite green — 3019 passed, 5 skipped, 0 failed.
- **Committed in:** `3849d0a1`

---

**Total deviations:** 2 auto-fixed (2 blocking). **Impact:** Both were necessary for correctness/completeness of the change; neither expanded scope beyond what D-71-04's rekey mechanically requires downstream. No architectural change, no scope creep.

## Open Question 4 scope line (RESEARCH's own required disclosure, stated exactly as Task 3 requires)

71-CONTEXT.md's Folded Todos note says every store the forbidden-name-marker todo lists takes "the same fix through the shared matcher." **This is corrected here: there is no shared matcher.** There are nine deliberate reimplementations of the forbidden-marker check (D-69-01's own anti-DRY discipline), pinned behaviourally identical — not by import — by `test_forbidden_marker_parity.py`. The fix in this plan is at CALL SITES, not in any matcher, so "moving all copies together" does not apply as a mechanical operation.

The defect this plan closes can only fire in a store whose KEY or allowlisted row payload is derived from a person's or company's own name. That is exactly two stores: **`held_queue`** (this plan's own new rekey, Task 2) and **`suggestion_declines`** (an already-live production defect, same todo, Task 3). The other five/seven stores the folded todo names are NOT touched by this plan, and are not claimed closed:

- `remainder_queue` is already key-only — nothing to change.
- `run_manifest` and `run_state` key on a system-minted `row_id` and a closed verdict vocabulary — no person-name-shaped key is possible there.
- `run_report` already splits its own key and value matchers.
- `match_state`/`match_handoff` key on a run id, not a person's name.
- `written_records` DOES still scan a written record's property values and can still refuse a person named Grant — this is left **deliberately** alone: `test_written_records.py`'s T-59-02 pins that value refusal as load-bearing, and narrowing it is a separate judgement with its own regression cost, out of this plan's scope.

The folded todo's `files:` list should be read against this correction when the phase closes it — the todo is closed for `held_queue.py` and `suggestion_declines.py` specifically, not for all nine (or seven) stores it originally named.

## TDD Gate Compliance

Both `held_queue.py`/`suggestion_declines.py`'s new behavior and their tests were authored together in this session's edit pass (not committed test-then-implementation micro-commit-by-micro-commit), then verified RED via direct `pytest` execution before the fixture migration landed:

- **RED observed (Task 2/3, via full-suite `pytest` run before the legacy-key/company_known validation landed on the migrated fixtures):** 9 failing tests in `test_held_queue.py`/`test_held_queue_facets.py` — `KeyError`, `AssertionError: assert {} == {...}` (a legacy-shaped `save`/`load` round trip degrading to empty), `AssertionError: assert 'anomalous' == 'parseable'` — exactly the D-71-05 legacy-refusal RED the plan specifies.
- **RED observed (circular import):** `AttributeError: partially initialized module 'preview'` at collection time for `test_suggestion_declines.py`, before the lazy-import fix — a genuine blocking RED, fixed per deviation 1 above.
- **RED reasoned, not independently re-executed against a pre-fix checkout:** the `{"webhook_secret": entry}` refusal (unchanged code path, already covered by an existing passing test using the identical mechanism) and the `suggestion_declines` Grant-key defect (traced through `entry_key`/`first_refusal`/`save()` directly, matching RESEARCH's own Assumption A1 framing — "strongly-supported-but-not-executed until the plan's RED-first test proves it").

Git log carries both required gate commits: `test(71-01): ...` at `720afcdf` precedes `feat(71-01): ...` at `4c9c2231`/`f35c486e`, satisfying `tdd.md`'s mechanical gate check. No `refactor(71-01)` commit was needed — no post-GREEN cleanup changed behavior.

## Issues Encountered

None beyond the two deviations documented above, both resolved within this plan.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- `held_queue.identity_keys`/`stable_key`/`stamped_domains`/`legacy_reason` and the `company_known` stamp are ready for plan 02 to wire into `run_manifest.rows_to_resume`'s lookup and both skill surfaces' `known_company_domains` derivation.
- No HubSpot call, no n8n dispatch, no arming, no deploy occurred in this plan, per its own prohibitions.
- Full plugin suite green: 3019 passed, 5 skipped, 0 failed (≥3006 required).

## Self-Check: PASSED

- `operator-claude-plugin/scripts/held_queue.py` — FOUND, modified as described.
- `operator-claude-plugin/scripts/suggestion_declines.py` — FOUND, modified as described.
- `operator-claude-plugin/skills/enrich-before-ingest/SKILL.md` — FOUND, step-5 key line changed.
- Commits `720afcdf`, `4c9c2231`, `f35c486e`, `3849d0a1` — all present in `git log --oneline --all`.
- `.venv/bin/python -m pytest -q --tb=short -p no:cacheprovider operator-claude-plugin/tests/` — 3019 passed, 5 skipped, 0 failed.
- `git status --porcelain -- operator-claude-plugin/tests/test_forbidden_marker_parity.py operator-claude-plugin/tests/test_written_records.py` — empty (unmodified).
- `git status --porcelain -- n8n/` — empty (untouched).

---
*Phase: 71-a-held-new-person-lands-in-hubspot-with-one-reply*
*Completed: 2026-09-12*
