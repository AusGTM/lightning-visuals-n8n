---
phase: 37-enrich-before-ingest
plan: 01
subsystem: enrichment
tags: [ast-guard, chunking, wire-contract, py-js-pin, n8n]

requires:
  - phase: 36-enrichment-propose-mode
    provides: "backend mode:\"propose\" match lane, ENRICH_MAX_PROPOSE_RECORDS=20"
provides:
  - "enrichment.build_envelope's rows branch: MATCH_LOOKUP_KEYS frozen allowlist, mode:\"propose\" set structurally"
  - "chunking.chunk_ceiling(config, key=) and plan_chunks/failed_batch rows branches"
  - "operator.local.example.json::max_rows_per_match_request, cross-repo pinned to ENRICH_MAX_PROPOSE_RECORDS"
  - "dispatch_enrichment visible to the AST arming guard for the first time"
affects: [37-02, 37-03, 37-04, 37-05, 37-06]

actuals:
  tokens: 9672
  tasks: 3
  commits: 3

tech-stack:
  added: []
  patterns:
    - "Byte-identical py<->js wire-contract pin (two files, one literal, real production imports on both sides)"
    - "AST-guard predicate extension: module-shaped transport default + own-parameter-name send-verb call"

key-files:
  created:
    - operator-claude-plugin/tests/test_rows_envelope_contract.py
    - tests/n8n/rowsEnvelopeContract.test.mjs
    - tests/test_match_ceiling_contract.py
  modified:
    - operator-claude-plugin/scripts/enrichment.py
    - operator-claude-plugin/scripts/chunking.py
    - operator-claude-plugin/config/operator.local.example.json
    - operator-claude-plugin/tests/test_chunking.py
    - operator-claude-plugin/tests/test_retry_reuses_dispatch.py

key-decisions:
  - "max_rows_per_match_request ships at 20, read by regex out of ENRICH_MAX_PROPOSE_RECORDS in scripts/build_cloud_workflows.py, never computed independently — the pin asserts <= (not ==) so the backend-first raise order leaves a legal intermediate state."
  - "Closing the AST guard's module-shaped blind spot also surfaced two pre-existing, already-documented module-shaped reads (review_queue.py::fetch_queue, probe_n8n_semantics.py::execute_probe) that were invisible to the guard before this change. Allowlisted alongside dispatch_enrichment with reasoning — both carry no HubSpot record payload and are gated by their own capability/gate checks, not the retry-arming gate this test protects."

requirements-completed: [STRUCT-01, PREVIEW-03, DISPATCH-03]

coverage:
  - id: D1
    description: "Rows envelope pinned byte-identical from both languages: enrichment.build_envelope's rows branch emits MATCH_LOOKUP_KEYS-projected events with mode:\"propose\" set structurally; the backend's own parseWebhookBody + laneOf route the exact client envelope to the MEDIUM match lane (\"name\"), never \"none\"."
    requirement: STRUCT-01
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_rows_envelope_contract.py"
        status: pass
      - kind: integration
        ref: "tests/n8n/rowsEnvelopeContract.test.mjs"
        status: pass
    human_judgment: false
  - id: D2
    description: "chunk_ceiling(config, key=) reads a second ceiling key with the identical no-fallback refusal; plan_chunks/failed_batch gain rows branches mirroring the record_ids branches exactly; max_rows_per_match_request ships equal to (by construction) and cross-repo pinned against ENRICH_MAX_PROPOSE_RECORDS, marked PROVISIONAL."
    requirement: PREVIEW-03
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_chunking.py"
        status: pass
      - kind: unit
        ref: "tests/test_match_ceiling_contract.py"
        status: pass
      - kind: unit
        ref: "tests/test_chunk_ceiling_contract.py"
        status: pass
    human_judgment: false
  - id: D3
    description: "The AST arming guard now sees dispatch_enrichment's module-shaped transport=requests default and internal transport.post call, and allowlists it with stated reasoning instead of being blind to it — closing a live, previously-unguarded second send path."
    requirement: DISPATCH-03
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_retry_reuses_dispatch.py::test_exactly_one_module_defines_the_send_shaped_function"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_retry_reuses_dispatch.py::test_dispatch_enrichment_armed_parameter_still_carries_no_default"
        status: pass
    human_judgment: false

duration: 15min
completed: 2026-08-05
status: complete
---

# Phase 37 Plan 01: Rows Envelope, Chunk Ceiling, AST Guard Summary

**The rows-form wire contract, its own configured match ceiling, and the arming guard's blind spot to `dispatch_enrichment` — all pinned byte-identical, cross-repo, and structurally, before anything is built on top of them.**

## Performance

- **Duration:** ~15 min
- **Completed:** 2026-08-05T08:37:44Z
- **Tasks:** 3/3
- **Files modified:** 8 (3 created, 5 modified)

## Accomplishments

