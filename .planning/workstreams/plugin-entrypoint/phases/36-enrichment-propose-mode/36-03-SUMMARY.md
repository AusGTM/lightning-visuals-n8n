---
phase: 36-enrichment-propose-mode
plan: 03
subsystem: infra
tags: [n8n, hubspot, code-node, workflow-builder, mode-threading, dos-guard]

# Dependency graph
requires:
  - phase: 36-enrichment-propose-mode
    plan: "02"
    provides: "the MEDIUM match lane, a match verdict on every contacts row, Enrichment Gate's unmatchable-row skip"
provides:
  - "parseWebhookBody() returning { events, providers, mode } — mode read at the envelope level, threaded onto every row via Parse HubSpot Event"
  - "Skip (NoOp) and Unsupported Object Type as row-carrying Code nodes, both ROW_REPLACING_BY_DESIGN waivers retired"
  - "Parse HubSpot Event refuses an events array above ENRICH_MAX_LIST_RECORDS, or of length zero, as a single terminating item routed to the caller as a 200"
provides_downstream: [36-04-response-shape, 37-client-chunking]

# Actuals (#2632)
actuals:
  tokens: 161145
  tasks: 3
  commits: 3

tech-stack:
  added: []
  patterns:
    - "Deferred placeholder substitution: ENRICH_PARSE_EVENT_CLOUD's __MAX_LIST_RECORDS__ token is replaced in a SECOND .replace() call chained after ENRICH_MAX_LIST_RECORDS is declared (which sits after the constant in file order) — no second ceiling constant, no reordering of either declaration"
    - "A refusal is a single terminating item carrying outcome:\"refused\"/reason/events:[], never a thrown exception — mirrors ENRICH_EXPAND_LIST_TO_EVENTS's shape exactly, reusing the existing IF Object Type Supported false edge (object_type:\"unknown\") so zero new nodes or edges are needed to route the reason to the caller"
    - "Set->Code conversion for a terminal marker keeps the node NAME identical and follows ENRICH_SET_DQ_JS's precedent ({ json: { ...it.json, <marker field> } }) so connections and NODE_CREDENTIAL_MAP keys (n/a for these two) resolve unchanged"

key-files:
  created:
    - tests/n8n/enrichmentBatchRefusal.test.mjs
  modified:
    - n8n/code/providerSelection.js
    - scripts/build_cloud_workflows.py
    - n8n/wf_enrichment_cloud.json
    - n8n/wf_backend_status_cloud.json
    - tests/n8n/providerSelection.test.mjs
    - tests/test_row_carry.py
    - tests/test_enrichment_lane_dedup.py

key-decisions:
  - "mode is extracted inside parseWebhookBody() itself (RESEARCH.md sec D.1 option 1), not read ad hoc inside ENRICH_PARSE_EVENT_CLOUD's wrapper — providers is the one other envelope-level field this webhook already supports, and it's read here; keeps both fields consistent for future readers"
  - "The size guard lives IN Parse HubSpot Event's own wrapper, not a separate node like Expand List To Events — that node's separate placement guards against a MISSING events array being masked by parseWebhookBody's bare-event fallback; an oversized or empty array still IS an array, so the fallback never masks either case and a separate node buys nothing (RESEARCH.md sec F Open Question 2, resolved)"
  - "n8n/wf_backend_status_cloud.json picked up an incidental diff (doc-comment/function-body text only) because ENRICH_STATUS_BUILD_RESPONSE also inlines providerSelection.js — no behavior change, included in Task 1's commit since it's a direct consequence of the same module edit"
  - "Task 1's Decide Action write-guard predicate (action:\"proposed\" before _writeSafetyAllows) is explicitly OUT of this plan's scope per the plan's own must_haves (T-36-15's mitigation names plan 36-04) — this plan only threads mode onto the row; the predicate that reads it lands next"

patterns-established:
  - "Node-level behavioral test evaluates the repo's OWN committed jsCode via new Function against event arrays of varying length, mirroring bareEventChainFlow.test.mjs's harness idiom rather than extracting the guard into a separate pure module (parseWebhookBody's contract is not moved)"

requirements-completed: [PREVIEW-03, DISPATCH-02, STRUCT-04]

