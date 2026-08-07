---
phase: 41-validation-data-import-end-to-end-proof
plan: 02
subsystem: crm-automation
tags: [hubspot, pre-flight, parity-harness, write-safety, pytest, dry-run]
status: complete

requires:
  - phase: 40-scoring-engine-remediation-notes/40-02
    provides: tests/scoring_fixtures.py (FIT_SCORE_PROPS, fetch_for_parity/expected_for)
      and scripts/run_scoring_parity.py's build_report()/false-green guard, extended
      here rather than forked
  - phase: 41-validation-data-import-end-to-end-proof/41-01
    provides: config/june_candidates.json (`rows` keyed by June HubSpot id,
      `_meta.source_sha256`) and config/june_candidates_source.json (the June-era
      `name`/`sources` snapshot) -- consumed by the resolver at runtime, not by any
      test in this plan
provides:
  - scripts/resolve_june_ids.py -- read-only pre-flight resolver: GET each June id,
    re-match a 404 by domain (derived from the candidate row's evidence URLs) then by
    name, record outcome live/rematched/ambiguous/unmatched, refuse before any network
    call without credentials or against the wrong portal
  - _provenance_check()/_require_provenance() in scripts/run_scoring_parity.py --
    presence/valid-JSON/fields/sources assertion on the lv_enrichment_provenance blob,
    recorded on every comparison, a real_finding only under
    PARITY_REQUIRE_PROVENANCE=true
  - scripts/june_run_arm.py -- two independent operator commands (arm/--disarm)
    implementing D-06's whole-run arming style directly against
    n8n_arming.arm_for_dispatch()/disarm(), never through the paired armed_window
    context manager
affects: [41-03-deploy-and-canary, 41-04-full-run-and-parity-proof]

actuals:
  tokens: 5400
  tasks: 3
  commits: 3

tech-stack:
  added: []
  patterns:
    - "resolve_june_ids.py's build_report() takes plain dicts (rows, source_snapshot,
      meta), not file paths -- offline-testable with zero filesystem/network reachable
      when rows is empty, same split main()/build_report() shape
      scripts/run_scoring_parity.py already established"
    - "Domain-first re-match derives a candidate domain from the June row's per-field
      _evidence URLs (urlparse().netloc) rather than requiring an explicit domain field
      -- the June source snapshot carries none at all"
    - "Provenance is recorded unconditionally on every parity comparison but only
      promoted to a real_finding under an explicit env flag -- the same
      recorded-vs-enforced split PARITY_REQUIRE_PROVENANCE establishes keeps the
      standing unattended sweep's default behavior byte-identical"
    - "june_run_arm.py imports operator-claude-plugin/scripts modules (n8n_arming,
      config_gate, executions_client) directly via a sys.path insert, since PLUGIN-04's
      import boundary is one-directional (plugin -> backend forbidden by
      test_no_backend_imports.py; backend -> plugin is not scanned)"

key-files:
  created:
    - scripts/resolve_june_ids.py
    - tests/test_resolve_june_ids.py
    - scripts/june_run_arm.py
    - tests/test_june_run_arm.py
  modified:
    - scripts/run_scoring_parity.py
    - tests/scoring_fixtures.py
    - tests/test_scoring_parity.py

key-decisions:
  - "Domain for the D-09 re-match is derived from the candidate row's per-field
    _evidence URLs (the first parseable netloc, www.-stripped), not from an explicit
    domain field -- config/june_candidates_source.json carries no domain at all, only
    evidence URLs per output field. A row with no evidence URL simply skips the
    domain-first search and goes straight to the name search."
  - "The top-level `unmatched` list in the resolution report includes BOTH ambiguous
    and true-unmatched ids (anything not resolved), while each record's own `outcome`
    field keeps the finer-grained distinction (ambiguous vs unmatched) -- satisfies
    T-41-10's 'both are distinct recorded outcomes' without conflating the report's
    two levels of detail."
  - "_provenance_check()'s real_finding append is additive, not a mutation of the
    record's existing classification: a shallow copy of the comparison record with
    classification overridden to provenance_missing is appended to real_findings
    separately from any score/tier/flag mismatch classification already on the same
    record -- a record can in principle appear in real_findings twice (once per
    reason), by design, never silently overwritten."
  - "june_run_arm.py's arm()/disarm() wrap n8n_arming.ArmingRefused/DisarmFailed in
    try/except and return the library's own outcome payload rather than letting the
    exception propagate to an uncaught traceback -- Rule 2 (missing error handling):
    the plan's <action> text only explicitly required catching DisarmFailed, but a raised
    ArmingRefused reaching main() uncaught would print a Python traceback instead of the
    same clean refused/failed JSON shape every other path returns, which is a correctness
    gap on the exact command an operator runs live."
  - "The ALLOW_N8N_ARM kill switch is never pre-checked in the wrapper (per the plan's
    explicit instruction) -- arm() always calls the real n8n_arming.arm_for_dispatch(),
    whose own _arm_gate() is the single source of truth and returns a refusal before
    touching any transport. Proven by a test that lets the real (unmocked) arm_for_dispatch
    run and patches requests.get/requests.post to fail the test if either is ever called."

