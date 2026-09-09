---
phase: 70-one-merge-one-result-channel-n8n-runtime-truth
plan: 06
subsystem: operator-claude-plugin (client result channel) + repo webhook drivers
tags: [result-channel, rundata, run-id-correlation, written-records, confidence-gate, ack-only]
status: complete

requires:
  - "70-02: ack-only ingest webhook, lane-aware `watch.recover_dispatch`, `run_id` on the ingest multipart POST"
  - "70-03: `dispatch_plan`'s sync-body flush deleted; `run_id` always rides the enrichment envelope"
  - "70-05: IF-shaped write gates with emitted refusals (the rows this channel now carries)"
provides:
  - "`chunking.dispatch_and_recover` — the ONE dispatch-and-recover cycle, every mode"
  - "`watch.require_executions_api` + `config_gate.CAPABILITY_KEYS` gaining `n8n_api_key` on every send-capable row"
  - "`watch.child_execution_ids` + `recover_dispatch(include_children=True)` — scale-up children on the sole channel"
  - "`run_state.read_progress(execution_status=)` — settlement from the execution's own status"
  - "`preingest.partition_for_ingest` — the ONE per-row verdict shared by preview and dispatch"
  - "`remediate_veto_companies.post_webhook_event(..., run_id=)` returning a handle, not a Response"
  - "`report_enrichment.build_row_reports` (renamed from `build_sync_report`)"
affects:
  - "every enrichment/ingest/match send in the plugin"
  - "the four surviving repo webhook drivers"
  - "`enrich-records`, `contact-upload`, `enrich-before-ingest` SKILL.md runbooks"

actuals:
  tokens: 118000
  tasks: 3
  commits: 5
plan_head_before: 5fb7e54b156378a6473d57a412b552c8b692bbea

tech-stack:
  added: []
  patterns:
    - "one result channel: rows are recovered from the settled execution, correlated on the client-minted `run_id`, never read from the HTTP body"
    - "caller discipline over a widened callee: the ledger gate is at the append's call site, not a new outcome taught to `append_chunk`"
    - "one verdict, shared function: the preview's send count IS the dispatch sendable count because both call the same function"
    - "refuse before the spend: a missing capability key is a table entry, not a post-hoc diagnosis"

key-files:
  created: []
  modified:
    - operator-claude-plugin/scripts/watch.py
    - operator-claude-plugin/scripts/chunking.py
    - operator-claude-plugin/scripts/report.py
    - operator-claude-plugin/scripts/report_enrichment.py
    - operator-claude-plugin/scripts/run_state.py
    - operator-claude-plugin/scripts/preingest.py
    - operator-claude-plugin/scripts/scheduled_arm.py
    - operator-claude-plugin/scripts/config_gate.py
    - operator-claude-plugin/skills/enrich-records/SKILL.md
    - operator-claude-plugin/skills/contact-upload/SKILL.md
    - operator-claude-plugin/skills/enrich-before-ingest/SKILL.md
    - operator-claude-plugin/tests/conftest.py
    - operator-claude-plugin/tests/test_watch_settle_reporting.py
    - operator-claude-plugin/tests/test_chunking.py
    - operator-claude-plugin/tests/test_run_report.py
    - operator-claude-plugin/tests/test_written_records.py
    - operator-claude-plugin/tests/test_preingest_preview.py
    - operator-claude-plugin/tests/test_preingest_merge.py
    - operator-claude-plugin/tests/test_preingest_match.py
    - operator-claude-plugin/tests/test_report_sufficiency.py
    - operator-claude-plugin/tests/test_report_enrichment.py
    - operator-claude-plugin/tests/test_scheduled_arm.py
    - operator-claude-plugin/tests/test_skill_sequence_coverage.py
    - operator-claude-plugin/tests/test_write_grant.py
    - operator-claude-plugin/tests/test_enrich_skill_contract.py
    - operator-claude-plugin/tests/test_init_check.py
    - operator-claude-plugin/tests/test_status_unknown.py
    - operator-claude-plugin/tests/test_control_pipeline.py
    - scripts/remediate_veto_companies.py
    - scripts/enrich_coverage_companies.py
    - scripts/fix_sfv_region.py
    - scripts/probe_company_propose_mode.py
    - scripts/prove_async_recovery.py
    - scripts/prove_zoominfo_balance.py
    - scripts/bounce_n8n_workflows.py
    - tests/test_enrich_coverage_companies.py
    - tests/test_fix_sfv_region.py
  deleted:
    - scripts/probe_n8n_async_semantics.py
    - scripts/prove_scale_up_runtime.py
    - tests/test_probe_n8n_async_semantics.py

