---
status: complete
quick_id: 260829-lg3
task: "Close all five GRANDFATHERED_UNCOVERED entries in test_skill_sequence_coverage.py with real composition tests, moving each to COVERED and driving MAX_GRANDFATHERED to 0"
date: 2026-08-29
requirements: []
actuals:
  tokens: 7716
  tasks: 3
  commits: 3
---

# Quick 260829-lg3: close the five grandfathered SKILL.md composition sequences — Summary

All five `GRANDFATHERED_UNCOVERED` entries shipped by 260829-hjm are now `COVERED` by
three new composition tests, each driving the SPECIFIC named undriven join with a real
value flowing between calls — never the same calls invoked side by side.
`GRANDFATHERED_UNCOVERED` is the empty dict; `MAX_GRANDFATHERED` is `0`. This is P2 of
`.planning/HANDOVER-2026-08-29-backlog.md`. Zero production-code changes across all
three tasks — every change is test-file additions plus release metadata
(`operator-claude-plugin/.claude-plugin/plugin.json` 0.28.3 → 0.28.6,
`operator-claude-plugin/CHANGELOG.md` matching entries, one bump per commit).

## Closed entries and their covering tests

| # | Skill | Tuple (sink) | Covering test |
|---|---|---|---|
| 1 | `contact-upload` | `...authorize_send/authorize_ungranted_send → armed_window → dispatch.dispatch` | `test_write_grant.py::test_authorize_send_and_authorize_ungranted_send_each_drive_dispatch_inside_their_own_armed_window` |
| 4 | `enrich-before-ingest` | same tuple as #1 | same test as #1 |
| 3 | `enrich-before-ingest` | `...resolve_providers → plan_chunks/chunk_ceiling → authorize_* → armed_window → dispatch_plan → merge_enriched` | `test_chunking.py::test_the_enrich_before_ingest_waterfall_chains_resolve_providers_through_merge_enriched` |
| 7 | `enrich-records` | same prefix as #3, no `merge_enriched` | `test_chunking.py::test_the_enrich_records_waterfall_chains_resolve_providers_through_dispatch_plan` |
| 2 | `enrich-before-ingest` | `...plan_chunks → chunk_ceiling(key='max_rows_per_match_request') → match_batch → classify_matches` | `test_chunking.py::test_chunk_ceilings_real_match_key_return_flows_into_match_batch_and_classify_matches` |

## Task 1 — #1 + #4 (one shared test, two COVERED entries)

Added one new test to `test_write_grant.py` driving BOTH branches the registry named as
separately undriven: the grant-present `authorize_send` branch (never before chained
into `armed_window` at all) and the `authorize_ungranted_send` branch (whose existing
tracer test's `with armed_window(...): pass` stopped one call short of
`dispatch.dispatch`). Each branch opens its own `armed_window` around a real
`dispatch.dispatch(str(sample_csv), True, ...)` call and asserts on the returned
`result["run_id"]` and the shared `stub_transport.calls` count (1 after branch 1, 2 after
branch 2). `executions_client._workflow_id_cache` (process-lifetime, keyed by workflow
name) had to be cleared between the two branches — both use the identical "enrichment"
lane name, so branch 2's own `plan_grant` would otherwise silently skip its own
workflow-list read and consume the second branch's scripted transport queue one entry
out of step. This was found empirically (branch 2 failed `armed is True` on first run)
and fixed with an explicit `executions_client._workflow_id_cache.clear()` between the two
branches — not called out in the plan's read_first, but consistent with
`test_write_grant.py`'s own pre-existing `_clear_workflow_id_cache` autouse fixture,
which exists for exactly this reason across separate TEST functions but does not reach
across two branches inside one function body.

**Falsifiability check performed:** reverted branch 1's `with armed_window(...): body`
to `pass`, re-ran the test — observed `NameError: name 'result' is not defined` at the
`assert result["run_id"]` line (the reference the reverted body no longer defines) —
then restored the body and re-confirmed green.

