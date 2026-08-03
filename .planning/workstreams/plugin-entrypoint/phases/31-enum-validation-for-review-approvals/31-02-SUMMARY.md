---
phase: 31-enum-validation-for-review-approvals
plan: 02
subsystem: n8n-backend
tags: [write-safety-gate, review-loop, outcome-vocabulary, two-sided-test, operator-runbook, defense-in-depth]

requires:
  - phase: 31
    plan: 01
    provides: "the enum spine (hubspotEnums.js/generated.js) and the outcome word `refused` this plan leaves unmodified for enum refusals"
  - phase: 30
    plan: 7
    provides: "the RB-9 armed canary that recorded the live BUG 30 evidence: an allowlist drop answering no body at all, indistinguishable from the enum 400 the client also reported as unparseable_response"
provides:
  - "n8n/code/reviewDecision.js's `writeAllowed` input and `not_allowlisted` outcome — an explicit refusal on an allowlist drop, checked after `flagged` and before reject/approve so both refuse identically"
  - "the `Build Review Decision` wrapper's own `_writeSafetyAllows(\"review\", row.hs_object_id, row.domain)` pre-check, computed from the SAME baked constants the spliced write gate reads — an earlier, louder answer in front of the unchanged gate, never a replacement for it"
  - "review_decision.py's `not_allowlisted` in NON_WRITING_OUTCOMES, the corrected unparseable_response/no_response messaging (n8n execution history, not the allowlist), and the corrected docstring gate-3 paragraph"
  - "operator-claude-plugin/tests/test_review_outcome_parity.py — the two-sided pin reading n8n/code/reviewDecision.js AND the committed wf_review_decision_cloud.json as text against review_decision.OUTCOMES"
  - "tests/n8n/reviewAllowlistRefusal.test.mjs — the agreement-matrix test proving the pre-check and the committed write gate never disagree on permit/deny across four independent arming combinations"
  - "OPERATOR-RUNBOOK.md RB-9's corrected diagnostic advice, corrected snapshot-script flags, and the note that the RB-9 canary record was cleared 2026-08-03"
affects:
  - "31-03 (close-out) — ships the regenerated wf_review_decision_cloud.json this plan built, and the two-sided contract inventory it will assemble includes this plan's not_allowlisted pin"

tech-stack:
  added: []
  patterns:
    - "earlier-louder-refusal-in-front-of-an-unchanged-authority: a Code node upstream of a spliced write gate computes the SAME _writeSafetyAllows(...) verdict the gate itself will apply, and answers explicitly on denial rather than letting the row travel further only to be silently dropped — the gate is never touched, never bypassed, and an agreement-matrix test (not just an assumption) proves the two never diverge"
    - "empty-properties-forces-dry-run (reused from 31-01's enum guard): returning empty `properties` on a refusal makes the wrapper's existing hasWrite/dry_run rule route the row straight to the response, with no new IF branch needed — the SAME trick BUG 29's enum fix already established, now reused for a second refusal class"
    - "two-sided outcome-vocabulary pin, extended to cover the DEPLOYED artifact: test_review_outcome_parity.py reads the source module as text, extracts literals by regex, AND separately reads the committed workflow JSON's own inlined copy of that module — a build step that stripped or renamed an outcome while inlining would fail even if the source module still read correctly"

key-files:
  created:
    - tests/n8n/reviewAllowlistRefusal.test.mjs
    - operator-claude-plugin/tests/test_review_outcome_parity.py
  modified:
    - n8n/code/reviewDecision.js
    - scripts/build_cloud_workflows.py
    - n8n/wf_review_decision_cloud.json
    - operator-claude-plugin/scripts/review_decision.py
    - operator-claude-plugin/tests/test_review_decision.py
    - tests/n8n/reviewDecisionEndpoint.test.mjs
    - tests/n8n/hubspotEnumValidation.test.mjs
    - .planning/workstreams/plugin-entrypoint/OPERATOR-RUNBOOK.md
    - .planning/workstreams/plugin-entrypoint/ROADMAP.md

