---
phase: 60-review-lane-authority
plan: 05
subsystem: review-lane-verification
tags: [python, markdown, review-decision, write-safety, gap-closure, release]

requires:
  - phase: 60-review-lane-authority
    plan: 01
    provides: "review" as a third grantable lane, write_grant.authorize_send(lane="review")
  - phase: 60-review-lane-authority
    plan: 02
    provides: n8n_arming.armed_review_window, write_grant.authorize_review_batch
  - phase: 60-review-lane-authority
    plan: 04
    provides: review-triage/SKILL.md's grant-authorized batch window (D-60-06)
provides:
  - "review_decision.verify_decision reports verified on a fully successful review approve even though lv_enrichment_reviewed_at, the provenance blob's embedded timestamp and the reviewed-by label are minted by the backend at submit time"
  - "review_decision.PREVIEW_UNPINNABLE_KEYS — the one closed set read by both leg 1 (exclusion) and leg 2 (expected-value source)"
  - "verify_live_write_safety.verify(..., armed_workflow=...) — a correctly-scoped single-workflow armed expectation that cannot blind the scan"
  - "review-triage/SKILL.md step 4 instructs reading the armed allowlist back from window.arm_result['observed'] and quotes the admin-side scoped verifier invocation"
  - "operator-claude-plugin v0.38.0"
affects: []

actuals:
  tokens: 42000
  tasks: 3
  commits: 3

tech-stack:
  added: []
  patterns:
    - "a comparison split into two legs over the same closed exclusion set, read from both directions (exclude vs re-source), rather than two independently-maintained lists"
    - "per-report rule dispatch (armed vs disarmed) keyed on which workflow a discovered node report came from, with a zero-match guard as its own failure reason — the same discovery-first shape 23-07 established, extended rather than replaced"

key-files:
  created: []
  modified:
    - operator-claude-plugin/scripts/review_decision.py
    - operator-claude-plugin/tests/test_review_decision.py
    - scripts/verify_live_write_safety.py
    - tests/test_verify_live_write_safety.py
    - operator-claude-plugin/skills/review-triage/SKILL.md
    - operator-claude-plugin/CHANGELOG.md
    - operator-claude-plugin/.claude-plugin/plugin.json
    - operator-claude-plugin/tests/test_plugin_manifest.py

decisions:
  - "Leg 2 stays anchored on `intended`'s key set (never leg 1's union) — a deliberate, plan-mandated non-change, because leg 1 already returns on any pinnable-key difference before leg 2 runs, and widening leg 2 to a key the operator never approved would grow what the refetch comparison asserts in the very direction this plan guards against."
  - "PREVIEW_UNPINNABLE_KEYS holds exactly four names (two provenance blobs — companies and contacts — plus reviewed_at and reviewed_by) and is read by both leg 1 and leg 2; `preview_decision`'s signature is NOT widened to accept a reviewed-by argument, per the plan's explicit prohibition."
  - "verify_live_write_safety.verify() dispatches each discovered node report to one of two extracted judgment functions (_judge_disarmed_report / _judge_armed_report) rather than writing a third rule body for the scoped case — the named workflow's reports route to the armed judgment, every other workflow's reports route to the disarmed judgment."
  - "test_plugin_manifest.py's BACKEND_REPO_SCRIPTS exemption (Phase 43's named, one-citation-per-entry shell-out allowlist) gained a review-triage entry for verify_live_write_safety.py — required because the plan's own Task 3 action instructs quoting that script's invocation in the skill, which the existing manifest guard would otherwise reject as a reference to a script the plugin does not ship. This file is not in the plan's files_modified list; the edit is Rule 3 (auto-fix a blocking issue) — the plan's own prescribed verify command for Task 3 could not otherwise pass."

metrics:
  duration: "~90 minutes"
  completed: 2026-09-03

status: complete
---

# Phase 60 Plan 05: Review-lane verification gap closure (G-60-1, G-60-2) Summary

Fixed two defects the 2026-09-03 live supervised operator walk found: a false `failed`
verdict on every successful review approve, caused by comparing a preview-time map against
a submit-time refetch on properties the backend mints at request time; and an armed-window
verifier that could only express a global armed expectation, so a correctly-scoped
single-workflow arm (`armed_review_window`) reported the other three workflows' correctly
disarmed nodes as failures.

## What changed