patterns-established:
  - "A repo-root script directly importing operator-claude-plugin/scripts modules via a
    sys.path insert is a sanctioned pattern for backend-side orchestration tooling that
    needs the plugin's write-safety library -- PLUGIN-04's guard
    (test_no_backend_imports.py) only scans files under operator-claude-plugin/ for
    imports of src/scripts, so this direction was never forbidden, just previously
    unused."

interfaces:
  produced:
    - symbol: resolve_june_ids.build_report(rows, source_snapshot, meta)
      kind: function
      signature: "(dict, dict, dict) -> tuple[dict, int]"
      description: "Pure resolution core -- one entry per June id with outcome/
        resolved_id/domain/annualrevenue_present/numberofemployees_present, plus
        resolved_ids/unmatched/verdict at the report's top level. Empty rows -> exit 1
        with a verdict containing 'zero' and 'examined' (false-green guard, D-13-style)."
    - symbol: run_scoring_parity._provenance_check(props)
      kind: function
      signature: "(dict) -> dict"
      description: "{present, valid_json, fields, sources} for the
        lv_enrichment_provenance blob on one company's fetched properties."
    - symbol: PARITY_REQUIRE_PROVENANCE
      kind: env-var
      signature: "exact-'true' semantics, same as every other kill switch in this repo"
      description: "When true, a comparison record with missing/unparseable provenance
        becomes a real_finding (classification provenance_missing) and the sweep exits
        non-zero. Unset (the standing sweep's default): recorded, never enforced."
    - symbol: june_run_arm.arm(ids_csv, workflow_name=DEFAULT_WORKFLOW_NAME)
      kind: function
      signature: "(str, str) -> dict"
      description: "Resolves the workflow id by name, refuses on an empty --ids or an
        unresolvable name, otherwise calls n8n_arming.arm_for_dispatch() with
        record_domains=[] and allow_create=False. Never calls disarm() or
        armed_window."
    - symbol: june_run_arm.disarm(workflow_name=DEFAULT_WORKFLOW_NAME)
      kind: function
      signature: "(str) -> dict"
      description: "Resolves the workflow id by name, calls n8n_arming.disarm(),
        never gated on ALLOW_N8N_ARM. Catches n8n_arming.DisarmFailed and returns its
        outcome payload rather than letting the exception surface as a bare
        traceback."
  consumed:
    - symbol: src.hubspot_client.get_record / search_records
      source: src/hubspot_client.py (Phase 4/MVP)
      description: "The only two HubSpot client primitives resolve_june_ids.py imports
        -- no write primitive is imported anywhere in the file (grep-enforced)."
    - symbol: n8n_arming.arm_for_dispatch / disarm / ArmingRefused / DisarmFailed
      source: operator-claude-plugin/scripts/n8n_arming.py (Phase 28-03)
      description: "june_run_arm.py's entire safety model -- the ALLOW_N8N_ARM gate,
        allowlist charset validation, and fail-closed re-scan all live here, called
        directly rather than duplicated."
    - symbol: config_gate.load_config / executions_client.resolve_workflow_id
      source: operator-claude-plugin/scripts/ (Phase 27/26)
      description: "Local config load and workflow-name-to-id resolution, imported via
        a sys.path insert onto operator-claude-plugin/scripts."

operator-commands:
  resolver: |
    .venv/bin/python -c \
        "from dotenv import load_dotenv; load_dotenv(); import runpy; \
         runpy.run_path('scripts/resolve_june_ids.py', run_name='__main__')"
  arm: |
    ALLOW_N8N_ARM=true .venv/bin/python scripts/june_run_arm.py --ids <comma-separated resolved ids>
  disarm: |
    .venv/bin/python scripts/june_run_arm.py --disarm
  provenance-enforcing-parity-sweep: |
    PARITY_SAMPLE_IDS=<comma-separated ids> \
    PARITY_REQUIRE_PROVENANCE=true \
    PARITY_REPORT_DIR=.planning/phases/41-validation-data-import-end-to-end-proof/ \
    .venv/bin/python -c \
        "from dotenv import load_dotenv; load_dotenv(); import runpy; \
         runpy.run_path('scripts/run_scoring_parity.py', run_name='__main__')"

metrics:
  duration: ~45m
  completed: 2026-08-07
  tasks_completed: 3
  files_created: 4
  files_modified: 3
  commits: 3
---

# Phase 41 Plan 02: Instrumentation for the June-population run Summary

Built the three pieces of live-run instrumentation Plan 03/04 need and did not have
before this plan: a read-only pre-flight resolver that turns the 66 five-week-old June
HubSpot ids into a verified write allowlist (with domain/name re-match and an ambiguous/
unmatched distinction, not a silent drop), an automated `lv_enrichment_provenance`
presence/shape assertion added to the existing Phase 40 parity harness (opt-in via
`PARITY_REQUIRE_PROVENANCE=true`, standing-sweep behavior unchanged by default), and a
tested pair of unpaired `arm`/`--disarm` commands implementing D-06's whole-run arming
style on top of `n8n_arming`'s existing library functions.

Nothing in this plan touched the portal, n8n, or Anthropic. Every one of the 29 new
offline tests (10 + 7 + 12 across the three tasks) stubs its transport (`src.hubspot_client.requests` for the resolver,
monkeypatched `n8n_arming`/`config_gate`/`executions_client` for the arm/disarm wrapper,
a stubbed `fetch_fn` for the parity harness extension). All three scripts are commands
Plan 03 and Plan 04 will hand to the operator verbatim, not run themselves.

## What Was Built

### Task 1: Pre-flight id resolver (`scripts/resolve_june_ids.py`)

Reads `config/june_candidates.json`'s `rows` (66 June-era HubSpot company ids, built by
41-01), GETs each one, and classifies it into exactly one of four outcomes:

- `live` — the id still resolves; current `name`/`domain`/firmographic-presence flags
  recorded.
- `rematched` — a 404 followed by a domain search (candidate domain derived from the
  row's `_evidence` URLs, since the June source snapshot carries no explicit domain
  field) or, failing that, a name search (from `config/june_candidates_source.json`'s
  committed snapshot) returning exactly one hit.
- `ambiguous` — a domain or name search returning two or more results; the re-match
  stops immediately rather than guessing, and the id is excluded from the resolved list
  but still recorded with its own outcome.
- `unmatched` — nothing resolves and no search hits (including a non-404 GET error,
  recorded with the error text rather than raised).

Refuses before any network call without `HUBSPOT_PRIVATE_APP_TOKEN` or against any
portal other than the hard-coded `22617666` — no env override, same discipline as
`scripts/run_scoring_parity.py`. An empty input table (or every id failing to resolve)
is a false-green-guarded failure: the verdict string contains both `zero` and
`examined`, exit code 1. The script is read-only by construction — `grep -c
'patch_record\|create_record\|delete_record\|batch_update_companies'
scripts/resolve_june_ids.py` returns 0 — and writes
`.planning/phases/41-validation-data-import-end-to-end-proof/41-id-resolution.json`,
printing the comma-joined resolved id list on the final stdout line for Plan 03 to paste
into the arm command.

10 offline tests cover all four outcomes, the credential/portal refusal gates (with a
proof that zero transport calls happen), the empty-table false-green guard, and a
non-404 error path.

### Task 2: Automated provenance assertion (`scripts/run_scoring_parity.py`,
`tests/scoring_fixtures.py`)

