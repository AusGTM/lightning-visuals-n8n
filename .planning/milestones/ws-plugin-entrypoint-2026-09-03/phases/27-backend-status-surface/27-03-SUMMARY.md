---
phase: 27-backend-status-surface
plan: 03
subsystem: operator-claude-plugin
tags: [plugin, n8n-api, status, credential-boundary, unknown-vs-zero, tracer]

requires:
  - phase: 27
    plan: 01
    provides: "hubspot/backend-status's full-health response shape ({counts, credential_health, checked_at, balances}) — consumed verbatim by render_backend_status()"
  - phase: 26
    plan: 01
    provides: "executions_client.py's read-only n8n API calling convention and conftest's recording GET stub, both mirrored/widened here"
provides:
  - "operator-claude-plugin/scripts/n8n_read.py — list_workflows(), get_workflow(), last_execution(), read_write_safety(); GET-only, degrade-to-None"
  - "operator-claude-plugin/scripts/backend_status.py — fetch_backend_status(); one bodyless POST, degrades to unavailable"
  - "operator-claude-plugin/scripts/status.py — describe_workflow(), status_report(), render()/render_source_health()/render_backend_status()"
  - "config_gate.CAPABILITY_KEYS / require_capability() / usable_capabilities() — per-capability refusal replacing the all-or-nothing gate"
  - "config keys n8n_api_key and stuck_execution_minutes in the committed template"
affects: [27-04 (widens describe_workflow to every workflow and consumes the renderer), 27-05 (dashboard reads the same rendered mapping), 28 (its read-back verification uses n8n_read)]

tech-stack:
  added: []
  patterns:
    - "None means 'could not tell', [] means 'read fine, nothing there' — the two never conflated, mirroring backendStatus.js's extractSearchTotal on the n8n side"
    - "credential split as a code shape: reads the client is entitled to live in n8n_read; credential-gated facts arrive over HTTP from backend_status"
    - "write-safety read by scanning every node and reporting desync, never a fixed node list (D-10)"
    - "per-capability config refusal: a missing key disables one capability, not the plugin"

key-files:
  created:
    - operator-claude-plugin/scripts/n8n_read.py
    - operator-claude-plugin/scripts/backend_status.py
    - operator-claude-plugin/scripts/status.py
    - operator-claude-plugin/tests/test_n8n_read.py
    - operator-claude-plugin/tests/test_status_tracer.py
    - operator-claude-plugin/tests/test_status_unknown.py
  modified:
    - operator-claude-plugin/tests/conftest.py
    - operator-claude-plugin/scripts/config_gate.py
    - operator-claude-plugin/config/operator.local.example.json
    - operator-claude-plugin/tests/test_no_backend_imports.py
    - operator-claude-plugin/tests/test_retry_reuses_dispatch.py
    - .planning/workstreams/plugin-entrypoint/phases/27-backend-status-surface/27-CONTEXT.md
    - .planning/workstreams/plugin-entrypoint/phases/27-backend-status-surface/27-03-PLAN.md

key-decisions:
  - "The plan's instruction to widen the autouse network guard to requests.get was NOT followed — it restated the claim 27-CONTEXT.md D-11 refutes empirically. The guard already blocks GET via the patched Session.request. Added a test asserting that coverage instead; corrected both the plan and D-11 so it cannot be re-litigated."
  - "n8n_read.py reimplements the ~8 lines of base-URL/header/GET plumbing rather than importing sibling executions_client.py: that module's contract is raise-on-failure (right for the report lane, which must not report a fabricated run), and this module's is degrade-to-unknown (right for a status read, which must answer even when a read fails). Sharing the plumbing would have meant sharing the wrong contract."
  - "read_write_safety() returns the extracted literal and node names only — never a line of code and never the workflow body, which is hundreds of KB of backend internals (T-27-11). Asserted at both the extractor and the composition seam."
  - "The status capability requires n8n_url + n8n_api_key but NOT webhook_secret: losing the webhook secret costs only the backend-supplied half, which reports itself unavailable, rather than the whole answer."
  - "STATUS-01 left Pending, not marked Complete. This plan proves the data for ONE workflow end to end; the operator-facing plain-language answer across every workflow is 27-04's deliverable. Marking it here would overclaim."

