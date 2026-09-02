---
phase: 37-enrich-before-ingest
plan: 03
subsystem: preingest
tags: [ast-guard, match-lane, propose-mode, tdd]

requires:
  - phase: 37-enrich-before-ingest
    plan: 01
    provides: "enrichment.MATCH_LOOKUP_KEYS, build_envelope's rows branch, chunking.chunk_ceiling(key=)/plan_chunks/failed_batch rows branches, AST guard's module-shaped predicate pair"
provides:
  - "preingest.build_rows_spec(rows) — ids minted once, at the whole-batch level, before any chunking"
  - "preingest.fetch_matches(chunk, config, transport=requests.post) — one unarmed POST per chunk, allowlisted on the AST arming guard with two bounding keeper tests"
  - "preingest.match_batch(plan, config, transport=requests.post) — sequential, skip-a-failing-chunk, unchecked never unmatched"
  - "preingest.classify_matches(rows, response, unchecked_row_ids=None) — four tiers joined by row_id, nothing auto-picked"
  - "config_gate.CAPABILITY_KEYS['match'] — its own capability row, same keys as 'enrichment'"
affects: [37-04, 37-05, 37-06]

actuals:
  tokens: 11181
  tasks: 3
  commits: 3

tech-stack:
  added: []
  patterns:
    - "Attribute-shaped unarmed transport, allowlisted on the AST arming guard with two bounding keeper tests (payload-kwarg ban + frozen-lookup-key pin)"
    - "Response-shape normalization (bare object vs one-element array) mirrored from backend_status.py's 29-05 fix"
    - "Walk-the-input-rows join (never the response), duplicate-id refusal, unknown-id reporting — propose-then-confirm precedent extended to a match response"

key-files:
  created:
    - operator-claude-plugin/scripts/preingest.py
    - operator-claude-plugin/tests/test_preingest_match.py
  modified:
    - operator-claude-plugin/scripts/config_gate.py
    - operator-claude-plugin/tests/test_config_gate.py
    - operator-claude-plugin/tests/test_status_unknown.py
    - operator-claude-plugin/tests/test_retry_reuses_dispatch.py

key-decisions:
  - "fetch_matches folds a non-2xx status and an unreadable body into the same DispatchError a transport exception raises, rather than adapting chunking._StatusCapturingTransport (which wraps a module-shaped `.post()` transport — fetch_matches's transport is attribute-shaped, a bare callable, so the two wrapper shapes don't fit). match_batch then treats DispatchError and the backend's whole-batch refusal item identically: both mark the whole chunk unchecked."
  - "match_batch also lands on the AST arming guard's allowlist alongside fetch_matches — it carries the same transport=requests.post default because it threads the parameter straight through, never calling requests.post itself. Same predicate, same allowlisted read, not two exemptions; documented in the allowlist comment so a reader doesn't mistake it for a second finding."
  - "classify_matches's MEDIUM candidate output re-projects to exactly CANDIDATE_KEYS via a dict comprehension rather than passing the backend's dict through unmodified — defensive, so a backend response that ever widened would still be trimmed client-side to the six-key allowlist, never silently propagated."

requirements-completed: [STRUCT-04, PREVIEW-03, DISPATCH-03]

coverage:
  - id: D1
    description: "build_rows_spec mints one row_id per row, once, at the whole-batch level (deterministic, non-UUID sequence), refusing a pre-existing row_id and an empty list; fetch_matches is one unarmed, attribute-shaped POST per chunk carrying only MATCH_LOOKUP_KEYS, gated by config_gate's new 'match' capability, allowlisted on the AST arming guard with two bounding keeper tests."
    requirement: STRUCT-04
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_preingest_match.py (Task 1 section)"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_retry_reuses_dispatch.py (allowlist + two keepers)"
        status: pass
    human_judgment: false
  - id: D2
    description: "match_batch sends chunks sequentially, skipping a failing one and continuing; a transport failure, non-2xx status, unreadable body, or the backend's whole-batch refusal item all mark the whole chunk unchecked (never unmatched), carrying the backend's own reason where available; failed_batch is built through chunking.failed_batch for a re-sendable retry."
    requirement: PREVIEW-03
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_preingest_match.py (Task 2 section)"
        status: pass
    human_judgment: false
  - id: D3
    description: "classify_matches buckets every row into exactly one of four named groups joined by row_id (never by position), refusing a duplicated row_id and reporting (never attaching) an unknown one; a MEDIUM row with 2+ candidates is flagged ambiguous with nothing pre-selected; each candidate is projected to exactly the six shipped keys."
    requirement: DISPATCH-03
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_preingest_match.py (Task 3 section)"
        status: pass
    human_judgment: false

