---
phase: 73-ga-fix-list-from-stress-attempt-2
plan: 05
subsystem: n8n-backend-status-lane, operator-plugin-cost-guard
tags: [n8n, carry-merge, write-grant, cost-guard, tdd]
requires:
  - phase: 73-ga-fix-list-from-stress-attempt-2 (plans 01-04)
    provides: the earlier waves' fixes to the ingest/company-match/review/throttle lanes this plan's cost-envelope work sits beside
provides:
  - the backend-status lane's balances/credential_health surviving the full carry-merge chain to Build Status (F-B6, wiring gap, fixed)
  - a real per-lane cost model on plan_grant()/envelope() (cost_lane: contact-upload / companies / enrich-before-ingest) wired into every SKILL.md call site and authorize_ungranted_send
affects: [73-06, 73-07, any future skill that opens a write grant]
actuals:
  tokens: 10724
  tasks: 2
  commits: 3
tech-stack:
  added: []
  patterns:
    - "graph-level offline walk (walkWorkflow.mjs) as the diagnostic instrument for a carry-merge wiring defect, before any code change (RESEARCH Pitfall 4)"
    - "cost_lane as a deliberately distinct parameter name from this file's pervasive lane/lanes (arming) vocabulary, after the collision was caught live in a RED run"
key-files:
  created:
    - tests/n8n/backendStatusCredits.test.mjs
  modified:
    - scripts/build_cloud_workflows.py
    - n8n/wf_backend_status_cloud.json
    - operator-claude-plugin/scripts/write_grant.py
    - operator-claude-plugin/tests/conftest.py
    - operator-claude-plugin/tests/test_cost_guard.py
    - operator-claude-plugin/tests/test_write_grant.py
    - tests/test_backend_status_workflow.py
    - operator-claude-plugin/skills/contact-upload/SKILL.md
    - operator-claude-plugin/skills/enrich-before-ingest/SKILL.md
    - operator-claude-plugin/skills/enrich-records/SKILL.md
key-decisions:
  - "F-B6 verdict: WIRING GAP, not deploy-parity. The committed graph itself dropped `balances` — proven by an offline walk before any fix, per RESEARCH Pitfall 4."
  - "New cost-pricing parameter named `cost_lane`, not `lane` — this file already uses `lane` pervasively for the ARMING lane vocabulary (covers(), authorize_send(), check_before_send(), authorize_ungranted_send(), plan_grant's own for-loop); a first attempt using `lane` was silently clobbered by that loop's leftover value, caught live in a RED run before the rename."
  - "contact-upload's execution projection corrected mid-plan from chunk_count to a literal 1, after confirming against dispatch.py that this lane makes exactly one multipart POST per send regardless of row count (watch.recover_dispatch(..., expected_chunk_count=1, ...) is hardcoded, not computed)."
  - "cost_lane is wired into every real caller (three SKILL.md files plus authorize_ungranted_send), not left as a dead API parameter no production path exercises."
patterns-established:
  - "A cost lane and an arming lane are independent, orthogonal identities a grant can name at once — never assume one vocabulary covers both."
