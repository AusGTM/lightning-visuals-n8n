---
phase: 74-code-review-follow-ups-from-phase-73
plan: 01
subsystem: offline-tooling
tags: [n8n, redaction, secrets, fixtures, tdd, python, node-test]

# Dependency graph
requires: []
provides:
  - "scripts/freeze_execution_rundata.py's _scrub/_SENSITIVE_KEYS -- a non-enumerating, whole-node-run redaction (D-74-07)"
  - "scripts/freeze_execution_rundata.py's --rescrub CLI mode -- re-redact an already-committed fixture in place, no n8n credentials needed"
  - "tests/n8n/frozenFixtureSecrets.test.mjs -- a directory-wide value-shape secret guard (D-74-09)"
  - "tests/n8n/fixtures/frozen/exec_12522.runData.json -- the D-74-03 fidelity fixture"
affects: [74-04-PLAN.md, 74-05-PLAN.md]

# Actuals (#2632)
actuals:
  tokens: 5686   # code-only (scripts/freeze_execution_rundata.py + both test files + README): chars/4 = 22745/4
  tasks: 3
  commits: 4
  # Full realized diff including the 7 re-redacted/reformatted fixture JSON files: 7,564,195 chars
  # (~1,891,049 chars/4) -- dominated by sort_keys=True JSON reformatting of the 5 pre-freezer
  # Phase-70 fixtures (which never went through this tool before), not by authored content. The
  # code-only figure above is the meaningful one for estimate calibration.

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Non-enumerating recursive redaction (_scrub): walk every dict/list at any depth, replace a matched key's value wholesale, never descend into the replacement"
    - "--rescrub CLI mode: re-apply a redaction/scrub function to already-committed bytes without re-fetching from the network"
    - "Value-shape-only secret guard test (never key-name): a directory-wide regex refusal list that must pass against legitimate jsCode/notes strings containing the same key/scheme names"

key-files:
  created:
    - tests/n8n/frozenFixtureSecrets.test.mjs
    - tests/test_freeze_execution_rundata.py
    - tests/n8n/fixtures/frozen/exec_12522.runData.json
  modified:
    - scripts/freeze_execution_rundata.py
    - tests/n8n/fixtures/frozen/README.md
    - tests/n8n/fixtures/frozen/exec_12434.runData.json
    - tests/n8n/fixtures/frozen/exec_12449.runData.json
    - tests/n8n/fixtures/frozen/exec_12354.runData.json
    - tests/n8n/fixtures/frozen/exec_12355.runData.json
    - tests/n8n/fixtures/frozen/exec_12356.runData.json
    - tests/n8n/fixtures/frozen/exec_12357.runData.json
    - tests/n8n/fixtures/frozen/exec_12358.runData.json
    - tests/n8n/fixtures/frozen/run_6891d018-decide-and-response.excerpt.json

key-decisions:
  - "Widened _SENSITIVE_KEYS beyond D-74-07's literal five (headers/error/request/options/config) to also include zoom_token/access_token -- the five specified keys alone never reach the live ZoomInfo OAuth JWT actually committed in exec_12434/exec_12449 (both leak under zoom_token or access_token, siblings of json, not nested under any of the five). Traced every eyJ-prefixed string in both fixtures back to its parent key before writing the fix; documented as a Rule 1/2 deviation in the module docstring, an inline comment, and a dedicated unit test."
  - "Added a --rescrub CLI mode rather than re-fetching from n8n to re-redact the 7 pre-existing fixtures: re-applies the current _scrub to bytes already on disk, no N8N_URL/N8N_API_KEY needed. Matches the task instruction's 'through the freezer's own re-scrub path -- never a hand edit of the JSON.'"
  - "Task 3 (freeze execution 12522) used the raw capture already sitting in the session scratchpad (fetched in a prior session) via freeze_execution_rundata.build_full_fixture(execution) directly, instead of a fresh live GET through an in-process dotenv driver. Costs strictly less (zero network calls of any kind, not merely zero n8n executions) and is still 'the widened tool' -- same module, same _scrub, same build_full_fixture shape contract."
  - "Guard test assertions use assert.equal(pattern.test(raw), false, msg) rather than assert.doesNotMatch(raw, pattern, msg) -- the latter's failure output embeds the entire matched input (here: the whole multi-megabyte fixture, including the secret it caught) into the test/commit transcript."
  - "IN_SCOPE_FILES in the widened guard is computed via fs.readdirSync + filter, not hardcoded, so a future fixture added to the directory is automatically in scope and the guard's own file-count assertion catches drift."