duration: 20min
completed: 2026-08-05
status: complete
---

# Phase 37 Plan 03: preingest.py — The Match Lane's Client Half Summary

**Rows get an id once, an unarmed match POST the AST guard can see and was told why to
exempt, and every answer HubSpot's match search can give — including its two ways of
declining to answer — comes back as its own distinguishable state.**

## Performance

- **Duration:** ~20 min
- **Completed:** 2026-08-05T09:10:42Z
- **Tasks:** 3/3
- **Files modified:** 6 (2 created, 4 modified)

## Accomplishments

- `preingest.build_rows_spec(rows)` mints one `row_id` per row at the whole-batch level,
  before any chunking, as a deterministic sequence (`row-1`, `row-2`, ...) rather than a
  UUID — a re-run over the same input is comparable to its predecessor. Refuses a row
  that already carries a `row_id` and refuses an empty list. Splitting the resulting spec
  into chunks and collecting every chunk's ids still yields as many distinct ids as input
  rows — the exact property a per-chunk `enumerate` would break.
- `preingest.fetch_matches(chunk, config, transport=requests.post)` is one POST per
  chunk, written attribute-shaped deliberately (mirroring `dispatch.py`, not
  `enrichment.py`'s module-shaped `dispatch_enrichment`) so it lands on
  `test_retry_reuses_dispatch.py`'s AST arming-guard allowlist by being visible to it,
  not by evading it. It takes no `armed` parameter at all — a match call sends an
  explicit empty provider selection, so it spends no credit and writes nothing HubSpot-side.
  Gated by a new `config_gate.CAPABILITY_KEYS["match"]` row (same two keys as
  `"enrichment"`, separate wording) so a missing `webhook_secret` refuses naming the
  match step, never "enriching records" or "uploading contacts". Normalizes a bare-object
  or one-element-array response body identically, mirroring `backend_status.py`'s 29-05
  fix for the same webhook host.
- `preingest.match_batch(plan, config, transport=requests.post)` mirrors
  `chunking.dispatch_plan`'s sequential, skip-a-failing-chunk contract with no arming
  concept at all. A transport failure, a non-2xx status, an unreadable body (all folded
  into `DispatchError` inside `fetch_matches` itself, since its attribute-shaped transport
  doesn't fit `chunking._StatusCapturingTransport`'s module-shaped wrapper), or the
  backend's whole-batch refusal item all mark every row id in that chunk `unchecked` —
  never `unmatched` — carrying the backend's own reason where one exists. The re-sendable
  failed batch is built through `chunking.failed_batch`, reusing the existing rows branch
  rather than re-deriving one.
- `preingest.classify_matches(rows, response, unchecked_row_ids=None)` buckets every row
  into exactly one of `auto_matched` / `proposed` / `unmatched` / `unchecked`, joined by
  `row_id` — walking the input rows (never the response) so a missing item is detectable
  rather than silently invisible. A duplicated `row_id` in the response raises
  `ClassifyError` rather than last-one-wins; an unknown `row_id` is reported in
  `unknown_response_row_ids`, never attached to a row. A MEDIUM row with two or more
  candidates is flagged `ambiguous` and nothing is pre-selected. Each candidate is
  projected to exactly the six keys the backend ships
  (`hs_object_id, firstname, lastname, email, jobtitle, company`) — no `lastmodifieddate`,
  and the id key stays `hs_object_id`. There is deliberately no handler for the backend's
  write-path-only `needs_match_review` action, no fifth bucket, and no branch on `action`
  at all — this client only ever sends the propose mode, so that action can never arrive
  in its own responses (verified in 36-04-SUMMARY.md).

## Task Commits

1. **Task 1: preingest.py — ids once, and one unarmed POST the guard can see** - `eee4400` (feat)
2. **Task 2: match_batch — a chunk that could not be looked at is unchecked** - `86b6755` (feat)
3. **Task 3: classify_matches — four groups, joined by id, nothing auto-picked** - `7924b5e` (feat)

_No separate plan-metadata commit — this SUMMARY and STATE.md updates are committed
together per `final_commit`._

## Files Created/Modified

- `operator-claude-plugin/scripts/preingest.py` — new module: `build_rows_spec`,
  `refused_reason`, `fetch_matches`, `MatchOutcome`, `match_batch`, `classify_matches`,
  `CANDIDATE_KEYS`, `RowSpecError`, `ClassifyError`
- `operator-claude-plugin/tests/test_preingest_match.py` — new test file, 36 tests across
  all three tasks
- `operator-claude-plugin/scripts/config_gate.py` — new `"match"` capability row +
  description
- `operator-claude-plugin/tests/test_config_gate.py` — `"match"` added to the hardcoded
  capability tuple in `test_empty_webhook_secret_still_refuses_contact_upload_by_name`
  (settles 37-RESEARCH Open Question 1: the existing test is not capability-name-agnostic,
  so extending its tuple is the change — no new subprocess harness needed)
- `operator-claude-plugin/tests/test_status_unknown.py` — Rule 3 fix: the new `"match"`
  capability row broke `test_a_fully_configured_config_passes_every_capability`'s own
  hardcoded capability set; extended it to include `"match"`
- `operator-claude-plugin/tests/test_retry_reuses_dispatch.py` — `fetch_matches` and
  `match_batch` allowlisted with reasoning; two new keeper tests
  (`test_the_allowlisted_match_post_carries_no_multipart_or_form_payload`,
  `test_match_lookup_keys_stays_the_frozen_four`)

## Decisions Made

- **Status/unreadable-body handling lives inside `fetch_matches`, not a second wrapper.**
  `chunking._StatusCapturingTransport` wraps a module-shaped `.post()` transport;
  `fetch_matches`'s transport is attribute-shaped (a bare callable) by design. Rather than
  writing a second status-capturing wrapper for a different transport shape,
  `fetch_matches` itself raises `DispatchError` on a non-2xx status or an unreadable body
  — the same exception class a transport exception raises — so `match_batch` treats all
  three the same way with one `except DispatchError` clause.
- **`match_batch` shares the AST guard allowlist entry with `fetch_matches`, not a second
  one.** It threads its own `transport=requests.post` default straight through to
  `fetch_matches` without ever calling `requests.post` itself, so the same guard predicate
  (`_has_send_shaped_transport_default`) flags it too. Documented in the allowlist comment
  so this reads as one allowlisted read, not two separate exemptions to track.
- **MEDIUM candidates are re-projected to `CANDIDATE_KEYS`, not passed through.** The
  backend already ships exactly six keys per candidate (36-01's own information-disclosure
  control), but `classify_matches` re-projects defensively via a dict comprehension rather
  than trusting the input shape — a future backend response that widened would still be
  trimmed to six keys client-side.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - blocking issue] Adding `config_gate.CAPABILITY_KEYS["match"]` broke an