requirements-completed: [F-B6, F-A1, F-A2, F-B1]
coverage:
  - id: D1
    description: "F-B6 fixed — backend-status lane's balances/credential_health survive the carry-merge chain to Build Status"
    requirement: F-B6
    verification:
      - kind: unit
        ref: "tests/n8n/backendStatusCredits.test.mjs"
        status: pass
      - kind: unit
        ref: "tests/test_backend_status_workflow.py::test_build_credit_status_only_outbound_feeds_the_hubspot_count_search_chain"
        status: pass
    human_judgment: false
  - id: D2
    description: "contact-upload grant prices zero provider credits and exactly one execution per POST"
    requirement: F-A1
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_write_grant.py::test_envelope_contact_upload_lane_prices_zero_provider_credits_and_one_execution_per_post"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_write_grant.py::test_envelope_contact_upload_lane_stays_one_execution_even_when_chunk_count_exceeds_one"
        status: pass
    human_judgment: false
  - id: D3
    description: "contact-upload figure equals the preview's figure for the identical send"
    requirement: F-A2
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_write_grant.py::test_envelope_contact_upload_figure_equals_the_previews_figure_for_the_identical_send"
        status: pass
    human_judgment: false
  - id: D4
    description: "a companies grant prices Lusha at the measured companies-match rate, not the contacts rate"
    requirement: F-B1
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_write_grant.py::test_envelope_companies_lane_prices_lusha_at_the_companies_match_rate_not_the_contacts_rate"
        status: pass
    human_judgment: false
  - id: D5
    description: "cost_lane wired into every real operator-facing call site (three SKILL.md files, authorize_ungranted_send)"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_write_grant.py::test_authorize_ungranted_send_threads_the_cost_lane_through_to_plan_grant"
        status: pass
    human_judgment: true
    rationale: "the SKILL.md edits are prose+snippet instructions a future Claude session follows, not executed code — a Python test can pin authorize_ungranted_send's own forwarding but cannot prove a human/Claude will read and honor the updated snippet text at send time; that is 73-07's or a live UAT's job"
duration: 90min
completed: 2026-09-16
status: complete
---

# Phase 73 Plan 05: Real balances and honest per-lane cost arithmetic Summary

**Fixed a carry-merge wiring bug that dropped the backend-status lane's provider balances entirely, and gave the write-grant cost envelope a real per-lane rate/execution model wired into every place that opens a grant.**

## Performance
- **Duration:** ~90 min - **Started:** 2026-09-16 - **Completed:** 2026-09-16 - **Tasks:** 2 (plus one advisor-driven follow-up) - **Files modified:** 13 (2 created, 11 modified)

## Accomplishments
- Diagnosed F-B6 offline first (RESEARCH Pitfall 4): wrote `tests/n8n/backendStatusCredits.test.mjs`, a graph-level walk of the COMMITTED `n8n/wf_backend_status_cloud.json`, and observed it RED against the unmodified graph — proving the defect lives in the wiring, not in a stale live deploy.
- Fixed the one-line root cause: `splice_carry_merge_after`'s carry_source for the first HS-search carry merge named `"ZoomInfo Usage Result Carry Merge"` (the item that FEEDS `"Build Credit Status"`, one hop too early) instead of `"Build Credit Status"` itself (the actual, unmodified direct predecessor of `"HS Requested Search (Companies)"` and the only node in the chain that emits `balances`). Item counts matched either way (single-item chain, D-14), which is exactly why a node-count check could never have caught it.
- Closed the plugin half of D-73-17 with a new fixture (`backend_status_all_three_lusha_zoominfo_known_apollo_unknown`) and pinning test proving `cost_guard.compare()` bounds on Lusha/ZoomInfo's real numbers while Apollo stays `unknown` — `cost_guard.py`/`backend_status.py` already did this correctly; no plugin code changed for this half.
- Gave `plan_grant()`/`envelope()` a real `cost_lane` parameter (`contact-upload` / `companies` / `enrich-before-ingest`), TDD RED-then-GREEN, and wired it into `authorize_ungranted_send` plus all three real call sites (`contact-upload`, `enrich-before-ingest`, `enrich-records` SKILL.md files) so the fix is not a dead API surface.
- Corrected the contact-upload execution model mid-plan after checking it against `dispatch.py`: this lane makes exactly ONE multipart POST per send regardless of row count, never a chunk-derived count — pinned with a 12-record/ceiling-5 test proving `chunk_count` (3) and `projected_executions` (1) no longer coincide.

## Task Commits
1. **Task 1: diagnose the status lane offline, then fix or classify (F-B6)** - `c54853c2` (fix)
2. **Task 2: price the grant by lane, not by blanket object type (D-73-16)** - `18469597` (feat)
3. **Advisor-driven follow-up: wire cost_lane into real call sites, correct the execution model** - `3104df6a` (fix)

**Plan metadata:** (this commit)

