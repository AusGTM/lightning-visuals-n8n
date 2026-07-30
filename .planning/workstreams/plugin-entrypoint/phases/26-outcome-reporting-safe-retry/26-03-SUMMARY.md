---
phase: 26-outcome-reporting-safe-retry
plan: 03
subsystem: infra
tags: [claude-plugin, retry-safety, ast-guard, contact-upload, dispatch-04]

requires:
  - phase: 26-01
    provides: "report.py's contact_row_ledger()/reconcile()/build_contact_report(), the contact_execution conftest fixture, and SKILL.md's step 7 (report the outcome)"
provides:
  - "operator-claude-plugin/scripts/report.py — classify_retryability() and the resendable_rows report roll-up: four retryability states (nothing_to_retry, transport_failure, permanently_stuck, business_outcome) attached per row"
  - "operator-claude-plugin/tests/test_retry_reuses_dispatch.py — classification tests plus an ast-based single-send-path / no-accepted-row-store structural guard"
  - "operator-claude-plugin/skills/contact-upload/SKILL.md steps 8-9 — re-check (one fetch, only when asked) and retry (same dispatch() call, arming gate intact)"
  - "operator-claude-plugin/CHANGELOG.md — one client-scoped Phase 26 entry covering report + retry together"
affects: [26-02, 27, 29-notice-phases, 30-review-queue]

tech-stack:
  added: []
  patterns:
    - "Retryability classified by verb/shape, not by 'looks like a ledger operation': the AST guard distinguishes a send from a fetch by checking whether a function's own transport parameter defaults to requests.post/put (dispatch.py's shape) versus requests.get (executions_client.py's shape) — not by whether the function calls something named 'transport', which would have false-flagged every read-only fetcher 26-01 already shipped."
    - "Module-scope-only name scanning for the accepted-row-store guard: a local variable recomputed fresh inside a function body every call (extraction.py's own 'accepted' rows from Phase 24) cannot persist anything and is not a dedupe ledger — only names assigned as direct children of the module body are in scope, mirroring executions_client.py's own '_workflow_id_cache' as the one legitimate module-level persisted dict in this plugin."

key-files:
  created:
    - operator-claude-plugin/tests/test_retry_reuses_dispatch.py
  modified:
    - operator-claude-plugin/scripts/report.py
    - operator-claude-plugin/skills/contact-upload/SKILL.md
    - operator-claude-plugin/CHANGELOG.md

key-decisions:
  - "classify_retryability(row) maps reconcile()'s existing not_confirmed label to transport_failure. There is no chunking concept yet in the contact-upload lane (single-shot dispatch, one file, one POST) — Phase 25's failed-chunk batch is an enrichment-lane concept that has not landed as code. not_confirmed (a decided update/create the write-safety gate never confirmed reached HubSpot) is the closest existing shape to 'a chunk that never got a response or came back with a server error,' and is the only row-level state in the current ledger that isn't a business decision."
  - "The AST guard's send-vs-fetch distinction is by HTTP verb (requests.post/put) on the function's own transport parameter default or a direct requests.post/put call in its body — not by matching any call to something literally named 'transport'. The first draft of the guard matched on the latter and false-flagged executions_client.py's _get_json/resolve_workflow_id/list_executions/get_execution, all of which call their own injected transport parameter (defaulting to requests.get) to perform read-only fetches. Corrected before commit."
  - "The no-accepted-row-store guard scans module-level (top-of-file) assignments only, not every assignment anywhere in the AST. The first draft walked the whole tree and false-flagged extraction.py's and preview.py's local 'accepted'/'final_accepted' variables (Phase 24's per-call extraction-validation output, recomputed fresh every invocation) as if they were a persisted ledger. A store implies persistence across calls; a function-local variable cannot persist anything, so only module scope is a meaningful signal. Corrected before commit."

patterns-established:
  - "Structural guards distinguish by observable shape (HTTP verb, assignment scope) rather than by name-substring matching against call targets — a name-substring guard is exactly the kind of check that either false-flags legitimate code (as both drafts here did) or is trivially defeated by a rename."

requirements-completed: [DISPATCH-04]

