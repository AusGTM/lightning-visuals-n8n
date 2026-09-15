---
phase: 73-ga-fix-list-from-stress-attempt-2
plan: 01
subsystem: operator-plugin-reporting
tags: [n8n, hubspot, run-report, written-records, run-manifest, executions-api, pytest]

requires:
  - phase: 70-one-merge-one-result-channel-n8n-runtime-truth
    provides: "D-70-05/D-70-07's runData-only result channel (watch.recover_dispatch, report.all_node_items) that this plan's backfill reads"
provides:
  - "A frozen, redacted, live-fetched proof (executions 12434/12449 full, plus an 18-execution excerpt for run 6891d018e84f4d869eb8080292dac6c5) that pins the F-B5 defect permanently"
  - "report_enrichment.backfill_missing_identity: recovers hs_object_id/action/object_type for a company-update row before it reaches written_records, using data the run's own settled executions already carry"
  - "chunking.dispatch_and_recover wired to apply that backfill to the durable copy only, leaving the immediate per-send report untouched"
  - "enrich-before-ingest step 5's run_manifest read scoped to the current run_id (D-73-14), closing the folded cross-run manifest-bleed todo"
affects: [run-report, written-records, enrich-before-ingest, enrich-records, backend-status-reporting]

actuals:
  tokens: 9863   # chars/4 over authored code/docs (git diff, fixture JSON dumps excluded)
  tasks: 3
  commits: 4
  # Fixture JSON alone is ~4.5MB (live data, not authored code) -- excluded from the
  # token figure above per estimateTokens' own "the files you actually changed" intent
  # reading as authored content; included here for completeness: fixture bytes ~1.1M chars.

tech-stack:
  added: []
  patterns:
    - "Restore identity BEFORE persistence, not inside the never-raise durable-store reader (run_report.py stays a pure join over what written_records already holds; the fix lives at the write side, in chunking.dispatch_and_recover, where run_data is already in scope)"
    - "Whole-request execution-level markers (research_failed/recompute_refused/list_expansion_refused) are excluded from per-record accounting rather than forced into an unjoinable bucket -- they never described a row"

key-files:
  created:
    - scripts/freeze_execution_rundata.py
    - tests/n8n/fixtures/frozen/exec_12434.runData.json
    - tests/n8n/fixtures/frozen/exec_12449.runData.json
    - tests/n8n/fixtures/frozen/run_6891d018-decide-and-response.excerpt.json
    - operator-claude-plugin/tests/test_run_report_enrich_account.py
  modified:
    - tests/n8n/fixtures/frozen/README.md
    - operator-claude-plugin/scripts/report_enrichment.py
    - operator-claude-plugin/scripts/chunking.py
    - operator-claude-plugin/skills/enrich-before-ingest/SKILL.md
    - operator-claude-plugin/tests/test_run_manifest.py
    - operator-claude-plugin/tests/test_enrich_before_ingest_skill_contract.py
    - operator-claude-plugin/tests/test_skill_sequence_coverage.py
    - .planning/todos/completed/2026-09-12-shared-run-manifest-accumulates-positional-verdicts-across-runs.md

