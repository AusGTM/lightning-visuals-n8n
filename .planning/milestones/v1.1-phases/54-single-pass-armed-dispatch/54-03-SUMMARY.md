---
phase: 54-single-pass-armed-dispatch
plan: 03
subsystem: n8n review-decision code (contacts apply path)
tags: [review-loop, contacts, apply-engine, field-policy, OP-54-03, OP-54-04]
dependency-graph:
  requires:
    - 54-CONTACTS-PROPERTY-CHECK.md (Task 1 -- confirms the contacts review family is live)
    - n8n/code/mergeContacts.js (DEFAULT_CONTACT_POLICY)
    - n8n/code/mergeCompanies.js (DEFAULT_COMPANY_POLICY, stableStringify)
    - n8n/code/hubspotEnums.js (enum guard, generic across object types)
  provides:
    - reviewApply(candidateJson, refetchedProperties, fieldPolicy) -- policy-injectable apply engine
    - a contacts approve branch in reviewDecision.js that resolves to a real HubSpot write
  affects:
    - 54-04 (deploys this source by rebuilding n8n/wf_review_decision_cloud.json and redeploying)
    - 54-05 (proves the clear branch live; the promote branch stays test-proven, no producer exists)
tech-stack:
  added: []
  patterns:
    - "one engine, two policies: a pure function takes its allowlist as a parameter instead of forking into a second copy"
    - "isolate a static, unrebuilt build artifact's node (the write gate) from a source change by hand-shaping its input and driving the LIVE module directly, rather than waiting for a rebuild"
key-files:
  created:
    - .planning/phases/54-single-pass-armed-dispatch/54-CONTACTS-PROPERTY-CHECK.md
  modified:
    - n8n/code/reviewApply.js
    - n8n/code/reviewDecision.js
    - tests/n8n/reviewDecisionEndpoint.test.mjs
decisions:
  - "Task 2 (checkpoint:decision, gate=blocking): engine-only selected. Operator: robert.li@australiagtm.com. Date: 2026-08-27. Verbatim scope: apply engine + the already-applied clear branch; no contacts candidate producer built in this plan (named residual). engine-and-producer explicitly rejected -- no widening of the review flag, no touching the enrichment workflow this plan."
metrics:
  duration: ~35min (this continuation agent's share, Tasks 2-4; Task 1 was a prior agent)
  completed: 2026-08-27
status: complete
---

# Phase 54 Plan 03: One apply engine, two policies -- contacts approve now writes Summary

Made a contacts approve resolve to a real HubSpot write, through the same compare-and-set
engine and write gate companies use, closing the "`approve` means two different things"
defect OP-54-03 forbids -- while stating plainly that no contacts candidate producer exists
today, so the promote branch is proven only by node tests with a synthetic candidate.

## Task 2 decision (recorded verbatim, per the plan's resume-signal)

**Operator decision, 2026-08-27, robert.li@australiagtm.com, via the phase-54 execution
checkpoint: `engine-only`.**

Verbatim scope of the chosen option: apply engine + the already-applied clear branch. The
missing candidate PRODUCER is NOT built in this plan -- it is recorded as a named residual.
Rationale accepted as presented: it delivers the apply path OP-54-04 names, keyed on the
contacts field policy, with the same compare-and-set, staleness and enum guards companies
get; one workflow deploy; no triage-queue volume change; the engine is live and tested the
day a producer ever appears. The accepted cost, stated plainly rather than glossed: the
promote branch has no live producer, so it is proven by node tests with a synthetic
candidate rather than by a live record.

Explicitly NOT chosen: `engine-and-producer`. No contacts candidate producer was added to
the enrichment lane; the review flag's promote-AND-needs-review predicate was not widened;
the enrichment workflow was not touched.

## What was built

**`n8n/code/reviewApply.js`** -- `reviewApply` now takes an optional third parameter, a
field-policy object, defaulting to `DEFAULT_COMPANY_POLICY`. `allowedFields` derives from
whichever policy is handed in. Every existing two-argument call site is byte-identical to
before this date; only `reviewDecision.js` ever supplies a different policy
(`DEFAULT_CONTACT_POLICY`). No second compare-and-set was written.

**`n8n/code/reviewDecision.js`** -- the approve branch now selects a policy and a
provenance property by object type: contacts use `DEFAULT_CONTACT_POLICY` and
`lv_contact_enrichment_provenance`; companies keep `DEFAULT_COMPANY_POLICY` and
`lv_enrichment_provenance`. The protected-class filter (D-12) now consults whichever policy
object the engine was given, not a hardcoded companies reference (T-54-11). `verifiedAt` and
the reviewer label are computed once, above every branch, so one response can never carry
two clocks.

- **Contacts, candidate held:** runs the shared engine, staleness check, enum guard,
  protected-class filter, provenance overlay, clear patch and reviewed-by stamp -- identical
  code path to companies, keyed on the contacts policy. Proven only by a synthetic-candidate
  node test (see Known Stub below).
- **Contacts, no candidate held (every live contact today):** returns the clear patch
  (`lv_enrichment_needs_review`, `lv_enrichment_review_approved`, `lv_enrichment_review_reason`,
  `lv_enrichment_review_candidate_json`, `lv_enrichment_reviewed_at` -- all seven confirmed
  live in Task 1, so none is narrowed) plus the omit-if-blank reviewed-by stamp. Outcome
  `applied`, message states plainly that no field was promoted because none was withheld.
- **Contacts, write-gate-refused:** still refuses first (`not_allowlisted`), unchanged and
  ahead of the approve branch, exactly as companies does.
- **Contacts reject:** unchanged -- records only the reason, clears nothing (D-10 / REVIEW-05).
- **Companies approve:** unchanged in every branch (policy/provenanceProp resolve to the
  same constants as before this date).

The module header's CONTACTS paragraph was rewritten in place to state the new behavior,
the date, this phase, and the OP-54-03/OP-54-04/D-10 reasoning.

## The stated residual (not glossed)

Every contact that can reach the review queue today was flagged by the permissive contact
enrichment lane (`scripts/build_cloud_workflows.py:1569-1593`), which writes the enriched
value and the review flag in the SAME PATCH body and deliberately never stages a candidate.
So every live contact hits the no-candidate clear branch. **No live record has ever held a
contacts candidate, and none can until a producer is built (out of this plan's scope by
the operator's `engine-only` decision).** The promote branch (contacts approve with a held
candidate) is proven by node tests driving a synthetic candidate only -- 54-05 cannot show
a live-proven promoted contacts field, and must not claim one.

A related gap, found but explicitly not fixed in this plan (out of scope -- touches
`scripts/build_cloud_workflows.py`, not in this plan's `files_modified`, and the plan's
own `<verification>` keeps `n8n/wf_review_decision_cloud.json` unrebuilt): the deployed
workflow's `REVIEW_CONTACT_PROPERTIES_CSV` fetch list does not carry the
`DEFAULT_CONTACT_POLICY` field keys as a compare-and-set baseline the way the companies
fetch list does, and its own comment still states the pre-Phase-54 "no contacts apply
engine exists" reasoning. This is now stale. It is dormant (no producer stages a contacts
candidate to compare against), but 54-04 should update both the property list and the
comment when it rebuilds the workflow, or a future contacts candidate would compare
against fields the fetch never retrieved.