`FIT_SCORE_PROPS` gained five properties, appended (not inserted — the first fifteen
entries are byte-identical): `lv_enrichment_provenance`, `lv_org_type_verified_at`,
`lv_produces_content_verified_at`, `lv_enrichment_needs_review`,
`lv_enrichment_review_reason`. This is the live cloud-pipeline provenance shape (one
JSON blob keyed by field, each entry carrying `source`/`confidence`/`verified_at`/
`validation_status`/`value` — `n8n/code/mergeCompanies.js`'s documented model), not the
per-field `*_source`/`*_confidence` properties CLAUDE.md's superseded local-MVP design
describes.

`_provenance_check(props)` parses the blob and returns `{present, valid_json, fields,
sources}` — `fields` is the sorted key list, `sources` the distinct `source` values
across entries. `build_report`'s per-record loop now attaches `provenance`,
`needs_review`, and `review_reason` to every comparison record unconditionally. A new
`_require_provenance()` reads `PARITY_REQUIRE_PROVENANCE` with the repo's standard
exact-`'true'` semantics; when set, a record whose provenance is absent, empty, or not
valid JSON gets a *second*, additive entry appended to `real_findings` with
`classification: "provenance_missing"` — never overwriting a score/tier/flag mismatch
classification that record might already carry from the pre-existing comparison logic.
The standing unattended sweep, which runs over records this phase never touches and
which legitimately have no provenance, is unaffected by default: `PARITY_REQUIRE_
PROVENANCE` unset means missing provenance is recorded but never a `real_finding`.

7 new offline tests in `test_scoring_parity.py`'s new provenance section (including the
`FIT_SCORE_PROPS` shape assertion) cover: absence unenforced/enforced, valid-JSON
field/source extraction, unparseable-JSON enforcement, `needs_review`/`review_reason`
copy-through, and the empty-sample guard still firing with the flag on.

### Task 3: Unpaired whole-run arm and disarm (`scripts/june_run_arm.py`)

`scripts/june_run_arm.py --ids <csv>` resolves the workflow id for `LV Enrichment
(Cloud template)` (overridable via `--workflow-name`) and calls
`n8n_arming.arm_for_dispatch(workflow_id, record_ids=<ids>, record_domains=[],
allow_create=False, config=cfg)` directly — never through `armed_window`
(`grep -c 'armed_window' scripts/june_run_arm.py` returns 0) and never followed by a
call to `disarm`. `scripts/june_run_arm.py --disarm` calls `n8n_arming.disarm()` on the
same resolved workflow id and is deliberately never gated on `ALLOW_N8N_ARM` — an
operator must always be able to close the window.

The wrapper adds exactly the two refusals the library cannot make on its own: an empty
`--ids` (an empty allowlist denies every write and would otherwise look like a
successful arm) and an unresolvable workflow name. Every other safety property — the
`ALLOW_N8N_ARM` kill switch, the allowlist charset validation, the fail-closed re-scan —
stays inside `n8n_arming`, called, never duplicated: a test proves that with
`ALLOW_N8N_ARM` absent, the *real* (unmocked) `arm_for_dispatch` runs and its own
`_arm_gate()` refuses before touching `requests.get`/`requests.post`, which are patched
to fail the test if either is ever called. `ArmingRefused` and `DisarmFailed` are both
caught and converted into the same JSON outcome shape a clean refusal already returns,
so a partially-applied state on a live workflow can never print as a bare Python
traceback or read as success.

12 offline tests cover: scoped call arguments (`record_domains=[]`,
`allow_create=False`), that arm mode never touches `armed_window`/`disarm` and disarm
mode never touches `arm_for_dispatch`, the empty-`--ids` and unresolvable-workflow-name
refusals, the `ALLOW_N8N_ARM`-absent zero-HTTP-call proof, disarm succeeding without
`ALLOW_N8N_ARM` set, the `DisarmFailed` exception path, and `main()`'s exit codes/stdout
for both modes.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - missing error handling] `arm()` catches `n8n_arming.ArmingRefused`**
- **Found during:** Task 3, writing `arm()`
- **Issue:** `n8n_arming.arm_for_dispatch()` can raise `ArmingRefused` from its internal
  `_assert_only_declaration_lines_changed()` / fail-closed re-scan path (not just return
  a refusal dict, unlike the `ALLOW_N8N_ARM`-absent case). The plan's `<action>` text
  only explicitly named `DisarmFailed` handling; an uncaught `ArmingRefused` reaching
  `main()` would print a Python traceback on the exact live command an operator runs,
  instead of the same clean `{"outcome": "refused", ...}` JSON shape every other
  refusal path already returns.
