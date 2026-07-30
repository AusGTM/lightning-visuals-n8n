---
phase: 27-backend-status-surface
plan: 04
subsystem: operator-claude-plugin
tags: [plugin, n8n-api, status, no-allowlist, execution-age, per-node-errors, renderer, skill]

requires:
  - phase: 27
    plan: 03
    provides: "describe_workflow()/last_execution()/read_write_safety()/render() — the per-workflow slice this plan loops, and the unknown discipline every rendered datum still routes through"
  - phase: 27
    plan: 02
    provides: "error_table.translate() — the single translation entry point every harvested finding passes through, guardrail and redaction included"
  - phase: 27
    plan: 01
    provides: "hubspot/backend-status's counts/credential_health/balances, rendered into the records-waiting-on-a-human and providers sections"
provides:
  - "status.describe_all() — every workflow the key can see, no allowlist (D-07)"
  - "status.full_report() — describe_all() plus the backend-supplied half, behind the status capability gate"
  - "n8n_read.recent_executions() / get_execution() / summarize_execution() / stuck_threshold_minutes() / elapsed_minutes()"
  - "execution_errors.harvest_errors() — execution-level, node-level and item-level failures, collapsed and translated"
  - "render_text.render_report() / render_failure() / attach_failures() — the conversational answer"
  - "skills/backend-status/SKILL.md — slash handle /operator-claude-plugin:backend-status"
affects: [27-05 (edits the SKILL.md dashboard marker and renders the same mapping), 28 (its read-back verification uses n8n_read and describe_all)]

tech-stack:
  added: []
  patterns:
    - "The collection response IS the list — no allowlist anywhere, asserted by a source-scanning test rather than by convention"
    - "Tri-state stuck: True / False / None-for-unknown-age, so an unreadable run cannot round down to 'running normally'"
    - "A bounded page is a shortcut, never a history: absence from it triggers a filtered top-up read before never-run is claimed"
    - "Failures read from per-node output, because the pipeline was built to keep running when a provider fails and therefore reports those runs successful"
    - "Collapse key (node, cause) — a hundred rows rejected the same way by the same node is one problem with a count"

key-files:
  created:
    - operator-claude-plugin/scripts/execution_errors.py
    - operator-claude-plugin/scripts/render_text.py
    - operator-claude-plugin/skills/backend-status/SKILL.md
    - operator-claude-plugin/tests/test_status_all_workflows.py
    - operator-claude-plugin/tests/test_execution_errors.py
    - operator-claude-plugin/tests/test_status_skill.py
  modified:
    - operator-claude-plugin/scripts/n8n_read.py
    - operator-claude-plugin/scripts/status.py
    - .planning/workstreams/plugin-entrypoint/phases/27-backend-status-surface/27-CONTEXT.md
    - .planning/workstreams/plugin-entrypoint/REQUIREMENTS.md

key-decisions:
  - "`stuck` is tri-state rather than boolean. None means in flight with an unreadable start time; collapsing it to False would render an unjudgeable run as 'running normally', which is D-08's unknown-as-healthy failure wearing a different key. Folded into 27-CONTEXT.md as D-07b(i)."
  - "describe_all() uses a collection entry as the workflow body only when it actually carries a `nodes` list, and fetches the body otherwise. n8n's /workflows is documented to return full objects, but nothing in this repo proves it; a thin entry would make write-safety read `unknown` for every workflow at once — D-10's under-reporting failure wearing an honest word. Folded into 27-CONTEXT.md under D-10."
  - "describe_workflow() gained optional `body`/`last_run` parameters instead of being duplicated. describe_all() already holds both from its two collection calls, so the widening reuses the proven composer and still costs two calls in the common case."
  - "A recognised failure renders its sentence and attribution and NOTHING else — no code, no node name, no stack. The node name is carried in the data for the harvester's collapse key but deliberately not rendered, per the plan's 'nothing else about it'."
  - "render_text.py is the skill's single rendering entry point and does the gated failure-detail fetch itself, so the skill is two commands rather than an orchestration the model has to get right. execution_errors.py keeps its own CLI for the operator-names-an-execution case."
  - "STATUS-01 marked Complete. 27-03 deliberately left it Pending because it proved the data for ONE workflow; the plain-language answer across every workflow is this plan's deliverable and now exists."