requirements-completed: []

coverage:
  - id: D1
    description: "For one workflow, on-or-off, live-write state, and last-run outcome are all read from the n8n API rather than asserted from local config (D-03, STATUS-01)"
    requirement: STATUS-01
    verification:
      - kind: unit
        ref: "tests/test_status_tracer.py::test_describe_workflow_composes_on_off_write_safety_and_last_run, ::test_describe_workflow_reads_state_from_the_api_not_from_local_config"
        status: pass
    human_judgment: false
  - id: D2
    description: "The two calls carry different secrets and never each other's; every URL touched lives under the configured n8n base, so the plugin constructs no provider request of any kind (D-01, D-02, T-27-13, STATUS-03)"
    requirement: STATUS-03
    verification:
      - kind: unit
        ref: "tests/test_status_tracer.py::test_the_two_calls_carry_different_secrets_and_never_each_others, ::test_the_plugin_constructs_no_provider_request_of_any_kind"
        status: pass
      - kind: command
        ref: "grep -rEc 'api\\.(lusha|apollo|zoominfo)\\.com|api\\.hubapi\\.com' operator-claude-plugin/scripts/ | grep -v ':0$' | wc -l -> 0"
        status: pass
    human_judgment: false
  - id: D3
    description: "A value the backend could not supply renders as the word unknown — never 0, never blank, never healthy; a genuine 0 and a False survive intact (D-08, STATUS-06)"
    requirement: STATUS-06
    verification:
      - kind: unit
        ref: "tests/test_status_unknown.py (11 renderer cases incl. all-null mapping asserted to contain no standalone zero, and a refused source asserted to carry no healthy-sounding word)"
        status: pass
    human_judgment: false
  - id: D4
    description: "Write-safety is read from the fetched workflow by scanning every node; disagreement between declaring nodes reports unknown plus the desync rather than a guess (D-10)"
    requirement: STATUS-01
    verification:
      - kind: unit
        ref: "tests/test_n8n_read.py::test_read_write_safety_reports_disagreement_rather_than_picking_a_value, ::test_read_write_safety_finds_the_constant_however_many_nodes_declare_it"
        status: pass
      - kind: unit
        ref: "tests/test_n8n_read.py::test_committed_cloud_workflows_read_as_a_single_consistent_value — the extractor run against the artifacts that actually ship, with a non-vacuity guard"
        status: pass
    human_judgment: false
  - id: D5
    description: "Never-run, unreadable, and in-flight are three distinct answers; a response carrying only `finished` still derives a status rather than raising"
    requirement: STATUS-01
    verification:
      - kind: unit
        ref: "tests/test_n8n_read.py::test_last_execution_reports_never_run_distinctly_from_unreadable, ::test_last_execution_derives_a_status_from_finished_when_status_is_absent, ::test_last_execution_marks_a_running_execution_in_flight"
        status: pass
    human_judgment: false
  - id: D6
    description: "A missing n8n_api_key refuses the status capability in plain language, names the key and the example file, states what still works, and leaks no configured value (PLUGIN-03, T-27-12)"
    requirement: STATUS-01
    verification:
      - kind: unit
        ref: "tests/test_status_unknown.py::test_status_capability_refuses_when_the_api_key_is_absent, ::test_that_refusal_points_at_the_example_file_and_says_what_still_works, ::test_no_capability_refusal_ever_contains_a_configured_value, ::test_the_status_read_refuses_before_any_transport_is_constructed"
        status: pass
    human_judgment: false
  - id: D7
    description: "No plugin test can reach the network, including through a GET; a dead status endpoint degrades rather than raising (T-27-14, T-27-15)"
    requirement: STATUS-06
    verification:
      - kind: unit
        ref: "tests/test_n8n_read.py::test_requests_get_raises_inside_a_test; tests/test_status_tracer.py::test_fetch_backend_status_degrades_rather_than_raising"
        status: pass
    human_judgment: false
  - id: D8
    description: "No mutating verb is reachable from the read client at all (T-27-10)"
    requirement: STATUS-01
    verification:
      - kind: unit
        ref: "tests/test_status_tracer.py::test_n8n_read_exposes_no_mutating_verb (name scan + source scan for requests.post/put/patch/delete)"
        status: pass
    human_judgment: false