key-decisions:
  - "The live n8n executions API was reachable read-only from this session (via the plugin's own operator.local.json credentials, not .env), so Task 1 used REAL data throughout -- no synthetic fallback, no question todo needed."
  - "The plan's Open Question 3 (Task 2's real defect location) resolved to none of the three literal candidates (a)/(b)/(c) it offered -- the actual cause is one step upstream: Build Response's own item for a company update is the bare, undecorated HubSpot PATCH echo (no action/hs_object_id/row_id at top level), because the create branch is decorated by Adapt Company Create and the update branch is a Merge pass-through with no equivalent node. run_report._identity_for_entry's join is already correct; it had nothing correct to join on."
  - "Fixed at chunking.dispatch_and_recover + a new report_enrichment.backfill_missing_identity, NOT inside run_report.py -- run_report.py ended up with ZERO diff. Rejected fixing inside run_report.py itself: it only ever sees written_records.load()'s output, and written_records.classify_item already discarded the raw id field by the time that data reaches it; recovering it there would require either widening build_run_report's call signature to thread run_data through (out of scope) or having run_report.py call the executions API itself, which was explicitly rejected (a never-raise, durable-store-only join used for crash recovery must not depend on a live network call)."
  - "D-73-12's 'research-node rows join by hs_object_id and are never counted as unjoinable' does not hold as literally written: the research_failed marker is emitted once per EXECUTION (18 markers across 18 executions), never once per row, and carries no company identity of any kind at Build Response. The amended reading implemented: these markers are EXCLUDED from per-record accounting entirely (counted separately, never forced into a fabricated bucket) -- this is what 'never counted as unjoinable' means for something that was never a row."
  - "The plan's literal 'zero unjoinable' truth is not fully met: the Illawarra skip row (never created in HubSpot, no row_id minted by the companies form, no id) has no identity to recover. Extending _identity_for_entry with a name-based fallback would be a second join, which Task 2's own acceptance criteria forbids adding. Left at 1 unjoinable (down from 54), documented rather than faked."
  - "Task 1's fixture set is 3 files, not the literal 2 the plan named: executions 12434 and 12449 (both frozen, as named) contain zero enrich rows between them (2 creates + 1 skip + 2 research markers), so a test built only from them could never assert an update outcome, red or green. A third file (an 18-execution excerpt of Decide Company Action + Build Response only) was added to make the D-73-13 proof possible at all."

requirements-completed: [F-B5]

coverage:
  - id: D1
    description: "Frozen, redacted, live proof of the F-B5 defect (executions 12434/12449 full + an 18-execution excerpt), pinned as a real, checked-in fixture rather than a guess"
    requirement: F-B5
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_run_report_enrich_account.py::test_frozen_recording_matches_the_real_written_records_distribution"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_run_report_enrich_account.py::test_named_fixtures_exist_and_are_execution_12434_and_12449"
        status: pass
      - kind: other
        ref: "grep -c 'x-enrichment-secret' on both frozen fixtures -> 0; secret VALUE (from live config) checked absent by direct string compare"
        status: pass
    human_judgment: false
  - id: D2
    description: "report_enrichment.backfill_missing_identity restores hs_object_id/action/object_type for a company-update row before persistence; wired into chunking.dispatch_and_recover"
    requirement: F-B5
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_run_report_enrich_account.py::test_run_report_enrich_account_reconciles_after_backfill"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/ (full suite, 3071 passed / 5 skipped)"
        status: pass
    human_judgment: false
  - id: D3
    description: "enrich-before-ingest step 5's run_manifest read scoped to the current run_id (D-73-14); folded todo closed"
    requirement: F-B5
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_run_manifest.py::test_scoped_read_of_run_b_does_not_return_run_as_verdicts_even_though_both_share_the_shared_manifest"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_run_manifest.py::test_scoped_read_of_a_run_with_no_scoped_manifest_yet_is_an_empty_mapping_not_the_shared_file"
        status: pass
      - kind: other
        ref: "grep -c 'run_manifest.load()' operator-claude-plugin/skills/enrich-before-ingest/SKILL.md -> 0"
        status: pass
    human_judgment: false

duration: 55min
completed: 2026-09-15
status: complete
---

# Phase 73 Plan 01: Plugin run report tells the truth about an enrichment batch Summary

**Traced 24 "invisible" company-update outcomes to an undecorated HubSpot PATCH echo in the n8n graph's Build Response node, restored their identity one hop upstream of persistence (chunking.dispatch_and_recover + a new report_enrichment.backfill_missing_identity), and closed a separate cross-run manifest-bleed defect (D-73-14) — all proven against a live, redacted recording, not a guess.**

## Performance