requirements-completed: [D-74-07, D-74-08, D-74-09, D-74-03]

coverage:
  - id: D1
    description: "D-74-07: freezer's _scrub replaces headers/error/request/options/config (plus zoom_token/access_token) at any depth of a whole node-run entry, including run.error"
    requirement: D-74-07
    verification:
      - kind: unit
        ref: "tests/test_freeze_execution_rundata.py#test_error_sibling_of_data_is_replaced"
        status: pass
      - kind: unit
        ref: "tests/test_freeze_execution_rundata.py#test_nested_bearer_under_error_request_headers_replaced_at_first_match"
        status: pass
      - kind: unit
        ref: "tests/test_freeze_execution_rundata.py#test_options_or_config_key_at_any_depth_is_replaced"
        status: pass
      - kind: unit
        ref: "tests/test_freeze_execution_rundata.py#test_zoom_token_and_access_token_values_are_replaced"
        status: pass
    human_judgment: false
  - id: D2
    description: "D-74-08: all 7 pre-existing committed runData/excerpt fixtures re-redacted in place through the widened scrub, no path exemptions; no JWT body or non-placeholder shared-secret value remains"
    requirement: D-74-08
    verification:
      - kind: e2e
        ref: "node --test tests/n8n/frozenFixtureSecrets.test.mjs (directory-wide)"
        status: pass
      - kind: integration
        ref: "operator-claude-plugin/tests/test_run_report_enrich_account.py (Pitfall 4 regression check)"
        status: pass
      - kind: integration
        ref: "node --test tests/n8n/v1RuntimeRecordings.test.mjs tests/n8n/walkerEngineFidelity.test.mjs"
        status: pass
    human_judgment: false
  - id: D3
    description: "D-74-09: value-shape-only guard test over the whole frozen directory, provably passing on the 4 workflow-body fixtures that legitimately carry the key NAME/scheme string in jsCode"
    requirement: D-74-09
    verification:
      - kind: e2e
        ref: "tests/n8n/frozenFixtureSecrets.test.mjs#guard reports its own in-scope file count"
        status: pass
    human_judgment: false
  - id: D4
    description: "D-74-03 (fixture half): tests/n8n/fixtures/frozen/exec_12522.runData.json frozen through the widened tool, per-node counts agree exactly with D-74-01's recorded shape, zero n8n executions/network calls consumed"
    requirement: D-74-03
    verification:
      - kind: integration
        ref: "node --test tests/n8n/walkerEngineFidelityV1.test.mjs"
        status: pass
      - kind: other
        ref: "manual per-node count read-back against 74-CONTEXT.md D-74-01 (HubSpot Create [21,0], Create Carry Merge 1x42, Build Association Request Merge 1x22, HubSpot Associate Company 1x22, Ingest Merge Response 1 run/6 inputs, Build Ingest Response 1x46)"
        status: pass
    human_judgment: false

duration: 55min
completed: 2026-09-19
status: complete
---

# Phase 74 Plan 01: Freezer redaction widening + execution 12522 fixture Summary

**Widened `scripts/freeze_execution_rundata.py`'s secret scrub from a single hardcoded path (`json.headers`) to a recursive, whole-node-run walk over seven sensitive key names, re-redacted all 7 pre-existing frozen fixtures through it with no path exemptions, added a directory-wide value-shape guard test, and froze execution `12522` as the fixture Phase 74's later walker-fidelity work depends on.**

## Performance

- **Duration:** 55 min
- **Started:** 2026-09-19T07:40:00Z (approx, first commit `bf83e6ba`)
- **Completed:** 2026-09-19
- **Tasks:** 3
- **Files modified:** 13 (3 created, 10 modified)

## Accomplishments