requirements-completed: [STATUS-01]

coverage:
  - id: D1
    description: "Every workflow the n8n API key can see is reported with no allowlist — a newly deployed or renamed workflow appears without a configuration edit (D-07)"
    requirement: STATUS-01
    verification:
      - kind: unit
        ref: "tests/test_status_all_workflows.py::test_every_workflow_in_the_collection_is_reported, ::test_a_newly_added_workflow_appears_with_no_other_change, ::test_no_workflow_allowlist_exists_in_any_plugin_source"
        status: pass
      - kind: command
        ref: "grep -rn 'workflow_allowlist\\|WORKFLOW_ALLOWLIST' operator-claude-plugin/scripts/ | wc -l -> 0"
        status: pass
    human_judgment: false
  - id: D2
    description: "An execution running past the configured threshold is reported stuck, carrying its actual age and the threshold so the operator can judge the call (D-07b, A2)"
    requirement: STATUS-04
    verification:
      - kind: unit
        ref: "tests/test_status_all_workflows.py::test_a_run_past_the_threshold_is_stuck_and_carries_its_age_and_the_threshold, ::test_a_run_under_the_threshold_is_in_flight_and_not_stuck, ::test_the_threshold_comes_from_configuration, ::test_the_threshold_falls_back_to_the_documented_default_when_absent"
        status: pass
      - kind: unit
        ref: "tests/test_status_skill.py::test_a_stuck_run_states_its_elapsed_time_and_the_threshold_together"
        status: pass
    human_judgment: false
  - id: D3
    description: "A provider failure inside a run n8n reports as successful is still surfaced, because per-node output is read rather than only the run status (D-04a/D-04b)"
    requirement: STATUS-02
    verification:
      - kind: unit
        ref: "tests/test_execution_errors.py::test_a_provider_rejection_surfaces_even_when_the_run_status_reads_successful, ::test_an_error_inside_a_node_output_item_is_collected, ::test_all_four_status_02_causes_are_reachable_from_node_output"
        status: pass
    human_judgment: false
  - id: D4
    description: "A failed run is reported by cause in one plain sentence naming who can fix it, with no status code and no stack trace (STATUS-02, D-04c)"
    requirement: STATUS-02
    verification:
      - kind: unit
        ref: "tests/test_status_skill.py::test_a_failed_run_renders_its_translated_sentence_and_its_attribution, ::test_a_rendered_failed_run_carries_no_status_code_and_no_traceback (regex sweep for a bare three-digit token plus four traceback markers), ::test_an_unrecognised_failure_keeps_its_label_and_its_raw_text_apart"
        status: pass
    human_judgment: false
  - id: D5
    description: "The records-needing-a-human block shows counts for queued and for review backlog on both object types, with any count the backend could not read shown as unknown (STATUS-04, STATUS-06)"
    requirement: STATUS-04
    verification:
      - kind: unit
        ref: "tests/test_status_skill.py::test_the_answer_carries_queued_and_review_counts_for_both_object_types, ::test_a_null_count_renders_as_unknown_and_never_as_a_zero, ::test_a_genuine_zero_survives_as_a_zero"
        status: pass
    human_judgment: false
  - id: D6
    description: "A workflow with no execution history is reported never-run; a workflow whose history is merely outside the fetched page is not, and a failed top-up read is unknown rather than never-run (T-27-17)"
    requirement: STATUS-01
    verification:
      - kind: unit
        ref: "tests/test_status_all_workflows.py::test_a_workflow_absent_from_the_page_gets_its_own_filtered_read, ::test_an_empty_top_up_read_is_never_run, ::test_a_failed_top_up_read_is_unknown_and_specifically_not_never_run, ::test_an_unreadable_collection_is_unknown_and_not_an_empty_list, ::test_a_genuinely_empty_collection_is_readable_with_no_workflows"
        status: pass
    human_judgment: false
  - id: D7
    description: "The large execution-detail payload is fetched only for a run already known to have failed or one the operator names, never for every run in the page (T-27-18)"
    requirement: STATUS-02
    verification:
      - kind: unit
        ref: "tests/test_execution_errors.py::test_nothing_fetches_a_detail_payload_for_every_run_in_the_page; tests/test_status_skill.py::test_attach_failures_fetches_detail_only_for_a_run_that_failed (three workflows scripted, exactly one detail call made)"
        status: pass
    human_judgment: false
  - id: D8
    description: "The skill states in plain language that this surface only reads, and no mutating call site exists in any module this plan touches (T-27-19)"
    requirement: STATUS-01
    verification:
      - kind: unit
        ref: "tests/test_status_skill.py::test_the_skill_states_that_it_only_reads, ::test_every_script_path_named_in_the_skill_body_exists_on_disk, ::test_the_skill_is_reachable_as_a_slash_command_with_no_commands_directory"
        status: pass
      - kind: command
        ref: "grep -nE 'requests\\.(post|put|patch|delete)' operator-claude-plugin/scripts/*.py -> only backend_status.py's allowlisted read-POST, dispatch.py, and status.py's pass-through parameters"
        status: pass
    human_judgment: false
  - id: D9
    description: "Translation stays single-pathed: the harvester consumes error_table.translate() and exposes no caller-supplied attribution override (D-05)"
    requirement: STATUS-02
    verification:
      - kind: unit
        ref: "tests/test_execution_errors.py::test_this_module_holds_no_second_translation_path, ::test_an_unrecognised_signature_keeps_the_guarded_interpretation, ::test_raw_text_arrives_already_redacted_and_bounded"
        status: pass
    human_judgment: false

