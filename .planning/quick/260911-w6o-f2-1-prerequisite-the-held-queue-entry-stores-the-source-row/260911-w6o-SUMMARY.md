---
phase: quick-260911-w6o
plan: 01
subsystem: operator-plugin
tags: [held-queue, enrich-before-ingest, allowlist, forbidden-name-scan, F2-1]

# Dependency graph
requires: []
provides:
  - "held_queue.ROW_FIELD_ALLOWLIST widened to 11 enumerated names (row_id + MATCH_LOOKUP_KEYS + jobtitle, phone, company_id, mobilephone, lv_linkedin_url) so a held entry carries what the waterfall found, not just the operator's source spreadsheet line"
  - "held_queue.save()'s row payload scan narrowed to key names only (_first_forbidden_key); observed_signals/reason/row_id keep full key+value scanning"
  - "skills/enrich-before-ingest/SKILL.md's persist fence passes the merge_report-derived merged row to held_queue.build_entry, never the bare source row"
affects: [260911-w6p, 260911-w6q, 260911-w6r]

actuals:
  tokens: 6808
  tasks: 2
  commits: 2
  plan_head_before: 8437419c

tech-stack:
  added: []
  patterns:
    - "Key-name-only forbidden-scan vs full key+value scan, chosen per field based on whether an allowlist already closes the field to a fixed set before the scan runs (precedent: run_report._looks_forbidden_value)"

key-files:
  created: []
  modified:
    - operator-claude-plugin/scripts/held_queue.py
    - operator-claude-plugin/skills/enrich-before-ingest/SKILL.md
    - operator-claude-plugin/tests/test_held_queue.py
    - operator-claude-plugin/tests/test_enrich_before_ingest_skill_contract.py
    - operator-claude-plugin/tests/test_preingest_merge.py
    - .planning/todos/pending/2026-09-11-forbidden-name-marker-whole-token-still-refuses-grant-token.md

key-decisions:
  - "ROW_FIELD_ALLOWLIST is enumerated, not derived from extraction.canonical_props()/preingest.promotable_contact_props() — preingest imports held_queue (a cycle), and extraction._load_mapping raises when the column mapping is unresolvable"
  - "Widening admits exactly 5 new keys (jobtitle, phone, company_id, mobilephone, lv_linkedin_url); seniority/lv_persona_group/location keys deliberately excluded — no consumer needs them, and each is PII this store would then hold with nothing reading it"
  - "row's forbidden-name scan narrowed to KEY NAMES only (new _first_forbidden_key); observed_signals/reason/row_id keep full key+value scanning unchanged, per the run_report._looks_forbidden_value precedent for a legitimate key/value asymmetry"

patterns-established:
  - "A held-queue entry stores the MERGED row (dispatch step's own MergeResult), never the bare loop-source row — the fence takes a row_id-keyed lookup over merge_report.rows and falls back to the source row only when merge_report has no entry for that id"

requirements-completed: []

coverage:
  - id: D1
    description: "held_queue.ROW_FIELD_ALLOWLIST widened to 11 enumerated names; a merged row's email/phone/mobile/LinkedIn survive a save()/load() round trip and the still-excluded keys (city, seniority) do not"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_held_queue.py::test_an_enriched_held_row_survives_the_write_to_disk_end_to_end"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_held_queue.py::test_building_from_the_source_row_instead_of_the_merged_one_still_loses_the_email"
        status: pass
    human_judgment: false
  - id: D2
    description: "The row payload's forbidden-name scan is key-names-only; a person named Grant Dewsbury persists, and every other forbidden-shape refusal (secret-shaped observed_signals value, row_id key, reason, hand-built row key) still raises and leaves the queue byte-identical"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_held_queue.py::test_a_row_for_grant_dewsbury_saves_and_loads_back_unchanged"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_held_queue.py::test_save_still_refuses_every_forbidden_shape_except_a_row_value"
        status: pass
    human_judgment: false
  - id: D3
    description: "Persisting an email into a held row's stored row does not make a confidence_held no_match hold auto-resumable"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_held_queue.py::test_persisting_an_email_into_a_held_row_does_not_make_a_no_match_hold_resumable"
        status: pass
    human_judgment: false
  - id: D4
    description: "SKILL.md's persist fence hands held_queue.build_entry the merge_report-derived merged row, not the bare source row; the fence adds no new module.function call and test_skill_sequence_coverage.py's registered sequence for this block is byte-for-byte unchanged"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_enrich_before_ingest_skill_contract.py::test_the_persist_fence_hands_build_entry_the_merged_row_not_the_source_row"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_enrich_before_ingest_skill_contract.py::test_the_persist_fence_adds_no_merge_call_the_registered_sequence_is_untouched"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_skill_sequence_coverage.py (unedited, full suite green)"
        status: pass
    human_judgment: false