key-decisions:
  - "`report.sync_response_is_sufficient` DELETED, not repurposed — its whole job was choosing between the body and the executions API, and there is no choice left."
  - "`report_enrichment.build_sync_report` RENAMED to `build_row_reports` — the rename IS the migration; the body is unchanged because the recovered rows are byte-identical in shape to what the synchronous body used to carry."
  - "D-70-06: `report.reconcile` is SHARED, not copied — and applied on the INGEST lane only, because its write-node map names the ingest workflow's nodes. A parity test would pin two rules agreeing about the wrong lane."
  - "The ledger gate is caller discipline at `dispatch_and_recover`'s append site; `written_records.append_chunk` is unchanged."
  - "`config_gate.CAPABILITY_KEYS` is the fail-closed mechanism for the executions-API key; `watch.require_executions_api` is that rule's named front door."
  - "`preingest.partition_for_ingest` runs `confidence.assess` FIRST and the email check second, so a no-match row is held for the signal that actually withheld it."

requirements-completed: [D-70-05, D-70-06, D-70-08, D-70-08a, D-70-09, D-70-10, D-70-11]

coverage:
  - deliverable: "Every send in every mode recovers its rows from the settled execution, correlated on `run_id`"
    human_judgment: false
    verification:
      - "`.venv/bin/python -m pytest operator-claude-plugin/tests/ -q` → 2864 passed, 5 skipped — pass"
      - "`test_dispatch_and_recover_completes_without_the_time_proximity_lookup` (write + propose) and `test_the_ingest_mode_completes_a_full_dispatch_and_recover_cycle` drive all three modes with `find_execution_for_dispatch` patched to raise — pass"
      - "`test_dispatch_and_recover_reads_rows_from_rundata_never_from_the_ack` — pass"
  - deliverable: "Scale-up children are recovered on the sole channel"
    human_judgment: false
    verification:
      - "`test_recover_dispatch_folds_in_the_rows_of_a_scale_up_child_execution` — pass"
      - "`test_recover_dispatch_does_not_settle_while_a_scale_up_child_is_still_running` — pass"
  - deliverable: "A missing executions-API key refuses before start; the time-proximity lookup is unreachable"
    human_judgment: false
    verification:
      - "`test_dispatch_plan_refuses_before_any_send_when_the_executions_api_key_is_missing` (transport records zero calls) — pass"
      - "`test_no_surviving_repo_driver_correlates_an_execution_by_start_time` (AST, a CALL never a mention) — pass"
      - "`test_require_executions_api_refuses_a_config_with_no_key` / `..._never_names_the_key_value` — pass"
  - deliverable: "The ledger records write-capable legs only"
    human_judgment: false
    verification:
      - "`test_a_no_write_leg_never_enters_the_ledger[propose|match|enrich-proposal]` with a recording ledger double — pass"
      - "`test_a_write_leg_still_creates_its_ledger_entry` / `test_the_ingest_leg_still_creates_its_ledger_entry` — pass"
  - deliverable: "The preview's per-row verdict is `confidence.assess`, and its send count equals dispatch's sendable count"
    human_judgment: false
    verification:
      - "`test_the_previews_send_count_is_the_dispatch_sendable_count_itself` — pass"
      - "`test_a_no_match_row_with_a_found_email_renders_held_never_sendable` — pass"
      - "`git diff --stat -- operator-claude-plugin/scripts/confidence.py` → empty — pass"
  - deliverable: "The repo drivers read runData through the one shared poster; the two spent probes are deleted"
    human_judgment: false
    verification:
      - "`.venv/bin/python -m pytest tests/ -q` → 1783 passed, 149 skipped — pass"
      - "`git ls-files -- scripts/probe_n8n_async_semantics.py scripts/prove_scale_up_runtime.py` → empty — pass"
      - "`test_the_shared_poster_returns_a_handle_never_a_response` / `..._mints_a_run_id_and_sends_it_on_the_event` / `..._forwards_a_callers_own_run_id_unchanged` / `test_the_arming_refusal_still_fires_before_the_run_id_is_even_minted` — pass"
  - deliverable: "Exactly one bounded-poll site remains; no n8n change"
    human_judgment: false
    verification:
      - "`test_no_plugin_script_polls_sleeps_or_loops_on_execution_status` (allowlist unchanged at `{watch.py}`) — pass"
      - "`node --test tests/n8n/*.test.mjs` → 1032 pass / 0 fail — pass"
      - "`git status --porcelain -- n8n/` → empty — pass"
