---
phase: 23-walking-skeleton-plugin-shell-tabular-dispatch
plan: 04
subsystem: infra
tags: [claude-plugin, skill, openpyxl, requests, multipart, arming-gate]

requires:
  - phase: 23-02
    provides: the live smoke-test result proving both file-handoff legs (attachment and @mention) resolve to real filesystem paths
  - phase: 23-03
    provides: plugin-local requirements.txt, gitignored config boundary, autouse no_network test guard, shared fixtures (sample_csv, sample_xlsx, fake_config, stub_transport)
provides:
  - "operator-claude-plugin/scripts/config_gate.py — load_config(), describe_target(), ConfigError; refuses before any network call"
  - "operator-claude-plugin/scripts/tabular.py — read_table(), to_csv_bytes(); CSV/XLSX read unchanged, XLSX re-serialized to CSV format only"
  - "operator-claude-plugin/scripts/dispatch.py — dispatch(file_path, armed, config, transport); armed has no default; NotArmedError/DispatchError"
  - "operator-claude-plugin/.claude-plugin/plugin.json — plugin manifest"
  - "operator-claude-plugin/skills/contact-upload/SKILL.md — the one skill driving all three scripts, auto-triggered and slash-invocable"
  - "operator-claude-plugin/tests/test_no_backend_imports.py — AST-based guard: no plugin file imports repo src/scripts or a named backend module"
affects: [23-05, 23-06, 24]

tech-stack:
  added: []
  patterns:
    - "Two-legged file handoff (attachment try/except, then @mention) built as a real
      leg rather than a defensive stub, per 23-02's positive smoke-test result"
    - "Disarmed-by-default dispatch: armed is a required positional-or-keyword argument
      with no default, so a caller that omits it gets TypeError rather than a silent send"
    - "AST-based (not grep-based) architecture guard for import-boundary enforcement"

key-files:
  created:
    - operator-claude-plugin/scripts/config_gate.py
    - operator-claude-plugin/scripts/tabular.py
    - operator-claude-plugin/scripts/dispatch.py
    - operator-claude-plugin/.claude-plugin/plugin.json
    - operator-claude-plugin/skills/contact-upload/SKILL.md
    - operator-claude-plugin/tests/test_config_gate.py
    - operator-claude-plugin/tests/test_dispatch_multipart.py
    - operator-claude-plugin/tests/test_plugin_manifest.py
    - operator-claude-plugin/tests/test_no_backend_imports.py
  modified: []