- **Duration:** ~55 min (includes extensive live forensic diagnosis via the n8n executions API before any code was written; not precisely timestamped from the first tool call)
- **Completed:** 2026-09-15
- **Tasks:** 3 completed
- **Files modified/created:** 12 (5 created, 8 modified — one file, the folded todo, counted in both create-adjacent and modify contexts as a rename)

## Accomplishments

- Fetched real, live n8n executions (12432–12449, all 18 of run `6891d018e84f4d869eb8080292dac6c5`) read-only, via the plugin's own stored credentials — no `.env` touched, no write verb ever issued.
- Diagnosed the true root cause by direct inspection of live runData: `Build Response`'s item for a company UPDATE is the bare, undecorated HubSpot PATCH response (no `action`/`hs_object_id`/`row_id`/`object_type`), while the CREATE branch is decorated by `Adapt Company Create`. This exactly matches the real, currently-persisted `written_records-6891d018e84f4d869eb8080292dac6c5.json` artifact found on the operator's machine: 24 `(contacts, None, failed)` + 18 `(contacts, research_failed, failed)` + 11 `(companies, create, created_id_unknown)` + 1 `(companies, skip, no_action)`, all unjoinable.
- Built `report_enrichment.backfill_missing_identity`, which recovers `hs_object_id` from the raw response's own `id` field and, when `action` is still missing, looks up `Decide Company Action`/`Decide Action`'s own ledger (read fresh from the run's `run_data`, by the recovered id) to copy `action`/`object_type`/`row_id`. Wired into `chunking.dispatch_and_recover` immediately before the `written_records.append_chunk` call — only the durable copy is corrected; the immediate per-send report (step 9) is untouched.
- After the fix: 24 enrich → `write_attempted`, 11 create → `written`, 1 skip stays `no_action` — 35 of 36 rows now join by `hs_object_id` (34 distinct buckets; one company, `9604780317`, was independently enriched in two of the run's 18 executions and correctly folds into one record). Only the Illawarra skip (never created in HubSpot, no id of any kind) remains unjoinable.
- Closed the folded run_manifest cross-run bleed todo (D-73-14): `enrich-before-ingest` step 5 now reads its run-scoped manifest file, never the accumulated shared one.

## Task Commits

1. **Task 1: freeze the real runData and assert the account against it — RED first** - `fc9f3620` (test)
2. **Task 2: find and fix where the 24 updates are lost** - `a2cf5b8f` (feat)
3. **Task 3: scope run_manifest reads to the current run (D-73-14)** - `f9b19fa9` (fix) + `9da7ce39` (fix, completing a split commit — see Deviations)

_Note: Task 3 produced two commits because a multi-argument `git add` call partially failed (one pathspec no longer existed after a `git mv`) and silently staged only the rename; the second commit completes the same logical change with no new behaviour._

## Files Created/Modified

- `scripts/freeze_execution_rundata.py` — read-only GET-only CLI, reuses `executions_client`, redacts the whole `headers` object before write
- `tests/n8n/fixtures/frozen/exec_12434.runData.json`, `exec_12449.runData.json` — full runData, frozen live
- `tests/n8n/fixtures/frozen/run_6891d018-decide-and-response.excerpt.json` — 18-execution excerpt (`Decide Company Action` + `Build Response` only), added beyond the plan's literal 2-file ask (see Deviations)
- `operator-claude-plugin/tests/test_run_report_enrich_account.py` — the D-73-13 proof (RED, then GREEN)
- `operator-claude-plugin/scripts/report_enrichment.py` — new `backfill_missing_identity`
- `operator-claude-plugin/scripts/chunking.py` — one call site added in `dispatch_and_recover`
- `operator-claude-plugin/skills/enrich-before-ingest/SKILL.md` — step 5's manifest read scoped; one prose mention reworded
- `operator-claude-plugin/tests/test_run_manifest.py` — two new regression tests
- `operator-claude-plugin/tests/test_enrich_before_ingest_skill_contract.py`, `test_skill_sequence_coverage.py` — registered call-sequence contracts updated for the one new call the fix adds
- `.planning/todos/completed/2026-09-12-shared-run-manifest-accumulates-positional-verdicts-across-runs.md` — moved from `pending/`, resolution recorded

## Decisions Made

See `key-decisions` in the frontmatter — five decisions, each with its evidence and rationale, covering: the live-vs-synthetic fixture choice, the real defect location (not literally any of the plan's three candidates), why the fix landed in `report_enrichment.py`/`chunking.py` rather than `run_report.py`, the amended reading of D-73-12 for whole-request markers, and the honest 1-remaining-unjoinable result against the plan's literal "zero unjoinable" ask.

## Deviations from Plan

### Auto-fixed / Necessary Deviations

**1. [Rule 1 - Bug location] Task 2's fix landed in `report_enrichment.py` + `chunking.py`, not `run_report.py`**
- **Found during:** Task 2, after tracing live runData
- **Issue:** The plan's Task 2 `<files>` list named only `run_report.py` + the test file. The real defect — `Build Response`'s bare, undecorated item for a company update — is upstream of anything `run_report.py` can see: `written_records.load()` only returns what `classify_item` already computed, and `classify_item`'s output permanently discards the raw response's `id` field. `run_report._identity_for_entry`'s join (row_id then hs_object_id) was already correct and needed no change.
- **Fix:** Added `report_enrichment.backfill_missing_identity(rows, run_data)` and called it in `chunking.dispatch_and_recover`, immediately before `written_records.append_chunk`, on a COPY (the function's own returned `rows`, read by the immediate per-send report, is left untouched).
- **Files modified:** `operator-claude-plugin/scripts/report_enrichment.py`, `operator-claude-plugin/scripts/chunking.py`
- **Verification:** `test_run_report_enrich_account.py` (new), full plugin suite (3071 passed/5 skipped), `run_report.py` diff is empty (0 insertions/deletions) — confirmed by `git diff --stat`.
- **Commit:** `a2cf5b8f`

**2. [Rule 2 - Missing critical functionality] A third frozen fixture was required beyond the plan's named two**
- **Found during:** Task 1, immediately after freezing executions 12434 and 12449
- **Issue:** Executions 12434 (2 creates + 1 research marker) and 12449 (1 skip + 1 create + 1 research marker) contain zero `enrich` rows between them — this run's 24 enrich outcomes are spread across the other 16 of the 18 executions. A test built only from the two named fixtures could never assert an update outcome at all, red or green, making D-73-13's actual proof impossible to write.
- **Fix:** Added `tests/n8n/fixtures/frozen/run_6891d018-decide-and-response.excerpt.json`, an 18-execution excerpt restricted to `Decide Company Action` + `Build Response` only (keeping it to 472KB rather than committing 18 full runData recordings).
- **Files modified:** `tests/n8n/fixtures/frozen/README.md` (3 new rows, not the plan's literal 2), the excerpt file itself, `scripts/freeze_execution_rundata.py` gained a `--nodes`/`--combine` mode to produce it.
- **Verification:** `test_run_report_enrich_account.py`'s ground-truth test reproduces the real persisted `written_records-6891d018e84f4d869eb8080292dac6c5.json` artifact exactly (54 rows, same 4-way split).
- **Commit:** `fc9f3620`

**3. [Rule 4-adjacent, documented not asked] D-73-12's literal "never counted as unjoinable" is not fully achievable for one row**
- **Found during:** Task 2, verifying the post-fix reconciliation
- **Issue:** The Illawarra skip row never existed in HubSpot (the companies dispatch form mints no `row_id`, and a skipped row has no `id` either). D-73-12/must_haves ask for "zero unjoinable"; achieving that would require a name-based (or `company_dependency_id`-based) join key `run_report._identity_for_entry` does not have — which Task 2's own acceptance criteria explicitly forbids adding ("No new join function was added to run_report.py").
- **Resolution:** Left as 1 unjoinable (down from the pre-fix 54), documented here and in the test's own comments rather than invented. This is a genuine, argued limit, not an oversight.
- **Files modified:** none beyond the fix already described; documented in `test_run_report_enrich_account.py`'s own assertions and comments.
- **Commit:** `a2cf5b8f`

**4. [Bookkeeping] A split commit for Task 3**
- **Found during:** Task 3's commit step
- **Issue:** A single multi-argument `git add` call included a stale pathspec (the pending-directory path, already renamed by an earlier `git mv` in the same shell session) which errored the whole invocation; only the already-staged rename made it into the first commit (`f9b19fa9`), silently dropping the SKILL.md edit, the two contract-test updates, and the two new regression tests from that commit's actual diff despite the commit message describing them.
- **Fix:** A second commit (`9da7ce39`) adds the dropped files, explicitly naming the split in its own message.
- **Files modified:** none beyond what Task 3 already touched.
- **Commit:** `9da7ce39`

---

**Total deviations:** 4 (2 Rule-1/Rule-2 auto-fixes, 1 documented plan-vs-reality gap, 1 commit-bookkeeping correction).
**Impact:** The plan's stated `must_haves.truths` — "24 updates + 11 creates + 1 skip with zero unaccounted and zero unjoinable" — is met for "zero unaccounted" (36 of 36 rows accounted for, all correctly typed and outcome-classified) but not for "zero unjoinable" (1 of 36 remains unjoinable, by design, for a row with no HubSpot identity of any kind). This is the honest result of driving the fix from real data rather than authoring assertions to match the plan's pre-verification guess.

## Issues Encountered

None beyond what is already covered in Deviations above. No authentication gates were hit — the n8n executions API and the plugin's stored config were both already usable read-only.

## User Setup Required

None — no external service configuration required. The live n8n executions API read used credentials already present in the operator's plugin config; nothing new needs to be provisioned.

## Next Phase Readiness

Plan 01 of Phase 73 is complete and self-contained (wave 1, no `depends_on`). Full suites are green:
- `.venv/bin/python -m pytest -q --tb=short -p no:cacheprovider tests/ operator-claude-plugin/tests/` → **4957 passed, 154 skipped** (baseline was 4952/154; +5 net from 8 new tests minus... actually +5 exactly: 3 new tests in `test_run_report_enrich_account.py` + 2 new tests in `test_run_manifest.py`).
- `node --test tests/n8n/*.test.mjs` → **1170 passed, 0 failed** (unchanged — this plan touched no n8n graph).
- `.venv/bin/python scripts/build_cloud_workflows.py` → zero `n8n/` diff.

No blockers for the remaining plans in this phase (73-02 through 73-07).

## Self-Check: PASSED

- `scripts/freeze_execution_rundata.py` exists on disk: confirmed.
- `tests/n8n/fixtures/frozen/exec_12434.runData.json`, `exec_12449.runData.json`, `run_6891d018-decide-and-response.excerpt.json` exist on disk: confirmed.
- `operator-claude-plugin/tests/test_run_report_enrich_account.py` exists on disk: confirmed.
- `git log --oneline` shows commits `fc9f3620`, `a2cf5b8f`, `f9b19fa9`, `9da7ce39`, all matching `^(test|feat|fix)\(73-01\):`: confirmed.
- Re-ran every task's `<acceptance_criteria>` and `<verify>` command: all pass (see Task Commits / Coverage above).
- Re-ran the plan-level `<verification>` block: `pytest` 4957/154, `node --test` 1170/0, `build_cloud_workflows.py` zero diff — all pass.
- `git status --short` shows a clean tree aside from the untracked `.planning/milestone.lock` runtime lock (never staged, per this run's standing instructions).

plan_head_before: 3906fb85b111bba6607e6abfa8a326aa5006f60d
commits: 4
