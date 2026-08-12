---
phase: 48-enrichment-coverage
plan: 02
subsystem: n8n-enrichment-pipeline
tags: [n8n, workflow-as-code, error-handling, anthropic, control-flow]

requires:
  - phase: 47.5-veto-recompute-path
    provides: "_if_bool_expr_node builder, the IF Company Recompute/IF Company Skip
      gate-with-failure-branch idiom, the nodeAll try/catch precedent"
provides:
  - "IF Research Errored + Build Research Failure Response nodes in the built CLOUD
    enrichment workflow (n8n/wf_enrichment_cloud.json), closing D-04"
  - "tests/n8n/researchErrorGateFlow.test.mjs -- offline proof the gate's real emitted
    expression and the failure terminal's real jsCode behave as specified"
affects: [48-04-PLAN, 48-05-PLAN, 48-06-PLAN]

actuals:
  tokens: 72000
  tasks: 3
  commits: 3

tech-stack:
  added: []
  patterns:
    - "Gate-with-recovery-terminal, not gate-with-bare-passthrough: unlike IF Company
      Skip (which wires its true lane straight to Build Response because its item
      already carries action/hs_object_id/gate), IF Research Errored's true lane is
      the raw HTTP node output with none of those fields -- a recovery Code node
      (Build Research Failure Response) sits between the gate and Build Response,
      reusing Validate Research Output's own $('Build Research Request').all()
      try/catch idiom to recover identity before the row reaches the response builder"
    - "Bare $json is correct immediately downstream of an HTTP node: IF Research
      Errored reads $json.error/$json.content with no $() node-name lookup, safe
      because nothing sits between it and Claude Web Research to have replaced the
      item -- same reasoning IF Company Skip's own comment gives for its bare
      $json.action read"

key-files:
  created:
    - tests/n8n/researchErrorGateFlow.test.mjs
  modified:
    - scripts/build_cloud_workflows.py
    - n8n/wf_enrichment_cloud.json
    - tests/test_remaining_credits_response.py