key-decisions:
  - "writeAllowed gates BEFORE the reject/approve split, not inside either branch — a reject and an approve on an un-permitted row refuse identically (`not_allowlisted`), matching the committed write gate, which drops both the same way. Placing it only inside approve would have let an un-permitted reject silently 'succeed' at the pre-check while the gate later dropped it — the same class of lie BUG 29 closed."
  - "Once `Build Review Decision` declares the same five write-safety constants the gate does, a LIVE deploy's `enable_baked_flags()` (which rewrites every node in the workflow carrying a declaration, not one node) arms both together. Several pre-existing tests in reviewDecisionEndpoint.test.mjs and hubspotEnumValidation.test.mjs had armed ONLY the gate to simulate 'a real write reaching the write branch' — a state a live deploy can no longer produce in isolation. Updated those tests to arm the pre-check too (or, for the one test whose entire point was proving the GATE alone is fail-closed, to feed the gate a hand-shaped item instead of routing through the now-also-gating pre-check) — see Deviations."
  - "The agreement-matrix test drives the pre-check and the gate through the SAME four arming combinations reviewDecisionEndpoint.test.mjs already exercises for the gate alone ((b)(c)(c2)(d)), rather than inventing a new matrix — this is what makes 'never disagree' a checked property instead of an assumption (T-31-06)."

metrics:
  duration: ~1h40min
  completed: 2026-08-03
status: complete

actuals:
  tokens: 43800
  tasks: 3
  commits: 3
---

# Phase 31 Plan 02: BUG 30 — Explicit Allowlist Refusal Summary

Makes an allowlist drop on the review-decision endpoint answer an explicit
`not_allowlisted` refusal instead of silence, teaches the plugin client the new word
and the corrected meaning of an unparseable response, and corrects the runbook
advice that misled the live RB-9 run. The write gate that is the actual authority is
never touched — this adds an earlier, louder answer in front of it, proven never to
diverge from it.

## What was built

**Task 1 — the endpoint answers an explicit refusal on an allowlist drop** (`6288d8f`)

- `n8n/code/reviewDecision.js`: `buildReviewDecision` gained an optional
  `writeAllowed` input. Only the literal `false` refuses (every existing caller/test
  that omits the key is unaffected). The check sits immediately after the `flagged`
  determination and before the reject/approve split, returning
  `{ properties: {}, outcome: "not_allowlisted", message }` — a message stating in
  plain language that the record is not on the backend's `TEST_RECORD_*` allowlist,
  nothing was sent, the record is unchanged, and an administrator adds records to
  the allowlist at deploy time. No constant value or secret is named. The header's
  CONSUMER CONTRACT outcome list now includes `not_allowlisted`.
- `scripts/build_cloud_workflows.py`: `REVIEW_BUILD_DECISION` now prepends
  `WRITE_SAFETY_GATE_JS` (the same constants + `_writeSafetyAllows` the spliced
  `Review Decision Update Write Gate` uses), the way `ENRICH_DECIDE_CO_CLOUD`
  already does. The wrapper computes `writeAllowed` as `true` whenever
  `parsed.dry_run !== false` (a preview always keeps showing the patch), otherwise
  `_writeSafetyAllows("review", row.hs_object_id, row.domain)` — the SAME two
  fields (`hs_object_id`, `domain`) the spliced non-create gate resolves to on this
  lane, since `Review Extract Record` emits a flattened row carrying exactly those
  two names.