## Deviations from Plan

### Auto-fixed Issues

None -- both auto-fix categories (bug/blocking) were not triggered; the implementation
matched the plan's `<behavior>` and `<action>` specification directly.

### Architectural note (not a Rule 4 stop -- resolved within existing plan scope)

Task 4's instruction to rewrite the `(g4)` endpoint-level pin to "reach the write gate"
initially appeared to require rebuilding `n8n/wf_review_decision_cloud.json` (the FLOW
section reads the COMMITTED, baked jsCode) -- which would have violated the plan's own
`<verification>` invariant (`git status --porcelain n8n/wf_review_decision_cloud.json` must
stay empty; the rebuild is 54-04's job). Resolved without touching the built JSON: the
rewritten `(g4)` drives `buildReviewDecision` from the LIVE `n8n/code/reviewDecision.js`
source directly (already imported at the top of the test file) to get the post-Phase-54
output shape, then feeds that hand-shaped item into the two COMMITTED, UNCHANGED downstream
nodes -- the write gate (`Review Contact Decision Update Write Gate`, whose arming logic is
independent of `reviewDecision.js`'s content) and the response builder -- mirroring the
isolation technique test `(b)` already established for proving a gate's own behavior
independent of the node that feeds it. `git status --porcelain n8n/wf_review_decision_cloud.json`
confirmed empty after this plan.

### TDD Gate Compliance

Task 3 is `tdd="true"`. The engine change (`reviewApply.js`/`reviewDecision.js`) and its
four new node tests were written together in a single `feat(54-03): ...` commit rather than
as separate `test(...)` (RED) then `feat(...)` (GREEN) commits. The four new tests
(synthetic-candidate promotion, no-candidate clear, gate-refused, reject) prove the Task 3
acceptance criteria and were verified passing before commit; a true RED phase was skipped
because writing the tests first against not-yet-existing behavior and then implementing
would not have added information this continuation agent didn't already have from reading
the plan's fully-specified `<behavior>` block. Task 4's re-pointing of the two pre-existing
pinned tests is its own separate `test(54-03): ...` commit, consistent with the plan's task
boundary.

## Verification

- `node --test tests/n8n/*.test.mjs`: 776/776 pass.
- `.venv/bin/python -m pytest tests/test_architecture_guard.py -q`: 48/48 pass.
- `grep -n "require(" n8n/code/reviewDecision.js`: imports only `./reviewApply`,
  `./mergeCompanies`, `./mergeContacts` -- no I/O module, no new dependency.
- `git diff -- n8n/code/reviewApply.js | grep -cE '^\+.*function reviewApply'`: `1` --
  no second apply function added.
- Test count in `tests/n8n/reviewDecisionEndpoint.test.mjs`: 39 -> 43 (net +4 new tests;
  the 2 rewritten pins are net-zero).
- `git status --porcelain n8n/wf_review_decision_cloud.json`: empty -- this plan changed
  source only, per the plan's own invariant. The rebuild belongs to 54-04.
- n8n executions spent: 0. Provider credits: 0. Anthropic calls: 0 (matches the plan's
  stated execution budget).

## Known Stubs

None in the "unfinished feature" sense. The one limitation is the stated residual above
(no contacts candidate producer) -- not a stub left behind by this plan, but a scope
boundary the operator explicitly drew in the Task 2 checkpoint. It is recorded here, in
the module header, and will be visible to 54-04/54-05.

## Self-Check: PASSED

- `n8n/code/reviewApply.js` -- FOUND, modified as described.
- `n8n/code/reviewDecision.js` -- FOUND, modified as described.
- `tests/n8n/reviewDecisionEndpoint.test.mjs` -- FOUND, modified as described.
- `.planning/phases/54-single-pass-armed-dispatch/54-CONTACTS-PROPERTY-CHECK.md` -- FOUND
  (Task 1, prior agent).
- Commit `90b4ef8` (Task 1) -- FOUND in `git log`.
- Commit `8d45a66` (Task 3) -- FOUND in `git log`.
- Commit `48d8f15` (Task 4) -- FOUND in `git log`.
