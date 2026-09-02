---
phase: 23-walking-skeleton-plugin-shell-tabular-dispatch
plan: 03
subsystem: testing
tags: [pytest, openpyxl, requests, plugin-scaffolding, network-guard]

requires: []
provides:
  - operator-claude-plugin's own requirements.txt (openpyxl, requests, PyYAML)
  - gitignored real config path + tracked example config
  - operator-claude-plugin/tests/ package with autouse network guard
  - shared fixtures (sample_csv, sample_xlsx, fake_config, stub_transport)
affects: [23-04, 23-05, 23-06]

tech-stack:
  added: []
  patterns:
    - "Autouse pytest fixture monkeypatching requests.post/request/Session.request to
      raise, so no test in the suite can perform a real network call by omission"
    - "XLSX test fixtures generated at fixture time with openpyxl rather than committed
      as binaries, so content is visible in test source"

key-files:
  created:
    - operator-claude-plugin/requirements.txt
    - operator-claude-plugin/config/operator.local.example.json
    - operator-claude-plugin/tests/conftest.py
    - operator-claude-plugin/tests/test_transport_guard.py
  modified:
    - .gitignore

key-decisions:
  - "webhook_secret placeholder value hints at the X-Enrichment-Secret header name
    (matches scripts/provision_n8n_credentials.py) so a diagnosing admin can cross-check
    without JSON comments"
  - "conftest.py inserts operator-claude-plugin/scripts onto sys.path even though that
    directory does not exist yet (23-04 creates it) — sys.path.insert on a nonexistent
    path is a no-op until then, and this avoids a second edit later"

patterns-established:
  - "Every operator-claude-plugin test is network-stubbed by an autouse fixture, not by
    each test remembering to request one"

requirements-completed: [PLUGIN-02, PLUGIN-04]

coverage:
  - id: D1
    description: "Real plugin config path is un-committable; tracked example carries
      only placeholders (n8n_url, webhook_secret hinting at X-Enrichment-Secret,
      optional column_mapping_path)"
    requirement: "PLUGIN-02"
    verification:
      - kind: unit
        ref: "git check-ignore -q operator-claude-plugin/config/operator.local.json && python3 -c \"import json;d=json.load(open('operator-claude-plugin/config/operator.local.example.json'));assert set(('n8n_url','webhook_secret')) <= set(d)\""
        status: pass
    human_judgment: false
  - id: D2
    description: "Autouse no_network fixture blocks requests.post/request/Session.request
      in every plugin test; stub_transport still records calls without raising"
    requirement: "PLUGIN-04"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_transport_guard.py#test_requests_post_raises_inside_a_test"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_transport_guard.py#test_stub_transport_records_without_raising"
        status: pass
    human_judgment: false
  - id: D3
    description: "Plugin declares its own dependency set (openpyxl, requests, PyYAML) at
      the same floors already proven in this repo, independent of the repo root's
      requirements.txt"
    requirement: "PLUGIN-04"
    verification:
      - kind: unit
        ref: "grep -c openpyxl operator-claude-plugin/requirements.txt"
        status: pass
    human_judgment: false

duration: 12min
completed: 2026-07-30
status: complete
---

# Phase 23 Plan 03: Plugin Test Scaffolding + Network Guard Summary

**Plugin-local requirements.txt, gitignored config boundary, and an autouse pytest fixture that makes a real network call from any plugin test impossible by construction.**

## Performance

- **Duration:** ~12 min
- **Tasks:** 2
- **Files modified:** 5 (4 created, 1 modified)

## Accomplishments
- `operator-claude-plugin/config/operator.local.json` is exact-path gitignored; the
  tracked `operator.local.example.json` carries only placeholder `n8n_url` and
  `webhook_secret` (the latter's placeholder value names the `X-Enrichment-Secret`
  header the backend actually checks).