## Files Created/Modified
- `tests/n8n/backendStatusCredits.test.mjs` - graph-level walk proving F-B6's fix and pinning the fixed shape
- `scripts/build_cloud_workflows.py` - one-line `splice_carry_merge_after` carry_source fix, with the reasoning recorded inline
- `n8n/wf_backend_status_cloud.json` - regenerated (no hand-edit); `Build Credit Status` now has two outbound edges instead of one
- `operator-claude-plugin/scripts/write_grant.py` - `cost_lane` parameter on `envelope()`/`plan_grant()`/`authorize_ungranted_send()`, `COST_LANES` registry
- `operator-claude-plugin/tests/conftest.py` - `backend_status_all_three_lusha_zoominfo_known_apollo_unknown` fixture
- `operator-claude-plugin/tests/test_cost_guard.py` - D-73-17 combined-providers pinning test
- `operator-claude-plugin/tests/test_write_grant.py` - the `cost_lane` TDD suite (envelope, plan_grant, authorize_ungranted_send)
- `tests/test_backend_status_workflow.py` - updated the one structural assertion the wiring fix legitimately changed
- `operator-claude-plugin/skills/contact-upload/SKILL.md` - `cost_lane="contact-upload"` on both call sites
- `operator-claude-plugin/skills/enrich-before-ingest/SKILL.md` - `cost_lane="enrich-before-ingest"` on all three call sites
- `operator-claude-plugin/skills/enrich-records/SKILL.md` - `cost_lane` conditional on `object_type` on both call sites

## Decisions Made
- **F-B6 verdict: WIRING GAP.** `tests/n8n/backendStatusCredits.test.mjs` failed RED against the unmodified committed graph with:
  `AssertionError: the balances array must survive the whole carry-merge chain to Build Status — an empty/missing array here is exactly the F-B6 symptom (every provider reads as not_configured downstream)`.
  This settles Research Assumption A2: the same probe code works on the enrichment lane and failed here purely because of a mis-targeted carry-merge fan-in, not a credential/endpoint problem and not a live-instance-behind-committed-JSON gap. No live confirmation was needed to prove the code defect; 73-07's post-deploy status read remains the live confirmation that the fix reached production.