existing test outside the plan's named files**

- **Found during:** Task 1, running `operator-claude-plugin/tests/ -q` after the capability
  row landed.
- **Issue:** `test_status_unknown.py::test_a_fully_configured_config_passes_every_capability`
  iterates its own hardcoded capability tuple and asserts
  `config_gate.usable_capabilities(fake_config)` equals it exactly — the new `"match"` row
  made that set one larger than the test's literal, so the test failed.
- **Fix:** Extended the hardcoded tuple (and its accompanying comment, in the same register
  as the existing per-capability history notes) to include `"match"`.
- **Files modified:** `operator-claude-plugin/tests/test_status_unknown.py`.
- **Verification:** `operator-claude-plugin/tests/ -q` returns to green (1123 passed / 5
  skipped) after the fix.
- **Committed in:** `eee4400` (Task 1).

---

**Total deviations:** 1 auto-fixed (Rule 3 — a test outside the plan's named files was a
downstream consequence of the plan's own capability-row change, not a scope expansion).

## Red-Check Failure Text (recorded per task's explicit instruction)

**Task 1:**
- (a) Removing the `preingest.py` allowlist entry from `_EXPECTED_SEND_SHAPED`:
  `test_exactly_one_module_defines_the_send_shaped_function` failed —
  `AssertionError: ... At index 3 diff: ('preingest.py', ['fetch_matches', 'match_batch']) != ('probe_n8n_semantics.py', ['execute_probe']) ... Left contains one more item: ('review_queue.py', ['fetch_queue'])`,
  naming `preingest.py`/`fetch_matches` as the found-but-unexpected offender.
- (b) Adding a fifth name (`"phone"`) to `enrichment.MATCH_LOOKUP_KEYS`:
  `test_match_lookup_keys_stays_the_frozen_four` failed —
  `AssertionError: MATCH_LOOKUP_KEYS changed to ('email', 'firstname', 'lastname', 'company', 'phone') — a match request would widen or narrow what crosses the boundary per row.`
- (c) Adding an `armed=False` parameter to `fetch_matches`: `inspect.signature` showed
  `['chunk', 'config', 'armed', 'transport']` — the no-armed-parameter assertion
  (`assert 'armed' not in params`) failed with `AssertionError: FAILS as expected: armed param found: ['chunk', 'config', 'armed', 'transport']`.
- (d) Simulating a per-chunk `enumerate` instead of `build_rows_spec`'s batch-level
  minting, over 5 rows split into chunks of 2: distinct ids collapsed from 5 to 2
  (`AssertionError: FAILS as expected: ids collide across chunks`), confirming the
  property `build_rows_spec`'s batch-level minting exists to prevent.

**Task 2:**
- Changing the refusal branch to fall through to the normal per-row parse:
  `test_the_backends_whole_batch_refusal_marks_the_whole_chunk_unchecked_with_its_own_reason`
  failed — `AssertionError: assert frozenset() == {'row-1', 'row-2'}` — the refusal item
  has no `row_id` to join on, so it silently vanished instead of marking the chunk
  unchecked.
- Relabelling the failure branch's field name from `unchecked_row_ids` to
  `unmatched_row_ids` (simulating the vocabulary swap): 5 tests failed with
  `AttributeError: 'MatchOutcome' object has no attribute 'unchecked_row_ids'. Did you mean: 'unmatched_row_ids'?`,
  confirming every assertion in the suite is anchored to the `unchecked` vocabulary, not
  incidentally passing.

**Task 3:**
- Replacing the `row_id` index lookup with a positional zip (`response[_i]`), then
  feeding a 3-row input against a 2-item response missing the middle row's item:
  `test_a_row_id_absent_from_the_response_buckets_unchecked_never_dropped` failed —
  `AssertionError: assert 'row-3' == 'row-2'` — row-2 silently received row-3's response
  item under positional alignment (the exact §12-rejected misalignment class), and a
  second test (`test_classify_matches_respects_a_pre_seeded_unchecked_set_from_match_batch`)
  failed the same way.
- Mapping the `unknown` tier onto the `unmatched` bucket:
  `test_unknown_tier_buckets_unchecked_never_unmatched` failed —
  `AssertionError: assert 0 == 1` — the unknown-tier row landed in `unmatched` instead of
  `unchecked`, confirming the vocabulary distinction is load-bearing in the test, not
  decorative.

## Issues Encountered

While red-checking Task 1's item (a) via a scripted removal-and-restore, an intermediate
`git checkout --` used to restore the test file reverted ALL of that file's uncommitted
edits for the session (the allowlist entry, the comment, and both keeper tests — none had
been committed yet), not just the temporary removal. All edits were reconstructed from the
same source and re-verified green before proceeding; no test was silenced or weakened as a
result. Later red-checks in this plan used targeted `Edit`/restore pairs instead of `git
checkout` to avoid repeating this.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- `preingest.build_rows_spec`, `fetch_matches`, `match_batch`, and `classify_matches` are
  the exact primitives 37-04's `apply_match_decisions` and `merge_enriched` are specified
  to build on — no further match-lane work is needed before that plan starts.
- Suite counts after this plan: `operator-claude-plugin/tests/ -q` → 1123 passed, 5
  skipped (baseline 1085/5); repo-root `.venv/bin/python -m pytest -q` → 2038 passed, 6
  skipped (baseline 2000/6); `node --test tests/n8n/*.test.mjs` → 621 pass, unchanged;
  arming grep → 0 for every file; `operator-claude-plugin/scratch` clean.
- No blockers for 37-04 through 37-06.

---
*Phase: 37-enrich-before-ingest*
*Completed: 2026-08-05*

## Self-Check: PASSED

All 6 files created/modified by this plan verified present on disk; all 3 commit hashes
(`eee4400`, `86b6755`, `7924b5e`) verified present in `git log --oneline --all`.
