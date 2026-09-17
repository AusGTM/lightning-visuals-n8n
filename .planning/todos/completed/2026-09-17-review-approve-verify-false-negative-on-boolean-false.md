---
created: 2026-09-17T00:00:00.000Z
updated: 2026-09-18
title: verify_decision compared Python's capitalised rendering of a boolean against HubSpot's lowercase string, so a successful approve of a false-valued field reported as failed
area: operator-plugin
severity: medium
kind: defect
evidence: "Live re-read 2026-09-18 of Melbourne Racing Club company 9604614548 after the Stage E approve (73-UAT.md § Attempt 3, run_id 05f8c46e9aca4e289d23365b969a701b): HubSpot returned BOTH lv_is_hardware_vendor and lv_is_gambling_operator as the string `false` — the write LANDED. Every string field on the same record (industry, lv_org_type, lv_content_type, lv_country_region_normalized) verified on that same run, which is what isolates the comparison as the fault rather than the write. Regression coverage: operator-claude-plugin/tests/test_review_decision.py::test_a_boolean_false_approve_that_hubspot_reads_back_as_the_string_false_is_verified"
files:
  - operator-claude-plugin/scripts/review_decision.py
  - n8n/code/reviewApply.js
---

## Found during

Phase 73 plan 07 Task 3 (operator gate), Stage E of stress attempt 3, 2026-09-17/18.
Fixed by quick task 260918-322, 2026-09-18.

## What happened

**The original premise recorded here was FALSE and was not implemented.** This todo first
claimed HubSpot returns an unchecked `booleancheckbox` as an EMPTY string on read-back. That
was never observed. The live re-read on 2026-09-18 shows both fields holding the string
`false`.

The real chain:

1. `n8n/code/mergeCompanies.js` mints the candidate's `chosen_value` as the raw JS boolean
   `false`.
2. `reviewApply` passed a non-enum-bound value through unchanged — neither
   `lv_is_hardware_vendor` nor `lv_produces_content` appears in
   `n8n/code/hubspotEnums.generated.js`, so both reached `canonicalPatch` as bare booleans.
   D-07's stringify covered `clearPatch` only.
3. The PATCH body and the response's `would_write` therefore carried JSON `false`.
4. The plugin sets `intended = preview["would_write"]`, so Python saw `False`.
5. `verify_decision`'s leg 2 compared `str(False)` — `"False"`, capital F — against the
   refetched `"false"` and called it a mismatch, failing the whole approve.

Leg 1 passed only because both of its sides were the same Python `False`. A verify-only
false negative, never a lost write. The practical cost is operator trust: a genuinely clean
approve reads as `failed`, and an operator who believes the report may re-attempt a write
that already landed.

## Fixed by

Quick task **260918-322** (2026-09-18), three commits:

- **`_as_hubspot_text` in `operator-claude-plugin/scripts/review_decision.py`** — one
  module-level normaliser (bool to HubSpot's lowercase spelling, `None` to the empty string,
  everything else through `str()`; the bool case is checked first because Python treats
  booleans as an int subclass). Applied to **both sides of BOTH legs** of `verify_decision` —
  leg 1 intent stability and leg 2 landing — because a one-leg fix leaves the same false
  negative reachable from the other.
- **The boolean stringify in `n8n/code/reviewApply.js`**, completing D-07 across
  `canonicalPatch` as well as `clearPatch`. It runs strictly after the enum check and the
  stale compare-and-set, so neither gate can be bypassed by it. Regenerated through
  `scripts/build_cloud_workflows.py`; the committed JSON is ahead of live until the operator
  deploys.
- **Three regression tests** in `operator-claude-plugin/tests/test_review_decision.py`: the
  live MRC shape (RED before the fix), the blank-is-not-false guard (already green, now
  pinned), and the intended-`None`-against-a-blank-refetch behaviour change (RED before).
  Plus one new and two flipped assertions in `tests/n8n/reviewLoop.test.mjs` and
  `tests/n8n/reviewDecisionEndpoint.test.mjs`.
- Released as plugin **`0.50.1`**.

## What was deliberately NOT done

**The false-equals-empty rule this todo originally suggested was NOT implemented.** A field
that reads back BLANK still reports `failed` and the report still names it — pinned by
`test_a_boolean_false_approve_that_reads_back_BLANK_still_reports_failed`. A blank reads as
`unknown` to `src/icp_scoring.py` and to `Company Gate`'s REQUIRED set, so treating blank as
a match to `false` would mask a genuinely dropped write. No `booleancheckbox` type lookup
was added either — the normaliser is type-agnostic and changes only how a value is RENDERED
for comparison, never which keys are compared or what verdict a mismatch produces.