- **Post-deploy read caveat (for whoever runs 73-07's live status read):** `credential_health.state` for Lusha and ZoomInfo will likely still read `unknown`/`no_response` even after this fix deploys — no HTTP node in this graph sets `fullResponse`, so a bare 2xx success carries no status code for `deriveSourceHealth` to grade as `ok`. This is a separate, pre-existing characteristic of the graph, not a sign the fix failed. What must change post-deploy is `balances[...].credits` carrying real numbers (3708-ish for Lusha, 9358-ish for ZoomInfo) and `credential_health.apollo.reason` reading `http_403`, never `not_configured`.
- **Companies rate reaches `estimate_batch` un-overridden — confirmed, not changed.** `cost_guard.estimate_batch` (line 144) already normalizes `object_type` and picks `PROVIDER_RATE_KEYS["lusha"]["companies"]` (`lusha_companies_match`, 2 credits) whenever `object_type=="companies"`; nothing in the pre-existing `envelope()` ever overrode that. `cost_lane="companies"` adds a belt-and-braces force of `object_type="companies"` so a caller's possibly-wrong `object_type` argument can never defeat the correct rate — the fix is in the caller-authority layer, not in `estimate_batch` itself.
- **`cost_lane`, not `lane` (naming deviation from the acceptance criterion's literal wording — see Deviations).**
- **Contact-upload's execution model corrected mid-plan** from `chunk_count` (wrong — this lane never chunks) to a literal `1` (verified against `dispatch.py`'s hardcoded `expected_chunk_count=1`).
- **`cost_lane` wired into every real caller**, not left as dead code only `plan_grant`/`envelope`'s own tests exercise.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Parameter renamed from `lane` to `cost_lane`**
- **Found during:** Task 2, first implementation attempt
- **Issue:** The acceptance criterion's literal text says "`plan_grant` and `envelope` accept a `lane` argument". A first implementation used exactly that name. `write_grant.py` already uses `lane` pervasively and non-scoped for the ARMING lane concept — `covers()`, `authorize_send()`, `check_before_send()`, `authorize_ungranted_send()`, and, load-bearingly, `plan_grant`'s own `for lane in lane_names:` loop (a plain `for` loop leaks its variable in Python; a list comprehension does not). That loop's leftover value silently clobbered the new parameter before it ever reached `estimate_batch`.
- **Fix:** Renamed the new parameter to `cost_lane` throughout (`envelope()`, `plan_grant()`, `authorize_ungranted_send()`), documented the collision explicitly in `envelope()`'s docstring so a future reader does not repeat it.
- **Files modified:** `operator-claude-plugin/scripts/write_grant.py`
- **Verification:** re-ran the full `test_write_grant.py` suite (191 passed) after the rename; before the rename, six pre-existing tests failed with e.g. `ValueError: there is no cost lane called 'enrichment'` (the arming loop's leftover value reaching the new validation).
- **Commit:** `18469597`

**2. [Rule 1 - Bug] contact-upload execution projection corrected from chunk_count to a literal 1**
- **Found during:** advisor review after Task 2's commit
- **Issue:** The first implementation projected `chunk_count` (from `chunking.plan_chunks`) for the contact-upload lane's executions. `chunking.plan_chunks`/`chunk_ceiling` belong to the ENRICHMENT lane's `chunking.dispatch_plan` — the contact-upload lane's actual send path, `dispatch.py::dispatch()`, sends the whole CSV as ONE multipart POST regardless of row count and recovers it via `watch.recover_dispatch(..., expected_chunk_count=1, ...)`, a hardcoded 1. For any batch needing more than one chunk under the write-path ceiling, the prior fix would have over-projected executions (a small batch's `chunk_count==1` coincidentally matched the correct answer, masking the defect).
- **Fix:** `envelope()` now hardcodes `executions = 1` for `cost_lane="contact-upload"`, independent of `chunk_count`.
- **Files modified:** `operator-claude-plugin/scripts/write_grant.py`
- **Verification:** new test with 12 records at a ceiling of 5 (`chunk_count == 3`) asserts `projected_executions == 1`.
- **Commit:** `3104df6a`

**3. [Rule 2 - Missing critical functionality] `cost_lane` wired into every real call site**
- **Found during:** advisor review after Task 2's commit
- **Issue:** Task 2's acceptance criteria were satisfied at the `plan_grant`/`envelope()` API layer, but no production path passed the new argument — all three SKILL.md `plan_grant(...)` snippets and `authorize_ungranted_send` (which did not even accept the parameter) still priced every batch at the pre-fix default. F-A1/F-A2/F-B1 would have been fixed in the library but invisible to an operator.
- **Fix:** Added `cost_lane` to `authorize_ungranted_send` and forwarded it to `plan_grant`; updated all five real call sites across `contact-upload/SKILL.md`, `enrich-before-ingest/SKILL.md`, and `enrich-records/SKILL.md` to pass the correct lane (`enrich-records` conditionally, only for a companies batch).
- **Files modified:** `operator-claude-plugin/scripts/write_grant.py`, the three SKILL.md files, `operator-claude-plugin/tests/test_write_grant.py`
- **Verification:** new test `test_authorize_ungranted_send_threads_the_cost_lane_through_to_plan_grant`; full plugin suite re-run (191 passed in `test_write_grant.py`, 4989 passed / 154 skipped overall).
- **Commit:** `3104df6a`

**4. [Rule 1 - Bug] Updated a structural test invalidated by the Task 1 wiring fix**
- **Found during:** Task 2's full-suite verification run
- **Issue:** `tests/test_backend_status_workflow.py::test_build_credit_status_only_outbound_feeds_the_hubspot_count_search_chain` asserted `"Build Credit Status"` has exactly one outbound edge. Task 1's fix legitimately gives it a second edge — the carry merge that now correctly re-attaches `balances` — the same two-target carry idiom `"Status Credit Request"` already uses elsewhere in this exact file. D-14 ("never fanned out") governs the PROBE nodes' single inbound edge, never a node's outbound edge count.
- **Fix:** Updated the assertion to expect both targets (`set` comparison, plus a duplicate-edge guard), with the reasoning recorded in the test's own docstring.
- **Files modified:** `tests/test_backend_status_workflow.py`
- **Verification:** `test_backend_status_workflow.py` (16 passed).
- **Commit:** `18469597`

**Total deviations:** 4
**Impact:** All four keep the plan's stated intent (real balances, honest per-lane arithmetic) intact or make it actually reach the operator; none change scope, none touch a prohibited file, none arm/deploy/bounce anything.

## TDD Gate Compliance

Task 2 is `tdd="true"`. The gate was followed for the CORE lane-branching behavior (contact-upload zero-cost pricing, companies rate override, unrecognised-lane refusal) but not cleanly for every line added in this plan — recorded honestly rather than retrofitted:

- **RED observed, but not an assertion on planned behavior for the FIRST attempt's parameter name.** The first `git commit`-worthy RED was a `TypeError: envelope() got an unexpected keyword argument 'lane'` (6 of 6 new tests failing this way) — a missing-argument error, not yet an assertion on the lane's pricing behavior. After adding the bare parameter, six PRE-EXISTING tests then failed with `ValueError: there is no cost lane called 'enrichment'` — this was the real, informative RED: it is what exposed the `lane`/`lanes` naming collision (Deviation 1) before any production code shipped with it.
- **GREEN observed** after the `cost_lane` rename: all new and pre-existing tests in `test_write_grant.py` passed (191/191).
- **No separate `test(73-05):` / `feat(73-05):` commit pair exists** — the RED and GREEN states were both reached within the same working session before the first commit (`18469597` carries both the test and implementation together), so `gsd_run check tdd-red-evidence` was never run against a persisted RED record. This departs from the canonical RED-commit/GREEN-commit pattern; documented here rather than fabricating a RED-evidence artifact after the fact.
- The Rule 1/Rule 2 follow-up fixes (Deviations 2 and 3) were driven by advisor review, not a fresh TDD cycle — each was verified with a new or updated test asserting the corrected behavior, run to green, but no RED was captured for them since they corrected an already-shipped implementation rather than adding new planned behavior from scratch.

## Issues Encountered
None beyond the deviations documented above.

## User Setup Required
None - no external service configuration required. The regenerated `n8n/wf_backend_status_cloud.json` still needs the operator's own deploy + bounce (never Claude's, per D-73-18) before the fix is live — that is 73-07's job, not this plan's.