Bumped `plugin.json` 0.28.3 → 0.28.4, matching CHANGELOG entry, same commit as the test
and registry edit. `MAX_GRANDFATHERED` 5 → 3.

## Task 2 — #3 + #7 (two new tests in test_chunking.py)

Duplicated the arming scaffolding (`WORKFLOW_ID`, `RECORD_ID`, `_base_workflow`,
`_armed_workflow`, `_workflow_list`, `granting_config` fixture) verbatim from
`test_write_grant.py` into `test_chunking.py`, plus a local `_arming_sequence()` helper
returning the proven 14-entry open+arm+disarm list, and an autouse
`_clear_workflow_id_cache_between_chunking_tests` fixture (same fix as Task 1's finding,
applied preemptively here since both new tests in this file use the same lane name).

**Test 1** (`enrich-before-ingest`, grant-present `authorize_send` branch): builds a real
`row_spec` via `preingest.build_rows_spec`, resolves `providers =
enrichment.resolve_providers(None, cfg)` (the real `FULL_WATERFALL`, not a literal),
computes `ceiling = chunking.chunk_ceiling(cfg)` and `plan = chunking.plan_chunks(...)`,
opens a grant and `authorize_send`s it, then inside `armed_window` calls
`chunking.dispatch_plan(plan, providers, True, cfg, transport=<scripted 2-row response>)`.
After the window closes, flattens `outcome.responses` with the documented idiom and calls
`preingest.merge_enriched(row_spec["rows"], flattened)`, asserting each merged row's
`email` equals the scripted per-row value.

**Test 2** (`enrich-records`, `authorize_ungranted_send` branch — deliberate diversity):
a `record_ids`-shaped spec, same `resolve_providers`/`chunk_ceiling`/`plan_chunks`
pattern, `authorize_ungranted_send` → `armed_window` → `chunking.dispatch_plan`. Asserts
on the module-shaped transport's own recorded `.calls[0]["json"]`: `["events"]` equals
the exact chunked record-id/object-type pairs, and `["providers"]` equals
`enrichment.FULL_WATERFALL` — an expectation independent of the test's own `providers`
variable (see the finding below for why).

**Falsifiability checks performed:**
1. Test 1: temporarily changed the scripted `dispatch_plan` response's `email` value to a
   different string without updating the assertion — observed
   `AssertionError: ... assert 'row-1@DIFFER...VALUE.example' == 'row-1@example.com'` —
   then restored it.
2. Test 2, corrected mid-task (see below): temporarily hardcoded
   `providers = ["lusha"]` — observed
   `AssertionError: ... assert ['lusha'] == ['zoominfo', ...llo', 'lusha']` — then
   restored the real `resolve_providers` call.

**Deviation from the plan's literal wording (Rule 1 — bug in the plan's own acceptance
criterion, not the code under test):** the plan's acceptance criterion #2 for Task 2
specified asserting `call["json"]["providers"] == providers` (the test's own local
variable). Empirically this assertion is **tautological** — `providers` flows unchanged
from the resolve call into `dispatch_plan` and onto the wire, so comparing the wire value
against the very same variable passes regardless of whether `providers` was a real
resolved list or a hardcoded literal (confirmed live: hardcoding `providers = ["lusha"]`
and keeping the `== providers` assertion still passed). Fixed by comparing against an
independent expectation, `enrichment.FULL_WATERFALL`, which does fail when the call is
replaced with a literal — the falsifiability check above is against this corrected
assertion. This is a Rule 1 auto-fix under the executor's deviation rules (the plan's
verify step, taken literally, does not actually verify what it claims to), not a
weakening of anything already shipped.

Bumped `plugin.json` 0.28.4 → 0.28.5, matching CHANGELOG entry, same commit as the tests
and registry edit. `MAX_GRANDFATHERED` 3 → 1.

## Task 3 — #2 (the last entry: match-ceiling chain)