- `enrichment.build_envelope` gains a `rows` branch: `MATCH_LOOKUP_KEYS = ("email", "firstname", "lastname", "company")` is the frozen projection, `mode: "propose"` is set structurally inside the branch (never readable from `spec`), and the two-file py<->js contract pin proves the backend's own `parseWebhookBody` + `laneOf` route the exact client envelope to the MEDIUM match lane — with a camelCase-spelling regression test proving the D-19 class (a field-name mistake silently routing to lane `"none"`) is caught, not merely covered.
- `chunking.chunk_ceiling` gains a `key=` parameter so the match lane reads its own ceiling (`max_rows_per_match_request`) with the identical no-fallback refusal `max_records_per_chunk` already gets; `plan_chunks`/`failed_batch` gain `rows` branches mirroring the `record_ids` branches exactly.
- `max_rows_per_match_request` ships at 20 in `operator.local.example.json`, read by regex out of the backend's landed `ENRICH_MAX_PROPOSE_RECORDS` (`scripts/build_cloud_workflows.py:3512`) rather than computed independently — cross-repo pinned by `tests/test_match_ceiling_contract.py` (`<=`, not `==`, so the prescribed backend-first raise leaves a legal intermediate state) and marked PROVISIONAL in its own provenance note only.
- The AST arming guard (`test_retry_reuses_dispatch.py`) gains two predicates that together make `enrichment.dispatch_enrichment`'s module-shaped `transport=requests` default visible for the first time, and allowlist it with stated reasoning — the guard's own failure message ("a second dispatch path would let a retry bypass the arming gate") is now true of the code it guards.

## Task Commits

1. **Task 1: The rows envelope, pinned byte-identical from both languages** - `19d00ff` (feat)
2. **Task 2: A rows spec chunks against its own configured ceiling** - `2fe94cb` (feat)
3. **Task 3: Close the arming guard's module-shaped blind spot** - `5d3edcd` (test)

_No separate plan-metadata commit — this SUMMARY and STATE.md updates are committed together per `final_commit`._

## Files Created/Modified

- `operator-claude-plugin/scripts/enrichment.py` - `MATCH_LOOKUP_KEYS` frozen constant + `build_envelope`'s new `rows` branch
- `operator-claude-plugin/tests/test_rows_envelope_contract.py` - Python half of the rows-envelope contract pin
- `tests/n8n/rowsEnvelopeContract.test.mjs` - JS half, asserting the backend's `parseWebhookBody` + `laneOf` accept it
- `operator-claude-plugin/scripts/chunking.py` - `chunk_ceiling(key=)`, `plan_chunks`/`failed_batch` rows branches
- `operator-claude-plugin/config/operator.local.example.json` - `max_rows_per_match_request` + its two provenance notes
- `operator-claude-plugin/tests/test_chunking.py` - `key=` parameter tests, rows-branch split/rebuild tests
- `tests/test_match_ceiling_contract.py` - cross-repo ceiling pin against `ENRICH_MAX_PROPOSE_RECORDS`
- `operator-claude-plugin/tests/test_retry_reuses_dispatch.py` - two new AST predicates, extended `_EXPECTED_SEND_SHAPED`, armed-parameter test

## Decisions Made

- **Match ceiling derivation:** read by regex out of the backend's `ENRICH_MAX_PROPOSE_RECORDS` constant at plan-execution time (20), exactly as the pin test does — never computed from an independent client-side formula, so the two files cannot drift into disagreeing about the same bound.
- **`<=` not `==`** on the cross-repo ceiling pin, deliberately: the prescribed raise order is backend-first, client-second, and an equality pin would make that correct intermediate commit red.
- **AST guard allowlist scope:** rather than narrowing the new predicate to dodge two pre-existing module-shaped reads it also (correctly) surfaced, they were allowlisted with the same reasoning as the existing status-POST entry — see Deviations below.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1/2 - Structural discovery] The AST guard's new module-shaped predicate also surfaces two pre-existing send-shaped functions the plan did not name**

