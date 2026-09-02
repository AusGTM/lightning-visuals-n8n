---
phase: 26-outcome-reporting-safe-retry
plan: 01
subsystem: infra
tags: [claude-plugin, n8n-executions-api, ast-guard, contact-upload]

requires:
  - phase: 23-04
    provides: config_gate.py/dispatch.py/SKILL.md, the plugin's disarmed-by-default dispatch and no_network test guard, the fake_config/stub_transport conftest fixtures this plan extends
provides:
  - "operator-claude-plugin/scripts/executions_client.py — resolve_workflow_id(), list_executions(), get_execution() (X-N8N-API-KEY GETs, one fetch per call), and the pure find_execution_for_dispatch() time-proximity correlator"
  - "operator-claude-plugin/scripts/report.py — contact_row_ledger(), reconcile(), sync_response_is_sufficient(), build_contact_report()"
  - "operator-claude-plugin/tests/fixtures/execution_contact_upload.json — redacted execution fixture, exposed via a new contact_execution conftest fixture"
  - "SKILL.md step 7 — the report step (counts, failing rows in full, in-flight/unknown framing, run handle, manual re-check only)"
  - "an AST-based guard proving no plugin script under scripts/ imports time/sched, sleeps, or contains a while loop (D-07 as an enforced property, not a promise)"
affects: [26-02, 26-03, 29-notice-phases]

tech-stack:
  added: []
  patterns:
    - "Read the decision node, never the terminal node (Pattern 1) — contact_row_ledger() reads Decide Action's own output; Set Review only ever emits {\"queue\": \"needs_review\"}"
    - "Decided is not written (Pattern 2) — reconcile() downgrades update/create to not_confirmed when the terminal write node produced zero output items, never asserting a write that didn't land"
    - "Unknown is never rendered as finished — any execution status outside {success, error, crashed, canceled}, including absent/unrecognised, renders in_flight (Phase 25 D-10 discipline carried into this phase)"
    - "AST-based (not grep-based) architecture guard, matching 23-04's test_no_backend_imports.py precedent, for the no-poll-loop property"

key-files:
  created:
    - operator-claude-plugin/scripts/executions_client.py
    - operator-claude-plugin/scripts/report.py
    - operator-claude-plugin/tests/fixtures/execution_contact_upload.json
    - operator-claude-plugin/tests/test_executions_fallback.py
    - operator-claude-plugin/tests/test_report_sufficiency.py
  modified:
    - operator-claude-plugin/tests/conftest.py
    - operator-claude-plugin/skills/contact-upload/SKILL.md

key-decisions:
  - "sync_response_is_sufficient/reconcile/build_contact_report's adaptive shaping were all written into report.py during Task 1 as one cohesive module (executions_client.py and report.py were designed together, per the tracer task's own framing) — Task 2's commit therefore adds only the dedicated test coverage for those functions, not new report.py code."
  - "not_confirmed is a distinct per-row and per-count label (5th key alongside created/updated_matched/needs_review/rejected), matching the plan's own wording ('the four labels... plus the not-confirmed state') rather than folding a gated write silently into needs_review."
  - "SMALL_BATCH_THRESHOLD=20, matching conftest.py's existing >20-row adaptive-preview convention from Phase 23 (D-09's 'one convention across preview and report')."
  - "config's n8n_api_key key is read defensively (config.get, never a KeyError) since config_gate.py's own validation is out of this plan's files_modified list and was left untouched — schema documentation (operator.local.example.json) is left for a later plan."

patterns-established:
  - "executions_client.py's three GETs all take an injectable transport (mirroring dispatch.py's transport=requests.post pattern) so every test drives them through a stub — never a real socket."

requirements-completed: [REPORT-01, REPORT-03]