- Replaced `_redact_headers` (a single hardcoded `json.headers` path) with `_scrub`, a recursive, non-enumerating redaction over the entire node-run entry at any depth, closing CR-04's three named gaps (`run.error`, nested `request`/`options`/`config`).
- Found and fixed a real gap in the plan's own specified key list during Task 1: the two committed fixtures' actual live JWT leak sits under `zoom_token`/`access_token`, not under any of D-74-07's five named keys. Widened `_SENSITIVE_KEYS` accordingly (Rule 1/2 deviation, fully documented and unit-tested).
- Added a `--rescrub` CLI mode so all 7 pre-existing fixtures could be re-redacted in place without any live n8n credentials or network call.
- Widened the new guard test from one file to the whole `tests/n8n/fixtures/frozen/` directory (14 JSON files), proving it does not false-positive on the 4 workflow-body fixtures' legitimate `Bearer`/`X-Enrichment-Secret` jsCode literals.
- Froze execution `12522` — the fixture 74-05 depends on — using the raw capture already fetched in a prior session rather than a new live GET, consuming zero network calls of any kind. All per-node counts agree exactly with `74-CONTEXT.md`'s recorded shape for that execution.

## Task Commits

1. **Task 1 (RED): frozen fixture secret guard + freezer scrub unit tests** — `bf83e6ba` (test)
2. **Task 1 (GREEN): widen freezer scrub to headers/error/request/options/config at any depth** — `e7caad29` (feat)
3. **Task 2: re-redact remaining 6 fixtures, widen guard to whole directory** — `bc83d181` (feat)
4. **Task 3: freeze execution 12522 through the widened freezer** — `f3504fa2` (feat)

_TDD task (Task 1): RED confirmed via `gsd-tools check tdd-red-evidence` (`RED_EVIDENCE_OK`, `target_test_failed`) before any implementation edit; no REFACTOR commit was needed — the GREEN implementation was already minimal._

## Files Created/Modified