- `operator-claude-plugin/requirements.txt` pins `openpyxl>=3.1.2`, `requests>=2.32.0`,
  `PyYAML>=6.0.2` — the plugin's own dependency declaration, not inherited from the repo
  root.
- `operator-claude-plugin/tests/conftest.py` provides `sample_csv` (messy headers
  including one alias-table miss, 25 rows to exercise the >20-row preview branch),
  `sample_xlsx` (same content, built at fixture time with openpyxl), `fake_config`,
  `stub_transport` (recording callable), and an autouse `no_network` fixture that
  monkeypatches `requests.post`/`requests.request`/`requests.Session.request` to raise,
  naming the offending test.
- `operator-claude-plugin/tests/test_transport_guard.py` proves the guard is not vacuous:
  a real `requests.post`/`request`/`Session.request` call inside a test raises, and
  `stub_transport` records a call without raising.
- No `__init__.py` under `operator-claude-plugin/tests/`; `operator-claude-plugin/scripts`
  is pre-emptively added to `sys.path` from `conftest.py` (directory doesn't exist yet —
  created in 23-04) so future plugin modules import as flat names, never as a `scripts`
  package that would collide with the repo's backend `scripts/`.

## Task Commits

Task 2 followed TDD (RED then GREEN); Task 1 was a single commit.

1. **Task 1: Config boundary — gitignore entry, tracked example, plugin requirements** - `460c048` (feat)
2. **Task 2: Shared fixtures and the autouse network guard** - `893168a` (test, RED) → `007fb50` (feat, GREEN)

## Files Created/Modified
- `.gitignore` - added exact-path entry for `operator-claude-plugin/config/operator.local.json`
- `operator-claude-plugin/config/operator.local.example.json` - tracked placeholder config template
- `operator-claude-plugin/requirements.txt` - plugin's own pinned dependencies
- `operator-claude-plugin/tests/conftest.py` - shared fixtures + autouse network guard
- `operator-claude-plugin/tests/test_transport_guard.py` - proves the guard bites and the stub seam works

## Decisions Made
- Used the `column_mapping_path` key with value `null` in the example config (documented
  as "leave unset to use the repo's `config/column_mapping.yaml`") rather than omitting
  the key, so the operator's copy shows every recognized key up front.
- `stub_transport` is a plain callable class recording `url`/`headers`/`files`/`timeout`
  plus any extra kwargs into a `.calls` list, returning a canned `_StubResponse` with
  `.status_code` and `.json()` — matches the multipart POST shape 23-04's dispatch code
  will use without over-specifying it yet.

## Deviations from Plan

None - plan executed exactly as written. The TDD RED phase for Task 2 surfaced (and
confirmed) the exact risk 23-VALIDATION.md's Wave 0 constraint names: running
`test_transport_guard.py` before `conftest.py` existed caused `requests.post` to attempt
a real network connection (safely failed at DNS resolution against the `.invalid` TLD,
so no data was ever sent) — this is documentation of the RED state, not a deviation.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required. (The operator's own one-time config
setup from the tracked example is documented in the plugin README by a later plan, 23-05.)

## Next Phase Readiness
- `.venv/bin/python -m pytest operator-claude-plugin/tests -q` runs and passes (4 tests)
  against an otherwise-empty plugin — the later plans' `<automated>` verify commands now
  have a suite to run against.
- Full repo suite (`.venv/bin/python -m pytest -q`) still green at 709 passed — no
  basename collision between `operator-claude-plugin/tests/` and the repo's `tests/`
  package.
- 23-04 can now write `operator-claude-plugin/scripts/*.py` and have it import cleanly
  via the `sys.path` entry already in place, plus reuse `stub_transport`, `sample_csv`,
  `sample_xlsx`, and `fake_config` directly.

---
*Phase: 23-walking-skeleton-plugin-shell-tabular-dispatch*
*Completed: 2026-07-30*

## Self-Check: PASSED

All created files and commit hashes verified present on disk / in git log.