coverage:
  - id: D11
    description: "parseWebhookBody(body) returns { events, providers, mode }; mode is read at the envelope level with the identical guard/undefined-default idiom providers already uses, and is undefined for a bare event array, an envelope with no mode key, null, and undefined"
    requirement: STRUCT-04
    verification:
      - kind: unit
        ref: "tests/n8n/providerSelection.test.mjs (8 new mode cases)"
        status: pass
    human_judgment: false
  - id: D12
    description: "Parse HubSpot Event stamps mode: parsed.mode ?? event.mode ?? null onto every row, placed before the ...event spread so a caller-supplied event field can still override it; mode absent produces byte-identical rows to today"
    requirement: DISPATCH-02
    verification:
      - kind: structural
        ref: ".venv/bin/python -c \"...assert 'parsed.mode' in n['Parse HubSpot Event']['parameters']['jsCode']\""
        status: pass
      - kind: regression
        ref: ".venv/bin/python -m pytest -q (1951/6, no new failures vs 1947/6 baseline)"
        status: pass
    human_judgment: false
  - id: D13
    description: "Skip (NoOp) and Unsupported Object Type are n8n-nodes-base.code nodes that spread the inbound row under their original names; both ROW_REPLACING_BY_DESIGN waivers are removed in the same commit"
    requirement: DISPATCH-02
    verification:
      - kind: structural
        ref: "tests/test_row_carry.py (7 tests, including test_every_row_replacing_entry_is_still_a_real_node_somewhere)"
        status: pass
    human_judgment: false
  - id: D14
    description: "An events array longer than ENRICH_MAX_LIST_RECORDS is refused whole (one terminating item, outcome:refused, events:[]); exactly-at-the-limit is accepted; an empty events array is refused with its own reason; both refusal branches route through the existing IF Object Type Supported false edge to Build Response with zero new nodes or edges"
    requirement: PREVIEW-03
    verification:
      - kind: structural
        ref: "tests/test_enrichment_lane_dedup.py (4 new tests: oversize refusal, empty refusal, single-ceiling-constant, existing-edge routing)"
        status: pass
      - kind: unit
        ref: "tests/n8n/enrichmentBatchRefusal.test.mjs (length 0/1/2/3 + bare-array behavioral cases, executed against the committed jsCode via new Function)"
        status: pass
    human_judgment: false

duration: ~40min
completed: 2026-08-05
status: complete
---

# Phase 36 Plan 03: Mode Threading, Row-Carrying Terminals, Batch-Size Refusal Summary

**`mode` now rides every enrichment row from the envelope to `Decide Action`, both terminal
markers return a correlatable `row_id` instead of dropping it, and an oversize or empty `events`
array is refused whole with a reason instead of being silently truncated or hanging the webhook.**

## Performance

- **Duration:** ~40 min
- **Tasks:** 3/3 completed
- **Files modified:** 8 (1 new test file; 2 `n8n/*.json` regenerated via the builder, never
  hand-edited)

## Accomplishments

- **Task 1 — `mode` reaches the row:** `parseWebhookBody()` now extracts `mode` at the
  envelope level with the identical guard/undefined-default idiom `providers` already
  uses (`(body && !Array.isArray(body)) ? body.mode : undefined`). `Parse HubSpot Event`
  stamps `mode: parsed.mode ?? event.mode ?? null` onto every row, placed before the
  `...event` spread so a caller-supplied event field can still override it — mirroring
  the `providersRaw` fallback idiom exactly. 8 new RED-then-GREEN test cases in
  `tests/n8n/providerSelection.test.mjs` cover the envelope, absent, bare-array, explicit
  `"write"`, `null`/`undefined`, and single-bare-event-carrying-mode shapes, plus a
  byte-identical-outputs regression case.
- **Task 2 — row-carrying terminals:** `Skip (NoOp)` and `Unsupported Object Type` were
  `n8n-nodes-base.set` (typeVersion 3.4), which emits only its assigned key. Both are now
  `n8n-nodes-base.code` nodes under identical names, spreading `{ ...it.json, <marker> }`
  — mirroring `ENRICH_SET_DQ_JS`'s precedent for the same BUG 12 class. Both
  `ROW_REPLACING_BY_DESIGN` waivers in `tests/test_row_carry.py` were removed in the same
  commit; the other three entries are untouched. Every connection edge resolves unchanged
  (n8n connections are keyed by name).
- **Task 3 — batch-size refusal:** `Parse HubSpot Event`'s wrapper now guards
  `parsed.events.length` against `ENRICH_MAX_LIST_RECORDS` (strictly greater-than —
  exactly-at-the-limit is accepted) and against zero, immediately after
  `parseWebhookBody(body)` and before the per-event `.map()`. Either condition returns a
  single terminating item (`outcome: "refused"`, `reason`, `events: []`,
  `object_type: "unknown"`), never a thrown exception and never a partial map — reusing
  the existing `IF Object Type Supported` false edge into `Unsupported Object Type` ->
  `Build Response`, so the reason reaches the caller as a 200 with zero new nodes or
  edges. Implemented in-node (not a separate node like `Expand List To Events`): an
  oversized or empty array is still an array, so `parseWebhookBody`'s bare-event fallback
  never masks either case. The ceiling constant is read via a deferred placeholder
  substitution chained after `ENRICH_MAX_LIST_RECORDS`'s single declaration — no second
  ceiling constant exists.
- Every new/amended assertion red-checked individually: Task 1's builder edit reverted
  and restored; Task 2's waiver-dict-without-type-change and node-type-without-waiver
  directions both confirmed failing independently; Task 3's `>=` flip and
  zero-length-branch removal both confirmed failing across both pytest and node test
  layers.
- No deviations from the plan — all three tasks executed exactly as written.

## Task Commits

Each task was committed atomically:

1. **Task 1: mode threading** — `8fb114b` (feat: parseWebhookBody mode extraction,
   Parse HubSpot Event mode stamp, 8 new node tests)
2. **Task 2: row-carrying terminals** — `1d82fc0` (feat: Skip (NoOp) /
   Unsupported Object Type Set->Code conversion, waiver retirement)
3. **Task 3: batch-size refusal** — `5711cf4` (feat: oversize/empty events-array refusal,
   4 new pytest structural tests, 5 new node behavioral tests)

## Files Created/Modified

- `n8n/code/providerSelection.js` — `parseWebhookBody()` gains `mode`; doc-comment
  contract extended
- `scripts/build_cloud_workflows.py` — `ENRICH_PARSE_EVENT_CLOUD`'s `mode` stamp and
  size-refusal guard; `ENRICH_UNSUPPORTED_OBJECT_TYPE_JS` / `ENRICH_SKIP_NOOP_JS`
  constants replacing the two `Set` node build dicts; deferred
  `__MAX_LIST_RECORDS__` substitution chained after `ENRICH_MAX_LIST_RECORDS`
- `n8n/wf_enrichment_cloud.json`, `n8n/wf_backend_status_cloud.json` — regenerated via
  the builder (never hand-edited); the backend-status file picked up an incidental
  doc-comment diff because it also inlines `providerSelection.js`
- `tests/n8n/providerSelection.test.mjs` — 8 new `mode` extraction cases
- `tests/n8n/enrichmentBatchRefusal.test.mjs` — new file: length 0/1/2/3 + bare-array
  behavioral cases against the committed `jsCode`
- `tests/test_row_carry.py` — two waiver entries removed, comment recording why
- `tests/test_enrichment_lane_dedup.py` — 4 new structural tests for the size refusal

## Decisions Made

- `mode` extraction lives inside `parseWebhookBody()` itself, matching where `providers`
  is already read, rather than being read ad hoc inside `ENRICH_PARSE_EVENT_CLOUD`'s
  wrapper (RESEARCH.md sec D.1 option 1 — the more idiomatic fix).
- The size guard is in-node inside `Parse HubSpot Event`, not a separate node — the
  masking risk that forced `Expand List To Events` into its own node (a missing `events`
  array silently becoming a bare-event fallback) does not apply to an oversized or empty
  array, which is still an array.
- Decide Action's `action:"proposed"` write-guard predicate is deliberately NOT built in
  this plan — it is plan 36-04's job per the plan's own `must_haves`/threat register
  (T-36-15). This plan only threads `mode` onto the row so 36-04 can read it.

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None blocking. `n8n/wf_backend_status_cloud.json` picked up an incidental (non-functional,
doc-comment-only) diff in Task 1 because it shares the `inline("providerSelection.js")`
call with `ENRICH_BUILD_RESPONSE` and `ENRICH_PARSE_EVENT_CLOUD` — noted rather than
worked around, since it is a genuine regeneration output, not a hand-edit.

## User Setup Required

None — no external service configuration required. This plan makes zero live/deploy
changes; `scripts/deploy_n8n_workflows.py` was not run (denied to agents per this phase's
constraints).

## Next Phase Readiness

- Every enrichment row now carries `mode` (`null`/`"write"`/`"propose"`/any caller value)
  from `Parse HubSpot Event` through every downstream hop via the existing `...row`
  spread discipline — 36-04 (propose-mode dispatch) can read `row.mode` at `Decide
  Action`/`Decide Company Action` without any further plumbing.
- Both terminal markers return `row_id` on every path, so a HIGH-matched fresh row that
  gets skipped or an unsupported-object-type row are both correlatable replies.
- An oversize or empty `events` array can never reach the enrichment chain — 36-04 and
  Phase 37's client-side chunking build on a server that already refuses whole.
- Verification suites green against baselines: `.venv/bin/python -m pytest -q` -> 1951
  passed / 6 skipped (baseline 1947/6, +4 new this plan — Task 3's structural tests; Task
  1's 8 node tests and Task 3's 5 node tests are `.mjs`, not counted here).
  `node --test tests/n8n/*.test.mjs` -> 598 passing (baseline 585, +13 new: 8 mode cases +
  5 refusal-behavioral cases). `.venv/bin/python -m pytest operator-claude-plugin/tests/ -q`
  -> 1052 passed / 5 skipped (unchanged — this phase touches no plugin file).
  `grep -c 'ALLOW_HUBSPOT_[A-Z_]* = "true"' n8n/*.json` -> 0 for every file. Builder
  idempotent — a second `scripts/build_cloud_workflows.py` run leaves `git diff --stat n8n/`
  empty. No blockers for 36-04.

## Self-Check: PASSED

- FOUND: `.planning/workstreams/plugin-entrypoint/phases/36-enrichment-propose-mode/36-03-SUMMARY.md`
- FOUND commit: `8fb114b`
- FOUND commit: `1d82fc0`
- FOUND commit: `5711cf4`

---
*Phase: 36-enrichment-propose-mode*
*Completed: 2026-08-05*