**G-60-1 (`review_decision.py`).** `verify_decision` now runs two legs instead of one
comparison. Leg 1 (intent stability) compares the backend's own submit-time patch
(`response["would_write"]`) against the previewed/approved map, over the UNION of both
maps' keys minus a new closed set, `PREVIEW_UNPINNABLE_KEYS` (`lv_enrichment_reviewed_at`,
`lv_enrichment_provenance`, `lv_contact_enrichment_provenance`,
`lv_enrichment_reviewed_by`) — the union so a key the backend adds at submit time that the
operator never previewed cannot slip past unseen. Any difference here is `failed`, naming
the keys. Leg 2 (landing) is unchanged in authority and unchanged in key set — still every
key in `intended` compared against the independent post-PATCH `verified_properties` refetch
— with only the expected value for each of the four unpinnable keys re-sourced from the
backend's own submit-time patch instead of the preview's guess.

**G-60-2 (`verify_live_write_safety.py`).** `verify()` gained an optional `armed_workflow`
parameter, `None` by default (reproducing today's unscoped verdict exactly, including the
diagnosed bug, for backward compatibility with every existing caller and the completed
Phase 22 runbook). When given, the named workflow's own declaring-node reports are judged
by the existing armed rule; every OTHER workflow's reports are judged by the existing
disarmed rule instead — stricter than the old global armed rule, which never checked their
allowlist constants for residue. A name matching zero scanned workflows is a hard failure
naming the value given and the workflow names that were scanned. The two rule bodies were
extracted into `_judge_disarmed_report` / `_judge_armed_report` so the scoped and unscoped
paths share one implementation each rather than a third copy. Added the matching
`--armed-workflow` CLI argument, guarded the same way `--expect-armed` already is.

**Task 3.** `review-triage/SKILL.md` step 8 now explains what the two-leg verdict means in
operator-facing terms (checked twice: against the backend's own report and against the
independent re-read) without touching the `failed` bullet's "never soften" instruction.
Step 4 now instructs reading the literal armed allowlist back from
`window.arm_result["observed"]` and stating it id-by-id before the first decision, and
quotes the admin-side scoped `verify_live_write_safety.py` invocation in full — the skill
does not ask the operator to run it (the plugin does not ship that script; the skill's own
closing section forbids a step that shells out). `CHANGELOG.md` and `plugin.json` were both
bumped to `0.38.0` in the same commit.

## Observed RED evidence (TDD requirement)

**Task 1**, run against pre-fix `review_decision.py`:

```
FAILED test_a_successful_approve_verifies_despite_backend_minted_keys_advancing
  AssertionError: assert 'failed' == 'verified'
FAILED test_a_drifted_business_field_still_fails_even_with_backend_minted_keys_advancing
  (failed, but not for the reason asserted — old code reported multiple extra
  mismatches beyond lv_produces_content, confirming this test could not have
  passed by coincidence on old code either)
FAILED test_the_backends_own_submitted_patch_diverging_from_the_preview_fails
  [added_pinnable_key_never_previewed] — AssertionError: assert 'lv_icp_tier' in
  ['lv_enrichment_reviewed_at', 'lv_enrichment_reviewed_by', 'lv_enrichment_provenance']
FAILED test_an_unenumerated_future_key_diverging_at_submit_time_fails_closed
  AssertionError: assert 'lv_some_future_field' in [...]
FAILED test_the_contacts_provenance_property_behaves_exactly_like_the_companies_one
  AssertionError: assert 'failed' == 'verified'
5 failed, 1 passed, 59 deselected in 0.13s
```

The one incidental pass (`changed_business_value` case of test 3) is expected and noted in
the plan: old code already iterates `intended`'s keys against the refetch and multiple keys
(including the changed business field) mismatch, so `status == "failed"` was already true —
it is the *second* case (an added, never-previewed key) that old code's `intended`-only key
set cannot see, and that one failed as required. Tests 1 and 5 — the two the plan mandates
must be observed RED — failed exactly as predicted.

**Task 2**, run against pre-fix `verify_live_write_safety.py`:

```
FAILED test_the_live_walks_shape_passes_under_the_scoped_armed_expectation
  (and 8 more — all TypeError: verify() got an unexpected keyword argument
  'armed_workflow', since the parameter did not exist yet)
9 failed, 1 passed, 44 deselected in 0.19s
```

The scoped-armed pass case (`test_the_live_walks_shape_passes_under_the_scoped_armed_expectation`)
— the one the plan mandates must be observed RED — failed exactly as predicted, reproducing
the live walk's own `armed FAIL` on a genuinely correct scoped window.