key-decisions:
  - "Only the CLOUD build site (the one producing n8n/wf_enrichment_cloud.json) got the
    D-04 gate. The second Claude Web Research build site (~line 3214) that feeds
    wf_enrichment_local_live.json was deliberately left unchanged -- confirmed by
    grepping the local_live output for the new node name (zero matches) after the
    rebuild. It is a local dev harness with mocked HubSpot, never deployed, and D-04's
    stated target is the production lane. This is a knowing divergence, not an
    oversight."
  - "The failure terminal needed a recovery Code node, not a direct wire to Build
    Response. IF Research Errored's true-lane item is the raw HTTP-node output
    ({error:{...}}), carrying none of the action/hs_object_id/gate fields Build
    Response's pass-through-plus-credits shape assumes -- unlike IF Company Skip's
    true lane, whose upstream Code node already carries those fields. Build Research
    Failure Response recovers the pre-HTTP row by node name from 'Build Research
    Request', the identical try/catch idiom Validate Research Output already uses."
  - "The gate is built, tested, and committed but NOT yet running anywhere. Deploy +
    bounce is operator-only (plan 48-04's checkpoint) -- neither ALLOW_N8N_DEPLOY nor
    DRY_RUN=false was set at any point in this plan, and no n8n execution was made."

patterns-established:
  - "Pattern: extend, never relax, an exact-equality convergence-set test when a new
    terminal legitimately joins a shared sink. tests/test_remaining_credits_response.py's
    BUILD_RESPONSE_SOURCES asserts the exact set of nodes feeding Build Response; this
    plan's new terminal required adding one tuple, not loosening the assertion to a
    subset/superset check."

requirements-completed: []  # COVER-01/COVER-02 are D-02-split across Phase 47+48; neither
  # phase closes them alone (REQUIREMENTS.md). This plan hardens the research lane against
  # a class of false-coverage risk (D-04) but does not itself write lv_org_type or close
  # the requirement -- that is 48-03 (Racing NSW research) / 48-05/48-06 (writes + report).

coverage:
  - id: D1
    description: "An error-shaped payload leaving Claude Web Research (the live-observed
      Anthropic 400 shape from exec 11833) is routed to IF Research Errored's true lane
      and never reaches Validate Research Output / Merge Company / Decide Company Action."
    verification:
      - kind: unit
        ref: "tests/n8n/researchErrorGateFlow.test.mjs -- \"IF Research Errored's REAL expression returns true on the live-observed error shape\""
        status: pass
      - kind: unit
        ref: "tests/n8n/researchErrorGateFlow.test.mjs -- \"the wiring routes true->failure terminal, false->Validate Research Output, unchanged\""
        status: pass
    human_judgment: false
  - id: D2
    description: "The failure terminal's response row carries recovered company identity
      plus action:\"research_failed\" and a stated gate.reason, not a bare Anthropic error
      blob -- and fails closed (still reports research_failed) if the pre-HTTP row lookup
      itself throws."
    verification:
      - kind: unit
        ref: "tests/n8n/researchErrorGateFlow.test.mjs -- \"Build Research Failure Response recovers the pre-HTTP row and states the error reason\""
        status: pass
      - kind: unit
        ref: "tests/n8n/researchErrorGateFlow.test.mjs -- \"Build Research Failure Response fails closed when $('Build Research Request') throws\""
        status: pass
    human_judgment: false
  - id: D3
    description: "A healthy research response is routed down the false lane unchanged --
      the gate is additive, no existing behaviour altered -- and a degenerate/empty
      payload fails closed (treated as errored, never guessed as a match)."
    verification:
      - kind: unit
        ref: "tests/n8n/researchErrorGateFlow.test.mjs -- \"IF Research Errored's REAL expression returns false on a healthy shape\""
        status: pass
      - kind: unit
        ref: "tests/n8n/researchErrorGateFlow.test.mjs -- \"IF Research Errored's REAL expression returns true on a degenerate shape (fail closed)\""
        status: pass
      - kind: unit
        ref: "tests/n8n/researchErrorGateFlow.test.mjs -- \"a healthy research response still reaches Validate Research Output's real jsCode\""
        status: pass
    human_judgment: false
  - id: D4
    description: "n8n/wf_enrichment_cloud.json is regenerated from the builder (never
      hand-edited) and byte-reproducible -- a second builder run leaves git diff --stat
      n8n/ empty. The offline test evaluates the node's REAL emitted expression/jsCode,
      never a hand-copied string."
    verification:
      - kind: unit
        ref: "manual command: .venv/bin/python scripts/build_cloud_workflows.py && git diff --stat n8n/ (empty after staging)"
        status: pass
      - kind: unit
        ref: "tests/n8n/researchErrorGateFlow.test.mjs -- expression/jsCode both read from n8n/wf_enrichment_cloud.json at runtime, no literal restatement outside comments"
        status: pass
    human_judgment: false
  - id: D5
    description: "No second writer of lv_anti_icp_flag/lv_anti_icp_reason was introduced,
      and the recompute-lane's existing regression test stays green -- no node rename or
      connection-map collision from this plan's insertion."
    verification:
      - kind: unit
        ref: "tests/n8n/companyRecomputeLaneFlow.test.mjs (unchanged, run as part of node --test tests/n8n/*.test.mjs: 673/673 pass)"
        status: pass
      - kind: unit
        ref: ".venv/bin/python -m pytest (single-veto-writer conformance tests, part of the 2626-pass full suite)"
        status: pass
    human_judgment: false

duration: ~20min
completed: 2026-08-12
status: complete
---

# Phase 48 Plan 02: Research-Error Gate (D-04) Summary

**Landed `IF Research Errored` + `Build Research Failure Response` in the CLOUD enrichment workflow builder, closing the folded todo where an Anthropic 400 (e.g. credit exhaustion) silently flowed downstream as data instead of failing the research call -- built, rebuilt, and offline-tested; not deployed.**

## Performance