duration: 58min
completed: 2026-07-31
status: complete
---

# Phase 27 Plan 03: Backend status tracer — the credential split, proven Summary

**One question — "what is workflow X doing?" — wired end to end through the config gate, a GET-only n8n Public API client, the credential-boundary POST to the n8n-side status endpoint, and a renderer where anything the backend could not supply reads as the word unknown; no byte left the machine.**

## Performance

- **Duration:** ~58 min
- **Completed:** 2026-07-31
- **Tasks:** 2 completed (Task 1 the tracer, Task 2 the unknown/refusal pass)
- **Files modified:** 13 (6 created, 7 modified — 2 of them planning docs)

## Accomplishments

- **The credential split is proven as a code shape, not asserted.** `n8n_read.py` reads workflow
  and execution state with `X-N8N-API-KEY`; `backend_status.py` asks the n8n-side endpoint with
  `X-Enrichment-Secret` for the facts the plugin holds no credential for. A test asserts each call
  carries exactly one header and never the other's, and that every URL touched lives under the
  configured n8n base — so the plugin constructs no provider request of any kind (D-01).
- **`n8n_read.py` is GET-only by construction.** No activate, deactivate, PUT, PATCH or DELETE path
  exists in the module, verified by both a name scan and a source scan (T-27-10). Every read
  degrades to `None` rather than raising: `None` is "could not tell", `[]` / `never_run` is "read
  fine, nothing there", and no test lets the two be conflated.
- **Write-safety is read out of the deployed workflow, never from local belief (D-03).**
  `read_write_safety()` scans every node using the exact pattern `enable_baked_flags()` uses for its
  own fail-closed rescan, and on a desync between declaring nodes returns unknown **plus** the
  disagreeing node names rather than picking a value. A contract test runs the extractor over the
  committed cloud workflow JSONs — which is also now a standing assertion that every committed
  workflow ships disarmed.
- **Unknown reads as unknown everywhere.** `render()` turns null, absent and blank into the word
  unknown while a genuine `0` stays `0` and `False` stays `off`; `render_backend_status()` routes
  every backend-supplied datum through it at the point of composition, so no later renderer can
  bypass it. Apollo's by-design 403 therefore reads "unknown", never "0 credits" (Pitfall 4).
- **A half-configured plugin says what still works.** `config_gate.CAPABILITY_KEYS` replaces the
  all-or-nothing gate: a missing `n8n_api_key` refuses the status check by name, points at the
  example file, and states that contact upload still works — never a value in the message.

## Task Commits

1. **Task 1 (tracer) — RED:** `843db12` (test) — widened conftest stubs + the two test files
2. **Task 1 (tracer) — GREEN:** `52fed80` (feat) — the three modules + two Rule 3 guard fixes
3. **Task 2 — RED:** `4f0b9e9` (test) — unknown-vs-zero and per-capability refusal
4. **Task 2 — GREEN:** `6b413bf` (feat) — renderer, capability gate, example-config keys

## Test Counts

| Suite | Before | After | Delta |
|---|---|---|---|
| pytest (repo, `.venv/bin/python -m pytest -q`) | 919 passed, 1 skipped | 992 passed, 1 skipped | +73 |
| pytest (plugin only) | 156 passed | 229 passed | +73 |
| node (`node --test tests/n8n/*.test.mjs`) | 400 passed, 0 fail | 400 passed, 0 fail | 0 |

The +73 is entirely this plan's three new test files (36 + 37). The 919/156 baselines were taken
with sibling 27-02's two in-flight test files excluded — they failed collection mid-flight because
`error_table.py` was not yet committed; 27-02 has since landed and its tests are included in the
992/229 figures above (their 18 are counted in neither delta column, since the baseline predates
their commit — the honest reading is: this plan added 73, the sibling added the rest).

## Decisions Made

- **Did not widen the network guard.** See Deviations — the plan's instruction restated a claim
  CONTEXT already refutes.