coverage:
  - id: D1
    description: "find_execution_for_dispatch() selects the earliest execution at or after the dispatch instant (never the nearest earlier run), returns None when nothing qualifies, and marks its result best_effort so callers can't treat it as authoritative (D-12)"
    requirement: "REPORT-03"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_executions_fallback.py#test_find_execution_for_dispatch_returns_earliest_execution_at_or_after_dispatch"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_executions_fallback.py#test_find_execution_for_dispatch_returns_none_when_nothing_qualifies"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_executions_fallback.py#test_find_execution_for_dispatch_marks_result_best_effort"
        status: pass
    human_judgment: false
  - id: D2
    description: "contact_row_ledger() reads Decide Action's own output in source order, and returns an empty ledger plus a stated reason (never raising) when the decision node or the payload shape is missing"
    requirement: "REPORT-01"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_executions_fallback.py#test_contact_row_ledger_returns_one_entry_per_source_row_in_order"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_executions_fallback.py#test_contact_row_ledger_missing_decision_node_returns_empty_ledger_and_reason"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_executions_fallback.py#test_contact_row_ledger_never_raises_on_malformed_payload"
        status: pass
    human_judgment: false
  - id: D3
    description: "build_contact_report() sums counts to the ledger length on a finished fixture, and renders in_flight for a running or an unrecognised-status execution — never a finished framing for either"
    requirement: "REPORT-03"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_executions_fallback.py#test_build_contact_report_finished_fixture_counts_sum_to_ledger_length"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_executions_fallback.py#test_build_contact_report_running_execution_is_never_rendered_finished"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_executions_fallback.py#test_build_contact_report_unrecognised_status_is_also_in_flight"
        status: pass
    human_judgment: false
  - id: D4
    description: "sync_response_is_sufficient() judges a Set-Review-shaped (queue-marker-only) body insufficient, and a body with contact_id/hs_object_id/a full HubSpot object sufficient; empty/scalar/non-mapping bodies are insufficient"
    requirement: "REPORT-01"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_report_sufficiency.py#test_review_queue_marker_only_body_is_insufficient"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_report_sufficiency.py#test_body_with_contact_id_is_sufficient"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_report_sufficiency.py#test_non_list_scalar_body_is_insufficient"
        status: pass
    human_judgment: false
  - id: D5
    description: "reconcile() downgrades a decided create/update row to not_confirmed (never created/updated_matched) when the terminal write node produced zero output items or never ran at all"
    requirement: "REPORT-01"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_report_sufficiency.py#test_create_row_is_not_confirmed_when_hubspot_create_produced_zero_items"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_report_sufficiency.py#test_build_contact_report_never_labels_the_write_blocked_row_created"
        status: pass
    human_judgment: false
  - id: D6
    description: "A batch at/below the small-batch threshold renders every row; above it, the full failing subset plus counts plus a stated total is returned while successful rows are summarised"
    requirement: "REPORT-01"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_report_sufficiency.py#test_small_batch_renders_every_row"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_report_sufficiency.py#test_large_batch_omits_full_rows_but_keeps_the_full_failing_subset_and_a_total"
        status: pass
    human_judgment: false
  - id: D7
    description: "No plugin script under scripts/ imports time/sched, calls sleep, or contains a while loop — D-07 enforced by the suite via AST parsing, not grep, and the guard asserts it scanned at least one file"
    requirement: "REPORT-03"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_report_sufficiency.py#test_no_plugin_script_polls_sleeps_or_loops_on_execution_status"
        status: pass
    human_judgment: false
  - id: D8
    description: "The report step is wired into SKILL.md (step 7): sufficiency check first, executions-API fallback second, in-flight/executions-API framing stated plainly, NO_EMAIL/ambiguous rows named as permanently stuck rather than retryable, and the run handle printed with an explicit manual-only re-check"
    requirement: "REPORT-01"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_plugin_manifest.py#test_skill_body_references_only_scripts_that_exist_on_disk"
        status: pass
    human_judgment: true
    rationale: "The prose wording and step ordering in SKILL.md is a conversational contract for the Claude agent driving the skill — a passing test proves report.py/executions_client.py are correctly referenced and exist, but whether the report reads well and follows D-08/D-09's actionable-first convention in a live conversation needs a human/UAT read, same as Phase 23's own preview step."

duration: ~55min
completed: 2026-07-31
status: complete
---

# Phase 26 Plan 01: Outcome Reporting & Safe Retry — Tracer Summary

**A per-record contact-upload ledger read from `Decide Action` (never the terminal `Set Review` node), reconciled against the actual write, and rendered through one report shape that refuses to call an in-flight or unfetchable run finished — plus a run handle whose time-proximity correlation is labelled best-effort, and an AST-enforced guard that no poll loop can grow here.**

## Performance

- **Duration:** ~55 min
- **Tasks:** 3
- **Files modified:** 7 (2 created scripts, 1 fixture, 2 new test files, 1 modified conftest, 1 modified SKILL.md)