- **Duration:** ~20 min
- **Completed:** 2026-08-12
- **Tasks:** 3
- **Files modified:** 4 (`scripts/build_cloud_workflows.py`, `n8n/wf_enrichment_cloud.json`, `tests/n8n/researchErrorGateFlow.test.mjs` new, `tests/test_remaining_credits_response.py`)

## Accomplishments

- Inserted `IF Research Errored` (built via the existing `_if_bool_expr_node` helper) and
  `Build Research Failure Response` (a Code node) into the CLOUD enrichment workflow
  builder, between the existing `Claude Web Research` HTTP node and `Validate Research
  Output` -- the single pre-existing edge was replaced, not duplicated.
- `IF Research Errored` reads bare `$json.error`/`$json.content` -- correct immediately
  downstream of the HTTP node, no `$()` lookup, so it does not touch the `ENRICH_CO_GATE`
  shared-workflow trap.
- `Build Research Failure Response` recovers the pre-HTTP row by node name from `Build
  Research Request`, the identical try/catch idiom `Validate Research Output` already
  uses, so the response reaching `Build Response` carries `action: "research_failed"`,
  `gate.reason` (the Anthropic error message, or a fixed fallback), and the recovered
  company identity -- the same shape every other terminal produces.
- Rebuilt `n8n/wf_enrichment_cloud.json` from the builder and confirmed byte-reproducible
  (a second builder run left `git diff --stat n8n/` empty after staging).
- Confirmed `n8n/wf_enrichment_local_live.json` carries zero `IF Research Errored`
  occurrences -- the knowing scope decision to leave that build site untouched held.
- Wrote `tests/n8n/researchErrorGateFlow.test.mjs`, modelled directly on
  `tests/n8n/companyRecomputeLaneFlow.test.mjs`: evaluates the gate's REAL emitted
  expression (extracted from the built JSON, never hand-copied) against the live-observed
  error shape (exec 11833), a healthy shape, and a degenerate shape; drives the failure
  terminal's REAL jsCode through the faked-`$()` harness for both the identity-recovery
  case and the fails-closed-on-throw case; asserts the four specified edges; confirms
  `companyRecomputeLaneFlow.test.mjs` stays green.

## Task Commits

Each task was committed atomically:

1. **Task 1: Build the IF Research Errored gate and its failure terminal in the cloud lane** - `08128d3` (feat)
2. **Task 2: [BLOCKING] Regenerate the committed workflow JSON from the builder** - `3a1edf1` (feat)
3. **Task 3: Offline structural test driving the gate's REAL emitted expression** - `5fc157c` (test) -- includes the Rule 1 fix to `tests/test_remaining_credits_response.py`

## Files Created/Modified

- `scripts/build_cloud_workflows.py` - CLOUD-only builder edit: `IF Research Errored` +
  `Build Research Failure Response` node construction, and the rewired `Claude Web
  Research` -> `IF Research Errored` -> (true) `Build Research Failure Response` -> `Build
  Response` / (false) `Validate Research Output` connections
- `n8n/wf_enrichment_cloud.json` - regenerated build output, no hand edits
- `tests/n8n/researchErrorGateFlow.test.mjs` - new offline structural test (7 assertions
  across the gate expression, the failure terminal, and the wiring)
- `tests/test_remaining_credits_response.py` - `BUILD_RESPONSE_SOURCES` extended with the
  new terminal, exact-equality preserved

## Decisions Made

- **The local_live build site is deliberately unchanged.** `scripts/build_cloud_workflows.py`
  has two `Claude Web Research` build sites: the LOCAL LIVE workflow (~line 3214, feeding
  `wf_enrichment_local_live.json`) and the CLOUD workflow (~line 4770, feeding
  `wf_enrichment_cloud.json`). D-04's own text names the CLOUD lane as its target; the
  local_live site is a headless dev harness with mocked HubSpot, never deployed. Confirmed
  by grep after rebuild: `wf_enrichment_local_live.json` has zero `IF Research Errored`
  occurrences.