coverage:
  - id: D1
    description: "A no-email row with an ambiguous identity outcome (email_status=NO_EMAIL + outcome=ambiguous, D-11b/D-14) is classified permanently_stuck, its reason states it will reach review on every attempt and needs an email address or manual handling in HubSpot, and it is absent from resendable_rows"
    requirement: "DISPATCH-04"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_retry_reuses_dispatch.py#test_no_email_ambiguous_row_is_permanently_stuck"
        status: pass
    human_judgment: false
  - id: D2
    description: "A review/rejected row whose email_status is NO_EMAIL but whose outcome is NOT ambiguous (fixture row 4: 'missing required identity fields') is classified business_outcome, never permanently_stuck and never transport_failure — proving the marker requires the NO_EMAIL+ambiguous combination together, not email_status alone"
    requirement: "DISPATCH-04"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_retry_reuses_dispatch.py#test_review_row_with_a_reason_other_than_no_email_is_a_business_outcome"
        status: pass
    human_judgment: false
  - id: D3
    description: "A decided update/create row the write-safety gate never confirmed written (reconcile()'s existing not_confirmed label) is classified transport_failure and appears in resendable_rows; a successfully-written row is classified nothing_to_retry with no retry reason"
    requirement: "DISPATCH-04"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_retry_reuses_dispatch.py#test_not_confirmed_row_is_a_transport_failure_and_is_resendable"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_retry_reuses_dispatch.py#test_successfully_written_rows_are_nothing_to_retry"
        status: pass
    human_judgment: false
  - id: D4
    description: "classify_retryability() never raises on a row missing any field it reads (empty dict, partial dict, None, a non-dict scalar) -- always returns one of the four named states"
    requirement: "DISPATCH-04"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_retry_reuses_dispatch.py#test_classifier_never_raises_on_a_row_missing_every_field_it_reads"
        status: pass
    human_judgment: false
  - id: D5
    description: "Exactly one function across operator-claude-plugin/scripts/ is send-shaped (requests.post/put on its own transport default or in its body) -- dispatch.py's dispatch(); its armed parameter still carries no default; no module persists a module-level name suggesting an accepted/sent-row store. The guard's non-vacuity is asserted (scanned file count > 0), and both failure modes were proven red during development by temporarily adding a second send-shaped function and a module-level _accepted_row_ids set, confirming the guard catches each before the temporary change was reverted (not committed)."
    requirement: "DISPATCH-04"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_retry_reuses_dispatch.py#test_scan_found_at_least_one_plugin_source_file"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_retry_reuses_dispatch.py#test_exactly_one_module_defines_the_send_shaped_function"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_retry_reuses_dispatch.py#test_dispatch_armed_parameter_still_carries_no_default"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_retry_reuses_dispatch.py#test_no_module_defines_or_persists_a_previously_sent_row_store"
        status: pass
    human_judgment: false
  - id: D6
    description: "SKILL.md steps 8-9 (re-check, retry) are wired in: re-check is exactly one fetch through executions_client.py performed only when the operator asks, never scheduled; retry hands the file back to the existing dispatch.py entry point with the arming gate intact, states the backend-owned duplicate-safety property in the operator's own words, and excludes permanently-stuck rows from the retry offer"
    requirement: "DISPATCH-04"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_plugin_manifest.py#test_skill_body_references_only_scripts_that_exist_on_disk"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_retry_reuses_dispatch.py#test_dispatch_armed_parameter_still_carries_no_default"
        status: pass
    human_judgment: true
    rationale: "The prose wording of the retry/re-check steps -- what the operator is told about backend-owned duplicate safety, and how permanently-stuck rows are framed as never retryable -- is a conversational contract for the Claude agent driving the skill. A passing test proves the referenced scripts exist and the arming gate is structurally intact, but whether the language reads correctly in a live conversation needs a human/UAT read, same as every other SKILL.md step in this milestone."

duration: ~25min
completed: 2026-07-31
status: complete
---

# Phase 26 Plan 03: Retryability Classification, Retry/Re-check Steps, Single-Send-Path Guard Summary

**A four-state classifier (`nothing_to_retry` / `transport_failure` / `permanently_stuck` / `business_outcome`) that tells the operator which failing contact-upload rows a re-send can actually fix, wired into the skill's retry step that reuses `dispatch.py`'s one arming-gated entry point verbatim — with an AST guard proving no second send path or client-side accepted-row store can be added without the suite catching it.**

## Performance

- **Duration:** ~25 min
- **Tasks:** 2
- **Files modified:** 3 (1 created test file, 2 modified: report.py, SKILL.md), 1 CHANGELOG entry

## Accomplishments