- Regenerated `n8n/wf_review_decision_cloud.json` via the builder's normal entry
  point. Only that one workflow file changed (confirmed via `git diff --stat n8n/`)
  — `Merge Company`'s frozen jsCode fixture was untouched, so no re-baseline was
  needed this time (unlike 31-01's two re-baselines).
- `tests/n8n/reviewAllowlistRefusal.test.mjs` (10 tests): a real submit through the
  committed disarmed pre-check refuses explicitly; arming the pre-check reaches the
  ordinary outcome and the write branch; a preview never sees the refusal, armed or
  not; a reject and an approve refuse identically; a contacts row follows the SAME
  id-only allowlist rule the gate already enforces (30-02's g3 property); and the
  AGREEMENT MATRIX — 4 tests, one per arming combination `(b)(c)(c2)(d)` — proving
  the pre-check and the committed `Review Decision Update Write Gate` never
  disagree on permit/deny.

**Task 2 — the client stops conflating a fail-closed drop with a workflow error**
(`5447e8a`)

- `operator-claude-plugin/scripts/review_decision.py`: `not_allowlisted` added to
  `NON_WRITING_OUTCOMES` (and to `OUTCOMES`), so `verify_decision` reports it
  `not_written` and passes the endpoint's own message through unchanged. Corrected
  the docstring's gate-3 paragraph (dated 2026-08-03, names Phase 31 Plan 02/BUG
  30) and the `unparseable_response` branch's comment, both of which previously
  attributed a body that fails to parse to the allowlist drop — the exact wrong
  turn RB-9 took live. Gave `verify_decision`'s unavailable-message branch a
  reason-specific hint for `unparseable_response`/`no_response` naming n8n
  execution history as where to look, and stating that a genuinely un-allowlisted
  record now answers `not_allowlisted` instead; every other reason keeps the
  generic wording, and nothing interpolates a header, secret, or transport
  exception text.
- `operator-claude-plugin/tests/test_review_outcome_parity.py` (7 tests): reads
  `n8n/code/reviewDecision.js` as TEXT, extracts every `outcome: "..."` literal by
  regex, and asserts the set equals `review_decision.OUTCOMES`; separately reads
  the COMMITTED `wf_review_decision_cloud.json`'s own `Build Review Decision`
  jsCode and pins the same set against it, so the deployed artifact is covered, not
  only the source module. Plus behavioural pins: `not_allowlisted` maps to
  `not_written` with the message passed through; an `unparseable_response` verdict
  names execution history and omits `TEST_RECORD_IDS`; every other unavailable
  reason keeps the generic wording.
- One pre-existing test (`test_every_endpoint_outcome_has_a_handling_branch`,
  `operator-claude-plugin/tests/test_review_decision.py`) hardcoded the old
  six-outcome set — updated to the seven-outcome set (Deviations).

**Task 3 — correct RB-9's diagnostic advice** (`22381da`)

- Rewrote the "Two failure modes that look like something else" block: the first
  bullet now states an un-allowlisted decision answers `not_allowlisted` explicitly
  (client-reported `not_written`), and an empty/unreadable body means the WORKFLOW
  itself errored — n8n execution history is where the cause is, not
  `TEST_RECORD_IDS`. The second bullet (read the verdict from `verify_decision`,
  never an HTTP status) is unchanged. A new third bullet records the live cause
  this phase (31-01) fixed: an enum-invalid review approval now comes back
  `refused`, naming the property and value, on both preview and real submit.
- Corrected step 2's snapshot command from the nonexistent `--company-id` flag to
  the script's real interface, `--target-id` plus `--target-object-type`
  (established live 2026-08-03, 30-07-SUMMARY step 2). Step 1 now notes the RB-9
  canary record (`9604614548`) was cleared manually 2026-08-03 and a fresh
  `needs_review` fixture is required.
- Appended one change-log row dated 2026-08-03 naming Phase 31 Plan 02 and both
  corrections. Ticked the 31-02 checkbox in ROADMAP.md.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — bug, directly caused by Task 1] Nine pre-existing tests encoded the
now-superseded assumption that a real submit reaches the write branch without the
pre-check being armed too**

- **Found during:** Task 1's full-suite regression pass
  (`node --test tests/n8n/*.test.mjs` showed 9 unexpected failures across
  `tests/n8n/reviewDecisionEndpoint.test.mjs` (7: (b)(c)(f1)(f2)(g3)(g4)(g5)) and
  `tests/n8n/hubspotEnumValidation.test.mjs` (2: FLOW b, FLOW c)).
- **Root cause:** these tests built a `built` item via an UNARMED `Build Review
  Decision` and then armed ONLY the downstream write gate to simulate "a real write
  reaching the write branch." Once `Build Review Decision` also declares the same
  write-safety constants, a live `enable_baked_flags()` deploy — which rewrites
  every node in the workflow that carries a declaration — arms both nodes
  TOGETHER. Arming only one is no longer a state a live deploy can produce, so
  these tests' setup no longer represented reality.
- **Fix:** added an optional `precheckConstants` parameter to each file's shared
  `drive`/`driveDecision` helper, defaulting to unarmed (so the ~40 other calls
  across both files are unaffected), and armed the pre-check with the SAME
  constants each affected test already arms on the gate. The one exception is
  `(b) a real rejection through the COMMITTED (disarmed) gate yields zero items`:
  since its entire point is proving the GATE ALONE is fail-closed (T-31-06), it now
  asserts the pre-check's own `not_allowlisted` refusal first, then feeds the gate
  a hand-shaped item (as `Build Review Decision` would have emitted had the
  pre-check permitted the write) to isolate the gate's behavior from the
  pre-check's — preserving the test's original intent rather than making it
  redundant with the new agreement-matrix test.