Added `test_chunk_ceilings_real_match_key_return_flows_into_match_batch_and_classify_matches`
immediately after `test_chunk_ceiling_reads_the_match_key_and_it_is_larger_than_the_write_ceiling`
(left byte-identical). Reads `real_match_ceiling` from
`config/operator.local.example.json` at runtime via the file's own `CONFIG_EXAMPLE`
constant, builds a 3-row `preingest.build_rows_spec`, computes `ceiling =
chunking.chunk_ceiling(cfg, key="max_rows_per_match_request")` and asserts it equals the
real config value, plans one chunk, sends it through a scripted
`preingest.match_batch` (attribute-shaped `stub_post_transport_factory`, distinct from
`dispatch_plan`'s module-shaped transport), and asserts a three-way tier split
(auto-matched / unmatched / proposed) via `preingest.classify_matches` — proving both the
real ceiling-derived chunking and the real match response reached `classify_matches`
correctly, not merely that each function was called once.

`test_run_manifest.py` is untouched: `git diff --stat` shows zero changes to that file.
`git diff` on `test_chunking.py` for this commit shows zero removed lines (fully
additive). `grep -nE "plan_chunks\(row_spec, *[0-9]+\)" operator-claude-plugin/tests/test_chunking.py`
returns no matches — the ceiling reaching `plan_chunks` is always the `ceiling` variable
assigned from `chunk_ceiling`'s real return, never a literal.

Bumped `plugin.json` 0.28.5 → 0.28.6, matching CHANGELOG entry, same commit as the test
and registry edit. `GRANDFATHERED_UNCOVERED = {}`, `MAX_GRANDFATHERED = 0`.

## Verification

- `.venv/bin/python -m pytest operator-claude-plugin/tests -q` → **1725 passed, 5
  skipped, 0 failed** (baseline 1721/5 + 4 new test functions: 1 from Task 1, 2 from
  Task 2, 1 from Task 3 — matches the plan's own planned count exactly).
- `.venv/bin/python -m pytest operator-claude-plugin/tests/test_skill_sequence_coverage.py -q -v`
  → 11 passed, including `test_no_new_or_orphaned_sequence_exists_in_the_live_corpus`,
  `test_registries_have_no_orphaned_keys`, `test_the_three_registries_are_pairwise_disjoint`,
  `test_grandfathered_count_is_within_its_shrink_only_ceiling` (now `0 <= 0`), and
  `test_every_covered_nodeid_resolves_to_a_real_test_mentioning_the_sequences_sink`.
- `grep -c "GRANDFATHERED_UNCOVERED = {}" operator-claude-plugin/tests/test_skill_sequence_coverage.py`
  → `1`. `grep -n "MAX_GRANDFATHERED = 0" ...` → present at line 256.
- `.venv/bin/python -m pytest -q` (root suite) → **3332 passed, 154 skipped** (baseline
  3328/154 + 4 — the plugin tests are collected by the root suite, so the moved count is
  expected, not a regression).
- `node --test tests/n8n/*.test.mjs` not re-run: no file under `n8n/` or `tests/n8n/` was
  touched by this task (confirmed by `git diff --stat` across all three commits, which
  shows only files under `operator-claude-plugin/tests/` and
  `operator-claude-plugin/.claude-plugin/plugin.json` / `CHANGELOG.md`).
- Three separate commits, one per task, each touching only the files named in that
  task's `<files>` list, each with `plugin.json` and `CHANGELOG.md` changed alongside
  the test/registry edit: `8a4b638` (Task 1), `d8ad021` (Task 2), `d1a2881` (Task 3).
- Zero live n8n/HubSpot/Anthropic/provider calls at any point — every new test used a
  stub transport (`stub_module_transport_factory`, `stub_transport`, or
  `stub_post_transport_factory`, matched to the shape each function under test expects);
  the autouse `no_network`/`no_durable_writes` fixtures in `conftest.py` were never
  bypassed, patched, or worked around.
- No `skills/*/SKILL.md` file was edited. No file under `operator-claude-plugin/scripts/`,
  `n8n/`, or repo-root `scripts/` was touched.

## Decisions Made

- **The plan's Task 2 acceptance criterion #2 was corrected in execution** (see Task 2
  section above) — the specified assertion (`call["json"]["providers"] == providers`) is
  tautological and cannot fail regardless of whether the real `resolve_providers` call is
  present; replaced with a comparison against the independent `enrichment.FULL_WATERFALL`
  constant, which the corrected falsifiability check confirms actually fails on a
  hardcoded literal.
- **`executions_client._workflow_id_cache` clearing was added beyond the plan's literal
  read_first**, both mid-test (Task 1, between the two branches) and as a new autouse
  fixture (Task 2, between the two new test functions) — found empirically as a Rule 1
  bug (a real test failure, not a hypothetical), fixed with the same pattern
  `test_write_grant.py`'s own pre-existing `_clear_workflow_id_cache` fixture already
  uses for the identical class of leak.
- **No user-facing wording, source-level fix, or existing assertion was changed anywhere
  in this task** — every edit is a new test function, a registry cut-and-paste (verbatim
  tuples, never retyped), or release metadata.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug in the plan's own acceptance criterion] Task 2's specified
`providers` assertion is tautological**
- **Found during:** Task 2, running the falsifiability check the plan itself demanded
- **Issue:** `assert call["json"]["providers"] == providers` compares the wire value
  against the exact same local variable that produced it, so it cannot fail regardless
  of whether `providers` came from a real `resolve_providers()` call or a hardcoded
  literal — confirmed by temporarily hardcoding `providers = ["lusha"]` and observing
  the assertion still pass.
- **Fix:** Compared against `enrichment.FULL_WATERFALL` instead — an expectation
  independent of the variable under test.
- **Files modified:** `operator-claude-plugin/tests/test_chunking.py`
- **Verification:** Re-ran the falsifiability check against the corrected assertion;
  observed the expected `AssertionError` with the hardcoded literal, then restored the
  real call and confirmed green.
- **Committed in:** `d8ad021` (Task 2 commit)

**2. [Rule 1 - Bug] `executions_client._workflow_id_cache` leak across the two branches
of Task 1's shared test, and across Task 2's two new test functions**
- **Found during:** Task 1, first run of the new test (branch 2's `assert decision2["armed"] is True` failed)
- **Issue:** the cache is process-lifetime and keyed by workflow name; both branches/
  tests in each case resolve the identical "enrichment" lane name, so the second
  resolve silently skips its own workflow-list transport read and desyncs the scripted
  queue.
- **Fix:** explicit `executions_client._workflow_id_cache.clear()` between Task 1's two
  branches; a new autouse `_clear_workflow_id_cache_between_chunking_tests` fixture in
  `test_chunking.py` for Task 2's two tests.
- **Files modified:** `operator-claude-plugin/tests/test_write_grant.py`,
  `operator-claude-plugin/tests/test_chunking.py`
- **Verification:** both tests pass; full plugin suite (1725 passed) confirms no
  cross-file leak either, since `test_chunking.py`'s tests run before
  `test_write_grant.py`'s in the default alphabetical order and each file now clears its
  own cache regardless of run order.
- **Committed in:** `8a4b638` (Task 1), `d8ad021` (Task 2)

---

**Total deviations:** 2 auto-fixed (1 plan-acceptance-criterion bug, 1 test-isolation
bug). Both were found by actually running the falsifiability checks the plan itself
demanded, not skipped or rubber-stamped. No scope creep — no production code touched,
no existing assertion weakened.

## Issues Encountered

None beyond the two auto-fixed deviations above, both resolved within their own task.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

P2 of `.planning/HANDOVER-2026-08-29-backlog.md` is closed. `MAX_GRANDFATHERED` is `0`;
any future SKILL.md sequence added without a matching `COVERED`/`NOT_A_PIPELINE` entry
fails the guard immediately, with no headroom left to grandfather it away. The P3 item
named in 260829-hjm's own follow-on list (a stub harness that actually RUNS each
documented sequence, rather than a targeted composition test per identity) remains
explicitly out of scope and undone.

---
*Quick task: 260829-lg3-close-the-five-grandfathered-skill-md-co*
*Completed: 2026-08-29*