- **Fix:** Wrapped the `arm_for_dispatch` call in `try/except n8n_arming.ArmingRefused`,
  returning `{"outcome": "refused", "detail": str(exc)}`.
- **Files modified:** `scripts/june_run_arm.py`
- **Commit:** `1010310`

### None Otherwise

Tasks 1 and 2 executed exactly as written, including the domain-derivation design left
to discretion (documented above under `key-decisions`) and the additive real_findings
shape for provenance enforcement.

## Concurrent Wave-1 Observation (not this plan's regression)

Mid-execution, `.venv/bin/python -m pytest -q` briefly showed 2 failures in
`tests/test_architecture_guard.py::test_ar2_no_middleware_hosts` (both
`wf_enrichment_cloud.json` and `wf_enrichment_local_live.json` parametrizations). These
were caused entirely by Plan 41-01's concurrent, uncommitted regeneration of
`n8n/wf_enrichment_cloud.json` / `n8n/wf_enrichment_local_live.json` via
`scripts/build_cloud_workflows.py` (the June evidence-URL hosts newly baked into the
`Merge Company` node body) — confirmed via `git status --short`, which showed those
exact files modified but not staged by this plan, and `tests/test_architecture_guard.py`
itself modified concurrently (41-01 actively addressing it). None of this plan's three
files_modified touch `n8n/`, `scripts/build_cloud_workflows.py`, or
`tests/test_architecture_guard.py`, and per the wave-1 constraint this plan does not
touch 41-01's files. Not fixed here; noted for the orchestrator merging both plans'
waves. At the time of this plan's own commits, `.venv/bin/python -m pytest -q` reported
2343 passed / 118 skipped (2 concurrent, not-this-plan failures included in that run),
comfortably above the 2308 floor; `tests/test_resolve_june_ids.py
tests/test_june_run_arm.py tests/test_scoring_parity.py -k "not live"` reported 60
passed / 33 skipped / 1 deselected with zero failures.

## Known Stubs

None — every script in this plan is a complete, tested, read-only or safety-gated
implementation. No hardcoded empty values, no placeholder text, no unwired data paths.

## User Setup Required

None for this plan's own execution — every test stubs its transport. Plan 03/04 will
need `HUBSPOT_PRIVATE_APP_TOKEN`, `HUBSPOT_PORTAL_ID=22617666`, and (for the arm/disarm
commands only, operator's own shell) `ALLOW_N8N_ARM=true`, none of which this plan sets
or reads outside its own test doubles.

## Next Phase Readiness

- Plan 03 (deploy + canary) can hand the operator the resolver command verbatim, parse
  its printed resolved-id list, and hand the operator the arm command with that exact
  list substituted into `--ids`.
- Plan 04 (full run + parity proof) can hand the operator the disarm command and the
  `PARITY_REQUIRE_PROVENANCE=true` parity sweep command verbatim — both recorded above
  under `operator-commands`.
- The `.planning/phases/41-validation-data-import-end-to-end-proof/41-id-resolution.json`
  report path and shape are fixed and ready to be read/summarized by Plan 04's run
  report.
- The concurrent `test_architecture_guard.py` regression noted above is 41-01's own
  territory to close before the phase's overall gate; this plan's own three
  verification commands are fully green independent of it.

---
*Phase: 41-validation-data-import-end-to-end-proof*
*Completed: 2026-08-07*

## Self-Check: PASSED

All key files confirmed present on disk: `scripts/resolve_june_ids.py`,
`tests/test_resolve_june_ids.py`, `scripts/june_run_arm.py`,
`tests/test_june_run_arm.py`, `scripts/run_scoring_parity.py`,
`tests/scoring_fixtures.py`, `tests/test_scoring_parity.py`, this SUMMARY. All 3 task
commits (`414d784`, `4807857`, `1010310`) confirmed present in `git log --oneline
--all`.