---

# Phase 70 Plan 06: One Result Channel on the Client Summary

Every row on the client now comes from the settled execution, correlated on the run's own
client-minted id — one channel, no mode-dependent selection — and the three defects the
two-channel design was hiding are closed.

## Performance

- **Duration:** ~46 minutes
- **Tasks:** 3 of 3
- **Commits:** 5 (measured, `git rev-list --count 5fb7e54..HEAD`)
- **Suites at close:** plugin 2864 passed / 5 skipped; root 1783 passed / 149 skipped; node 1032 pass / 0 fail

## Accomplishments

### Task 1 — runData is the only channel

`chunking.dispatch_and_recover` is the one dispatch-and-recover cycle: it sends through the
existing `dispatch_plan`, then reads every row back through `watch.recover_dispatch` on the
run's own `run_id`. There is no channel selection anywhere — `DispatchOutcome.responses` is
documented as ACKS, and no code path reads it for a row outcome.

It was built as a wrapper rather than inlined into `dispatch_plan` because 61 existing test
call sites drive `dispatch_plan` with a POST double only; inlining would have made every one
of them attempt an executions-API read. The wrapper is also the single place D-70-09's ledger
gate can live, so one function serves both tasks.

`watch.require_executions_api` refuses a keyless config, and `config_gate.CAPABILITY_KEYS`
gained `n8n_api_key` on the `contact-upload`, `enrichment` and `match` rows — the table is the
mechanism (it fires before `dispatch_enrichment`/`dispatch.dispatch` reach the wire), the
function is its named front door.

`watch.child_execution_ids` + `include_children=True` fold a `scale_up` batch's child rows in.
The bug was the settlement condition, not a missing feature: the parent detaches and settles
at once, so `len(settled) >= expected` returned on the parent alone and dropped every fanned
row. A child that has not settled now keeps the whole recovery waiting.

`run_state.read_progress(execution_status=)` gives `Progress.settled` from the execution's own
status. It moves NO row between buckets — the five-bucket assert is untouched — because a
settled execution is evidence the run finished, never evidence any row succeeded (step 9).

Migrated off the body: `preingest.rerequest_unanswered`, `preingest.match_batch` (see Task-3
fixes), `scheduled_arm.run_scheduled_arm_cycle` (now recovering INSIDE the armed window), and
the `enrich-records` / `contact-upload` runbooks. `contact-upload/SKILL.md` no longer instructs
`find_execution_for_dispatch`.

### Task 2 — the ledger records writes only; one verdict on the preview

The ledger append is gated at its call site on the leg's built envelope being write-capable
(`chunking.envelope_can_write` → `ChunkResult.can_write`). Propose, match and enrich-proposal
legs never enter it, so the end-of-run report cannot label a row that was never sent — the
`row-2 … None -> failed` shape observed on run `2bc3617b`.