After the fix: `operator-claude-plugin/tests/test_review_decision.py` +
`test_review_outcome_parity.py` = 72 passed; `tests/test_verify_live_write_safety.py` = 54
passed; the plan's full listed verification block (5 files) = 225 passed; the full
`operator-claude-plugin/tests` suite = 2283 passed, 5 skipped. No pre-existing test was
modified.

## Why the repository verifier was not wired into the skill as an operator-run command

`scripts/verify_live_write_safety.py` lives in the backend repo's `scripts/`, not in the
plugin (`operator-claude-plugin/scripts/`), and the plugin ships no copy of it. The skill's
own closing section ("What this skill never asks the operator to do") forbids a step that
runs a command. Task 3 therefore relays the arm's own post-arm read-back
(`window.arm_result["observed"]`) as the in-conversation closure of the 49-W2 membership
lesson, and separately quotes the scoped verifier command in full as an admin-side
cross-check available to whoever has a repository checkout — the skill states plainly that
it does not ask the operator to run it. This is the same shell-out-to-backend-repo shape
Phase 43's `loss-reason-report` skill already uses for `build_loss_reason_report.py`;
`test_plugin_manifest.py`'s `BACKEND_REPO_SCRIPTS` allowlist (one named exemption per
citation, by design) gained a second entry for this.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - blocking issue] `test_plugin_manifest.py` needed a `BACKEND_REPO_SCRIPTS`
entry for `review-triage` / `verify_live_write_safety.py`**
- **Found during:** Task 3, running the plan's own prescribed verify command
- **Issue:** Quoting `scripts/verify_live_write_safety.py`'s scoped invocation in
  `review-triage/SKILL.md` (as Task 3's action instructs) tripped
  `test_every_skill_references_only_scripts_that_exist_on_disk`, which fails closed on any
  `scripts/<name>.py` reference that is neither shipped by the plugin nor explicitly
  allowlisted as a backend-repo shell-out.
- **Fix:** Added a `"review-triage": {"verify_live_write_safety.py"}` entry to
  `BACKEND_REPO_SCRIPTS`, following the exact one-exemption-one-citation pattern the
  existing `loss-reason-report` entry established (Phase 43 Plan 03).
- **Files modified:** `operator-claude-plugin/tests/test_plugin_manifest.py` (not in the
  plan's `files_modified` list — the plan's own Task 3 verify command could not otherwise
  pass)
- **Commit:** 020148b

No other deviations. Every other file matches the plan's `files_modified` list exactly.

## Nothing was armed, deployed, or written

No n8n workflow file was touched (`git diff --stat` against `n8n/` and
`scripts/build_cloud_workflows.py` across all three commits is empty). No deploy command
was run. No `armed_review_window` or `arm_for_dispatch` call was made. No HubSpot request
was issued. No provider credit was spent. Every test in this plan runs entirely offline
against synthetic fixtures (`stub_module_transport_factory`, hand-built workflow dicts via
`_wf`/`_node`) — the hermetic `autouse` fixture in `tests/test_verify_live_write_safety.py`
turns any leaked `requests.get/post/put` call into an assertion failure, and no such failure
occurred.

## Self-Check: PASSED

- FOUND: operator-claude-plugin/scripts/review_decision.py (PREVIEW_UNPINNABLE_KEYS, two-leg verify_decision)
- FOUND: operator-claude-plugin/tests/test_review_decision.py (5 new tests + parametrized case)
- FOUND: scripts/verify_live_write_safety.py (armed_workflow parameter, --armed-workflow CLI arg)
- FOUND: tests/test_verify_live_write_safety.py (11 new tests)
- FOUND: operator-claude-plugin/skills/review-triage/SKILL.md (step 4 and step 8 edits)
- FOUND: operator-claude-plugin/CHANGELOG.md ([0.38.0] section)
- FOUND: operator-claude-plugin/.claude-plugin/plugin.json (version 0.38.0)
- FOUND: operator-claude-plugin/tests/test_plugin_manifest.py (BACKEND_REPO_SCRIPTS entry)
- FOUND commit 2d1c881 (Task 1): fix(60-05): verify_decision proves intent stability AND landing, on two legs (G-60-1)
- FOUND commit 408ccf5 (Task 2): fix(60-05): scoped armed expectation that cannot blind the scan (G-60-2)
- FOUND commit 020148b (Task 3): docs(60-05): explain the two-leg verdict and the arm read-back, release 0.38.0