duration: 71min
completed: 2026-07-31
status: complete
---

# Phase 27 Plan 04: Every workflow, what is wedged, and why the last failure failed Summary

**The status surface widened from one workflow to every workflow the key can see with no allowlist, "stuck" answered as an execution-age verdict that carries its own evidence, failures read out of per-node output so a provider rejection inside a run n8n calls successful still reaches the operator, and all of it rendered as one plain-language answer behind a skill that says plainly it can only look.**

## Performance

- **Duration:** ~71 min
- **Completed:** 2026-07-31
- **Tasks:** 3 completed (Tasks 1 and 2 TDD with genuine RED; Task 3 module + skill + tests)
- **Files modified:** 10 (6 created, 4 modified — 2 of them planning docs)

## Accomplishments

- **`status.describe_all()` reports every workflow, with no allowlist anywhere (D-07).** The
  collection response *is* the list — a newly deployed or renamed workflow is in the answer the
  moment n8n returns it, asserted by a test that adds an entry and changes nothing else, plus a
  source-scanning test that fails if any plugin module ever grows the word `workflow_allowlist`.
  `readable: False` with an empty list ("could not read") and `readable: True` with an empty list
  ("genuinely none") stay distinct, the same discipline 27-03 established for `list_workflows()`.
- **Two calls in the common case, and never a fabricated never-run.** One workflow-collection call
  plus one bounded page of executions grouped by workflow. A workflow absent from that page gets
  its own filtered read before anything is claimed about it — a bounded page is not complete
  history. A top-up read that *fails* reports `unknown`, specifically not never-run: the
  reassuring answer is the dangerous one (T-27-17).
- **"Stuck" is an execution-age verdict on data the client already holds (D-07b).** No HubSpot
  lock state is queried, referenced or reconstructed — `enrichment_lock_until` does not exist in
  this portal's schema and nothing ever wrote a `running` status (D-07a). The verdict is
  **tri-state**: over threshold, under threshold, or `None` for in-flight-with-an-unreadable-start,
  which the renderer states as unknown age rather than as "running normally". Both the age and the
  threshold travel with the verdict and the rendered sentence says in words that the threshold is a
  convention, because A2 says it is carried, not measured.
- **`execution_errors.harvest_errors()` reads failures out of node output, not run status
  (D-04a/D-04b).** Three collection sites: the execution-level error, each node run's own error,
  and the error payloads inside node output items — that third one is where a provider rejection
  lands, because those nodes are `onError: continueRegularOutput` and their runs report `success`.
  The headline test asserts exactly that: a `success` execution whose node output carries a 401
  still surfaces the finding. Identical findings collapse per `(node, cause)` with a count, so a
  hundred rejected rows read as one problem.
- **One translation path, no second table, no override.** Every finding goes through
  `error_table.translate()`; a test asserts the module contains no `who_can_fix=` assignment at
  all, so no caller can blame the operator for a signature the table did not recognise.