- `report.classify_retryability(row)`: a pure, defensive classifier reading a
  ledger row's `reported_label`/`action`, `email_status`, and `outcome` into one of
  four states. `permanently_stuck` fires only on the exact D-11b/D-14 marker
  (`email_status == "NO_EMAIL"` **and** `outcome == "ambiguous"` together) — a
  NO_EMAIL row rejected for a different reason (fixture row 4, "missing required
  identity fields") is `business_outcome`, proving the combination is what matters,
  not either field alone. `not_confirmed` (26-01's existing reconciliation label
  for a decided write the terminal node never produced output for) maps to
  `transport_failure` — the closest existing shape in this lane's ledger to Phase
  25's not-yet-built failed-chunk concept, since contact-upload has no chunking of
  its own yet (single file, single POST).
- `build_contact_report()` now attaches `retryability` and `retry_reason` to every
  row, and the report object carries a new `resendable_rows` key: the subset of
  `failing_rows` classified `transport_failure`. Permanently-stuck and
  business-outcome rows are named in `failing_rows` (so the operator still sees
  them) but are never in `resendable_rows`.
- `SKILL.md` step 8 (re-check): one fetch through `executions_client.py` on the
  handle from step 7, only when the operator asks — explicitly no scheduling, no
  "checking again shortly," matching D-06/D-07's manual-only re-check for this
  phase.
- `SKILL.md` step 9 (retry): hands the file straight back to
  `python3 scripts/dispatch.py <path> armed` — the same function, same arguments,
  same arming gate as the original send. States the backend-owned duplicate-safety
  property in the operator's own words and explicitly excludes permanently-stuck
  rows from the offer.
- `tests/test_retry_reuses_dispatch.py`: 6 classification tests (Task 1) plus an
  AST-based structural guard (Task 2, mirroring `test_no_backend_imports.py`'s
  idiom) proving exactly one send-shaped function exists across
  `operator-claude-plugin/scripts/` (`dispatch.py`'s `dispatch()`), that its
  `armed` parameter still carries no default, and that no module persists a
  module-level name suggesting an accepted/sent-row store. Both failure modes were
  proven red during development (see Deviations) before being reverted.
- One `CHANGELOG.md` entry describing Phase 26's client-visible capability as a
  whole: per-record outcomes, safe retry, manual re-check.

## Task Commits

1. **Task 1: Classify what a re-send can actually fix** - `cf28c3e` (test)
2. **Task 2: Retry is the same send — the skill step and the structural guard** - `a28a9ca` (feat)

## Files Created/Modified
- `operator-claude-plugin/scripts/report.py` - `classify_retryability()`, `_retry_reason()`, `resendable_rows` roll-up in `build_contact_report()`
- `operator-claude-plugin/tests/test_retry_reuses_dispatch.py` - classification tests + single-send-path/no-ledger AST guard
- `operator-claude-plugin/skills/contact-upload/SKILL.md` - step 8 (re-check), step 9 (retry); step 8→10 (clean up) renumbered
- `operator-claude-plugin/CHANGELOG.md` - one Phase 26 client-scoped entry

## Decisions Made

- **`not_confirmed` → `transport_failure`.** Phase 25's failed-chunk batch concept
  (D-13) has not been built as code yet — only `25-02` (the credit-only
  backend-status endpoint) has landed; the enrichment-lane chunking/dispatch work
  is still plan-only. Contact-upload itself has never chunked (one file, one POST).
  `reconcile()`'s existing `not_confirmed` label — a decided write the terminal
  HubSpot node never produced output for — is the only row-level state already in
  this ledger that isn't a business decision, and is the closest available analog
  to "a chunk that never got a response or came back with a server error." This
  mapping is recorded here explicitly so a future plan that does build enrichment
  chunking doesn't assume `transport_failure` is chunk-native rather than reused.
- **AST guard distinguishes send-vs-fetch by HTTP verb, not by call-target name.**
  See Deviations below — this was corrected during development, not assumed
  correct from the plan text.
- **AST guard scans module-level assignments only for the accepted-row-store
  check.** See Deviations below — also corrected during development.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] AST send-shape guard's first draft matched on call-target name, false-flagging every read-only fetcher**
- **Found during:** Task 2, first test run of the guard
- **Issue:** The first draft of `_defines_send_shaped_function` matched any
  function that called something named `transport(...)`, or any `.post`/`.put`
  attribute call. Since `executions_client.py`'s own `_get_json` (and everything
  that calls it — `resolve_workflow_id`, `list_executions`, `get_execution`) calls
  its own injected `transport` parameter to perform a read-only GET, this shape
  would have flagged four legitimate 26-01 functions as offenders alongside the
  one real `dispatch()`.