- **Files modified:** `tests/n8n/reviewDecisionEndpoint.test.mjs`,
  `tests/n8n/hubspotEnumValidation.test.mjs`.
- **Commit:** `6288d8f`.
- **Why Rule 1, not a plan deviation requiring a stop:** the plan's task 1
  acceptance criteria state `reviewDecisionEndpoint.test.mjs` must pass "with NO
  edits" — but the plan's OWN described mechanism (the pre-check declaring and
  consulting the same constants the gate does) makes that literally impossible: a
  disarmed real submit refuses at the pre-check by design, which is the entire
  point of the fix. This is the identical shape 31-01's own Deviations section
  documented (two pre-existing tests that "encoded the exact bug this phase
  closes") — the correct move is updating the tests to the new, correct behavior,
  not narrowing the fix to keep them passing unmodified.

**2. [Rule 1 — bug, directly caused by Task 2] One pre-existing test hardcoded the
old six-outcome set**

- **Found during:** Task 2's `operator-claude-plugin/tests/` regression pass.
- **`test_every_endpoint_outcome_has_a_handling_branch`
  (`operator-claude-plugin/tests/test_review_decision.py`):** asserted
  `set(review_decision.OUTCOMES)` equals the six pre-31-02 outcomes. Updated to the
  seven-outcome set including `not_allowlisted`.
- **Files modified:** `operator-claude-plugin/tests/test_review_decision.py`.
- **Commit:** `5447e8a`.

**3. [Rule 3 — blocking, self-inflicted] `git checkout --` on a not-yet-committed
file discarded legitimate Task 2 edits along with an intentional demo edit**

- **Found during:** Task 2, while demonstrating the two-sided pin's fail-on-drift
  property (temporarily adding a literal to `NON_WRITING_OUTCOMES`, confirming the
  test fails, then reverting).
- **Issue:** `git checkout -- operator-claude-plugin/scripts/review_decision.py`
  reverted the file to its last COMMITTED state — which was still pre-Task-2, since
  Task 2's edits had not yet been committed — wiping the demo edit AND the
  legitimate docstring/`NON_WRITING_OUTCOMES`/message corrections in the same
  stroke.
- **Fix:** re-applied all three Task 2 edits from scratch, re-verified against the
  plan's exact acceptance-criteria commands, and re-ran the full suite before
  committing. No content was lost — the redo was verified byte-identical in intent
  by re-running the same acceptance checks.
- **Committed in:** `5447e8a` (the redone edits, committed together).

No other deviations — the rest of the plan executed as written.

## Two-sided pin demonstrated live (Task 2 acceptance criterion)

Temporarily added a literal (`"fake_outcome_probe"`) to
`NON_WRITING_OUTCOMES` alone → both `test_the_source_modules_outcome_literals_match_the_clients_tuple`
and `test_the_committed_workflows_own_copy_matches_the_clients_tuple_too` failed,
naming the drifted literal on the client-only side → reverted → both passed again.

## The exact `not_allowlisted` message

```
this record is not on the backend's TEST_RECORD_* allowlist, so nothing was sent to
HubSpot and the record is unchanged — an administrator adds records to that
allowlist at deploy time
```

## Write-gate scanner reconciliation

Neither `tests/test_write_gate_coverage.py` nor `tests/test_write_lane_contracts.py`
needed reconciling. `test_write_gate_coverage.py`'s `_all_paths_cross_a_gate` walks
upstream from the write node and stops at the FIRST node containing
`_writeSafetyAllows` — the spliced `Review Decision Update Write Gate` is still that
first node, so the scan never reaches `Build Review Decision` at all.
`test_write_lane_contracts.py`'s `_gated_writes` only inspects a write node's DIRECT
feeder — again the spliced gate, not the pre-check two hops upstream. Both were run
and passed unmodified; verified by direct read of both scanners' discovery logic
before running, and confirmed by the passing run.

## Verification

Suite counts, before (31-01 baseline) and after (final, all three tasks):

| Suite | 31-01 baseline | 31-02 final |
|---|---|---|
| `node --test tests/n8n/*.test.mjs` | 540 pass, 0 fail | **550 pass, 0 fail** |
| `.venv/bin/python -m pytest -q` (repo root, includes `operator-claude-plugin/tests/`) | 1689 passed, 6 skipped | **1697 passed, 6 skipped** |
| `.venv/bin/python -m pytest operator-claude-plugin/tests/ -q` (standalone) | — | **819 passed, 5 skipped** |

Net: **+10 node** (10 in `reviewAllowlistRefusal.test.mjs`), **+8 pytest** (7 new in
`test_review_outcome_parity.py`; `test_every_endpoint_outcome_has_a_handling_branch`
modified, not added). Zero regressions once the nine pre-existing tests were
updated to the new, correct behavior.

Disarmed gate, verified after every commit:

```
grep -c 'ALLOW_HUBSPOT_[A-Z_]* = "true"' n8n/*.json   ->  0 (all 8 files)
```

`operator-claude-plugin/tests/test_control_disarmed_artifacts.py`: 23 passed, 5
skipped.

`git diff --stat n8n/` after the builder run showed only
`wf_review_decision_cloud.json` changed — `Merge Company`'s frozen fixture test
(`test_companies_factory_frozen.py`) needed no re-baseline this plan, since neither
task touched `mergeCompanies.js` or any of its `inline()` call sites.

No network call of any kind at any point. No `git stash`/`clean`/`reset --hard`. No
package installs.

## Known Stubs

None. Every code path returns a real value or a named refusal reason; no
placeholder.

## Threat Flags

None beyond the plan's own threat register (T-31-06 through T-31-10) — no new
network endpoint, auth path, or schema change was introduced. `Build Review
Decision`'s allowlist pre-check is mitigated by construction (it can never become a
weaker second authority, per the agreement-matrix test) and by the unchanged,
sole-authority write gate downstream.