- **The conversational answer (D-09).** `render_text.render_report()` produces per-workflow blocks,
  then records-waiting-on-a-human, then providers — every datum through 27-03's `render()`, so a
  null reads `unknown` while a genuine `0` stays `0`. A recognised failure renders its sentence and
  attribution and nothing else; an unrecognised one keeps its interpretation label and its raw text
  on separate lines.
- **`skills/backend-status/SKILL.md`** opens by saying this skill reads and changes nothing, before
  any step. It carries the explicit `27-05 DASHBOARD STEP` marker so 27-05 is an edit.

## Task Commits

1. **Task 1 — RED:** `278cd2a` (test) · **GREEN:** `eed547d` (feat)
2. **Task 2 — RED:** `9bcd766` (test) · **GREEN:** `e5bead9` (feat)
3. **Task 3:** `da6f0f9` (feat)

RED was genuine both times: Task 1's RED failed 21 of 22 (the one pass is the static
no-allowlist source scan, correctly green from the start); Task 2's RED failed at collection
because `execution_errors` did not exist.

## Test Counts

| Suite | Before | After | Delta |
|---|---|---|---|
| pytest (repo, `.venv/bin/python -m pytest -q`) | 993 passed, 1 skipped | 1065 passed, 1 skipped | **+72** |
| pytest (plugin only) | 230 passed | 302 passed | **+72** |
| node (`node --test tests/n8n/<file>.test.mjs`) | 400 passed, 0 fail | 400 passed, 0 fail | 0 |

The +72 is exactly this plan's three new test files (22 + 21 + 29). No existing test was
weakened, deleted or skipped; no regression anywhere.

## Decisions Made

See `key-decisions` in the frontmatter. The two worth repeating because a later plan could
undo them without noticing:

- **Do not flatten `stuck` to a boolean.** `None` is in-flight-with-unknown-age. Folded into
  `27-CONTEXT.md` as **D-07b(i)**.
- **Do not delete `describe_all()`'s body-fetch fallback.** A collection entry without `nodes`
  would make write-safety read `unknown` for every workflow simultaneously — D-10's
  under-reporting failure wearing an honest-looking word. Folded into `27-CONTEXT.md` under D-10.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Test bug] An assertion forbade a key the design deliberately returns**
- **Found during:** Task 1, first GREEN run.
- **Issue:** `test_no_fetched_workflow_body_leaks_into_the_answer` asserted `"nodes" not in
  json.dumps(result)`. But `write_safety.nodes` is 27-03's deliberate list of **declaring node
  names**, which T-27-11 explicitly permits — the thing that must not cross out of the module is
  the body, i.e. `jsCode` under `parameters`. Nothing was wrong with the renderer.
- **Fix:** Narrowed the assertion to `jsCode` and `parameters`, with a comment naming the
  distinction so it is not re-broadened later. The marker-string assertion keeps its full strength.
- **Commit:** `eed547d`

**2. [Rule 1 - Test bug] A fixture built `runData` in the wrong shape**
- **Found during:** Task 2, first GREEN run.
- **Issue:** `test_a_node_absent_from_the_run_data_produces_no_finding` passed `{"Decide Action":
  _node_run()}` — a single run *dict* where n8n's `runData` maps a node to a *list* of runs. The
  harvester correctly failed closed as unreadable; the test asserted `available is True`. The
  module was right and the fixture was wrong.
- **Fix:** Wrapped the run in a list, which is the real shape. Left the fail-closed branch
  untouched and separately covered by
  `test_a_node_whose_runs_are_not_a_list_is_unreadable_rather_than_clean`.
- **Commit:** `e5bead9`

**3. [Rule 2 - Missing critical functionality] Write-safety literals were bypassing the on/off
rendering entirely**
- **Found during:** Task 3, first test run.
- **Issue:** `read_write_safety()` returns the baked literal as the **string** `"true"`/`"false"`,
  never a boolean, so `status.render()`'s boolean branch never fires and the operator-facing line
  read `ALLOW_HUBSPOT_CREATE false`. Correct, but the whole surface is written for a non-technical
  reader, and "false" beside a flag name is exactly the kind of line that gets misread.
- **Fix:** A three-line `_armed()` mapping `"true"`→on, `"false"`→off, and **everything else**
  falling through to `status.render()` — so an absent or unrecognised literal still reads `unknown`
  and can never become a reassuring "off".