key-decisions:
  - "Built the genuine two-legged file handoff (attachment leg + @mention leg) rather
    than the single-leg-plus-try/except degradation the plan text originally anticipated
    — licensed by 23-02's positive live smoke test, recorded in SKILL.md step 2."
  - "load_config() takes an optional explicit path argument (defaulting to the real
    plugin-root config path) so tests exercise missing/invalid/valid config states
    without ever touching the real gitignored operator.local.json."
  - "dispatch() checks `armed` before any file I/O, not just before the transport call
    — cheaper and strictly safer than the plan's stated minimum (raise before touching
    the transport)."
  - "test_no_backend_imports.py's requirements.txt-declared-import check scans only
    scripts/ and skills/ (the operator's actual runtime), excluding tests/ — pytest is a
    repo-.venv test-runner dependency, not something the plugin's own requirements.txt
    needs to repeat (matches 23-03's own reasoning)."

patterns-established:
  - "Each plugin script is both an importable library (for tests) and a CLI (a
    __main__ block printing JSON to stdout, no prose) — the skill invokes them by
    relative path and parses the JSON."

requirements-completed: [INGEST-02, STRUCT-01, DISPATCH-01, DISPATCH-03, PLUGIN-01, PLUGIN-03, PLUGIN-04]

coverage:
  - id: D1
    description: "config_gate.load_config() refuses before any network call when config is missing, empty webhook_secret, missing n8n_url, non-https n8n_url, or malformed JSON — every message names the missing/invalid key, points at operator.local.example.json, and never contains a secret value"
    requirement: "PLUGIN-03"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_config_gate.py"
        status: pass
    human_judgment: false
  - id: D2
    description: "read_table()/to_csv_bytes() read CSV and XLSX headers verbatim (no cleaning/mapping) and convert XLSX to CSV bytes with identical headers and values — no column remapped or dropped"
    requirement: "INGEST-02"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_dispatch_multipart.py#test_read_table_csv_returns_headers_verbatim_and_every_row"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_dispatch_multipart.py#test_to_csv_bytes_xlsx_source_matches_headers_and_values_no_remap"
        status: pass
    human_judgment: false
  - id: D3
    description: "dispatch() with armed=False raises NotArmedError and the stub transport records zero calls; calling dispatch() with no armed argument raises TypeError (armed has no default)"
    requirement: "DISPATCH-03"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_dispatch_multipart.py#test_unarmed_raises_and_stub_records_zero_calls"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_dispatch_multipart.py#test_missing_armed_argument_raises_typeerror"
        status: pass
    human_judgment: false
  - id: D4
    description: "dispatch(armed=True) POSTs multipart/form-data to {n8n_url}/webhook/hubspot/contact-upload with header X-Enrichment-Secret, one file field named data (text/csv), and a finite timeout — matching the deployed hubspot/contact-upload contract field-for-field"
    requirement: "DISPATCH-01"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_dispatch_multipart.py#test_armed_dispatch_calls_the_stub_exactly_once_with_the_deployed_contract"
        status: pass
    human_judgment: false
  - id: D5
    description: "The plugin loads as a Claude Code plugin: .claude-plugin/plugin.json (name/description/version/author, nothing else in that directory) plus skills/contact-upload/SKILL.md, auto-triggered and slash-invocable as /operator-claude-plugin:contact-upload, no commands/ directory"
    requirement: "PLUGIN-01"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_plugin_manifest.py"
        status: pass
    human_judgment: false
  - id: D6
    description: "No plugin file imports the repo's src/ or scripts/ packages or a named backend module (merge policy, scoring, providers, normalizer, hubspot client), and every third-party import the plugin's runtime files use is declared in its own requirements.txt"
    requirement: "PLUGIN-04"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_no_backend_imports.py"
        status: pass
    human_judgment: false

duration: 35min
completed: 2026-07-31
status: complete
---

# Phase 23 Plan 04: Walking Skeleton — Config Gate, Tabular I/O, Disarmed Dispatch, Plugin Shell Summary

**A loadable Claude Code plugin (manifest + one auto-triggered/slash-invocable skill) driving three thin, independently-testable Python modules that prove one path — CSV/XLSX in, config validated, `armed=False` refused with zero bytes sent, `armed=True` producing the exact `hubspot/contact-upload` multipart contract — with a genuine two-legged file handoff built on 23-02's positive smoke test.**

## Performance

- **Duration:** ~35 min
- **Tasks:** 3
- **Files modified:** 9 (all created, all under `operator-claude-plugin/`)

## Accomplishments
- `config_gate.py` refuses before any network call on missing config, empty
  `webhook_secret`, missing/non-`https` `n8n_url`, or malformed JSON — every refusal
  names the broken key, points at `operator.local.example.json`, and never contains a
  secret value. `describe_target()` gives the skill its "state the endpoint up front"
  line for free.
- `tabular.py` reads CSV and XLSX headers verbatim (no cleaning, no mapping — that's
  n8n's `Map Columns` job per D-07) and converts an XLSX source to CSV bytes with
  identical headers/values, since `Extract From File` only parses `operation: "csv"`.
- `dispatch.py`'s `dispatch(file_path, armed, config, transport)` has **no default for
  `armed`** — a forgotten argument is a `TypeError`, never a silent send. The unarmed
  path raises `NotArmedError` before any file is even read; the armed path calls the
  stub transport exactly once with the deployed contract: `X-Enrichment-Secret` header,
  one `data` file field, `text/csv` content type, 30s timeout.
- `.claude-plugin/plugin.json` + `skills/contact-upload/SKILL.md` give the plugin one
  loadable entry point — auto-triggered by natural phrasing and slash-invocable as
  `/operator-claude-plugin:contact-upload` — with no `commands/` directory duplicating
  it.
- `test_no_backend_imports.py` turns PLUGIN-04 into an AST-based test: no plugin file
  may import the repo's `src`/`scripts` packages or a named backend module, and every
  third-party import the plugin's own runtime files use must be declared in its own
  `requirements.txt`.
- **Built the genuine two-legged file handoff 23-02's live smoke test licensed**, not
  the single-leg-plus-try/except degradation the plan text originally anticipated: the
  skill body (step 2) tries the attachment path first, falls back to `@mention` for
  workspace files, and asks rather than hunts if neither resolves.

## Task Commits

1. **Task 1: End-to-end "a spreadsheet becomes a refused-because-disarmed dispatch"** - `bb72388` (feat)
2. **Task 2: Plugin manifest and the skill that drives the scripts** - `933bee8` (feat)
3. **Task 3: Architecture guard — the client touches no backend code** - `3402c38` (test)

## Files Created/Modified
- `operator-claude-plugin/scripts/config_gate.py` - config load/validate, `ConfigError`, `describe_target()`
- `operator-claude-plugin/scripts/tabular.py` - `read_table()`, `to_csv_bytes()`, `UnsupportedFileError`
- `operator-claude-plugin/scripts/dispatch.py` - `dispatch()`, `NotArmedError`, `DispatchError`
- `operator-claude-plugin/tests/test_config_gate.py` - config-gate refusal + success behaviors
- `operator-claude-plugin/tests/test_dispatch_multipart.py` - tabular read/convert + dispatch's arming gate and multipart contract
- `operator-claude-plugin/.claude-plugin/plugin.json` - plugin manifest
- `operator-claude-plugin/skills/contact-upload/SKILL.md` - the conversation contract driving all three scripts
- `operator-claude-plugin/tests/test_plugin_manifest.py` - manifest/skill packaging guard
- `operator-claude-plugin/tests/test_no_backend_imports.py` - AST-based no-backend-import + declared-dependency guard

## Decisions Made
- **Two-legged file handoff, not single-leg-plus-try/except.** 23-02's live Code-tab
  smoke test (2026-07-31) came back positive on all four observations: an operator
  attachment resolves to a real filesystem path, `@mention` also resolves to a real
  path (workspace-scoped), `python3` is available, and `openpyxl`/`requests`/`PyYAML`
  import with no install step. `23-CONTEXT.md` D-14a was amended accordingly before
  this plan started, and this plan builds the widened instruction: SKILL.md's step 2
  tries the attachment path first, falls back to `@mention`, and still builds no
  speculative plumbing beyond that (no temp-directory scanning, no upload shim, no
  retry loop — asks the operator directly if neither leg resolves).
- **`load_config(path=None)` takes an optional explicit path.** Defaults to the real
  plugin-root config location for production use; every test passes an explicit
  `tmp_path`-derived path so the real (gitignored) `operator.local.json` is never
  touched by the test suite.
- **`dispatch()` checks `armed` before touching the filesystem at all**, not just
  before the transport — a stricter reading of D-13 than the plan's literal minimum
  ("before constructing the request or touching the transport"), and free: it costs
  nothing and closes an even smaller surface.
- **The requirements.txt-declared-import check in `test_no_backend_imports.py` scans
  only `scripts/`/`skills/`**, excluding `tests/`. Tests run under this repo's `.venv`
  with its own `pytest` dependency; the plugin's own `requirements.txt` documents what
  the *operator's* runtime needs, which never includes a test framework. This mirrors
  23-03's own stated reasoning for the same omission.
- **Each script carries a thin `__main__` CLI block** printing JSON to stdout (no
  prose) so `SKILL.md` can invoke `python3 scripts/<name>.py ...` and parse the result,
  per the plan's explicit instruction that no module print prose.

## Deviations from Plan

**1. [Widened by 23-02's outcome, not a Rule 1-4 auto-fix] Two-legged file handoff instead of single-leg-plus-try/except**
- **Found during:** Reading `23-02-SUMMARY.md` and the amended `23-CONTEXT.md` D-14a before starting Task 2
- **Issue:** The plan text (written before the smoke test ran) instructs building the
  attachment leg behind a single try/except and relying on `@mention` as the only
  proven mechanism. The smoke test executed since the plan was written (2026-07-31)
  proved both legs resolve to real filesystem paths.
- **Fix:** SKILL.md's step 2 documents both legs as real: try the attachment path,
  fall back to `@mention` for workspace files. No code in `scripts/` needed to change —
  the widening is entirely in the conversation-level instructions, since neither script
  cares *how* a path arrived, only that one did.
- **Files modified:** `operator-claude-plugin/skills/contact-upload/SKILL.md`
- **Verification:** N/A (prose instruction, not a testable code path in this plan) —
  `test_plugin_manifest.py` confirms the skill file exists and references real scripts.
- **Committed in:** `933bee8` (Task 2 commit)

---

**Total deviations:** 1 (plan-anticipated, not an auto-fix under Rules 1-4 — the plan
itself instructed this widening once 23-02's outcome was known).
**Impact on plan:** None beyond the instructed widening. No scope creep — still no
temp-directory scanning, retry loop, or upload shim.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required. The operator's own one-time
`config/operator.local.json` setup from the tracked example remains a later plan's
(23-05) documentation concern, per 23-03's summary.

## Next Phase Readiness
- `.venv/bin/python -m pytest operator-claude-plugin/tests -q` — 33 passed.
- `.venv/bin/python -m pytest -q` (full repo suite) — 741 passed (up from 709 at the
  end of 23-03), no regressions.
- `git diff --name-only` across this plan's three commits touches only files under
  `operator-claude-plugin/` — no backend file modified.
- The disarmed refusal is proven by test (`test_unarmed_raises_and_stub_records_zero_calls`),
  not asserted in prose; the stub transport's call log is asserted empty, not just the
  raised exception.
- 23-05 can now replace `tabular.py`'s minimal preview marker (row count + headers) with
  the real adaptive preview (fill rates, first-10/last-3, `column_mapping.yaml`
  display-only labeling, Artifact rendering) by editing SKILL.md step 3 — the
  `PREVIEW-STEP-OWNER` comment in SKILL.md marks exactly where.
- D-15/D-16/D-16a's backend `allow_create` fix (the separately-justified backend change
  named in `23-CONTEXT.md`) is still outstanding and not addressed by this plan — it
  was not in this plan's task list. Flagging here since `23-CONTEXT.md` D-18 says it
  must land before Phase 23 can demonstrate its stated end-to-end flow.

---
*Phase: 23-walking-skeleton-plugin-shell-tabular-dispatch*
*Completed: 2026-07-31*

## Self-Check: PASSED

All created files and commit hashes verified present on disk / in git log.