## Next Phase Readiness
- F-B6, F-A1, F-A2, F-B1 are fixed in code and covered offline. The live confirmation (a real disarmed status POST reading real Lusha/ZoomInfo balances, and a real grant showing zero-cost contact-upload pricing) is 73-07's post-deploy gate, not performed here per D-73-18 (never arm/deploy/bounce from Claude).
- `n8n/wf_backend_status_cloud.json` is the only regenerated workflow with a diff from this plan; regeneration after every change left `n8n/` clean.
- `.planning/todos/pending/` — no new todo opened; every discovered gap (cost_lane wiring, execution model) was fixed in-plan rather than deferred, per the advisor's own recommendation to resolve before writing this SUMMARY.

## Self-Check: PASSED

- `tests/n8n/backendStatusCredits.test.mjs` exists and is committed (`c54853c2`).
- `node --test tests/n8n/*.test.mjs`: 1196 passed / 0 failed (baseline 1195/0).
- `.venv/bin/python -m pytest -q tests/ operator-claude-plugin/tests/`: 4989 passed / 154 skipped (baseline 4979/154).
- `.venv/bin/python scripts/build_cloud_workflows.py` leaves `n8n/` with zero git diff.
- `git log --oneline -E --grep="^[a-z]+\(0*73-0*5\):"` finds 3 commits: `c54853c2`, `18469597`, `3104df6a`.
- All three commits present in `git log`; `plan_head_before: d5f08b6a`, `commits: 3` (measured via `git rev-list --count d5f08b6a..HEAD`).

---
*Phase: 73-ga-fix-list-from-stress-attempt-2*
*Completed: 2026-09-16*