`preingest.partition_for_ingest(rows, responses)` is the one per-row verdict. The preview
renders it and the dispatch step calls it, so `preview["send_count"]` IS `len(sendable_rows)`
by construction. `confidence.assess` runs first and the email check second, so a no-match row
with a freshly-found email is held for `no_match` — the folded todo's exact shape. `confidence.py`
is byte-identical (`git diff --stat` empty); the email hold carries `hold_code: None` rather
than a new word, so `ALL_HOLD_CODES` stays closed (SAFE-01).

### Task 3 — the repo drivers, through their one shared poster

`build_webhook_event` gained an optional `run_id` (added only when set, like `recompute`/
`domain`/`mode`); `post_webhook_event` mints one when absent, sends it, and returns
`{run_id, ack, status_code}` — a handle, never a `Response` a caller could read a row outcome
off. Its arming refusal is unchanged and re-asserted.

**Disposition of all seven repo scripts:**

| Script | Disposition |
|---|---|
| `remediate_veto_companies.py` | the shared seam — migrated (run_id + handle) |
| `enrich_coverage_companies.py` | migrated; its `finder` (time-proximity) injection deleted |
| `fix_sfv_region.py` | migrated; reads rows via `recoverer` |
| `probe_company_propose_mode.py` | migrated; `observe_execution` lost its own `while` loop and its `finder` |
| `rescore_population.py` | **no change needed** — it makes no webhook POST at all; the only mention of `post_webhook_event` is a comment naming it as the alternative this driver does not use |
| `probe_n8n_async_semantics.py` | **deleted** |
| `prove_scale_up_runtime.py` | **deleted** |

**The recorded findings that make each deleted driver redundant, quoted:**

- `probe_n8n_async_semantics.py` — `61-SPIKE-VERDICT.md` P-13: *"a disarmed live probe on
  2026-08-30 dispatched a child with `waitForSubWorkflow` off (parent `12036` -> child `12037`)
  and, as a control, on (parent `12038` -> child `12039`); in both cases the parent dispatch
  node's own `runData` carried `metadata.subExecution.executionId` naming the child, and the
  child also appeared in the executions list. Detachment costs no correlation."* Raw evidence in
  `61-PREMISE-PROBE-VERDICT.json`; cited as `[observed live]` in CLAUDE.md §13.0.3.
- `prove_scale_up_runtime.py` — `61-SCALE-UP-VERDICT.json`: `"depth_guard_stopped_recursion":
  true`, and CLAUDE.md §13.0.3: *"A self-referencing `Execute Workflow` node publishes, runs, and
  terminates — the in-workflow depth guard stopped recursion, zero grandchildren. `[observed
  live, disarmed]` (`12045` → children `12046`/`12047`)."*