- **Files modified:** `operator-claude-plugin/scripts/render_text.py`
- **Commit:** `da6f0f9`

**Total deviations:** 3 — two test bugs where the module was right, one rendering gap closed.

## Plan/reality mismatches

Two, both folded into `27-CONTEXT.md` rather than left in this summary (the planner reads CONTEXT):

1. **The workflows collection may not carry `nodes`.** The plan's Task 1 action assumed widening
   was a straight loop over the collection. It is, except that write-safety needs a body, and this
   repo has never proved the collection endpoint always includes one. Recorded under **D-10**.
2. **`stuck` needed a third state the plan's behaviour list implied but did not name.** The plan
   says an unparseable start time is "reported unknown-age and is not classified stuck" — which a
   boolean can only express as `False`, i.e. as "fine". Recorded as **D-07b(i)**.

Everything else the plan relied on held. 27-03's interfaces were used exactly as its summary
described them: `list_workflows()`'s `None`-vs-`[]` distinction was preserved and never `or []`'d
away, `last_execution()`'s tri-state was extended rather than replaced, `read_write_safety()`'s
node list is never hardcoded, `started_at` was the raw ISO string the age arithmetic needed, and
`config_gate.require_capability(cfg, "status")` gates `full_report()` with no global gate
reinstated.

## Known Stubs

None. One deliberate not-yet-built statement exists in the skill body — step 4 tells the operator
the visual dashboard is not built yet and offers the text answer instead. That is 27-05's declared
scope, marked with an explicit `27-05 DASHBOARD STEP` comment and asserted by
`test_the_skill_leaves_an_explicit_marker_for_the_dashboard_step`, not a placeholder flowing to a
rendering surface.

## Threat Flags

None. No new network endpoint, no auth path, no file access pattern and no schema change was
introduced. Every URL touched lives under the configured n8n base, and the only new HTTP call is a
GET (`n8n_read.get_execution`).

## Safety invariants

- No write flag armed, no deploy, no activation, no live HubSpot or n8n call. No automated
  verification made a network request — the autouse `no_network` guard covers every plugin test,
  including GETs, and was left untouched (D-11).
- `grep -c 'ALLOW_HUBSPOT_[A-Z_]* = "true"' n8n/*.json` → **0 everywhere.** This plan touched no
  `n8n/` file at all.
- The plugin still constructs no provider request of any kind (D-01): the only send-shaped
  functions in the plugin remain `dispatch.py::dispatch` and the allowlisted bodyless
  `backend_status.py::fetch_backend_status`, both unchanged. The three compensating guards in
  `test_retry_reuses_dispatch.py` stayed green without any allowlist edit.
- Every commit staged explicit paths in the same shell invocation as the commit, with
  `git diff --cached --name-only` printed immediately beforehand. No `git add -A`, no `git add .`,
  no `git commit -a`, and no file outside this plan's declared region was ever staged.

## Issues Encountered

None. No sibling was running, so the index race 27-03 hit did not recur — the single-invocation
stage-and-commit discipline was kept anyway.

## User Setup Required

None new. `stuck_execution_minutes` (default 15) was already added to
`config/operator.local.example.json` by 27-03 and is now actually consumed; an operator who omits
it gets the documented 15-minute default rather than an error.

## Next Phase Readiness

- **27-05** edits `skills/backend-status/SKILL.md` at the `27-05 DASHBOARD STEP` marker in step 4
  and renders `status.full_report()`'s mapping — the same mapping `render_text.render_report()`
  consumes, so the dashboard and the text cannot drift apart. Note that
  `test_status_skill.py::test_every_script_path_named_in_the_skill_body_exists_on_disk` will fail
  if a `scripts/<name>.py` path is written into the body before that file exists.
- **Phase 28** can build its read-back verification on `describe_all()` and `n8n_read`, both of
  which stayed GET-only.
- No blocker.

---
*Phase: 27-backend-status-surface*
*Completed: 2026-07-31*

## Self-Check: PASSED

All six created source/skill/test files exist on disk; all five task commit hashes
(`278cd2a`, `eed547d`, `9bcd766`, `e5bead9`, `da6f0f9`) verified present in `git log`.