duration: ~45min
completed: 2026-09-11
status: complete
---

# Quick 260911-w6o: Held-queue entry stores the merged row, not the source row (F2-1) Summary

**Widened `held_queue.ROW_FIELD_ALLOWLIST` to 11 enumerated names, narrowed the `row`
payload's forbidden-name scan to key names only, and repointed
`enrich-before-ingest`'s persist fence at the dispatch step's own merged row — so a
held entry now carries what the waterfall actually found, not the operator's blank
spreadsheet line.**

## Performance

- **Tasks:** 2/2 completed
- **Files modified:** 6
- **Commits:** 2 (`3d264b3f`, `3dfbbb44`)

## Accomplishments

- `held_queue.ROW_FIELD_ALLOWLIST` widened from `row_id` + `enrichment.MATCH_LOOKUP_KEYS`
  (6 names) to 11 enumerated names, adding `jobtitle`, `phone`, `company_id`
  (mirroring `suggestion_declines.py`'s existing precedent) and `mobilephone`,
  `lv_linkedin_url` (the waterfall's own promoted keys for a mobile and a LinkedIn).
  Still a closed, enumerated tuple — `seniority`, `lv_persona_group`, and the five
  location keys deliberately stay out.
- `save()`'s `row` payload scan narrowed to key names only via a new
  `_first_forbidden_key` helper; `observed_signals`, `reason`, and `row_id` keep full
  key-and-value scanning, unchanged. A person named Grant Dewsbury now persists.
- `skills/enrich-before-ingest/SKILL.md`'s persist fence now builds a
  `row_id`-keyed lookup over `merge_report.rows` (the dispatch step's own
  `MergeResult`) and passes that merged row to `held_queue.build_entry`, falling
  back to the loop's own source row only when `merge_report` has no entry for that
  id. Prose above the fence names `merge_report`'s fresh-process rebuild path
  without a call-shaped argument list; prose after the fence states the resume-
  safety property (D-70-11) explicitly.
- Resume neutrality verified and pinned: `run_manifest.rows_to_resume` still reports
  a `confidence_held` `no_match` row as `still_held` when its stored `row` has
  gained an email — it compares by `resume_fingerprint` and reads the caller's rows,
  never `entry["row"]`.
- Corrected `test_preingest_merge.py`'s stale inline comment describing the old,
  narrower allowlist; annotated the open forbidden-name-marker todo (still open for
  the other six stores — `held_queue.py` is the only one this plan touches).

## Task Commits

1. **Task 1: An enriched held row survives the write to disk — end to end, on the
   recorded run's shape** - `3d264b3f` (fix)
2. **Task 2: The persist fence hands `build_entry` the merged row, and a contract
   test pins it** - `3dfbbb44` (fix)

No separate plan-metadata commit — per the orchestrator constraints for this
quick-batch leaf, STATE.md/ROADMAP.md updates and this SUMMARY's own commit belong
to the orchestrator, not this execution.

## TDD Gate Compliance

Both tasks carried `tdd="true"`. RED was observed against the shipped modules before
each fix, by temporarily stashing the source-only edit and running the new tests:

**Task 1** (`held_queue.py` stashed, tests present):
```
FAILED ...::test_an_enriched_held_row_survives_the_write_to_disk_end_to_end
    assert jimmy["phone"] == "0298765432"
E   KeyError: 'phone'

FAILED ...::test_a_row_for_grant_dewsbury_saves_and_loads_back_unchanged
E   held_queue.HeldQueueError: refusing to persist a held-queue entry for row
    'row-1' — 'Grant' suggests an arming grant, a live-write permission, a
    secret, or an API key. Nothing was written.

2 failed, 3 passed, 28 deselected
```
The 3 passing tests in that run (`test_building_from_the_source_row_instead_of_the_
merged_one_still_loses_the_email`, `test_save_still_refuses_every_forbidden_shape_
except_a_row_value`, `test_persisting_an_email_into_a_held_row_does_not_make_a_no_
match_hold_resumable`) were green throughout, as the plan predicted — they pin
regressions, not the defect.

**Task 2** (`SKILL.md` stashed, test present):
```
FAILED ...::test_the_persist_fence_hands_build_entry_the_merged_row_not_the_source_row
    assert PERSIST_FENCE_BUILD_ENTRY_CALL in span
AssertionError

1 failed, 1 passed
```
`test_the_persist_fence_adds_no_merge_call_the_registered_sequence_is_untouched`
(the second test) was green in that same run — same shape as task 1's regression
pins: it asserts the fence's call sequence equals `test_skill_sequence_coverage.py`'s
already-registered tuple, which the fence never violated even before this fix. The
plan's own behavior text calls this test "the registry is untouched" pin, distinct
from test A's "the contract pin" — the `<done>` criterion's "Tests A and B... were
observed RED" is accurate for the task's test *run* (which failed), not literally
per-test; documented here rather than claiming a RED test B never produced.

After each fix, the full plugin suite (`.venv/bin/python -m pytest
operator-claude-plugin/tests -q`) passed: 2958 passed, 5 skipped (task 1), then 2960
passed, 5 skipped (task 2, +2 new tests). `node --test tests/n8n/*.test.mjs`: 1101
passed, 0 failed (unchanged — zero n8n diff).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Plan finding 9 misread `test_build_entry_only_persists_allowlisted_row_fields`**
- **Found during:** Task 1, before the RED/GREEN cycle.
- **Issue:** Finding 9 claimed this pin (`test_held_queue.py:133`, "row is
  `row_id`+`email` only") survives the widening unchanged. It does not: the test's
  source row deliberately carries `phone`, and the widening admits `phone` —
  `entry["row"]` therefore gains a `phone` key, breaking both the exact-equality
  assertion at line 133 and the explicit `assert "phone" not in entry["row"]` at
  line 134.
- **Fix:** Swapped the test's "excluded field" example from `phone` to `seniority`
  (a real waterfall-promotable key that deliberately stays out of the allowlist),
  keeping the test's original intent — an arbitrary/non-admitted column is dropped
  — while accommodating the widening. Added a comment pointing to the new
  end-to-end test that now covers `phone`'s inclusion.
- **Files modified:** `operator-claude-plugin/tests/test_held_queue.py`
- **Commit:** `3d264b3f`

Or: this is the only deviation. Everything else executed exactly as planned — no
architectural changes, no scope expansion beyond the plan's stated four files
(task 1) and two files (task 2).

## Known Stubs

None.

## Threat Flags

None — the plan's own `<threat_model>` (T-w6o-01 through T-w6o-04) already covers
the widening's information-disclosure and resume-safety surface, and this execution
introduced no additional surface beyond what that register names.

## Pointers for the sibling quick items (carried forward from the plan objective, not rediscovered here)

- **For 260911-w6q:** `mobilephone` and `lv_linkedin_url` are NOT in
  `extraction.canonical_props()`. A create built from a held entry's `row` must go
  through `preingest.strip_enrichment_extras` before `extraction.write_dispatch_csv`,
  exactly as step 7's own ingest leg already does, or it raises
  `non_canonical_key_in_row`.
- **For 260911-w6p:** the stored `row` carries `company` (the name) and, only when
  the operator's own spreadsheet supplied one, `company_id` — never a company
  domain. Neither `extraction.canonical_props()` nor
  `preingest.promotable_contact_props()` contains a domain key. A facet classifier
  needing a domain must derive it from the row's own `email` via
  `enrichment._clean_domain`, or source it outside the entry. The enrichment lane's
  `Build Response` item does carry a per-row `company_domain`
  (`scripts/build_cloud_workflows.py:857`), and `observed_signals` is the
  allowlist-free slot it could be stashed in — but `observed_signals` values are
  still forbidden-name scanned (full key+value, unchanged by this plan), so a
  domain containing a marker token (`grant-...`, `token...`) would raise
  `HeldQueueError` and refuse the whole save. Decide deliberately in w6p.

## Self-Check: PASSED

- `git log --oneline --all | grep -q 3d264b3f` → FOUND
- `git log --oneline --all | grep -q 3dfbbb44` → FOUND
- `operator-claude-plugin/scripts/held_queue.py` → FOUND
- `operator-claude-plugin/skills/enrich-before-ingest/SKILL.md` → FOUND
- `operator-claude-plugin/tests/test_held_queue.py` → FOUND
- `operator-claude-plugin/tests/test_enrich_before_ingest_skill_contract.py` → FOUND
- `operator-claude-plugin/tests/test_preingest_merge.py` → FOUND
- `.planning/todos/pending/2026-09-11-forbidden-name-marker-whole-token-still-refuses-grant-token.md` → FOUND