## Accomplishments
- `executions_client.py`: thin read-only n8n API wrapper (`resolve_workflow_id`,
  `list_executions`, `get_execution`) authenticated with `X-N8N-API-KEY` (never the
  webhook's `X-Enrichment-Secret`), each call carrying an explicit finite timeout and an
  injectable transport. `find_execution_for_dispatch()` is pure — no fetch of its own —
  and marks its result `best_effort: True` since neither deployed workflow references
  `$execution.id` (D-12): the handle could name a neighbouring run, and the report says so.
- `report.py`: `contact_row_ledger()` reads `Decide Action`'s own output — verified against
  the node's actual `jsCode` return statement (`action, outcome, contact_id, hs_object_id,
  reason, email_status, properties` — no `email`, correcting 26-RESEARCH.md's assumed field
  list per D-11a) — never `Set Review`, which n8n's Edit-Fields default reduces to
  `{"queue": "needs_review"}` alone. `reconcile()` downgrades a decided update/create to
  `not_confirmed` when the terminal write node produced zero output items or never ran,
  which is the conservative, only-safe direction (T-26-01). `build_contact_report()` treats
  any status outside `{success, error, crashed, canceled}` — including absent or
  unrecognised — as `in_flight`, mirroring Phase 25 D-10's "unknown is never rendered as
  success" discipline, and renders a `state: "unknown"` report (handle intact) when the
  execution itself could not be fetched.
- `sync_response_is_sufficient()`: the synchronous webhook body is used only when every
  item is row-identifying or a full HubSpot object — a `Set Review`-shaped body (queue
  marker only) falls through to the executions-API path by construction (D-11, Pitfall 1).
- Adaptive shaping in `build_contact_report()`: a batch at or below 20 rows renders every
  row; above it, the full failing subset (with reason + identity/ordinal position) is still
  returned in full alongside counts and a stated total, while successful rows are
  summarised — one convention across Phase 23's preview and this report (D-08/D-09).
- `tests/fixtures/execution_contact_upload.json`: a redacted, execution-shaped fixture with
  one `Decide Action` row per outcome (match/net_new/ambiguous/rejected) plus `HubSpot
  Update`, `HubSpot Create`, and `Set Review` entries — exposed via a new
  `contact_execution` conftest fixture (deep-copied per test) for later plans to reuse.
- SKILL.md step 7 ("Report the outcome"): sufficiency check first, executions-API fallback
  on an insufficient/timed-out/gatewayed body (the Cloudflare ~100s ceiling, D-13), an
  explicit "this came from the executions API and may still be progressing" framing
  (D-03), summary counts then the failing rows in full then successful-row detail only for
  small batches, the `NO_EMAIL`/`ambiguous` permanently-stuck case named plainly rather than
  presented as retryable (D-11b/D-14), and the run handle printed with an explicit
  "re-check only happens when you ask" (D-06/D-07).
- An AST-based guard (`ast.parse`, not grep) asserting no file under `scripts/` imports
  `time`/`sched`, calls `sleep`, or contains a `while` loop — turning D-07 into a property
  the suite enforces, and asserting it scanned at least one file so it can't pass by
  scanning nothing.

## Task Commits

1. **Task 1: End-to-end tracer — executions client, contact outcome ledger, run handle** - `e70010d` (feat)
2. **Task 2: Sufficiency of the synchronous body, and write reconciliation** - `a04d3cc` (test)
3. **Task 3: Report step in the skill, and the no-poll-loop guard** - `347faaf` (feat)

## Files Created/Modified
- `operator-claude-plugin/scripts/executions_client.py` - workflow/execution GETs + pure time-proximity correlator
- `operator-claude-plugin/scripts/report.py` - contact_row_ledger, reconcile, sync_response_is_sufficient, build_contact_report
- `operator-claude-plugin/tests/fixtures/execution_contact_upload.json` - redacted execution fixture, one row per outcome
- `operator-claude-plugin/tests/test_executions_fallback.py` - executions_client + report (executions-API path) coverage
- `operator-claude-plugin/tests/test_report_sufficiency.py` - sufficiency, reconcile, adaptive-shaping, no-poll-loop guard
- `operator-claude-plugin/tests/conftest.py` - `n8n_api_key` on `fake_config`, `contact_execution` fixture, `stub_get_transport_factory`
- `operator-claude-plugin/skills/contact-upload/SKILL.md` - step 6 tightened, new step 7 (report), cleanup renumbered to step 8

## Decisions Made
- `report.py`'s full functional surface (`sync_response_is_sufficient`/`reconcile`/adaptive
  shaping, not just `contact_row_ledger`/`build_contact_report`) was written in one pass
  during Task 1, since `executions_client.py` and `report.py` were designed as one cohesive
  module per the tracer task's own framing. Task 2's commit is therefore test-only —
  dedicated coverage for functions that already existed, not new implementation.
- `not_confirmed` is carried as its own label (a 5th count key alongside
  created/updated_matched/needs_review/rejected), matching the plan action text literally
  ("the four labels... plus the not-confirmed state") rather than silently folding a
  write-gated row into `needs_review`'s count.
- `SMALL_BATCH_THRESHOLD = 20`, reusing the same threshold `conftest.py`'s own
  `CSV_ROW_COUNT = 25` comment already documents for Phase 23's adaptive-preview branch —
  one number, one convention, across preview and report (D-09).
- `config_gate.py` was left untouched (not in this plan's `files_modified`): the new
  `n8n_api_key` config key is read defensively via `config.get(...)` in
  `executions_client.py` rather than validated at load time. `operator.local.example.json`
  documentation for this key is left to a later plan.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `build_contact_report()` guards against a non-dict execution, not just `None`**
- **Found during:** Task 1, writing the malformed-payload test
- **Issue:** The plan's stated behavior only names `execution is None` (a pruned run / 404)
  as the "unknown" trigger. A non-dict value (a string, an int, a list) passed in by a
  caller error would have fallen through to `execution.get(...)`, raising `AttributeError`.
- **Fix:** Guard on `not isinstance(execution, dict)` instead of `execution is None` — every
  non-dict input (including `None`) now returns the `state: "unknown"` report; an actually
  empty dict (a genuinely fetched-but-content-less execution) still renders `in_flight`
  per the unknown-status rule, which is the more precise behavior.
- **Files modified:** `operator-claude-plugin/scripts/report.py`
- **Verification:** `test_build_contact_report_never_raises_on_a_non_dict_execution`,
  `test_build_contact_report_empty_dict_execution_is_in_flight_not_a_crash`
- **Committed in:** `e70010d` (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 — defensive-parsing correctness, matching the
plan's own "never raises, never a partial guess" requirement more precisely than its literal
wording named).
**Impact on plan:** None beyond the hardening itself. No scope creep.

## Issues Encountered

**Concurrent-agent git-index race on `SKILL.md` (shared file, not code-level, no data lost).**
Sibling agents 24-02/24-03 were executing concurrently in the same working tree, both
touching `operator-claude-plugin/skills/contact-upload/SKILL.md` (their step 2/3 edits) at
the same time Task 3 here was editing step 6/7/8 of the same file. Both agents run `git
add`/`git commit` against one shared git index — there is no worktree isolation between
these parallel wave agents. During the Task 3 commit sequence, one `git add -p`/`git
commit` cycle raced with a sibling commit and landed a **misattributed** commit,
`d8bc409` ("feat(26): report step in the skill...") whose actual diff is the *sibling's*
step 2/3 hunks, not mine. This was caught by inspecting `git show --stat` immediately after
committing (it showed only 21 insertions where ~120 were expected). No content was lost —
my step 6/7/8 edits remained live in the working tree throughout and were verified via
`git diff` and a passing test run, then committed cleanly and correctly in `347faaf` once
the sibling's own commit cycle (`aa78119`/`89bf998`) had settled. **`d8bc409` remains in
history with its message not matching its actual diff** — it is not destructive (the
content it contains is the sibling's legitimate, subsequently-verified work) and is now an
ancestor of several later commits, so rewriting it via rebase/amend was avoided per the
destructive-git-prohibition rather than risk losing concurrent work. Flagging this
explicitly for the orchestrator/reviewer: `d8bc409`'s commit message describes Task 3 of
this plan, but its diff belongs to 24-03.

## User Setup Required
None — no external service configuration required. (A future plan should add `n8n_api_key`
to `operator-claude-plugin/config/operator.local.example.json`'s documented fields; this
plan's `config_gate.py` scope did not include that, per its `files_modified` list.)

## Next Phase Readiness
- `.venv/bin/python -m pytest operator-claude-plugin/tests -q` — 125 passed.
- `.venv/bin/python -m pytest -q` (full repo suite) — 869 passed, 1 skipped, no regressions.
- `git diff --name-only` across this plan's three commits (`e70010d`, `a04d3cc`, `347faaf`)
  touches only files under `operator-claude-plugin/` — no backend file modified, matching
  the plan's own `<verification>` requirement.
- No automated verification in this plan performed a network call, armed or otherwise — the
  autouse `no_network` guard (which patches `Session.request`, covering `requests.get` too)
  proves this by construction.
- 26-02/26-03 can build on `report.py`'s report-object shape (`source`, `state`, `reason`,
  `counts`, `total`, `rows`, `failing_rows`, `reason_groups`, `adaptive`, `handle`) and the
  `contact_execution` conftest fixture without redefining either.
- The `d8bc409` misattributed-commit history artifact (see Issues Encountered) should be
  visible to whoever reviews this wave's commit log — it is cosmetic (message/diff
  mismatch), not a functional defect, but worth knowing before assuming commit messages
  match their diffs 1:1 in this wave's history.

---
*Phase: 26-outcome-reporting-safe-retry*
*Completed: 2026-07-31*

## Self-Check: PASSED

All created files verified present on disk (`executions_client.py`, `report.py`,
`tests/fixtures/execution_contact_upload.json`, `tests/test_executions_fallback.py`,
`tests/test_report_sufficiency.py`) and all three commit hashes (`e70010d`, `a04d3cc`,
`347faaf`) verified present in `git log --oneline --all`.