Deleting the drivers loses nothing: both were one-shot semantics probes whose findings are on
record in verdict JSON and cited in CLAUDE.md. `tests/test_probe_n8n_async_semantics.py` (the
offline test of the deleted script's pure half) went with it. Four comment references to the
deleted files were repointed rather than left as rot.

## Task Commits

| Task | Commit | What |
|---|---|---|
| 1 (RED) | `a3761aa` | 10 intentional failures — scale-up children, key refusal, settlement |
| 1 (GREEN) | `ac0d4f2` | runData is the only result channel, in every mode |
| 2 | `40874cd` | the ledger records writes only; the preview's verdict is the gate's |
| 3 | `65fe5f0` | repo drivers read runData through the one shared poster; probes deleted |
| review fixes | `f484092` | partial-batch recovery, the send-path key gate, the match leg, D-70-06 |

## Files Created/Modified

See `key-files` in the frontmatter. Two scripts and one test file deleted.

## Decisions Made

1. **The sufficiency helper was DELETED, not repurposed.** Its whole job was D-01's first leg —
   decide whether the synchronous body could identify rows, and fall through to the executions
   API when it could not. There is no longer a choice to make. Repurposing it as "a sanity check
   on the ack's shape" was considered and rejected: the ack's shape is `Build Ack`'s own contract,
   pinned on the n8n side, and a client-side re-assertion of it is a second copy of a rule with
   one home. A helper that still ASKED the question would keep a second channel alive in the
   reader's mind with no branch left to take.

2. **`build_sync_report` was RENAMED to `build_row_reports`, and the rename is the migration.**
   Its body is unchanged: the rows it is handed today are `Build Response`'s own output items
   recovered from the settled execution, byte-identical in shape to what the synchronous body
   used to carry. Under the old name a caller kept handing it an ack, which reports nothing
   politely — worse than failing.

3. **D-70-06: the enrichment ledger SHARES `report.reconcile` — and applies it on the ingest
   lane only.** `WRITE_NODE_FOR_ACTION` is `{"update": "HubSpot Update", "create": "HubSpot
   Create"}` — the *ingest* workflow's node names. On the enrichment lane those nodes do not
   exist, so reconciling there would downgrade every enrichment write to `not_confirmed` on the
   strength of a node that was never going to be in its runData: a false downgrade written into
   the ledger. A parity test was rejected because it would only pin two rules agreeing about the
   wrong lane. When the enrichment lane's own write-node map is established it belongs as a
   PARAMETER to this same function, never as a second copy.

4. **The ledger gate is caller discipline, not a widened callee.** `written_records.append_chunk`
   is unchanged; restricting who calls it is a smaller and more durable change than teaching it
   an outcome for a leg that writes nothing.

5. **`dispatch_and_recover` is a wrapper, not an inlining of recovery into `dispatch_plan`.**
   61 existing plugin-test call sites drive `dispatch_plan` with a POST double only.

6. **`config_gate.CAPABILITY_KEYS` is the fail-closed mechanism.** The plan asked for the refusal
   to join "the existing fail-closed conditions list rather than inventing a second mechanism";
   the table is that list. `watch.require_executions_api` remains as the named entry the plan
   specified.

## Deviations from Plan

**1. [Rule 1 - Bug] `chunking.plan_chunks` dropped `propose` on the companies branch**
- **Found during:** Task 2, by the enrich-proposal ledger test
- **Issue:** the companies chunk was built as `{"companies": [...]}` with the `propose` key
  discarded, so `enrichment.build_envelope` saw no propose intent and produced a **WRITE-mode**
  envelope. A chunked enrich-proposal request reached the backend as a write, with only the
  write-safety allowlist between it and HubSpot.
- **Fix:** carry `propose` per chunk, only when set (a plain companies plan's chunk shape is
  byte-identical to before).
- **Files modified:** `operator-claude-plugin/scripts/chunking.py`
- **Verification:** `test_a_no_write_leg_never_enters_the_ledger[spec_form2]` — red before, green after
- **Commit:** `40874cd`

**2. [Rule 1 - Bug] `preingest.fetch_matches` still read the ack as the match verdicts**
- **Found during:** review, before declaring Task 1 done
- **Issue:** `fetch_matches` returned `response.json()` and `match_batch` used it as the per-row
  verdicts. Against the ack-only webhook every match row would have read `unmatched` live — and
  these verdicts are `confidence.assess`'s only input, so an `unmatched` here becomes a held row,
  an unenriched person, and an operator told nothing was found.
- **Fix:** `fetch_matches` puts the batch's `run_id` on the envelope and returns the ack;
  `match_batch` recovers the verdicts once from runData. A run that does not settle leaves its
  rows `unchecked` ("we could not look"), never `unmatched`.
- **Files modified:** `operator-claude-plugin/scripts/preingest.py`, `tests/test_preingest_match.py`, `tests/conftest.py`
- **Verification:** `test_preingest_match.py` 45 pass; full plugin suite green
- **Commit:** `f484092`

**3. [Rule 1 - Bug] `dispatch_and_recover` waited for one execution per RESULT**
- **Found during:** review
- **Issue:** a failed chunk produced no execution carrying the run id, so `expected_chunk_count`
  could never be met — the recovery burned the full bound and returned nothing, erasing the rows
  of the chunks that did land.
- **Fix:** count only chunks that reached the backend; skip the wait entirely when none did.
- **Files modified:** `operator-claude-plugin/scripts/chunking.py`
- **Verification:** `test_a_failed_chunk_does_not_erase_the_rows_of_the_chunks_that_landed`, `test_a_run_where_every_chunk_failed_never_waits_on_the_result_channel`
- **Commit:** `f484092`

**4. [Rule 2 - Missing critical] the ingest send path spent before it refused**
- **Found during:** review
- **Issue:** `dispatch.dispatch` → `require_capability("contact-upload")` required only
  `(n8n_url, webhook_secret)`, so a keyless config POSTed and only then failed to read the rows
  back — the diagnosis-after-the-money D-70-10 exists to prevent.
- **Fix:** `n8n_api_key` added to the `contact-upload`, `enrichment` and `match` rows of
  `config_gate.CAPABILITY_KEYS`.
- **Files modified:** `operator-claude-plugin/scripts/config_gate.py` (**outside `files_modified`** —
  Rule 3), `tests/test_init_check.py`, `tests/test_status_unknown.py`, `tests/test_control_pipeline.py`
- **Verification:** full plugin suite green; the three capability tests now assert the true new
  answer (without the key, `review` still works; `contact-upload` does not)
- **Commit:** `f484092`

**5. [Rule 3 - Blocking] SKILL.md edits outside `files_modified`**
- **Found during:** Tasks 1-2
- **Issue:** SKILL.md files are executed instructions. Leaving `sync_response_is_sufficient(body)`,
  `build_sync_report(response)`, `outcome.responses` and `find_execution_for_dispatch()` in them
  would leave dangling calls and a forbidden correlation path in live runbooks.
- **Fix:** `enrich-records`, `contact-upload` and `enrich-before-ingest` migrated to
  `dispatch_and_recover` / `build_row_reports` / `partition_for_ingest`, and the time-proximity
  instruction replaced with an explicit prohibition naming D-70-10.
- **Verification:** `test_enrich_skill_contract.py`, `test_skill_sequence_coverage.py`,
  `test_write_grant.py`'s runbook AST guards — all green
- **Commits:** `ac0d4f2`, `40874cd`

**6. [Rule 3 - Blocking] a 70-03 guard was narrowed**
- **Issue:** `test_dispatch_plan_no_longer_imports_written_records_at_all` asserted the *module*
  holds no reference to `written_records`. The module now legitimately appends RECOVERED rows for
  a write-capable leg, from `dispatch_and_recover` — which IS D-70-09's ledger gate.
- **Fix:** narrowed to an AST scan of `dispatch_plan`'s OWN body, which is the invariant that
  actually matters: `dispatch_plan` sees only the ack and must never write the ledger. Renamed
  `test_dispatch_plan_itself_never_touches_the_ledger`.
- **Commit:** `ac0d4f2`

**7. The acceptance grep for `response.json()` matches one file — by construction, not by defect**
- The AC reads: "`/usr/bin/grep -l 'response.json()' …` prints nothing — no surviving caller reads
  the ack body for a row outcome." It matches `scripts/remediate_veto_companies.py`, which is the
  **poster itself**, parsing the ack INTO the handle it returns. It is not a caller and it reads no
  row outcome; that is the one place the ack is legitimately parsed. The AC's stated property holds
  — the four caller files print nothing. Recorded here rather than dodged by rewriting the parse to
  avoid a string match.

**8. `gsd-tools check tdd-red-evidence` is absent from this runtime's `check` verb list**
- Available subcommands: `api-coverage-verify-pre, auto-mode, decision-coverage-plan, …`. The RED
  evidence is therefore the recorded failure output: 10 failures, every one an `AttributeError`/
  `TypeError` on a symbol not yet written, named in commit `a3761aa`.

**Total deviations:** 8 (3 auto-fixed bugs, 1 missing-critical, 2 blocking, 2 recorded facts).
**Impact on plan:** none to scope. Deviations 2, 3 and 4 are defects this plan's own contract
exposed and would have shipped without; the rest are mechanical consequences of the migration.

## Issues Encountered

- **A constant clock stub hangs the recovery loop, it does not fail it.** `now=lambda: 0.0` makes
  `elapsed` permanently 0, so a recovery that never matches loops forever. Two test runs timed out
  before this was diagnosed. New tests use a `_stepping_clock()` helper; the failure mode is
  documented on it.
- **A large body of existing tests scripts row-shaped payloads on the POST double.** Those tests
  describe what the RUN decided; only the channel changed. Rather than rewrite each, an autouse
  conftest shim routes the same scripted rows through the real `watch.recover_dispatch` entry
  point. It is a TEST HARNESS, not a production fallback — `dispatch_and_recover` and `match_batch`
  have no body-reading branch left to take — and a test that exercises the recovery mechanism
  itself overrides it by passing its own `get_transport`.

## User Setup Required

None. Nothing was deployed, nothing was armed, no live n8n call was made by any task in this plan.

**One operator-visible consequence:** a config without `n8n_api_key` can no longer upload contacts,
enrich, or match. That is deliberate (D-70-10) — a send whose rows can never be read back cannot be
reported on — and the refusal names the key and points at `operator.local.example.json`.

## Next Phase Readiness

Ready for **70-07** (docs). Carried forward:

- **`scripts/prove_async_recovery.py` still reads `sync_outcome.responses` / `async_outcome.responses`
  as rows (L123, L137).** The plan explicitly keeps this script as the D-70-19 proof driver for
  70-07 to adapt — so it was NOT migrated here — but it is the last body-reader in the repo and
  should be 70-07's first job.
- **D-70-08's flagged gap closes by construction.** `run_report.py` reading `written_records.load()`
  is now correct: only write-capable legs enter the ledger, so there is nothing there for it to
  mislabel. No change was needed in `run_report.py`.
- **`DispatchOutcome.written_records_failures` is now permanently empty.** Recover-side bookkeeping
  misses live on `dispatch_and_recover`'s return; `scheduled_arm` reads both and reports the union.
- **`scheduled_arm` now waits up to `watch.DEFAULT_BOUND_SECONDS` INSIDE the armed window, by
  design.** Recovering outside the window would disarm (and bounce) the write-safety gate underneath
  a still-running armed execution. Worth stating in the docs plan.
- **The enrichment lane has no write-node map for `report.reconcile`.** Establishing it is a
  follow-up; the parameterisation point is named in `dispatch_and_recover`'s comment.
- **`70-DEFERRED-GATES.md` unchanged** — this plan ran no live probe and reached no
  `gate="blocking-human"` checkpoint, so no new Gate entry was appended.
- **Gate 1 and Gate 70-05-A remain open** in `70-DEFERRED-GATES.md` for the end-of-phase UAT.

## Self-Check: PASSED

- `key-files.created` is empty; every path in `key-files.modified` verified present with `[ -f ]`,
  and the three `deleted` paths verified absent from `git ls-files`.
- `git log --oneline --all --grep="70-06"` → 5 commits found (`a3761aa`, `ac0d4f2`, `40874cd`,
  `65fe5f0`, `f484092`).
- `commits: 5` is MEASURED via `git rev-list --count 5fb7e54..HEAD`, with `plan_head_before`
  recorded so `/gsd-verify-work` re-measures on the same instrument.
- Acceptance criteria re-run at close: plugin `pytest -q` → 2864 passed / 5 skipped; root
  `pytest -q` → 1783 passed / 149 skipped; `node --test tests/n8n/*.test.mjs` → 1032 pass / 0 fail;
  `git status --porcelain -- n8n/` → empty; `git diff --stat -- …/confidence.py` → empty;
  `git ls-files -- <the two probes>` → empty; the poll-site allowlist is unchanged at `{watch.py}`.

---
*Phase: 70-one-merge-one-result-channel-n8n-runtime-truth*
*Completed: 2026-09-10*