- **Did not import `executions_client.py`'s plumbing.** Its contract is raise-on-failure, correct
  for the report lane where a fabricated run would be worse than an error. A status read has the
  opposite obligation: answer even when a read fails. Sharing ~8 lines of header/URL construction
  would have meant sharing the wrong failure contract, so `n8n_read.py` reimplements it and the
  docstring says why.
- **Left `STATUS-01` Pending in REQUIREMENTS.md.** This plan proves the data end to end for one
  workflow; STATUS-01's "one plain-language answer, per workflow" across every workflow is 27-04.
  (`STATUS-02/03/06` were already marked Complete by 27-01 and 27-02; nothing needed changing, so
  REQUIREMENTS.md was not touched — one less shared-file collision with the concurrent sibling.)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Refuted premise] The plan's instruction to widen the autouse network guard to `requests.get` was not followed**
- **Found during:** Task 1, first action.
- **Issue:** `27-03-PLAN.md`'s `key_links` and Task 1 `<action>` both asserted the guard "patches
  post/request/Session.request but NOT `requests.get`", and directed adding the GET entry point.
  This is the claim `27-CONTEXT.md` D-11 refutes empirically, and that HANDOFF §5 flags as
  verified-not-a-hole: `requests.get` delegates to `requests.api.request`, which opens a `Session`
  and calls the patched `Session.request`. Acting on the instruction would have implied a hole that
  does not exist and marked an already-sound guard as previously broken.
- **Fix:** Left the guard untouched. Added
  `tests/test_n8n_read.py::test_requests_get_raises_inside_a_test`, which fails loudly if the
  coverage ever regresses. What *did* need widening was the GET **stub**, which carried a JSON body
  only and could not express a non-2xx / dead transport / unparseable body — the three shapes a
  degrade-to-unknown read must be driven through.
- **Folded back into:** `27-CONTEXT.md` D-11 (now records the execution-time re-verification and
  names the test) and `27-03-PLAN.md` (both the `key_links` line and the Task 1 action paragraph
  corrected in place, original text quoted so the correction is legible).
- **Commit:** `843db12`

**2. [Rule 3 - Blocking] `test_no_backend_imports.py`'s `LOCAL_MODULES` was a hand-maintained list that every new plugin module trips**
- **Found during:** Task 1, running the plugin suite after adding the three modules.
- **Issue:** `test_every_third_party_import_is_declared_in_requirements_txt` failed on
  `{n8n_read, backend_status}` — flat local imports mistaken for undeclared third-party packages.
  The list had already drifted (it named neither `executions_client` nor `report_enrichment`), so
  the same wall waits for 27-04, 27-05 and every Phase 28 module.
- **Fix:** Root cause rather than another entry: `LOCAL_MODULES` is now derived from
  `scripts/*.py`. A module is local exactly when a file of that name exists there, so the guard
  cannot fail a plan for the wrong reason again. The guard's actual invariant (no undeclared
  third-party import) is unweakened.
- **Files modified:** `operator-claude-plugin/tests/test_no_backend_imports.py`
- **Commit:** `52fed80`

**3. [Rule 3 - Blocking] `test_retry_reuses_dispatch.py`'s send-shape guard flagged the status POST as a second dispatch path**
- **Found during:** Task 1, same run.
- **Issue:** `test_exactly_one_module_defines_the_send_shaped_function` asserts `dispatch()` is the
  only function with a `transport=requests.post` default, so that no retry path can bypass the
  arming gate. `fetch_backend_status()` has that shape — but only because the n8n webhook answering
  it is a POST endpoint. Its chain contains no write node
  (`tests/test_backend_status_wiring.py::test_endpoint_chain_contains_no_write_node`, 27-01) and the
  request carries no records at all.
- **Fix:** Allowlisted narrowly, with the reasoning in a comment, **plus** a new test keeping the
  allowlist from becoming a rubber stamp: `backend_status.py` may not pass `files=` or `data=`. The
  day it carries a payload it stops being exempt and the suite says so.
- **Files modified:** `operator-claude-plugin/tests/test_retry_reuses_dispatch.py`
- **Commit:** `52fed80`

**4. [Rule 1 - Test bug] An assertion was true for the wrong reason**
- **Found during:** Task 2, first green run.
- **Issue:** `test_an_all_null_backend_renders_with_no_zero_standing_in_for_a_missing_count`
  asserted `"0" not in json.dumps(rendered)` and failed — on the `—` escape of an em dash,
  which contains a literal `0`. Nothing was wrong with the renderer.