- **Found during:** Task 3, immediately after implementing `_has_bare_requests_module_transport_default` + `_calls_transport_send_verb` and running the test suite.
- **Issue:** The plan's Task 3 only discusses `enrichment.py::dispatch_enrichment` and confirms `executions_client.py`'s read-shaped functions (`transport=requests.get`) must stay unflagged. Running the literal predicate the plan specifies against the actual codebase also flagged `review_queue.py::fetch_queue` and `probe_n8n_semantics.py::execute_probe` — both already module-shaped (`transport=requests`, body calls `transport.post(...)`) and, in `review_queue.py`'s case, carrying a docstring written under the (now-obsolete) assumption that the guard could never see it ("this module must never join that list ... If the guard fires here, this module is wrong"). `test_exactly_one_module_defines_the_send_shaped_function` failed against the plan's `_EXPECTED_SEND_SHAPED` list as literally specified.
- **Investigation:** Read both functions in full. `fetch_queue`'s POST body is `{"object_type": ..., "limit": ...}` — a query filter, never a HubSpot record. `execute_probe`'s POST carries no body at all and exists only to observe whether an n8n endpoint responds; it is gated by its own `_gate()` check and is explicitly documented as "never an operator-facing verb." Neither can carry a record write the way `dispatch.py`/`dispatch_enrichment` can.
- **Fix:** Allowlisted both alongside `dispatch_enrichment`, with reasoning in the same register as the existing `backend_status.py` entry (a read wearing a send verb's clothes). No production code changed — only the test-file allowlist and its accompanying comment.
- **Files modified:** `operator-claude-plugin/tests/test_retry_reuses_dispatch.py` (already the only file this task touches per the plan's `<files>` element).
- **Verification:** `test_exactly_one_module_defines_the_send_shaped_function` passes with the three-entry addition; the two red-checks (removing the `enrichment.py` entry; neutering `_calls_transport_send_verb`) both reproduce the expected failure shapes, confirming the predicate — not the allowlist — is what finds `dispatch_enrichment`.
- **Committed in:** `5d3edcd` (part of Task 3's commit).

---

**Total deviations:** 1 auto-fixed (Rule 1/2 — structural discovery within the guard's own domain, not a scope expansion into new files).
**Impact on plan:** No production code beyond what the plan specified was touched. The allowlist addition is a necessary consequence of correctly implementing the plan's own predicate against the real codebase; leaving it un-narrowed (rather than quietly excluding the two functions by name) keeps the guard's stated invariant — "every send-shaped function is either allowlisted with a stated reason or fails the guard" — actually true.

## Red-Check Failure Text (recorded per task's explicit instruction)

**Task 1** — renaming `lastname` -> `lastName` inside `build_envelope`'s rows branch (via the `MATCH_LOOKUP_KEYS` constant it loops over):
- Python: `test_build_envelope_produces_exactly_the_contract_literal` failed on the dict literal comparison (`{'events': [...'firstname': 'Jane', ...}]} != {...}`); `test_an_empty_or_none_row_value_emits_none_never_the_string_none` failed with `KeyError: 'lastname'`.
- JS (same one-character mistake reproduced in the JS-side literal to prove the JS pin is equally sensitive to it, since the two files are not cross-invoked at runtime): `the client's exact rows envelope reaches the MEDIUM match lane, never none` failed — `AssertionError: expected the MEDIUM match lane "name", got "none"`.

**Task 2:**
- Dropping the `key=` parameter from `chunk_ceiling`: `TypeError: chunk_ceiling() got an unexpected keyword argument 'key'` on both new match-key tests.
- Dropping the `rows` branch from `plan_chunks`: 5 rows-branch tests failed with `ChunkPlanError: No record IDs were given...` (the record_ids branch swallowed the rows spec and refused it for the wrong reason).
- Setting the client ceiling above the backend's (25 vs 20): `AssertionError: match ceiling drift: client max_rows_per_match_request=25 exceeds backend ENRICH_MAX_PROPOSE_RECORDS=20 ... assert 25 <= 20`.
- Collapsing the match ceiling onto `max_records_per_chunk` (2): `AssertionError: the match ceiling must not collapse onto the write-path ceiling ... assert 2 > 2`.
- Stripping the PROVISIONAL marker from the provenance note: `AssertionError: 20 is the backend's own conservative propose-mode bound, not a measurement — the label must say so until a live propose run measures it` — while `test_chunk_ceiling_contract.py`'s own PROVISIONAL-absence assertion on the write-path neighbour's notes stayed green throughout.

**Task 3:**
- Removing the `enrichment.py` entry from `_EXPECTED_SEND_SHAPED`: `test_exactly_one_module_defines_the_send_shaped_function` failed, diffing in `('enrichment.py', ['dispatch_enrichment'])` as a found-but-unexpected offender.
- Neutering `_calls_transport_send_verb` to return `False` unconditionally: the same test failed the other direction — `dispatch_enrichment` (and the other two module-shaped allowlisted entries, `fetch_queue` and `execute_probe`) vanished from the found set entirely, confirming the predicate is load-bearing rather than decorative.

## Issues Encountered

None beyond the AST-guard discovery documented above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `enrichment.MATCH_LOOKUP_KEYS`, `build_envelope`'s `rows` branch, and `chunking.chunk_ceiling(key=)`/`plan_chunks`/`failed_batch` rows branches are the exact primitives 37-03's `preingest.fetch_matches`/`match_batch` are specified to call — no further envelope or chunking work is needed before that plan starts.
- `max_rows_per_match_request` is live in the committed config template at 20, cross-repo pinned; 37-03 can read it via `chunk_ceiling(config, key="max_rows_per_match_request")` immediately.
- The AST guard now recognizes both attribute-shaped (`transport=requests.post`) and module-shaped (`transport=requests` + internal `.post`/`.put`) send functions. 37-03's `fetch_matches` must be written attribute-shaped (`transport=requests.post`, matching `dispatch.py`'s existing shape) per 37-CONTEXT §7/§12 — landing on the allowlist deliberately, not slipping past a still-blind guard.
- No blockers for 37-02 through 37-06.

---
*Phase: 37-enrich-before-ingest*
*Completed: 2026-08-05*