## What 31-03 needs to know

1. **`not_allowlisted` is a distinct outcome from `refused`** (31-01's enum
   refusal) and from every other non-writing outcome — the seven-outcome set is now
   `applied | rejected | stale | no_candidate | not_flagged | refused |
   not_allowlisted`, pinned two-sided by `test_review_outcome_parity.py`.
2. **`Build Review Decision` now declares the five write-safety constants** (the
   same ones `Review Decision Update Write Gate` and `Review Contact Decision
   Update Write Gate` declare). Any future live-deploy verification that counts
   declaring nodes per constant must account for this — `verify_live_write_safety.py`
   already discovers declaring nodes rather than naming a fixed count (T-31-10), so
   no code change is needed there, but the printed coverage count for
   `ALLOW_HUBSPOT_REVIEW_WRITES`/`TEST_RECORD_*` in `wf_review_decision_cloud.json`
   is now one node higher than before this plan.
3. **Arming `ALLOW_HUBSPOT_REVIEW_WRITES` at deploy time now arms the pre-check and
   the gate together** — there is no live-reachable state where one is armed and
   the other is not. Any future test simulating "a real write reaching the write
   branch" must arm both, or it is testing a rewritten pre-check-first refusal, not
   the write branch.
4. **The RB-9 canary record (`9604614548`) is no longer usable as-is** — it was
   cleared 2026-08-03. A fresh `needs_review` fixture (one enrichment run against a
   test company holding a conflicting staged value) is needed before any live
   canary re-run, including whatever 31-03 or a future runbook pass exercises.

## Self-Check: PASSED

- `n8n/code/reviewDecision.js` (writeAllowed + not_allowlisted) — FOUND
- `scripts/build_cloud_workflows.py` (WRITE_SAFETY_GATE_JS prepended to
  REVIEW_BUILD_DECISION) — FOUND
- `n8n/wf_review_decision_cloud.json` (regenerated, `_writeSafetyAllows` +
  `writeAllowed` present in `Build Review Decision`) — FOUND
- `operator-claude-plugin/scripts/review_decision.py` (not_allowlisted in
  NON_WRITING_OUTCOMES, corrected messages) — FOUND
- `tests/n8n/reviewAllowlistRefusal.test.mjs` — FOUND
- `operator-claude-plugin/tests/test_review_outcome_parity.py` — FOUND
- `.planning/workstreams/plugin-entrypoint/OPERATOR-RUNBOOK.md` (not_allowlisted,
  --target-object-type, no company-id) — FOUND
- commits `6288d8f`, `5447e8a`, `22381da` — all FOUND in `git log`
- no file deletions in any commit
- `git status --porcelain n8n/` shows the regenerated workflow JSON committed