- **Fix:** Redefined the signal as: a function's own `transport` parameter
  defaults to `requests.post`/`requests.put` (dispatch.py's exact shape, as
  opposed to `executions_client.py`'s `transport=requests.get` default), OR the
  function's body calls `requests.post`/`requests.put` directly. This is the
  actual distinguishing feature between a send and a fetch — the HTTP verb, not
  the parameter's name.
- **Files modified:** `operator-claude-plugin/tests/test_retry_reuses_dispatch.py`
- **Verification:** `test_exactly_one_module_defines_the_send_shaped_function` —
  confirmed to name only `dispatch.py`'s `dispatch()`.
- **Committed in:** `a28a9ca` (Task 2 commit; the false-flagging draft was never
  committed).

**2. [Rule 1 - Bug] No-accepted-row-store guard's first draft scanned every assignment in the AST, false-flagging Phase 24's local extraction variables**
- **Found during:** Task 2, first test run of the guard
- **Issue:** The first draft of `_all_assigned_names` walked the entire module
  tree, catching `preview.py`'s and `extraction.py`'s local `accepted` /
  `final_accepted` variables — Phase 24's per-call extraction-validation output,
  recomputed fresh on every invocation and discarded when the function returns.
  These share a substring with the forbidden marker set (`"accepted"`) but cannot
  persist anything across calls, so they are not the second dedupe authority the
  guard exists to forbid.
- **Fix:** Restricted the scan to assignments at module scope only (direct
  children of `ast.Module.body`) — the same scope `executions_client.py`'s own
  legitimate `_workflow_id_cache` lives at. A "store" implies cross-call
  persistence; a function-local variable is definitionally not one.
- **Files modified:** `operator-claude-plugin/tests/test_retry_reuses_dispatch.py`
- **Verification:**
  `test_no_module_defines_or_persists_a_previously_sent_row_store` — confirmed
  clean against the real codebase, and confirmed it still catches a temporarily
  added `_accepted_row_ids = set()` at module scope in `dispatch.py` (reverted,
  not committed).
- **Committed in:** `a28a9ca` (Task 2 commit; the false-flagging draft was never
  committed).

---

**Total deviations:** 2 auto-fixed (Rule 1 — both are guard-precision corrections
caught by running the guard against the real codebase before committing, exactly
the discipline the plan's acceptance criteria require: "the guard fails if a
second send-shaped function is added — prove this during development"). Neither
changed the plan's scope; both are the guard becoming correct rather than the
guard's purpose changing.

**Impact on plan:** None beyond the hardening itself.

## Issues Encountered

**Concurrent sibling agent (26-02) committed on top of this plan's Task 1 commit
mid-execution — no conflict, confirmed by inspection.** Between this plan's Task 1
commit (`cf28c3e`) and Task 2 commit (`a28a9ca`), two sibling commits landed:
`5b138a1` (docs, phase 27 plan-checker fix) and `b915cb9` (`test(26): enrichment
outcomes, review flag, remaining credits`, 26-02's own tracer work on
`report_enrichment.py` — a different module, for the enrichment lane, not the
contact lane this plan touches). Verified via `git show --stat b915cb9` before
staging Task 2's commit: zero file overlap with this plan's `files_modified` list.
`git status --short` before every stage showed only this plan's own files as
modified; `.planning/workstreams/plugin-entrypoint/REQUIREMENTS.md` also appeared
modified in the working tree (26-02's uncommitted REPORT-02 amendment,
`git diff` confirmed) and was deliberately left unstaged — not part of this
plan's `files_modified`, not mine to commit. Files were staged individually by
name at every commit (never `git add -A`/`git add .`), per the concurrency
protocol.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- `.venv/bin/python -m pytest operator-claude-plugin/tests/test_retry_reuses_dispatch.py operator-claude-plugin/tests/test_plugin_manifest.py -q` — 15 passed.
- `.venv/bin/python -m pytest operator-claude-plugin/tests -q` — 156 passed (baseline
  125 + this plan's 15 + sibling 26-02's 16 landed concurrently in between).
- `.venv/bin/python -m pytest -q` (full repo suite) — 900 passed, 1 skipped, no
  regressions.
- `git diff --name-only` across this plan's two commits (`cf28c3e`, `a28a9ca`)
  touches only files under `operator-claude-plugin/` — no backend file modified.
- No automated verification in this plan performed a live armed POST — the
  autouse `no_network` guard (patching `Session.request`, which `requests.get`
  routes through too) covers both this plan's tests and every prior plan's.
- DISPATCH-04 is now fully covered: failing rows are named with reason and
  identity/position (26-01), told apart by whether a re-send can fix them (this
  plan), and retry reuses the one existing arming-gated dispatch path with a
  structural guard preventing a second one from ever being added silently.
- 26-02 (concurrent) and any later plan can read `report.py`'s `resendable_rows`
  key and each row's `retryability`/`retry_reason` fields without redefining
  either.
- Phase 29 (NOTICE-01/02, the unprompted bounded watch) can build directly on
  `executions_client.py`'s existing fetch functions — this plan added no new
  fetch surface, only the one-fetch-per-ask re-check step in the skill, keeping
  the poll loop out of this phase as D-07 requires.

---
*Phase: 26-outcome-reporting-safe-retry*
*Completed: 2026-07-31*

## Self-Check: PASSED

All modified/created files verified present on disk
(`operator-claude-plugin/scripts/report.py`,
`operator-claude-plugin/tests/test_retry_reuses_dispatch.py`,
`operator-claude-plugin/skills/contact-upload/SKILL.md`,
`operator-claude-plugin/CHANGELOG.md`) and both commit hashes (`cf28c3e`,
`a28a9ca`) verified present in `git log --oneline --all`.