- **A recovery Code node was required, not a direct wire to `Build Response`.**
  `IF Company Skip`'s true lane wires straight to `Build Response` because its upstream
  Code node's item already carries `action`/`hs_object_id`/`gate`. `IF Research Errored`'s
  true-lane item is the raw HTTP-node output (`{error: {...}}`), missing all three. `Build
  Research Failure Response` closes that gap by recovering the pre-HTTP row from `Build
  Research Request`, exactly as `Validate Research Output` already does for the false lane.
- **Nothing was deployed, armed, or bounced.** This plan's scope ends at a committed,
  rebuilt, offline-tested artifact. `ALLOW_N8N_DEPLOY` was never set; `DRY_RUN` was never
  set to `false`; no `scripts/deploy_n8n_workflows.py` invocation was made. The gate exists
  in the committed JSON but is not running anywhere yet -- that is plan 48-04's checkpoint.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Extended `BUILD_RESPONSE_SOURCES`'s exact-equality convergence set**
- **Found during:** Task 3 (running the full pytest suite as required by the plan's
  `<verification>` bar)
- **Issue:** `tests/test_remaining_credits_response.py::test_build_response_is_reachable_from_every_terminal_branch`
  asserts an EXACT set of `(node, branchIndex)` tuples feeding `Build Response`. This
  plan's new `Build Research Failure Response` -> `Build Response` edge is exactly the
  kind of new terminal that test exists to catch drifting silently -- it failed as
  designed, not as a bug in the new code.
- **Fix:** Added `("Build Research Failure Response", 0)` to `BUILD_RESPONSE_SOURCES`,
  preserving exact-equality (not relaxed to a subset/superset check), with a comment
  explaining why the new terminal belongs there -- mirroring the file's own precedent
  comment for the Phase 47.5 `("IF Company Skip", 0)` addition.
- **Files modified:** `tests/test_remaining_credits_response.py`
- **Verification:** `.venv/bin/python -m pytest tests/test_remaining_credits_response.py`
  -- 15 passed; full suite `.venv/bin/python -m pytest` -- 2626 passed, 128 skipped, 0 failed
- **Committed in:** `5fc157c` (Task 3 commit)

---

**Total deviations:** 1 auto-fixed (1 pre-existing test correctly caught the new
convergence edge)
**Impact on plan:** No code behavior changed; the fix is exactly the extension the plan's
own must_haves anticipated ("the single existing edge is replaced, not duplicated" for the
builder; this is the equivalent statement for the offline convergence guard). No scope
creep.

## Issues Encountered

None beyond the deviation above.

## User Setup Required

None - no external service configuration required. This plan performed zero live network
calls, zero HubSpot reads/writes, zero n8n executions, and zero deploys.

## Next Phase Readiness

- The gate is built, rebuilt into the committed `n8n/wf_enrichment_cloud.json`, and
  proven offline against the live-observed error shape, a healthy shape, and a degenerate
  shape. It is NOT yet running in the deployed instance -- plan 48-04 owns the operator
  deploy+bounce.
- Per CONTEXT.md's own framing (D-04's "not yet built or tested this session" note in
  48-RESEARCH.md is now resolved): structural presence + offline expression evaluation is
  the achievable bar this phase. This plan does not, and cannot, claim the gate FIRES live
  -- there is no way to force an Anthropic 400 on demand this session, and no execution in
  this plan touched the research branch at all.
- `tests/n8n/companyRecomputeLaneFlow.test.mjs` (Phase 47.5's regression guard) stays
  green -- no node rename or connection-map collision from this plan's insertion.
- No blockers for 48-03 (Racing NSW's fresh research call, unaffected by this plan -- it
  runs through the standalone Python `src/web_research.py` path, not through n8n) or
  48-04 (the operator deploy this plan's gate is waiting on).

## Self-Check: PASSED

All 5 claimed files found on disk (`scripts/build_cloud_workflows.py`,
`n8n/wf_enrichment_cloud.json`, `tests/n8n/researchErrorGateFlow.test.mjs`,
`tests/test_remaining_credits_response.py`, this SUMMARY). All 3 task commit hashes
(`08128d3`, `3a1edf1`, `5fc157c`) found in `git log --oneline --all`.

---
*Phase: 48-enrichment-coverage*
*Completed: 2026-08-12*