- `scripts/freeze_execution_rundata.py` — `_scrub`/`_SENSITIVE_KEYS` replace `_redact_headers`; new `--rescrub` CLI mode; docstring rewritten to describe the widened scope
- `tests/n8n/frozenFixtureSecrets.test.mjs` — new D-74-09 guard, directory-wide by Task 2
- `tests/test_freeze_execution_rundata.py` — new; offline behavioral coverage for `_scrub` (no prior test file covered this script)
- `tests/n8n/fixtures/frozen/README.md` — new "Widened scope" subsection documenting the rule
- `tests/n8n/fixtures/frozen/exec_12434.runData.json`, `exec_12449.runData.json` — re-redacted (JWT bodies removed)
- `tests/n8n/fixtures/frozen/exec_1235{4,5,6,7,8}.runData.json` — re-redacted (headers wholesale-replaced; these 5 predate the freezer tool and previously used a different, per-key header redaction)
- `tests/n8n/fixtures/frozen/run_6891d018-decide-and-response.excerpt.json` — re-redacted (no secret content changed; confirmed produced by the same tool's `--combine` mode)
- `tests/n8n/fixtures/frozen/exec_12522.runData.json` — new, the D-74-03 fixture half

## Decisions Made

See `key-decisions` in frontmatter. In short: the plan's specified 5-key redaction list was empirically insufficient for the actual leak in the two named fixtures (found by tracing every `eyJ`-prefixed value back to its parent key before writing the fix) — widened to 7 keys as a documented Rule 1/2 deviation. Task 3 used the already-fetched raw capture instead of a fresh live GET, which is strictly cheaper and still routes through the same widened tool.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1/2 - Bug/Missing critical] `_SENSITIVE_KEYS` widened beyond D-74-07's literal five keys**
- **Found during:** Task 1, before writing any implementation code — walked every `eyJ`-prefixed value in `exec_12434.runData.json`/`exec_12449.runData.json` back to its parent key.
- **Issue:** D-74-07/74-CONTEXT.md/74-RESEARCH.md all specify exactly five sensitive keys (`headers`/`error`/`request`/`options`/`config`). None of the 56 live JWT occurrences across the two named fixtures sit under any of those five — all 56 are direct children of `json` under the keys `zoom_token` (52 occurrences) or `access_token` (4 occurrences). A scrub built to the letter of D-74-07 would leave the fixture's own `<done>` criterion ("carries no JWT-shaped value") and the D-74-09 guard's JWT-body assertion both unsatisfiable.
- **Fix:** Added `zoom_token` and `access_token` to `_SENSITIVE_KEYS`, documented in the module docstring, an inline code comment, and a dedicated unit test (`test_zoom_token_and_access_token_values_are_replaced`) naming the deviation explicitly.
- **Files modified:** `scripts/freeze_execution_rundata.py`, `tests/test_freeze_execution_rundata.py`
- **Verification:** `grep -c "eyJ" tests/n8n/fixtures/frozen/exec_12434.runData.json` → 0 (was 37); same for `exec_12449.runData.json` (was 19). `node --test tests/n8n/frozenFixtureSecrets.test.mjs` green.
- **Committed in:** `e7caad29` (Task 1 GREEN commit)

**2. [Rule 2 - Missing critical, methodology] `--rescrub` CLI mode added, not specified by name in the plan**
- **Found during:** Task 1 — the plan's action text says fixtures must be re-redacted "through the freezer's own re-scrub path — never a hand edit of the JSON," implying such a path must exist, but the freezer only ever had a live-GET-and-write path before this task.
- **Issue:** Re-fetching 7 already-committed executions from n8n purely to re-apply a scrub would be wasteful and, for `run_6891d018-decide-and-response.excerpt.json`, would require 18 fresh GETs against executions already fetched in Phase 73.
- **Fix:** Added `--rescrub PATH [PATH...]`, operating entirely on bytes already on disk, no credentials needed.
- **Files modified:** `scripts/freeze_execution_rundata.py`
- **Verification:** Used to re-redact all 7 fixtures in Tasks 1-2; all consumer tests stayed green.
- **Committed in:** `e7caad29`

---

**Total deviations:** 2 auto-fixed (1 Rule 1/2 bug in the plan's own specified redaction key list, 1 Rule 2 missing-mechanism addition). **Impact:** both were necessary for the plan's own stated acceptance criteria to be satisfiable on the real committed data; no scope creep beyond what Tasks 1-2's action text already implied.

## Issues Encountered

None beyond the deviations above. One thing worth flagging for later plans: the 5 Phase-70 fixtures (`exec_1235{4..8}.runData.json`) predate `freeze_execution_rundata.py`'s existence and were previously redacted by a different, per-key mechanism that preserved most benign header fields (`host`, `user-agent`, etc.) alongside individually-blanked sensitive ones. Running them through the current tool's wholesale-headers replacement collapsed that whole object into the single placeholder string, which is a large textual diff (~34k lines net across the 5 files) but was verified structurally (not just by text diff) to change nothing beyond the documented `_SENSITIVE_KEYS` set — confirmed via a Python round-trip comparison before committing, and via the full existing test suites for those fixtures staying green.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- 74-04-PLAN.md and 74-05-PLAN.md are unblocked: `tests/n8n/fixtures/frozen/exec_12522.runData.json` now exists for the walker-fidelity fix and the D-74-12/MN-01 search (neither performed here — MN-01's search is explicitly out of this plan's scope per its `requirements` list, which does not include D-74-12).
- D-74-03 and D-74-09 are shared IDs with sibling plans in this phase (`gsd-tools query requirements.ready-ids` reported them `blocked`, not `ready`, pending those siblings) — expected per the #2388 shared-ID gate; no action needed here.
- Full test baseline confirmed green at plan close: `node --test tests/n8n/*.test.mjs` → 1305 pass / 0 fail (was 1303/0). `.venv/bin/python -m pytest -q --tb=short -p no:cacheprovider` → 5140 passed / 160 skipped (was 5132/160). `operator-claude-plugin/tests/test_run_report_enrich_account.py` → 3 passed (no Pitfall 4 collision).
- Zero n8n executions and zero network calls of any kind were consumed by this plan (Task 3 reused an already-fetched raw capture instead of issuing a fresh GET).

## Self-Check: PASSED

- `[ -f scripts/freeze_execution_rundata.py ]` → FOUND
- `[ -f tests/n8n/frozenFixtureSecrets.test.mjs ]` → FOUND
- `[ -f tests/test_freeze_execution_rundata.py ]` → FOUND
- `[ -f tests/n8n/fixtures/frozen/exec_12522.runData.json ]` → FOUND
- `git log --oneline --all | grep -q bf83e6ba` → FOUND
- `git log --oneline --all | grep -q e7caad29` → FOUND
- `git log --oneline --all | grep -q bc83d181` → FOUND
- `git log --oneline --all | grep -q f3504fa2` → FOUND

---
*Phase: 74-code-review-follow-ups-from-phase-73*
*Completed: 2026-09-19*