- **Fix:** `json.dumps(..., ensure_ascii=False)`, with a comment naming the trap. The assertion
  keeps its full strength over the actual values.
- **Commit:** `6b413bf`

**Total deviations:** 4 — one refuted-premise correction folded back into CONTEXT and the plan, two
pre-existing guards adapted (one root-caused, one narrowed and re-hardened), one test bug.

## Interfaces 27-04 Inherits

- `status.describe_workflow(config, workflow_id, transport=requests.get) -> dict` — takes ONE
  workflow, returns ONE mapping `{workflow_id, name, active, write_safety, last_run, in_flight}`.
  Widening to every workflow is `for wf in n8n_read.list_workflows(cfg): describe_workflow(...)`, a
  loop, not a rewrite. `list_workflows()` returns `None` when unreadable and `[]` when there are
  genuinely none — do not `or []` that distinction away.
- `n8n_read.last_execution(...) -> {status, started_at, stopped_at, never_run, in_flight, error}` —
  `started_at` is the raw ISO string from the API, which is what 27-04's stuck-execution threshold
  needs; `stuck_execution_minutes` is already in the committed config template (default 15).
- `n8n_read.read_write_safety(body, flag) -> {value, nodes, disagreement}` — `value` is the string
  `"true"`/`"false"` or `None`; `disagreement` is a list of `{node, value}` when declaring nodes
  desync. `status.WRITE_SAFETY_FLAGS` names both flags.
- `status.render()`, `render_source_health()`, `render_backend_status()` — the unknown discipline
  lives here. Route new backend-supplied data through `render()` at composition, not at print time.
- `config_gate.require_capability(cfg, "status")` before constructing any transport;
  `usable_capabilities(cfg)` for the "what still works" sentence. Add a new capability by adding a
  row to `CAPABILITY_KEYS` — do not re-add a global gate.
- `backend_status.fetch_backend_status(cfg) -> {available, reason, data}` — `data` is 27-01's body
  verbatim: `{counts{4 keys}, credential_health[{source,state,status,reason}], checked_at,
  balances[{provider,configured,credits,unreadable,error,status}]}`.

## Issues Encountered

- **Concurrency with sibling 27-02:** the git index is shared across agents in one working tree. A
  set of staged files was silently unstaged mid-plan by the sibling's own `git add`/commit cycle.
  Nothing was lost (the files were untracked on disk), but every commit from that point staged and
  committed in a single shell invocation to shrink the race window. Worth telling future concurrent
  executors: **verify `git diff --cached --name-only` immediately before committing, not earlier.**
- The repo's `git` wrapper mangles a `$(cat <<'EOF' ...)` commit message; `git commit -F <file>`
  works. Not a code issue.

## User Setup Required

Operators who already have `config/operator.local.json` must add two keys — the template
(`config/operator.local.example.json`) now documents both:
- `n8n_api_key` — from n8n Settings > n8n API. **A different secret from `webhook_secret`**; they
  travel on different headers to the same base URL, so crossing them yields a 401 that looks like a
  configuration problem.
- `stuck_execution_minutes` — default `15`, consumed by 27-04.

Without `n8n_api_key` the plugin refuses only the status check, by name, and says contact upload
still works. Nothing was deployed, activated or armed by this plan; no live HTTP call was made by
any verification.

## Next Phase Readiness

- 27-04 can widen to every workflow, add stuck detection and per-node error harvesting against the
  interfaces above without touching `n8n_read.py`'s shape.
- 27-05's dashboard consumes `status_report()`'s rendered mapping directly.
- No blocker. `grep -c 'ALLOW_HUBSPOT_[A-Z_]* = "true"' n8n/*.json` → 0 everywhere (this plan
  touched no `n8n/` file at all).

---
*Phase: 27-backend-status-surface*
*Completed: 2026-07-31*

## Self-Check: PASSED

All six created source/test files exist on disk; all four task commit hashes
(`843db12`, `52fed80`, `4f0b9e9`, `6b413bf`) verified present in `git log`.
